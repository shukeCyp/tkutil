import sys
import os
import socket
import qrcode
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import threading
import shutil
from PyQt5.QtWidgets import (QApplication, QMainWindow, QPushButton, QVBoxLayout, 
                            QHBoxLayout, QFileDialog, QLabel, QWidget, QListWidget,
                            QListWidgetItem, QSplitter)
from PyQt5.QtGui import QPixmap, QImage, QIcon, QDragEnterEvent, QDropEvent
from PyQt5.QtCore import Qt, QByteArray, QSize, QUrl
from io import BytesIO

class SingleFileHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, file_path=None, **kwargs):
        self.file_path = file_path
        self.file_name = os.path.basename(file_path) if file_path else ""
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            
            html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>文件下载</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; text-align: center; }}
                    .download-container {{ max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 8px; }}
                    .download-button {{ display: inline-block; background-color: #4CAF50; color: white; padding: 12px 24px; 
                                      text-decoration: none; border-radius: 4px; font-size: 18px; margin-top: 20px; }}
                    .file-info {{ margin: 20px 0; }}
                </style>
            </head>
            <body>
                <div class="download-container">
                    <h1>文件共享</h1>
                    <div class="file-info">
                        <p>文件名: {self.file_name}</p>
                        <p>文件大小: {self.format_size(os.path.getsize(self.file_path))}</p>
                    </div>
                    <a href="/download" class="download-button">下载文件</a>
                </div>
            </body>
            </html>
            """
            
            self.wfile.write(html.encode())
        elif self.path == '/download':
            try:
                with open(self.file_path, 'rb') as file:
                    self.send_response(200)
                    self.send_header('Content-type', 'application/octet-stream')
                    self.send_header('Content-Disposition', f'attachment; filename="{self.file_name}"')
                    self.send_header('Content-Length', str(os.path.getsize(self.file_path)))
                    self.end_headers()
                    shutil.copyfileobj(file, self.wfile)
            except Exception as e:
                self.send_error(404, f"文件下载错误: {str(e)}")
        else:
            self.send_error(404, "文件未找到")
    
    def format_size(self, size_bytes):
        """格式化文件大小为人类可读格式"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"
    
    def log_message(self, format, *args):
        # 禁止控制台输出访问日志
        pass

class FileServer:
    def __init__(self, file_path, port=8851):
        self.file_path = file_path
        self.port = port
        self.server = None
        self.server_thread = None
    
    def start(self):
        if self.server_thread and self.server_thread.is_alive():
            return False
        
        handler = lambda *args, **kwargs: SingleFileHandler(*args, file_path=self.file_path, **kwargs)
        self.server = ThreadingHTTPServer(("", self.port), handler)
        
        self.server_thread = threading.Thread(target=self.server.serve_forever)
        self.server_thread.daemon = True
        self.server_thread.start()
        return True
    
    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server = None
            self.server_thread = None
            return True
        return False
    
    def get_url(self):
        # 获取局域网IP地址
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # 连接到一个外部地址，不需要真正发送数据
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
        except Exception:
            ip = '127.0.0.1'  # 如果获取失败，使用本地回环地址
        finally:
            s.close()
        return f"http://{ip}:{self.port}"

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.file_server = None
        self.current_file = ""
        self.initUI()
    
    def initUI(self):
        self.setWindowTitle('单文件共享')
        self.setGeometry(300, 300, 600, 500)
        self.setAcceptDrops(True)
        
        # 创建主布局
        main_layout = QVBoxLayout()
        
        # 创建文件信息区域
        self.file_info_label = QLabel('拖放文件到此处或点击选择文件按钮')
        self.file_info_label.setAlignment(Qt.AlignCenter)
        self.file_info_label.setStyleSheet("border: 2px dashed #aaa; padding: 20px; border-radius: 5px;")
        self.file_info_label.setMinimumHeight(100)
        
        # 创建选择文件按钮
        self.file_button = QPushButton('选择文件')
        self.file_button.clicked.connect(self.select_file)
        
        # 创建启动/停止服务器按钮
        self.server_button = QPushButton('启动服务器')
        self.server_button.clicked.connect(self.toggle_server)
        self.server_button.setEnabled(False)
        
        # 创建服务器状态标签
        self.status_label = QLabel('服务器状态: 未启动')
        
        # 创建URL标签
        self.url_label = QLabel('URL: ')
        self.url_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        
        # 创建二维码标签
        self.qr_label = QLabel()
        self.qr_label.setAlignment(Qt.AlignCenter)
        
        # 添加组件到布局
        main_layout.addWidget(self.file_info_label)
        main_layout.addWidget(self.file_button)
        main_layout.addWidget(self.server_button)
        main_layout.addWidget(self.status_label)
        main_layout.addWidget(self.url_label)
        main_layout.addWidget(self.qr_label)
        
        # 设置主窗口的中心组件
        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)
    
    def select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, '选择要共享的文件')
        if file_path:
            self.set_file(file_path)
    
    def set_file(self, file_path):
        self.current_file = file_path
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        
        # 格式化文件大小
        size_str = self.format_size(file_size)
        
        self.file_info_label.setText(f'文件: {file_name}\n大小: {size_str}')
        self.server_button.setEnabled(True)
        
        if self.file_server:
            self.file_server.stop()
            self.file_server = None
            self.status_label.setText('服务器状态: 未启动')
            self.server_button.setText('启动服务器')
            self.url_label.setText('URL: ')
            self.qr_label.clear()
        
        self.file_server = FileServer(file_path)
    
    def format_size(self, size_bytes):
        """格式化文件大小为人类可读格式"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"
    
    def toggle_server(self):
        if not self.file_server:
            return
        
        if self.server_button.text() == '启动服务器':
            if self.file_server.start():
                self.status_label.setText('服务器状态: 运行中')
                self.server_button.setText('停止服务器')
                url = self.file_server.get_url()
                self.url_label.setText(f'URL: {url}')
                self.generate_qr_code(url)
        else:
            if self.file_server.stop():
                self.status_label.setText('服务器状态: 已停止')
                self.server_button.setText('启动服务器')
                self.url_label.setText('URL: ')
                self.qr_label.clear()
    
    def generate_qr_code(self, url):
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(url)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # 将PIL图像转换为QPixmap
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        qimage = QImage.fromData(QByteArray(buffer.getvalue()))
        pixmap = QPixmap.fromImage(qimage)
        
        # 调整大小以适应标签
        pixmap = pixmap.scaled(300, 300, Qt.KeepAspectRatio)
        self.qr_label.setPixmap(pixmap)
    
    # 拖放事件处理
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
    
    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if urls and len(urls) > 0:
            file_path = urls[0].toLocalFile()
            if os.path.isfile(file_path):
                self.set_file(file_path)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_()) 