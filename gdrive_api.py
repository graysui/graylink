import os
import time
import pickle
from typing import Optional, Callable, Dict, Any
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from utils.logging_utils import logger
from db_manager import DatabaseManager
from config import Config

class GoogleDriveMonitor:
    """Google Drive监控器"""
    
    def __init__(self, 
                 db_manager: DatabaseManager,
                 config: Config,
                 on_file_change: Optional[Callable[[str], None]] = None):
        """
        初始化Google Drive监控器
        
        Args:
            db_manager: 数据库管理器实例
            config: 配置实例
            on_file_change: 文件变化回调函数
        """
        self.db_manager = db_manager
        self.config = config
        self.on_file_change = on_file_change
        self.service = None
        self.last_check_time = None
    
    def _load_credentials(self) -> None:
        """加载Google Drive API凭证"""
        creds = None
        
        # 尝试从token文件加载凭证
        if os.path.exists(self.config.gdrive_token_path):
            with open(self.config.gdrive_token_path, 'rb') as token:
                creds = pickle.load(token)
        
        # 如果没有有效凭证，则请求新凭证
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.config.gdrive_credentials_path,
                    ['https://www.googleapis.com/auth/drive.readonly']
                )
                creds = flow.run_local_server(port=0)
            
            # 保存凭证
            with open(self.config.gdrive_token_path, 'wb') as token:
                pickle.dump(creds, token)
        
        # 创建Drive API服务
        self.service = build('drive', 'v3', credentials=creds)
        logger.info("Google Drive API服务初始化成功")
    
    def _get_file_info(self, file_id: str) -> Optional[Dict[str, Any]]:
        """
        获取文件信息
        
        Args:
            file_id: Google Drive文件ID
            
        Returns:
            Optional[Dict[str, Any]]: 文件信息字典
        """
        try:
            file = self.service.files().get(
                fileId=file_id,
                fields='id, name, mimeType, modifiedTime, size, parents'
            ).execute()
            
            # 构建本地路径
            path = self._build_local_path(file)
            if not path:
                return None
            
            return {
                'path': path,
                'size': int(file.get('size', 0)),
                'mtime': datetime.fromisoformat(file['modifiedTime'].replace('Z', '+00:00')).timestamp()
            }
            
        except Exception as e:
            logger.error(f"获取文件信息失败 {file_id}: {e}")
            return None
    
    def _build_local_path(self, file: Dict[str, Any]) -> Optional[str]:
        """
        构建文件的本地路径
        
        Args:
            file: Google Drive文件信息
            
        Returns:
            Optional[str]: 本地路径
        """
        try:
            # 如果不是根目录，递归获取父目录路径
            if 'parents' in file:
                parent_id = file['parents'][0]
                if parent_id != self.config.gdrive_root_folder_id:
                    parent = self.service.files().get(
                        fileId=parent_id,
                        fields='id, name, parents'
                    ).execute()
                    parent_path = self._build_local_path(parent)
                    if parent_path:
                        return os.path.join(parent_path, file['name'])
            
            # 如果是根目录下的文件，直接返回
            return os.path.join(self.config.mount_points[0], file['name'])
            
        except Exception as e:
            logger.error(f"构建本地路径失败 {file.get('id')}: {e}")
            return None
    
    def _check_changes(self) -> None:
        """检查文件变化"""
        try:
            # 设置查询参数
            query = f"'{self.config.gdrive_root_folder_id}' in parents" if self.config.gdrive_root_folder_id else "root"
            if self.last_check_time:
                query += f" and modifiedTime > '{self.last_check_time.isoformat()}Z'"
            
            # 获取文件列表
            results = self.service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name, mimeType, modifiedTime, size, parents)'
            ).execute()
            
            # 处理变化的文件
            for file in results.get('files', []):
                if file['mimeType'].startswith('application/vnd.google-apps'):
                    continue  # 跳过Google文档类型
                    
                file_info = self._get_file_info(file['id'])
                if not file_info:
                    continue
                
                # 检查文件是否已存在于数据库
                existing_info = self.db_manager.get_file_info(file_info['path'])
                if existing_info:
                    if existing_info['mtime'] == file_info['mtime']:
                        logger.debug(f"文件未变化，跳过处理: {file_info['path']}")
                        continue
                    logger.info(f"更新文件记录: {file_info['path']}")
                else:
                    logger.info(f"新增文件记录: {file_info['path']}")
                
                # 更新数据库
                self.db_manager.add_file(
                    file_info['path'],
                    file_info['size'],
                    file_info['mtime']
                )
                
                # 通知文件变化
                if self.on_file_change:
                    self.on_file_change(file_info['path'])
            
            self.last_check_time = datetime.utcnow()
            
        except Exception as e:
            logger.error(f"检查文件变化失败: {e}")
    
    def start(self) -> None:
        """启动监控"""
        try:
            self._load_credentials()
            logger.info("Google Drive监控已启动")
            
        except Exception as e:
            logger.error(f"启动Google Drive监控失败: {e}")
            raise
    
    def stop(self) -> None:
        """停止监控"""
        if self.service:
            self.service.close()
            self.service = None
        logger.info("Google Drive监控已停止")
    
    def run_forever(self) -> None:
        """持续运行监控"""
        try:
            self.start()
            
            while True:
                # 检查文件变化
                self._check_changes()
                # 等待下一次检查
                time.sleep(self.config.polling_interval)
                
        except KeyboardInterrupt:
            logger.info("收到停止信号")
        finally:
            self.stop() 