import os
import time
from typing import Optional, Callable, List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileModifiedEvent, FileDeletedEvent
from utils.logging_utils import logger
from db_manager import DatabaseManager
from config import Config
from datetime import datetime

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
                
                try:
                    # 获取文件信息
                    stat = os.stat(path)
                    mtime = stat.st_mtime if hasattr(stat, 'st_mtime') else time.time()
                    size = stat.st_size if hasattr(stat, 'st_size') else 0
                    
                    file_info = {
                        'path': path,
                        'size': size,
                        'mtime': mtime
                    }
                    
                    # 检查文件是否已存在于数据库
                    existing_info = self.db_manager.get_file_info(path)
                    if existing_info and existing_info.get('mtime'):
                        if existing_info.get('mtime') == file_info['mtime']:
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
                        
                except (OSError, IOError) as e:
                    logger.error(f"获取文件信息失败 {path}: {e}")
                except Exception as e:
                    logger.error(f"处理文件失败 {path}: {e}")
                    
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
        
        # 创建线程池
        self.executor = ThreadPoolExecutor(max_workers=self.config.thread_pool_size)
        
        # 进度统计
        self._reset_stats()
        
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
    
    def _reset_stats(self) -> None:
        """重置统计信息"""
        self.total_files = 0  # 总文件数
        self.processed_files = 0  # 已处理文件数
        self.skipped_files = 0  # 跳过的文件数
        self.error_files = 0  # 错误文件数
        self.start_time = time.time()  # 开始时间
        self.last_progress_time = time.time()  # 上次进度更新时间
        self.last_processed_files = 0  # 上次已处理文件数
    
    def _log_progress(self, force: bool = False) -> None:
        """
        记录处理进度
        
        Args:
            force: 是否强制记录，不考虑时间间隔
        """
        current_time = time.time()
        time_elapsed = current_time - self.start_time
        
        # 使用配置中的进度日志更新间隔
        if force or (current_time - self.last_progress_time) >= self.config.progress_interval:
            # 计算处理速度（每秒处理文件数）
            interval = current_time - self.last_progress_time
            files_in_interval = self.processed_files - self.last_processed_files
            speed = files_in_interval / interval if interval > 0 else 0
            
            # 计算预计剩余时间
            remaining_files = self.total_files - self.processed_files
            eta = remaining_files / speed if speed > 0 else 0
            
            # 更新统计信息
            self.last_progress_time = current_time
            self.last_processed_files = self.processed_files
            
            # 记录进度日志
            progress = (self.processed_files / self.total_files * 100) if self.total_files > 0 else 0
            logger.info(
                f"扫描进度: {progress:.1f}% "
                f"({self.processed_files}/{self.total_files}) "
                f"速度: {speed:.1f} 文件/秒 "
                f"预计剩余时间: {eta:.0f}秒 "
                f"跳过: {self.skipped_files} "
                f"错误: {self.error_files}"
            )
    
    def _process_files_batch(self, files: List[Dict[str, str]]) -> None:
        """
        并行处理一批文件
        
        Args:
            files: 文件信息列表，每个文件包含 path 和 mtime
        """
        futures = []
        for file_info in files:
            future = self.executor.submit(self.event_handler._process_file, file_info['path'])
            futures.append(future)
        
        # 等待所有任务完成
        for future in as_completed(futures):
            try:
                future.result()  # 获取任务结果，如果有异常会在这里抛出
                self.processed_files += 1
            except Exception as e:
                logger.error(f"并行处理文件失败: {e}")
                self.error_files += 1
            
            # 更新进度
            self._log_progress()
    
    def _scan_files(self) -> None:
        """扫描所有监控目录下的文件变化"""
        try:
            # 重置统计信息
            self._reset_stats()
            
            for monitor_path in self.config.monitor_paths:
                # 检查挂载点状态
                if not self.event_handler._is_mount_point_available(monitor_path):
                    logger.warning(f"挂载点不可用，跳过扫描: {monitor_path}")
                    continue
                
                # 获取上次扫描时间
                last_scan_time = self.db_manager.get_last_scan_time(monitor_path)
                if last_scan_time:
                    logger.info(f"开始增量扫描目录: {monitor_path}，上次扫描时间: {last_scan_time}")
                else:
                    logger.info(f"开始首次扫描目录: {monitor_path}")
                
                # 首先统计需要处理的文件总数
                logger.info(f"正在统计文件数量...")
                for root, _, files in os.walk(monitor_path):
                    for filename in files:
                        file_path = os.path.join(root, filename)
                        try:
                            stat = os.stat(file_path)
                            mtime = datetime.fromtimestamp(stat.st_mtime)
                            if last_scan_time and mtime <= last_scan_time:
                                self.skipped_files += 1
                            else:
                                self.total_files += 1
                        except Exception:
                            continue
                
                logger.info(f"找到 {self.total_files} 个文件需要处理，{self.skipped_files} 个文件将跳过")
                
                # 收集需要处理的文件
                files_to_process = []
                
                # 遍历目录
                for root, _, files in os.walk(monitor_path):
                    for filename in files:
                        file_path = os.path.join(root, filename)
                        try:
                            # 获取文件状态
                            stat = os.stat(file_path)
                            mtime = datetime.fromtimestamp(stat.st_mtime)
                            
                            # 如果有上次扫描记录，且文件未修改，则跳过
                            if last_scan_time and mtime <= last_scan_time:
                                continue
                            
                            # 添加到待处理列表
                            files_to_process.append({
                                'path': file_path,
                                'mtime': mtime.isoformat()
                            })
                            
                            # 当收集到足够的文件时，启动并行处理
                            if len(files_to_process) >= self.config.batch_size:
                                self._process_files_batch(files_to_process)
                                files_to_process = []  # 清空列表
                            
                        except (OSError, IOError) as e:
                            logger.error(f"获取文件状态失败 {file_path}: {e}")
                            self.error_files += 1
                        except Exception as e:
                            logger.error(f"处理文件失败 {file_path}: {e}")
                            self.error_files += 1
                
                # 处理剩余的文件
                if files_to_process:
                    self._process_files_batch(files_to_process)
                
                # 更新扫描时间
                self.db_manager.update_scan_time(monitor_path)
                
                # 记录最终进度
                self._log_progress(force=True)
                
                # 记录完成信息
                total_time = time.time() - self.start_time
                avg_speed = self.processed_files / total_time if total_time > 0 else 0
                logger.info(
                    f"完成目录扫描: {monitor_path}\n"
                    f"总耗时: {total_time:.1f}秒\n"
                    f"平均速度: {avg_speed:.1f} 文件/秒\n"
                    f"处理文件: {self.processed_files}\n"
                    f"跳过文件: {self.skipped_files}\n"
                    f"错误文件: {self.error_files}"
                )
                
        except Exception as e:
            logger.error(f"扫描文件失败: {e}")
            
    def start(self) -> None:
        """启动监控"""
        try:
            # 启动文件系统观察者
            self.observer.start()
            logger.info("启动文件系统监控")
            
            # 首次扫描
            self._scan_files()
            
            # 定期扫描
            while True:
                time.sleep(self.polling_interval)
                self._scan_files()
                
        except Exception as e:
            logger.error(f"监控失败: {e}")
            self.stop()
            
    def stop(self) -> None:
        """停止监控"""
        try:
            # 停止文件系统观察者
            self.observer.stop()
            self.observer.join()
            
            # 关闭线程池
            self.executor.shutdown(wait=True)
            
            logger.info("停止文件系统监控")
        except Exception as e:
            logger.error(f"停止监控失败: {e}") 