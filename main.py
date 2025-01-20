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
        logger.info("配置加载完成")
        
        # 初始化组件
        self.db_manager = DatabaseManager(self.config.db_path)
        self.emby_notifier = EmbyNotifier(self.config)
        self.symlink_manager = SymlinkManager(
            self.db_manager,
            self.config,
            self.emby_notifier.notify_file_change
        )
        
        # 初始化监控器
        self.local_monitor = LocalMonitor(
            self.db_manager,
            self.config,
            self.symlink_manager.handle_file_change
        )
        self.gdrive_monitor = GoogleDriveMonitor(
            self.db_manager,
            self.config,
            self.symlink_manager.handle_file_change
        )
        
        # 初始化目录树生成器
        self.snapshot_generator = SnapshotGenerator(
            self.db_manager,
            self.symlink_manager,
            self.config
        )
        
        self.html_exporter = HtmlExporter(self.db_manager, self.config)
        
        # 初始化线程
        self.local_monitor_thread: Optional[threading.Thread] = None
        self.gdrive_monitor_thread: Optional[threading.Thread] = None
        self._running = False
    
    def _setup_signal_handlers(self) -> None:
        """设置信号处理器"""
        def signal_handler(signum, frame):
            logger.info(f"收到信号: {signum}")
            self.stop()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    def full_scan(self) -> bool:
        """
        执行全量扫描
        
        Returns:
            bool: 是否成功
        """
        try:
            logger.info("开始执行全量扫描...")
            
            # 清理失效的软链接
            self.symlink_manager.cleanup()
            
            # 扫描所有挂载点
            for mount_point in self.config.mount_points:
                if os.path.exists(mount_point):
                    if not self.snapshot_generator.scan_directory(mount_point):
                        logger.error(f"扫描目录失败: {mount_point}")
                        return False
                else:
                    logger.warning(f"挂载点不存在，跳过扫描: {mount_point}")
            
            logger.info("全量扫描完成")
            return True
            
        except Exception as e:
            logger.error(f"全量扫描失败: {e}")
            return False
    
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
    parser.add_argument("--full-scan", action="store_true", help="执行全量扫描")
    
    # 解析命令行参数
    args = parser.parse_args()
    
    # 检查配置文件
    if not os.path.exists(args.config):
        print(f"配置文件不存在: {args.config}")
        sys.exit(1)
    
    try:
        # 创建应用实例
        app = GrayLink(args.config)
        
        # 如果指定了全量扫描选项
        if args.full_scan:
            if not app.full_scan():
                sys.exit(1)
            sys.exit(0)
        
        # 否则正常运行
        app.run()
        
    except Exception as e:
        logger.error(f"程序运行失败: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main() 