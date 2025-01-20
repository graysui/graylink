import os
import time
from typing import Dict, Any
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
        
        # 初始化统计信息
        self.total_files = 0
        self.total_size = 0
        self.start_time = 0
        
        # 确保软链接目录存在
        os.makedirs(self.config.symlink_base_path, exist_ok=True)
    
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
        ext = os.path.splitext(path)[1].lower()
        for pattern in self.config.file_patterns:
            if pattern.endswith(ext):
                return True
        
        logger.debug(f"文件扩展名不匹配，跳过处理: {path}")
        return False
    
    def _process_directory(self, path: str) -> None:
        """
        处理目录
        
        Args:
            path: 目录路径
        """
        try:
            # 获取目录内容
            items = os.listdir(path)
            
            # 分别处理文件和目录
            for item in sorted(items):
                item_path = os.path.join(path, item)
                
                if os.path.isdir(item_path):
                    # 递归处理子目录
                    self._process_directory(item_path)
                    
                elif os.path.isfile(item_path) and self._should_process_file(item_path):
                    # 获取文件信息
                    stat = os.stat(item_path)
                    
                    # 更新统计信息
                    self.total_files += 1
                    self.total_size += stat.st_size
                    
                    # 更新数据库
                    self.db_manager.add_file(
                        item_path,
                        stat.st_size,
                        stat.st_mtime
                    )
                    
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
            
            # 为每个文件创建软链接
            for file_info in files:
                self._create_symlink(file_info['path'])
                total_links += 1
            
            # 输出统计信息
            elapsed_time = time.time() - start_time
            logger.info(f"软链接创建完成:")
            logger.info(f"- 总链接数: {total_links}")
            logger.info(f"- 处理时间: {elapsed_time:.2f} 秒")
            
            return True
            
        except Exception as e:
            logger.error(f"创建软链接失败: {e}")
            return False
    
    def scan_directories(self) -> bool:
        """
        扫描所有监控目录并处理文件，完成后创建软链接
        
        Returns:
            bool: 是否成功
        """
        try:
            logger.info("开始扫描监控目录")
            self.start_time = time.time()
            
            # 重置统计信息
            self.total_files = 0
            self.total_size = 0
            
            # 处理每个监控目录
            for monitor_path in self.config.monitor_paths:
                if not os.path.exists(monitor_path):
                    logger.warning(f"监控目录不存在，跳过扫描: {monitor_path}")
                    continue
                    
                logger.info(f"扫描目录: {monitor_path}")
                self._process_directory(monitor_path)
            
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