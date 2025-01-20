import os
import time
from typing import Optional, Callable
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileModifiedEvent, FileDeletedEvent
from utils.logging_utils import logger
from db_manager import DatabaseManager
from config import Config

class FileEventHandler(FileSystemEventHandler):
    """文件事件处理器"""
    
    def __init__(self, db_manager: DatabaseManager, config: Config, on_file_change: Optional[Callable[[str, bool], None]] = None):
        """
        初始化文件事件处理器
        
        Args:
            db_manager: 数据库管理器实例
            config: 配置实例
            on_file_change: 文件变化回调函数，参数为(路径, 是否删除)
        """
        super().__init__()
        self.db_manager = db_manager
        self.config = config
        self.on_file_change = on_file_change
    
    def _is_mount_point_available(self, path: str) -> bool:
        """
        检查文件所在的挂载点是否可用
        
        Args:
            path: 文件路径
            
        Returns:
            bool: 挂载点是否可用
        """
        # 检查文件所在的挂载点
        for mount_point in self.config.mount_points:
            if path.startswith(mount_point):
                try:
                    # 尝试多次检查挂载点状态
                    for attempt in range(self.config.mount_retry_count + 1):
                        if os.path.ismount(mount_point):
                            if attempt > 0:
                                logger.info(f"挂载点恢复可用: {mount_point}")
                            return True
                        
                        if attempt < self.config.mount_retry_count:
                            logger.warning(f"挂载点不可用，等待重试 ({attempt + 1}/{self.config.mount_retry_count}): {mount_point}")
                            time.sleep(self.config.mount_retry_delay)
                    
                    # 所有重试都失败
                    logger.error(f"挂载点不可用，已达到最大重试次数: {mount_point}")
                    return False
                    
                except Exception as e:
                    logger.error(f"检查挂载点状态失败 {mount_point}: {e}")
                    return False
        
        return False
    
    def _process_file(self, path: str, is_delete: bool = False) -> None:
        """
        处理文件变化
        
        Args:
            path: 文件路径
            is_delete: 是否是删除操作
        """
        try:
            # 只在删除操作时检查挂载点状态
            if is_delete:
                # 如果挂载点不可用，跳过删除操作
                if not self._is_mount_point_available(path):
                    logger.warning(f"挂载点不可用，跳过删除操作: {path}")
                    return
                
                # 1. 删除数据库记录
                if self.db_manager.remove_file(path):
                    logger.info(f"删除文件记录: {path}")
                    # 2. 通知软链接管理器处理删除
                    if self.on_file_change:
                        self.on_file_change(path, True)
            else:
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
                
                # 1. 更新数据库
                self.db_manager.add_file(file_info['path'], file_info['size'], file_info['mtime'])
                
                # 2. 通知软链接管理器处理更新
                if self.on_file_change:
                    self.on_file_change(path, False)
                    
        except Exception as e:
            logger.error(f"处理文件失败 {path}: {e}")
    
    def on_created(self, event: FileCreatedEvent) -> None:
        """处理文件创建事件"""
        if not event.is_directory:
            self._process_file(event.src_path, is_delete=False)
    
    def on_modified(self, event: FileModifiedEvent) -> None:
        """处理文件修改事件"""
        if not event.is_directory:
            self._process_file(event.src_path, is_delete=False)
    
    def on_deleted(self, event: FileDeletedEvent) -> None:
        """处理文件删除事件"""
        if not event.is_directory:
            self._process_file(event.src_path, is_delete=True)

class LocalMonitor:
    """本地文件监控器"""
    
    def __init__(self, db_manager: DatabaseManager, config: Config, on_file_change: Optional[Callable[[str, bool], None]] = None):
        """
        初始化本地文件监控器
        
        Args:
            db_manager: 数据库管理器实例
            config: 配置实例
            on_file_change: 文件变化回调函数，参数为(路径, 是否删除)
        """
        self.db_manager = db_manager
        self.config = config
        self.on_file_change = on_file_change
        self.polling_interval = config.local_polling_interval
        
        # 创建文件事件处理器
        self.event_handler = FileEventHandler(db_manager, config, on_file_change)
        self.observer = Observer()
        
        # 检查挂载点状态
        available_mount_points = []
        for mount_point in self.config.mount_points:
            if os.path.exists(mount_point) and os.path.ismount(mount_point):
                available_mount_points.append(mount_point)
                logger.info(f"挂载点可用: {mount_point}")
            else:
                logger.warning(f"挂载点不可用: {mount_point}")
        
        if not available_mount_points:
            logger.error("没有可用的挂载点")
            return
            
        # 为每个监控目录创建观察者
        for monitor_path in self.config.monitor_paths:
            # 检查监控目录所在的挂载点是否可用
            mount_point = next((mp for mp in available_mount_points if monitor_path.startswith(mp)), None)
            if mount_point and os.path.exists(monitor_path):
                self.observer.schedule(self.event_handler, monitor_path, recursive=True)
                logger.info(f"添加监控目录: {monitor_path}")
            else:
                logger.warning(f"监控目录不可用: {monitor_path}")
    
    def _scan_files(self) -> None:
        """扫描所有文件"""
        try:
            for monitor_path in self.config.monitor_paths:
                if not os.path.exists(monitor_path):
                    logger.warning(f"监控目录不存在，跳过扫描: {monitor_path}")
                    continue
                    
                logger.info(f"开始扫描目录: {monitor_path}")
                for root, _, files in os.walk(monitor_path):
                    for name in files:
                        path = os.path.join(root, name)
                        self.event_handler._process_file(path, is_delete=False)
                        
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