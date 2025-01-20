import os
import time
from typing import Optional, Dict, List, Any
from datetime import datetime
import requests
from utils.logging_utils import logger
from config import Config

class EmbyNotifier:
    """Emby通知器"""
    
    def __init__(self, config: Config):
        """
        初始化Emby通知器
        
        Args:
            config: 配置实例
        """
        self.config = config
        self._validate_config()
        
        # 构建API基础URL
        self.base_url = self.config.emby_host.rstrip('/')
        
        # 设置请求头
        self.headers = {
            'X-Emby-Token': self.config.emby_api_key,
            'Content-Type': 'application/json'
        }
        
        # 初始化会话
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        
        # 缓存媒体库信息
        self.libraries: Dict[str, Dict[str, Any]] = {}
        self.last_libraries_update = 0
        self.libraries_cache_ttl = 300  # 5分钟缓存
        
        # 验证连接并初始化媒体库信息
        self._check_connection()
        self._update_libraries_cache()
    
    def _validate_config(self) -> None:
        """验证配置是否有效"""
        if not self.config.emby_host:
            raise ValueError("Emby服务器地址未配置")
        if not self.config.emby_api_key:
            raise ValueError("Emby API密钥未配置")
    
    def _check_connection(self) -> None:
        """检查与Emby服务器的连接"""
        try:
            response = self.session.get(f"{self.base_url}/System/Info")
            response.raise_for_status()
            logger.info("Emby服务器连接成功")
            
        except requests.RequestException as e:
            logger.error(f"Emby服务器连接失败: {e}")
            raise
    
    def _update_libraries_cache(self) -> None:
        """更新媒体库缓存"""
        try:
            current_time = time.time()
            if current_time - self.last_libraries_update < self.libraries_cache_ttl:
                return
                
            response = self.session.get(f"{self.base_url}/Library/MediaFolders")
            response.raise_for_status()
            items = response.json().get('Items', [])
            
            # 获取每个媒体库的详细配置
            for item in items:
                library_id = item['Id']
                config_response = self.session.get(
                    f"{self.base_url}/Library/VirtualFolders/LibraryOptions",
                    params={'libraryId': library_id}
                )
                config_response.raise_for_status()
                
                self.libraries[library_id] = {
                    'id': library_id,
                    'name': item['Name'],
                    'type': item.get('CollectionType', ''),
                    'paths': item.get('Paths', []),
                    'config': config_response.json()
                }
            
            self.last_libraries_update = current_time
            logger.debug(f"媒体库缓存已更新，共{len(self.libraries)}个库")
            
        except Exception as e:
            logger.error(f"更新媒体库缓存失败: {e}")
    
    def _find_library_for_path(self, path: str) -> Optional[Dict[str, Any]]:
        """
        查找包含指定路径的媒体库信息
        
        Args:
            path: 文件路径
            
        Returns:
            Optional[Dict[str, Any]]: 媒体库信息
        """
        try:
            # 更新缓存
            self._update_libraries_cache()
            
            # 规范化路径
            norm_path = os.path.normpath(path)
            longest_match = 0
            matched_library = None
            
            # 查找最匹配的媒体库
            for library in self.libraries.values():
                for lib_path in library['paths']:
                    lib_path = os.path.normpath(lib_path)
                    if norm_path.startswith(lib_path) and len(lib_path) > longest_match:
                        longest_match = len(lib_path)
                        matched_library = library
            
            return matched_library
            
        except Exception as e:
            logger.error(f"查找媒体库失败: {e}")
            return None
    
    def _is_subtitle_file(self, path: str) -> bool:
        """
        判断是否是字幕文件
        
        Args:
            path: 文件路径
            
        Returns:
            bool: 是否是字幕文件
        """
        subtitle_exts = {'.srt', '.ass', '.ssa', '.sub'}
        return os.path.splitext(path)[1].lower() in subtitle_exts
    
    def refresh_library(self, path: str, is_delete: bool = False) -> bool:
        """
        刷新媒体库中的指定路径
        
        Args:
            path: 文件路径
            is_delete: 是否是删除操作
            
        Returns:
            bool: 是否成功
        """
        try:
            # 查找相关的媒体库
            library = self._find_library_for_path(path)
            if not library:
                logger.warning(f"未找到包含路径的媒体库: {path}")
                return False
            
            # 构建更新请求
            update_type = "Deleted" if is_delete else "Modified"
            is_subtitle = self._is_subtitle_file(path)
            
            if is_subtitle:
                # 对于字幕文件，只刷新其所在目录
                parent_dir = os.path.dirname(path)
                response = self.session.post(
                    f"{self.base_url}/Library/Media/Updated",
                    json={
                        'Updates': [{
                            'Path': parent_dir,
                            'UpdateType': update_type
                        }]
                    }
                )
            else:
                # 对于视频文件，直接刷新文件
                response = self.session.post(
                    f"{self.base_url}/Library/Media/Updated",
                    json={
                        'Updates': [{
                            'Path': path,
                            'UpdateType': update_type
                        }]
                    }
                )
            
            response.raise_for_status()
            logger.info(f"媒体库[{library['name']}]刷新请求已发送: {path}")
            return True
            
        except requests.RequestException as e:
            logger.error(f"刷新媒体库失败: {e}")
            return False
    
    def notify_file_change(self, path: str, is_delete: bool = False) -> None:
        """
        通知文件变化
        
        Args:
            path: 变化的文件路径
            is_delete: 是否是删除操作
        """
        try:
            if self.refresh_library(path, is_delete):
                logger.info(f"已通知Emby刷新{'删除' if is_delete else '更新'}: {path}")
            else:
                logger.warning(f"通知Emby刷新失败: {path}")
                
        except Exception as e:
            logger.error(f"处理文件变化通知失败: {e}")
    
    def close(self) -> None:
        """关闭通知器"""
        if self.session:
            self.session.close()
            logger.info("Emby通知器已关闭") 