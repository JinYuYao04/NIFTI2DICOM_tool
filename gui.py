#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NIFTI转DICOM工具 - 图形界面
"""

import sys
import os
from pathlib import Path
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QFileDialog, QTextEdit,
    QProgressBar, QMessageBox, QGroupBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont
import logging

from nifti_converter import NiftiToDicomConverter


class ConverterThread(QThread):
    """转换线程"""
    progress_updated = pyqtSignal(int, str)
    conversion_finished = pyqtSignal(bool, str)
    
    def __init__(self, input_path, output_path):
        super().__init__()
        self.input_path = input_path
        self.output_path = output_path
        
    def run(self):
        """运行转换"""
        try:
            converter = NiftiToDicomConverter(progress_callback=self.progress_callback)
            result = converter.convert(self.input_path, self.output_path)
            
            if result.success:
                self.conversion_finished.emit(True, f"转换成功!\n输出目录: {result.output_path}")
            else:
                self.conversion_finished.emit(False, result.error_message)
        except Exception as e:
            self.conversion_finished.emit(False, f"转换出错: {str(e)}")
    
    def progress_callback(self, percent, message):
        """进度回调"""
        self.progress_updated.emit(percent, message)


class MainWindow(QMainWindow):
    """主窗口"""
    
    def __init__(self):
        super().__init__()
        self.converter_thread = None
        self.init_ui()
        self.setup_logging()
        
    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle("NIFTI转DICOM工具 v1.0")
        self.setMinimumSize(800, 600)
        
        # 中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题
        title_label = QLabel("NIfTI到DICOM转换工具")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)
        
        # 输入路径组
        input_group = QGroupBox("输入文件")
        input_layout = QHBoxLayout()
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("选择NIfTI文件 (.nii 或 .nii.gz)...")
        input_layout.addWidget(self.input_edit)
        
        input_btn = QPushButton("选择文件")
        input_btn.clicked.connect(self.select_input_file)
        input_layout.addWidget(input_btn)
        
        input_group.setLayout(input_layout)
        main_layout.addWidget(input_group)
        
        # 输出路径组
        output_group = QGroupBox("输出目录")
        output_layout = QHBoxLayout()
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("选择DICOM文件输出目录...")
        output_layout.addWidget(self.output_edit)
        
        output_btn = QPushButton("选择目录")
        output_btn.clicked.connect(self.select_output_folder)
        output_layout.addWidget(output_btn)
        
        output_group.setLayout(output_layout)
        main_layout.addWidget(output_group)
        
        # 转换按钮
        convert_btn = QPushButton("开始转换")
        convert_btn.setMinimumHeight(50)
        convert_btn_font = QFont()
        convert_btn_font.setPointSize(12)
        convert_btn_font.setBold(True)
        convert_btn.setFont(convert_btn_font)
        convert_btn.clicked.connect(self.start_conversion)
        main_layout.addWidget(convert_btn)
        
        # 进度条
        progress_group = QGroupBox("转换进度")
        progress_layout = QVBoxLayout()
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)
        
        self.progress_label = QLabel("等待开始...")
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        progress_layout.addWidget(self.progress_label)
        
        progress_group.setLayout(progress_layout)
        main_layout.addWidget(progress_group)
        
        # 日志输出
        log_group = QGroupBox("日志信息")
        log_layout = QVBoxLayout()
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(200)
        log_layout.addWidget(self.log_text)
        
        log_group.setLayout(log_layout)
        main_layout.addWidget(log_group)
        
        # 底部说明
        info_label = QLabel(
            "支持的格式: NIfTI (.nii / .nii.gz) → DICOM (.dcm)\n"
            "转换将创建多个DICOM文件，每个文件对应NIfTI的一个切片\n"
            "基于 nii2dcm 项目 (https://github.com/tomaroberts/nii2dcm)"
        )
        info_label.setStyleSheet("color: #666; font-size: 9pt;")
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(info_label)
        
    def setup_logging(self):
        """设置日志"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[LogHandler(self.log_text)]
        )
        
    def select_input_file(self):
        """选择输入文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择NIfTI文件",
            "",
            "NIfTI Files (*.nii *.nii.gz);;All Files (*)"
        )
        if file_path:
            self.input_edit.setText(file_path)
            self.log_message(f"选择输入文件: {file_path}")
            
            # 自动设置输出目录
            if not self.output_edit.text():
                input_path = Path(file_path)
                output_dir = input_path.parent / f"{input_path.stem}_dicom"
                self.output_edit.setText(str(output_dir))
            
    def select_output_folder(self):
        """选择输出文件夹"""
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "选择DICOM输出目录"
        )
        if folder_path:
            self.output_edit.setText(folder_path)
            self.log_message(f"选择输出目录: {folder_path}")
            
    def start_conversion(self):
        """开始转换"""
        input_path = self.input_edit.text().strip()
        output_path = self.output_edit.text().strip()
        
        # 验证输入
        if not input_path:
            QMessageBox.warning(self, "警告", "请选择输入NIfTI文件!")
            return
            
        if not output_path:
            QMessageBox.warning(self, "警告", "请选择输出DICOM目录!")
            return
            
        if not os.path.exists(input_path):
            QMessageBox.warning(self, "警告", "输入文件不存在!")
            return
        
        # 禁用按钮
        self.setEnabled(False)
        
        # 重置进度
        self.progress_bar.setValue(0)
        self.progress_label.setText("开始转换...")
        self.log_message("=" * 50)
        self.log_message("开始转换...")
        
        # 创建并启动转换线程
        self.converter_thread = ConverterThread(input_path, output_path)
        self.converter_thread.progress_updated.connect(self.on_progress_updated)
        self.converter_thread.conversion_finished.connect(self.on_conversion_finished)
        self.converter_thread.start()
        
    def on_progress_updated(self, percent, message):
        """更新进度"""
        self.progress_bar.setValue(percent)
        self.progress_label.setText(message)
        self.log_message(f"[{percent}%] {message}")
        
    def on_conversion_finished(self, success, message):
        """转换完成"""
        self.setEnabled(True)
        
        if success:
            self.progress_bar.setValue(100)
            self.progress_label.setText("转换完成!")
            self.log_message("转换完成!")
            self.log_message(message)
            QMessageBox.information(self, "成功", message)
        else:
            self.progress_label.setText("转换失败")
            self.log_message("转换失败!")
            self.log_message(message)
            QMessageBox.critical(self, "错误", message)
            
    def log_message(self, message):
        """添加日志消息"""
        self.log_text.append(message)
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )


class LogHandler(logging.Handler):
    """日志处理器"""
    
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget
        
    def emit(self, record):
        msg = self.format(record)
        self.text_widget.append(msg)


def main():
    """主函数"""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
