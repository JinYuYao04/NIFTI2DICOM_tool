#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NIFTI转DICOM工具 - 核心转换器
基于 nii2dcm 项目 (https://github.com/tomaroberts/nii2dcm)
"""

import os
import sys
import logging
import numpy as np
import nibabel as nib
from pathlib import Path
from typing import Optional
import pydicom
from pydicom.dataset import Dataset, FileDataset, FileMetaDataset
from pydicom.uid import generate_uid
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


class ConversionResult:
    """转换结果类"""
    def __init__(self, success: bool, output_path: str = None, error_message: str = None):
        self.success = success
        self.output_path = output_path
        self.error_message = error_message


class NiftiToDicomConverter:
    """NIFTI到DICOM转换器"""
    
    def __init__(self, progress_callback=None):
        self.logger = logging.getLogger(__name__)
        self.progress_callback = progress_callback
        
    def _report_progress(self, percent: float, message: str):
        """报告进度"""
        if self.progress_callback:
            self.progress_callback(int(percent * 100), message)
    
    def _get_nifti_parameters(self, nib_nii):
        """从NIfTI头信息提取DICOM相关参数"""
        nii_img = nib_nii.get_fdata()
        
        # 获取维度信息
        if nib_nii.header['dim'][0] == 3:
            nX, nY, nZ = nib_nii.header['dim'][1:4].tolist()
            dimX, dimY, dimZ = nib_nii.header['pixdim'][1:4].tolist()
        else:
            raise ValueError("NIfTI文件不是3维数据")
        
        # 计算窗宽窗位
        maxI = np.amax(nii_img)
        minI = np.amin(nii_img)
        windowCenter = round((maxI - minI) / 2)
        windowWidth = round(maxI - minI)
        
        # 方向余弦
        A = nib_nii.affine
        dircosX = -1 * A[:3, 0] / dimX
        dircosY = -1 * A[:3, 1] / dimY
        
        # 图像位置
        image_pos_array = []
        for i in range(nZ):
            T1N = A.dot([0, 0, i, 1])
            image_pos_array.append([T1N[0], T1N[1], T1N[2]])
        
        params = {
            'dimX': dimX,
            'dimY': dimY,
            'dimZ': dimZ,
            'nX': nX,
            'nY': nY,
            'nZ': nZ,
            'WindowCenter': windowCenter,
            'WindowWidth': windowWidth,
            'ImageOrientationPatient': [dircosY[0], dircosY[1], dircosY[2], 
                                       dircosX[0], dircosX[1], dircosX[2]],
            'ImagePositionPatient': image_pos_array,
            'RescaleIntercept': 0,
            'RescaleSlope': 1,
            'minI': minI,
            'maxI': maxI
        }
        
        return params
    
    def _create_dicom_dataset(self, pixel_array: np.ndarray, slice_index: int,
                             total_slices: int, series_uid: str, study_uid: str,
                             image_position: list, nii_params: dict) -> FileDataset:
        """创建单个DICOM数据集"""
        
        # 创建文件元信息
        file_meta = FileMetaDataset()
        file_meta.MediaStorageSOPClassUID = '1.2.840.10008.5.1.4.1.1.4'  # MR Image Storage
        file_meta.MediaStorageSOPInstanceUID = generate_uid()
        file_meta.TransferSyntaxUID = '1.2.840.10008.1.2.1'  # Explicit VR Little Endian
        file_meta.ImplementationClassUID = generate_uid()
        file_meta.ImplementationVersionName = 'nifti2dicom_v1.0'
        
        # 创建数据集
        ds = FileDataset("temp", {}, file_meta=file_meta, preamble=b"\0" * 128)
        ds.is_implicit_VR = False
        ds.is_little_endian = True
        
        # 当前时间
        dt = datetime.now()
        date_str = dt.strftime('%Y%m%d')
        time_str = dt.strftime('%H%M%S.%f')
        
        # Patient Module
        ds.PatientName = "Anonymous"
        ds.PatientID = "NIFTI2DICOM"
        ds.PatientBirthDate = ""
        ds.PatientSex = ""
        
        # General Study Module
        ds.StudyInstanceUID = study_uid
        ds.StudyDate = date_str
        ds.StudyTime = time_str
        ds.ReferringPhysicianName = ""
        ds.StudyID = "1"
        ds.AccessionNumber = ""
        ds.StudyDescription = "Converted from NIfTI"
        
        # General Series Module
        ds.Modality = "MR"
        ds.SeriesInstanceUID = series_uid
        ds.SeriesNumber = "1"
        ds.SeriesDate = date_str
        ds.SeriesTime = time_str
        ds.SeriesDescription = "NIfTI to DICOM Conversion"
        
        # Frame of Reference Module
        ds.FrameOfReferenceUID = generate_uid()
        ds.PositionReferenceIndicator = ""
        
        # General Equipment Module
        ds.Manufacturer = "nifti2dicom"
        ds.ManufacturerModelName = "nifti2dicom_v1.0"
        ds.SoftwareVersions = "1.0"
        
        # General Image Module
        ds.InstanceNumber = str(slice_index + 1)
        ds.PatientOrientation = ""
        ds.ContentDate = date_str
        ds.ContentTime = time_str
        ds.ImageType = ['DERIVED', 'SECONDARY']
        
        # Image Plane Module
        ds.PixelSpacing = [nii_params['dimX'], nii_params['dimY']]
        ds.ImageOrientationPatient = [f"{x:.6f}" for x in nii_params['ImageOrientationPatient']]
        ds.ImagePositionPatient = [f"{x:.6f}" for x in image_position]
        ds.SliceThickness = nii_params['dimZ']
        ds.SliceLocation = image_position[2]
        
        # Image Pixel Module
        ds.SamplesPerPixel = 1
        ds.PhotometricInterpretation = "MONOCHROME2"
        ds.Rows = pixel_array.shape[0]
        ds.Columns = pixel_array.shape[1]
        ds.BitsAllocated = 16
        ds.BitsStored = 16
        ds.HighBit = 15
        ds.PixelRepresentation = 1  # signed
        
        # 转换像素数据为int16
        pixel_data = pixel_array.astype(np.int16)
        ds.PixelData = pixel_data.tobytes()
        
        # VOI LUT Module
        ds.WindowCenter = str(nii_params['WindowCenter'])
        ds.WindowWidth = str(nii_params['WindowWidth'])
        ds.RescaleIntercept = str(nii_params['RescaleIntercept'])
        ds.RescaleSlope = str(nii_params['RescaleSlope'])
        
        # SOP Common Module
        ds.SOPClassUID = '1.2.840.10008.5.1.4.1.1.4'  # MR Image Storage
        ds.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
        ds.InstanceCreationDate = date_str
        ds.InstanceCreationTime = time_str
        
        # MR Image Module (基本信息)
        ds.ScanningSequence = "RM"
        ds.SequenceVariant = "NONE"
        ds.ScanOptions = ""
        ds.MRAcquisitionType = "3D"
        ds.EchoTime = "0"
        ds.RepetitionTime = "0"
        
        return ds
    
    def convert(self, input_path: str, output_dir: str) -> ConversionResult:
        """
        执行NIfTI到DICOM的转换
        
        Args:
            input_path: 输入NIfTI文件路径
            output_dir: 输出DICOM文件目录
            
        Returns:
            ConversionResult对象
        """
        try:
            input_path = Path(input_path)
            output_dir = Path(output_dir)
            
            self._report_progress(0.0, "开始加载NIfTI文件...")
            
            # 检查输入文件
            if not input_path.exists():
                return ConversionResult(False, None, f"输入文件不存在: {input_path}")
            
            if not str(input_path).endswith(('.nii', '.nii.gz')):
                return ConversionResult(False, None, "输入文件必须是 .nii 或 .nii.gz 格式")
            
            # 加载NIfTI文件
            nib_nii = nib.load(str(input_path))
            nii_img = nib_nii.get_fdata()
            
            self._report_progress(0.1, f"NIfTI文件已加载，形状: {nii_img.shape}")
            self.logger.info(f"NIfTI形状: {nii_img.shape}")
            
            # 提取参数
            self._report_progress(0.15, "提取NIfTI头信息...")
            nii_params = self._get_nifti_parameters(nib_nii)
            
            total_slices = nii_params['nZ']
            self._report_progress(0.2, f"将创建 {total_slices} 个DICOM文件")
            
            # 创建输出目录
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # 生成Study和Series UID
            study_uid = generate_uid()
            series_uid = generate_uid()
            
            self._report_progress(0.25, "开始转换切片...")
            
            # 逐层转换
            created_files = []
            for i in range(total_slices):
                progress = 0.25 + 0.65 * (i / total_slices)
                self._report_progress(progress, f"转换切片 {i+1}/{total_slices}")
                
                # 获取当前切片
                if len(nii_img.shape) == 3:
                    slice_data = nii_img[:, :, i]
                else:
                    raise ValueError(f"不支持的NIfTI形状: {nii_img.shape}")
                
                # 获取图像位置
                image_pos = nii_params['ImagePositionPatient'][i]
                
                # 创建DICOM数据集
                ds = self._create_dicom_dataset(
                    slice_data, i, total_slices,
                    series_uid, study_uid,
                    image_pos, nii_params
                )
                
                # 保存DICOM文件
                output_file = output_dir / f"slice_{i+1:04d}.dcm"
                ds.save_as(str(output_file), write_like_original=False)
                created_files.append(output_file)
            
            self._report_progress(0.95, "正在完成...")
            
            self._report_progress(1.0, "转换完成!")
            self.logger.info(f"转换成功: 创建了 {len(created_files)} 个DICOM文件")
            self.logger.info(f"输出目录: {output_dir}")
            
            return ConversionResult(True, str(output_dir))
            
        except Exception as e:
            error_msg = f"转换失败: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            return ConversionResult(False, None, error_msg)
