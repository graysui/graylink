import os
import time
import threading
from queue import Queue
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List
from utils.logging_utils import logger
from db_manager import DatabaseManager
from config import Config

class SnapshotGenerator:
    """目录树生成器"""
    
    def __init__(self,
                 db_manager: DatabaseManager,
                 config: Config):
        """
        初始化目录树生成器
        
        Args:
            db_manager: 数据库管理器实例
            config: 配置实例
        """
        self.db_manager = db_manager
        self.config = config
        self.max_workers = self.config.thread_pool_size
        
        # 初始化统计信息
        self.total_files = 0
        self.total_size = 0
        self.start_time = 0
        
        # 线程安全的计数器
        self._file_count_lock = threading.Lock()
        self._size_lock = threading.Lock()
        
        # 确保软链接目录存在
        os.makedirs(self.config.symlink_base_path, exist_ok=True)
    
    def _increment_stats(self, size: int) -> None:
        """线程安全地更新统计信息"""
        with self._file_count_lock:
            self.total_files += 1
        with self._size_lock:
            self.total_size += size
    
    def _create_symlink(self, source_path: str) -> None:
        """
        创建软链接
        
        Args:
            source_path: 源文件路径
        """
        try:
            # 构建目标路径（使用与软链接模块相同的规则）
            rel_path = os.path.relpath(source_path, self.config.local_root_path)
            target_path = os.path.join(self.config.symlink_base_path, rel_path)
            
            # 确保目标目录存在
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            
            # 如果目标已存在且是软链接，先删除
            if os.path.islink(target_path):
                os.unlink(target_path)
            elif os.path.exists(target_path):
                logger.warning(f"目标路径已存在且不是软链接，跳过: {target_path}")
                return
            
            # 创建软链接
            os.symlink(source_path, target_path)
            logger.debug(f"创建软链接: {target_path} -> {source_path}")
            
            # 记录到数据库
            self.db_manager.add_symlink(source_path, target_path)
            
        except Exception as e:
            logger.error(f"创建软链接失败 {source_path}: {e}")
    
    def _should_process_file(self, path: str) -> bool:
        """
        判断是否需要处理该文件
        
        Args:
            path: 文件路径
            
        Returns:
            bool: 是否需要处理
        """
        # 检查是否是文件
        if not os.path.isfile(path):
            return False
            
        # 检查是否匹配排除模式
        for pattern in self.config.exclude_patterns:
            if pattern.strip('*') in path:
                logger.debug(f"文件匹配排除规则，跳过处理: {path}")
                return False
        
        # 检查文件扩展名是否匹配
        ext = os.path.splitext(path)[1].lower()  # 获取扩展名（包含点号）
        # 只处理视频文件
        video_extensions = {'.mp4', '.mkv', '.avi', '.m4v', '.wmv', '.mov', '.flv', '.rmvb', '.rm', 
                          '.3gp', '.ts', '.webm', '.vob', '.mts', '.m2ts', '.mpg', '.mpeg', '.m1v', 
                          '.m2v', '.mp2', '.asf', '.ogm', '.ogv', '.f4v'}
        if ext not in video_extensions:
            logger.debug(f"非视频文件，跳过处理: {path}")
            return False
            
        return True
    
    def _process_file(self, path: str) -> None:
        """处理单个文件"""
        try:
            if not self._should_process_file(path):
                return
                
            # 获取文件信息
            stat = os.stat(path)
            
            # 更新统计信息
            self._increment_stats(stat.st_size)
            
            # 更新数据库
            self.db_manager.add_file(
                path,
                stat.st_size,
                stat.st_mtime
            )
            
        except Exception as e:
            logger.error(f"处理文件失败 {path}: {e}")
    
    def _process_directory(self, path: str, executor: ThreadPoolExecutor) -> None:
        """
        处理目录
        
        Args:
            path: 目录路径
            executor: 线程池执行器
        """
        try:
            # 获取目录内容
            items = os.listdir(path)
            futures = []
            
            # 分别处理文件和目录
            for item in sorted(items):
                item_path = os.path.join(path, item)
                
                if os.path.isdir(item_path):
                    # 递归处理子目录
                    self._process_directory(item_path, executor)
                    
                elif os.path.isfile(item_path):
                    # 提交文件处理任务到线程池
                    future = executor.submit(self._process_file, item_path)
                    futures.append(future)
                    
            # 等待当前目录的所有文件处理完成
            for future in futures:
                try:
                    future.result()  # 等待任务完成并检查异常
                except Exception as e:
                    logger.error(f"处理文件失败: {e}")
                    
        except Exception as e:
            logger.error(f"处理目录失败 {path}: {e}")
    
    def create_symlinks(self) -> bool:
        """
        根据数据库记录创建软链接
        
        Returns:
            bool: 是否成功
        """
        try:
            logger.info("开始创建软链接...")
            start_time = time.time()
            
            # 获取所有文件记录
            files = self.db_manager.get_all_files()
            total_links = 0
            skipped_files = 0
            
            # 使用线程池创建软链接
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = []
                
                # 提交所有软链接创建任务
                for file_info in files:
                    # 再次检查文件类型，确保只为视频文件创建软链接
                    if self._should_process_file(file_info['path']):
                        future = executor.submit(self._create_symlink, file_info['path'])
                        futures.append(future)
                    else:
                        skipped_files += 1
                
                # 等待所有任务完成
                for future in futures:
                    try:
                        future.result()
                        total_links += 1
                    except Exception as e:
                        logger.error(f"创建软链接失败: {e}")
            
            # 输出统计信息
            elapsed_time = time.time() - start_time
            logger.info(f"软链接创建完成:")
            logger.info(f"- 总链接数: {total_links}")
            logger.info(f"- 跳过的非视频文件: {skipped_files}")
            logger.info(f"- 处理时间: {elapsed_time:.2f} 秒")
            logger.info(f"- 处理速度: {total_links / elapsed_time:.2f if elapsed_time > 0 else 0} 链接/秒")
            
            return True
            
        except Exception as e:
            logger.error(f"创建软链接失败: {e}")
            return False
    
    def scan_directories(self, skip_scan: bool = False) -> bool:
        """
        扫描目录并更新数据库
        
        Args:
            skip_scan: 是否跳过扫描直接创建软链接
            
        Returns:
            bool: 是否成功
        """
        try:
            if skip_scan:
                logger.info("跳过扫描，直接创建软链接...")
                return True
                
            logger.info("开始扫描目录...")
            self.total_files = 0
            self.total_size = 0
            futures = []  # 存储所有提交的任务
            
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                for directory in self.config.monitor_paths:
                    if not os.path.exists(directory):
                        logger.warning(f"目录不存在: {directory}")
                        continue
                        
                    logger.info(f"扫描目录: {directory}")
                    for root, _, files in os.walk(directory):
                        for file in files:
                            file_path = os.path.join(root, file)
                            # 提交任务并保存future对象
                            future = executor.submit(self._process_file, file_path)
                            futures.append(future)
                            
                            # 每处理100个文件输出一次进度
                            if len(futures) % 100 == 0:
                                completed = sum(1 for f in futures if f.done())
                                logger.info(f"已处理: {completed}/{len(futures)} 文件")
                
                # 等待所有任务完成
                for future in as_completed(futures):
                    try:
                        # 获取任务结果
                        result = future.result()
                        if result:
                            file_size = result
                            self.total_files += 1
                            self.total_size += file_size
                    except Exception as e:
                        logger.error(f"处理文件时发生错误: {e}")
            
            logger.info(f"扫描完成! 共处理 {self.total_files} 个文件, 总大小: {self.total_size / (1024*1024*1024):.2f} GB")
            return True
            
        except Exception as e:
            logger.error(f"扫描目录时发生错误: {e}")
            return False

    def scan_directory(self, root_path: str) -> bool:
        """
        扫描单个目录并处理文件，完成后创建软链接（已弃用，请使用 scan_directories）
        
        Args:
            root_path: 根目录路径
            
        Returns:
            bool: 是否成功
        """
        logger.warning("此方法已弃用，请使用 scan_directories")
        try:
            logger.info(f"开始扫描目录: {root_path}")
            self.start_time = time.time()
            
            # 重置统计信息
            self.total_files = 0
            self.total_size = 0
            
            # 处理根目录
            self._process_directory(root_path)
            
            # 输出统计信息
            elapsed_time = time.time() - self.start_time
            logger.info(f"目录扫描完成:")
            logger.info(f"- 总文件数: {self.total_files}")
            logger.info(f"- 总大小: {self.total_size / 1024 / 1024:.2f} MB")
            logger.info(f"- 扫描时间: {elapsed_time:.2f} 秒")
            
            # 扫描完成后创建软链接
            if not self.create_symlinks():
                logger.error("创建软链接失败")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"扫描目录失败: {e}")
            return False 