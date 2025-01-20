import os
import sys
import signal
import argparse
import threading
import time
from typing import Optional
from utils.logging_utils import logger, setup_logging
from config import Config
from db_manager import DatabaseManager
from local_monitor import LocalMonitor
from gdrive_api import GoogleDriveMonitor
from symlink_manager import SymlinkManager
from emby_notifier import EmbyNotifier
from snapshot_generator import SnapshotGenerator
from html_exporter import HtmlExporter

class GrayLink:
    """GrayLink主程序"""
    
    def __init__(self, config_path: str):
        """
        初始化GrayLink
        
        Args:
            config_path: 配置文件路径
        """
        # 设置日志
        setup_logging()
        
        # 加载配置
        self.config = Config.load_from_yaml(config_path)
        self.config_path = config_path
        logger.info("配置加载完成")
        
        # 初始化基础组件
        self.db_manager = DatabaseManager(self.config.db_path)
        
        # 初始化标记
        self._emby_notifier = None
        self._symlink_manager = None
        self._local_monitor = None
        self._gdrive_monitor = None
        self._snapshot_generator = None
        self._html_exporter = None
        
        # 初始化线程
        self.local_monitor_thread: Optional[threading.Thread] = None
        self.gdrive_monitor_thread: Optional[threading.Thread] = None
        self._running = False
    
    @property
    def emby_notifier(self) -> EmbyNotifier:
        """获取Emby通知器实例"""
        if self._emby_notifier is None:
            self._emby_notifier = EmbyNotifier(self.config)
        return self._emby_notifier
    
    @property
    def symlink_manager(self) -> SymlinkManager:
        """获取软链接管理器实例"""
        if self._symlink_manager is None:
            self._symlink_manager = SymlinkManager(
                db_manager=self.db_manager,
                config=self.config,
                on_symlink_change=self.emby_notifier.notify_file_change if self._emby_notifier else None
            )
        return self._symlink_manager
    
    @property
    def local_monitor(self) -> LocalMonitor:
        """获取本地监控器实例"""
        if self._local_monitor is None:
            self._local_monitor = LocalMonitor(
                db_manager=self.db_manager,
                config=self.config,
                on_file_change=self.symlink_manager.handle_file_change
            )
        return self._local_monitor
    
    @property
    def gdrive_monitor(self) -> GoogleDriveMonitor:
        """获取Google Drive监控器实例"""
        if self._gdrive_monitor is None:
            self._gdrive_monitor = GoogleDriveMonitor(
                self.db_manager,
                self.config,
                self.symlink_manager.handle_file_change
            )
        return self._gdrive_monitor
    
    @property
    def snapshot_generator(self) -> SnapshotGenerator:
        """获取快照生成器实例"""
        if self._snapshot_generator is None:
            self._snapshot_generator = SnapshotGenerator(
                db_manager=self.db_manager,
                config=self.config
            )
        return self._snapshot_generator
    
    @property
    def html_exporter(self) -> HtmlExporter:
        """获取HTML导出器实例"""
        if self._html_exporter is None:
            self._html_exporter = HtmlExporter(
                db_manager=self.db_manager,
                config=self.config
            )
        return self._html_exporter
    
    def _setup_signal_handlers(self) -> None:
        """设置信号处理器"""
        def signal_handler(signum, frame):
            logger.info(f"收到信号: {signum}")
            self.stop()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    def _full_scan(self) -> None:
        """执行完整扫描"""
        try:
            logger.info("开始执行完整扫描...")
            
            # 1. 清理无效的软链接
            self.symlink_manager.cleanup()
            
            # 2. 扫描目录并更新数据库
            if not self.snapshot_generator.scan_directories():
                logger.error("目录扫描失败")
                return
                
            # 3. 根据数据库记录创建软链接
            if not self.snapshot_generator.create_symlinks():
                logger.error("创建软链接失败")
                return
            
            logger.info("完整扫描完成")
            
        except Exception as e:
            logger.error(f"执行完整扫描失败: {e}")
            return
    
    def start(self) -> None:
        """启动GrayLink"""
        try:
            if self._running:
                logger.warning("GrayLink已经在运行")
                return
            
            logger.info("正在启动GrayLink...")
            self._setup_signal_handlers()
            
            # 清理失效的软链接
            self.symlink_manager.cleanup()
            
            # 启动本地监控线程
            self.local_monitor_thread = threading.Thread(
                target=self.local_monitor.run_forever,
                name="LocalMonitor"
            )
            self.local_monitor_thread.daemon = True
            self.local_monitor_thread.start()
            
            # 启动Google Drive监控线程
            self.gdrive_monitor_thread = threading.Thread(
                target=self.gdrive_monitor.run_forever,
                name="GDriveMonitor"
            )
            self.gdrive_monitor_thread.daemon = True
            self.gdrive_monitor_thread.start()
            
            # 启动HTML定时导出
            self.html_exporter.start_scheduler()
            
            self._running = True
            logger.info("GrayLink启动完成")
            
        except Exception as e:
            logger.error(f"启动GrayLink失败: {e}")
            self.stop()
            raise
    
    def stop(self) -> None:
        """停止GrayLink"""
        if not self._running:
            return
            
        logger.info("正在停止GrayLink...")
        self._running = False
        
        # 停止监控器
        self.local_monitor.stop()
        self.gdrive_monitor.stop()
        
        # 停止HTML定时导出
        try:
            self.html_exporter.stop_scheduler()
        except Exception as e:
            logger.error(f"停止HTML定时导出时出错: {e}")
        
        # 等待线程结束
        if self.local_monitor_thread:
            self.local_monitor_thread.join()
        if self.gdrive_monitor_thread:
            self.gdrive_monitor_thread.join()
        
        # 关闭其他组件
        self.emby_notifier.close()
        
        logger.info("GrayLink已停止")
    
    def run(self) -> None:
        """运行GrayLink"""
        try:
            self.start()
            
            # 主线程等待
            while self._running:
                time.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("收到停止信号")
        finally:
            self.stop()

    def export_html(self, output_path: str):
        """导出HTML快照
        
        Args:
            output_path: 输出文件路径
        """
        self.html_exporter.export_html(output_path)
    
    def export_json(self, output_path: str):
        """导出JSON快照
        
        Args:
            output_path: 输出文件路径
        """
        self.html_exporter.export_json(output_path)

def main():
    """主函数"""
    # 创建命令行解析器
    parser = argparse.ArgumentParser(description="GrayLink - 文件监控和软链接管理工具")
    parser.add_argument("config", help="配置文件路径")
    parser.add_argument("--full-scan", action="store_true", help="执行完整扫描")
    parser.add_argument("--export-html", metavar="PATH", help="导出HTML快照")
    parser.add_argument("--export-json", metavar="PATH", help="导出JSON快照")
    
    # 解析命令行参数
    args = parser.parse_args()
    
    # 检查配置文件
    if not os.path.exists(args.config):
        print(f"配置文件不存在: {args.config}")
        sys.exit(1)
    
    try:
        # 创建应用实例
        app = GrayLink(args.config)
        
        # 处理命令行选项
        if args.full_scan:
            app._full_scan()
            sys.exit(0)
        elif args.export_html:
            app.export_html(args.export_html)
            sys.exit(0)
        elif args.export_json:
            app.export_json(args.export_json)
            sys.exit(0)
        
        # 否则正常运行
        app.run()
        
    except Exception as e:
        logger.error(f"程序运行失败: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main() 