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
    
    def __init__(self, config_file: str = 'config.yaml'):
        """
        初始化GrayLink
        
        Args:
            config_file: 配置文件路径
        """
        # 设置日志系统
        setup_logging()
        
        self.config = Config.load_from_yaml(config_file)
        logger.info("配置加载完成")
        
        self.db_manager = DatabaseManager(self.config.db_path)
        logger.info("数据库初始化成功")
        
        # 组件初始化标记
        self._local_monitor = None
        self._gdrive_monitor = None
        self._symlink_manager = None
        self._html_exporter = None
        
        # 监控线程列表
        self._monitor_threads = []
        
        # 停止标志
        self._stop_flag = threading.Event()
    
    def _init_monitoring_components(self):
        """初始化监控相关组件"""
        try:
            # 初始化软链接管理器
            if self._symlink_manager is None:
                self._symlink_manager = SymlinkManager(
                    self.db_manager,
                    self.config
                )
            
            # 初始化本地监控器
            if self._local_monitor is None:
                self._local_monitor = LocalMonitor(
                    self.db_manager,
                    self.config,
                    self._symlink_manager.handle_file_change
                )
            
            # 初始化Google Drive监控器
            if self.config.enable_gdrive and self._gdrive_monitor is None:
                self._gdrive_monitor = GoogleDriveMonitor(
                    self.config.gdrive_root_path,
                    self.db_manager,
                    self.config
                )
                self._gdrive_monitor.on_file_change = self._symlink_manager.handle_file_change
            
            logger.info("监控组件初始化完成")
            
        except Exception as e:
            logger.error(f"监控组件初始化失败: {e}")
            raise
    
    def _init_html_exporter(self) -> HtmlExporter:
        """初始化HTML导出器"""
        if self._html_exporter is None:
            self._html_exporter = HtmlExporter(
                self.db_manager,
                self.config
            )
        return self._html_exporter
    
    def export_html(self, output_path: str) -> bool:
        """
        导出HTML快照
        
        Args:
            output_path: 输出文件路径
            
        Returns:
            bool: 是否成功
        """
        try:
            html_exporter = self._init_html_exporter()
            html_exporter.export_html(output_path)
            logger.info(f"HTML快照已导出到: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"导出HTML快照失败: {e}")
            return False
    
    def run(self):
        """启动服务"""
        try:
            logger.info("正在启动GrayLink...")
            
            # 检查服务是否已经在运行
            if self._monitor_threads:
                logger.warning("服务已在运行")
                return
            
            # 初始化监控组件
            self._init_monitoring_components()
            
            # 启动本地监控
            local_thread = threading.Thread(
                target=self._local_monitor.run_forever,
                name="LocalMonitor"
            )
            local_thread.daemon = True
            local_thread.start()
            self._monitor_threads.append(local_thread)
            
            # 启动Google Drive监控
            if self._gdrive_monitor:
                gdrive_thread = threading.Thread(
                    target=self._gdrive_monitor.run_forever,
                    name="GoogleDriveMonitor"
                )
                gdrive_thread.daemon = True
                gdrive_thread.start()
                self._monitor_threads.append(gdrive_thread)
            
            # 等待线程结束或停止信号
            while not self._stop_flag.is_set():
                # 检查线程是否还在运行
                for thread in self._monitor_threads[:]:
                    if not thread.is_alive():
                        logger.error(f"{thread.name} 已停止运行")
                        self._monitor_threads.remove(thread)
                
                # 如果所有线程都停止了，退出循环
                if not self._monitor_threads:
                    logger.error("所有监控线程已停止")
                    break
                
                time.sleep(1)
            
        except Exception as e:
            logger.error(f"启动服务失败: {e}")
            self.stop()
            raise
    
    def stop(self):
        """停止服务"""
        try:
            logger.info("正在停止GrayLink...")
            
            # 设置停止标志
            self._stop_flag.set()
            
            # 停止监控器
            if hasattr(self, '_local_monitor') and self._local_monitor:
                self._local_monitor.stop()
            
            if hasattr(self, '_gdrive_monitor') and self._gdrive_monitor:
                self._gdrive_monitor.stop()
            
            # 等待所有线程结束
            for thread in self._monitor_threads:
                thread.join(timeout=5)
                if thread.is_alive():
                    logger.warning(f"{thread.name} 未能正常停止")
            
            # 清空线程列表
            self._monitor_threads.clear()
            
        except Exception as e:
            logger.error(f"停止服务失败: {e}")
            raise
    
    def _full_scan(self, skip_scan: bool = False) -> bool:
        """
        执行完整扫描
        
        Args:
            skip_scan: 是否跳过扫描直接创建软链接
            
        Returns:
            bool: 是否成功
        """
        try:
            logger.info("开始执行完整扫描..." if not skip_scan else "开始创建软链接...")
            
            # 初始化必要组件
            if self._symlink_manager is None:
                self._symlink_manager = SymlinkManager(
                    self.db_manager,
                    self.config
                )
            symlink_manager = self._symlink_manager
            
            snapshot_generator = SnapshotGenerator(
                self.db_manager,
                self.config
            )
            
            # 清理无效的软链接
            symlink_manager.cleanup()
            
            if skip_scan:
                # 跳过扫描，直接创建软链接
                if not snapshot_generator.create_symlinks():
                    logger.error("创建软链接失败")
                    return False
            else:
                # 扫描目录
                if not snapshot_generator.scan_directories(skip_scan=False):
                    logger.error("目录扫描失败")
                    return False
                
                # 创建软链接
                if not snapshot_generator.create_symlinks():
                    logger.error("创建软链接失败")
                    return False
            
            logger.info("完整扫描完成" if not skip_scan else "软链接创建完成")
            return True
            
        except Exception as e:
            logger.error(f"执行完整扫描失败: {e}")
            return False
    
    def export_json(self, output_path: str) -> bool:
        """
        导出JSON快照
        
        Args:
            output_path: 输出文件路径
            
        Returns:
            bool: 是否成功
        """
        html_exporter = self._init_html_exporter()
        return html_exporter.export_json(output_path)

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