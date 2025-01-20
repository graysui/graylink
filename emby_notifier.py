import os
import time
import requests
from typing import Optional
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
        
        # 验证连接
        self._check_connection()
    
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
    
    def _get_library_items(self) -> Optional[list]:
        """
        获取媒体库列表
        
        Returns:
            Optional[list]: 媒体库列表
        """
        try:
            response = self.session.get(f"{self.base_url}/Library/MediaFolders")
            response.raise_for_status()
            return response.json()['Items']
            
        except requests.RequestException as e:
            logger.error(f"获取媒体库列表失败: {e}")
            return None
    
    def _find_library_for_path(self, path: str) -> Optional[str]:
        """
        查找包含指定路径的媒体库ID
        
        Args:
            path: 文件路径
            
        Returns:
            Optional[str]: 媒体库ID
        """
        try:
            libraries = self._get_library_items()
            if not libraries:
                return None
            
            # 规范化路径
            norm_path = os.path.normpath(path)
            
            # 查找包含该路径的媒体库
            for library in libraries:
                for path_info in library.get('Path', []):
                    lib_path = os.path.normpath(path_info)
                    if norm_path.startswith(lib_path):
                        return library['Id']
            
            return None
            
        except Exception as e:
            logger.error(f"查找媒体库失败: {e}")
            return None
    
    def refresh_library(self, path: str) -> bool:
        """
        刷新包含指定路径的媒体库
        
        Args:
            path: 文件路径
            
        Returns:
            bool: 是否成功
        """
        try:
            # 查找相关的媒体库
            library_id = self._find_library_for_path(path)
            if not library_id:
                logger.warning(f"未找到包含路径的媒体库: {path}")
                return False
            
            # 发送刷新请求
            response = self.session.post(
                f"{self.base_url}/Library/Media/Updated",
                json={
                    'Updates': [{
                        'Path': path,
                        'UpdateType': 'Modified'
                    }]
                }
            )
            response.raise_for_status()
            
            logger.info(f"媒体库刷新请求已发送: {path}")
            return True
            
        except requests.RequestException as e:
            logger.error(f"刷新媒体库失败: {e}")
            return False
    
    def notify_file_change(self, path: str) -> None:
        """
        通知文件变化
        
        Args:
            path: 变化的文件路径
        """
        try:
            if self.refresh_library(path):
                logger.info(f"已通知Emby刷新: {path}")
            else:
                logger.warning(f"通知Emby刷新失败: {path}")
                
        except Exception as e:
            logger.error(f"处理文件变化通知失败: {e}")
    
    def close(self) -> None:
        """关闭通知器"""
        if self.session:
            self.session.close()
            logger.info("Emby通知器已关闭") 