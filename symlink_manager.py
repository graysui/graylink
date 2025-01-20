import os
import re
from typing import Set, Optional, Callable, Tuple
from utils.logging_utils import logger
from db_manager import DatabaseManager
from config import Config

class SymlinkManager:
    """软链接管理器"""
    
    def __init__(self,
                 db_manager: DatabaseManager,
                 config: Config,
                 on_symlink_change: Optional[Callable[[str, bool], None]] = None):
        """
        初始化软链接管理器
        
        Args:
            db_manager: 数据库管理器实例
            config: 配置实例
            on_symlink_change: 软链接变化回调函数（用于通知Emby），参数为(路径, 是否删除)
        """
        self.db_manager = db_manager
        self.base_path = os.path.abspath(config.symlink_base_path)
        self.file_patterns = {p.lower() for p in config.file_patterns}
        self.exclude_patterns = config.exclude_patterns
        self.mount_points = config.mount_points
        self.on_symlink_change = on_symlink_change
        
        # 确保基础路径存在
        if not os.path.exists(self.base_path):
            os.makedirs(self.base_path)
            logger.info(f"创建软链接基础路径: {self.base_path}")
    
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
        for pattern in self.exclude_patterns:
            if pattern.strip('*') in path:
                logger.debug(f"文件匹配排除规则，跳过处理: {path}")
                return False
        
        # 检查文件扩展名是否匹配
        ext = os.path.splitext(path)[1].lower()
        for pattern in self.file_patterns:
            if pattern.endswith(ext):
                return True
        
        logger.debug(f"文件扩展名不匹配，跳过处理: {path}")
        return False
    
    def _get_relative_path(self, path: str) -> str:
        """
        获取相对于挂载点的路径
        
        Args:
            path: 完整文件路径
            
        Returns:
            str: 相对路径
        """
        # 查找第一个视频文件扩展名之前的路径部分
        for pattern in self.file_patterns:
            ext = pattern.split('*')[1]  # 获取扩展名部分
            if path.lower().endswith(ext):
                rel_path = path[:-(len(ext))]
                # 移除挂载点路径
                for mount_point in self.mount_points:
                    if rel_path.startswith(mount_point):
                        rel_path = rel_path[len(mount_point):].lstrip('/')
                        break
                return rel_path
        return path
    
    def _create_symlink(self, source_path: str) -> Optional[str]:
        """
        创建软链接
        
        Args:
            source_path: 源文件路径
            
        Returns:
            Optional[str]: 创建的软链接路径，如果创建失败返回None
        """
        try:
            # 获取相对路径
            rel_path = self._get_relative_path(source_path)
            # 构建目标路径
            link_path = os.path.join(self.base_path, rel_path)
            link_dir = os.path.dirname(link_path)
            
            # 确保目标目录存在
            if not os.path.exists(link_dir):
                os.makedirs(link_dir)
            
            # 如果已存在同名软链接，先删除
            if os.path.islink(link_path):
                os.unlink(link_path)
            elif os.path.exists(link_path):
                logger.warning(f"目标路径已存在且不是软链接，跳过: {link_path}")
                return None
            
            # 创建软链接
            os.symlink(source_path, link_path)
            logger.info(f"创建软链接: {source_path} -> {link_path}")
            
            # 添加到数据库
            self.db_manager.add_symlink(source_path, link_path)
            
            return link_path
            
        except Exception as e:
            logger.error(f"创建软链接失败 {source_path}: {e}")
            return None
    
    def _remove_symlink(self, link_path: str) -> bool:
        """
        删除软链接
        
        Args:
            link_path: 软链接路径
            
        Returns:
            bool: 是否成功删除
        """
        try:
            if os.path.islink(link_path):
                os.unlink(link_path)
                logger.info(f"删除软链接: {link_path}")
                
                # 从数据库中删除
                self.db_manager.remove_symlink(link_path)
                
                # 清理空目录
                dir_path = os.path.dirname(link_path)
                while dir_path != self.base_path:
                    if not os.listdir(dir_path):
                        os.rmdir(dir_path)
                        logger.info(f"删除空目录: {dir_path}")
                        dir_path = os.path.dirname(dir_path)
                    else:
                        break
                
                return True
            return False
            
        except Exception as e:
            logger.error(f"删除软链接失败 {link_path}: {e}")
            return False
    
    def handle_file_change(self, path: str, is_delete: bool = False) -> None:
        """
        处理文件变化
        
        Args:
            path: 变化的文件路径
            is_delete: 是否是删除操作
        """
        try:
            # 检查是否需要处理该文件
            if not self._should_process_file(path):
                return
            
            if is_delete:
                # 查找并删除相关的软链接
                symlinks = self.db_manager.get_symlinks_by_source(path)
                for link_path in symlinks:
                    if self._remove_symlink(link_path):
                        # 通知Emby删除
                        if self.on_symlink_change:
                            self.on_symlink_change(link_path, True)
            else:
                # 创建或更新软链接
                link_path = self._create_symlink(path)
                if link_path and self.on_symlink_change:
                    # 通知Emby更新
                    self.on_symlink_change(link_path, False)
                
        except Exception as e:
            logger.error(f"处理文件变化失败 {path}: {e}")
    
    def cleanup(self) -> None:
        """清理失效的软链接"""
        try:
            # 遍历基础路径下的所有软链接
            for root, _, files in os.walk(self.base_path):
                for name in files:
                    link_path = os.path.join(root, name)
                    if os.path.islink(link_path):
                        # 检查软链接是否有效
                        if not os.path.exists(os.path.realpath(link_path)):
                            if self._remove_symlink(link_path):
                                # 通知Emby删除
                                if self.on_symlink_change:
                                    self.on_symlink_change(link_path, True)
            
            # 清理空目录
            for root, dirs, files in os.walk(self.base_path, topdown=False):
                for name in dirs:
                    dir_path = os.path.join(root, name)
                    if not os.listdir(dir_path):
                        os.rmdir(dir_path)
                        logger.info(f"删除空目录: {dir_path}")
                        
        except Exception as e:
            logger.error(f"清理软链接失败: {e}")
    
    def rebuild_all(self) -> None:
        """重建所有软链接"""
        try:
            # 清理现有软链接
            self.cleanup()
            
            # 获取数据库中的所有文件
            files = self.db_manager.get_all_files()
            
            # 重建软链接
            for file_info in files:
                self.handle_file_change(file_info['path'])
                
            logger.info("重建软链接完成")
            
        except Exception as e:
            logger.error(f"重建软链接失败: {e}") 