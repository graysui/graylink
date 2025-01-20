import os
import time
from typing import Optional, Callable
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileModifiedEvent
from utils.logging_utils import logger
from db_manager import DatabaseManager
from config import Config

class FileEventHandler(FileSystemEventHandler):
    """文件事件处理器"""
    
    def __init__(self, db_manager: DatabaseManager, on_file_change: Optional[Callable[[str], None]] = None):
        """
        初始化文件事件处理器
        
        Args:
            db_manager: 数据库管理器实例
            on_file_change: 文件变化回调函数
        """
        super().__init__()
        self.db_manager = db_manager
        self.on_file_change = on_file_change
    
    def _process_file(self, path: str, is_realtime: bool = True) -> None:
        """
        处理文件变化
        
        Args:
            path: 文件路径
            is_realtime: 是否是实时监控事件
        """
        try:
            if not os.path.isfile(path):
                return
                
            # 获取文件信息
            stat = os.stat(path)
            file_info = {
                'path': path,
                'size': stat.st_size,
                'mtime': stat.st_mtime
            }
            
            # 检查文件是否已存在于数据库
            existing_info = self.db_manager.get_file_info(path)
            if existing_info:
                if existing_info['mtime'] == file_info['mtime']:
                    logger.debug(f"文件未变化，跳过处理: {path}")
                    return
                logger.info(f"更新文件记录: {path}")
            else:
                logger.info(f"新增文件记录: {path}")
            
            # 更新数据库
            self.db_manager.add_file(file_info['path'], file_info['size'], file_info['mtime'])
            
            # 如果是实时事件或文件发生变化，通知软链接管理器
            if is_realtime or not existing_info or existing_info['mtime'] != file_info['mtime']:
                if self.on_file_change:
                    self.on_file_change(path)
                    
        except Exception as e:
            logger.error(f"处理文件失败 {path}: {e}")
    
    def on_created(self, event: FileCreatedEvent) -> None:
        """处理文件创建事件"""
        if not event.is_directory:
            self._process_file(event.src_path, is_realtime=True)
    
    def on_modified(self, event: FileModifiedEvent) -> None:
        """处理文件修改事件"""
        if not event.is_directory:
            self._process_file(event.src_path, is_realtime=True)

class LocalMonitor:
    """本地文件监控器"""
    
    def __init__(self, db_manager: DatabaseManager, config: Config, on_file_change: Optional[Callable[[str], None]] = None):
        """
        初始化本地文件监控器
        
        Args:
            db_manager: 数据库管理器实例
            config: 配置实例
            on_file_change: 文件变化回调函数
        """
        self.db_manager = db_manager
        self.mount_points = config.mount_points
        self.polling_interval = config.polling_interval
        self.on_file_change = on_file_change
        
        # 创建文件事件处理器
        self.event_handler = FileEventHandler(db_manager, on_file_change)
        self.observer = Observer()
        
        # 为每个挂载点创建观察者
        for mount_point in self.mount_points:
            if os.path.exists(mount_point):
                self.observer.schedule(self.event_handler, mount_point, recursive=True)
                logger.info(f"添加监控目录: {mount_point}")
            else:
                logger.warning(f"挂载点不存在: {mount_point}")
    
    def _scan_files(self) -> None:
        """扫描所有文件"""
        try:
            for mount_point in self.mount_points:
                if not os.path.exists(mount_point):
                    logger.warning(f"挂载点不存在，跳过扫描: {mount_point}")
                    continue
                    
                logger.info(f"开始扫描目录: {mount_point}")
                for root, _, files in os.walk(mount_point):
                    for name in files:
                        path = os.path.join(root, name)
                        self.event_handler._process_file(path, is_realtime=False)
                        
            logger.info("目录扫描完成")
            
        except Exception as e:
            logger.error(f"扫描文件失败: {e}")
    
    def start(self) -> None:
        """启动监控"""
        self.observer.start()
        logger.info("本地文件监控已启动")
    
    def stop(self) -> None:
        """停止监控"""
        self.observer.stop()
        self.observer.join()
        logger.info("本地文件监控已停止")
    
    def run_forever(self) -> None:
        """持续运行监控"""
        try:
            self.start()
            
            while True:
                # 执行定期扫描
                self._scan_files()
                # 等待下一次扫描
                time.sleep(self.polling_interval)
                
        except KeyboardInterrupt:
            logger.info("收到停止信号")
        finally:
            self.stop() 