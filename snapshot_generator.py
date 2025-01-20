import os
import time
from typing import Dict, Any
from utils.logging_utils import logger
from db_manager import DatabaseManager
from symlink_manager import SymlinkManager
from config import Config

class SnapshotGenerator:
    """目录树生成器"""
    
    def __init__(self,
                 db_manager: DatabaseManager,
                 symlink_manager: SymlinkManager,
                 config: Config):
        """
        初始化目录树生成器
        
        Args:
            db_manager: 数据库管理器实例
            symlink_manager: 软链接管理器实例
            config: 配置实例
        """
        self.db_manager = db_manager
        self.symlink_manager = symlink_manager
        self.config = config
        
        # 初始化统计信息
        self.total_files = 0
        self.total_size = 0
        self.start_time = 0
    
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
                    
                    # 创建软链接
                    self.symlink_manager.handle_file_change(item_path)
                    
        except Exception as e:
            logger.error(f"处理目录失败 {path}: {e}")
    
    def scan_directory(self, root_path: str) -> bool:
        """
        扫描目录并处理文件
        
        Args:
            root_path: 根目录路径
            
        Returns:
            bool: 是否成功
        """
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
            
            return True
            
        except Exception as e:
            logger.error(f"扫描目录失败: {e}")
            return False 