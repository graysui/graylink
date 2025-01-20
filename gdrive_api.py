import os
import time
from typing import Optional, Callable, Dict, Any, List
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
        self.drive_service = None
        self.activity_service = None
        self.last_check_time = None
    
    def _load_credentials(self) -> None:
        """加载Google Drive API凭证"""
        try:
            # 使用rclone格式的配置创建凭证
            creds = Credentials(
                token=self.config.gdrive_token['access_token'],
                refresh_token=self.config.gdrive_token['refresh_token'],
                token_uri="https://oauth2.googleapis.com/token",
                client_id=self.config.gdrive_client_id,
                client_secret=self.config.gdrive_client_secret,
                expiry=datetime.strptime(self.config.gdrive_token['expiry'], "%Y-%m-%dT%H:%M:%S.%f%z")
            )
            
            # 如果凭证过期，刷新它
            if creds.expired:
                creds.refresh(Request())
                # 更新配置中的token
                self.config.gdrive_token.update({
                    'access_token': creds.token,
                    'refresh_token': creds.refresh_token,
                    'expiry': creds.expiry.isoformat()
                })
            
            # 创建Drive和Activity服务
            self.drive_service = build('drive', 'v3', credentials=creds)
            self.activity_service = build('driveactivity', 'v2', credentials=creds)
            logger.info("Google Drive API凭证加载成功")
            
        except Exception as e:
            logger.error(f"加载Google Drive API凭证失败: {e}")
            raise
    
    def _get_file_info(self, file_id: str) -> Optional[Dict[str, Any]]:
        """
        获取文件信息
        
        Args:
            file_id: Google Drive文件ID
            
        Returns:
            Optional[Dict[str, Any]]: 文件信息字典
        """
        try:
            file = self.drive_service.files().get(
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
                    parent = self.drive_service.files().get(
                        fileId=parent_id,
                        fields='id, name, parents'
                    ).execute()
                    parent_path = self._build_local_path(parent)
                    if parent_path:
                        return os.path.join(parent_path, file['name'])
            
            # 构建完整路径
            full_path = os.path.join('/', file['name'])
            
            # 检查是否包含目标路径
            if self.config.gdrive_root_path in full_path:
                # 找到目标路径在完整路径中的位置
                target_index = full_path.find(self.config.gdrive_root_path)
                # 提取目标路径及其后面的部分
                target_path = full_path[target_index:]
                # 替换为本地路径
                local_path = target_path.replace(self.config.gdrive_root_path, self.config.local_root_path)
                return local_path
            
            return None
            
        except Exception as e:
            logger.error(f"构建本地路径失败 {file.get('id')}: {e}")
            return None
    
    def _get_file_id_from_activity(self, target: Dict[str, Any]) -> Optional[str]:
        """
        从活动目标中提取文件ID
        
        Args:
            target: 活动目标信息
            
        Returns:
            Optional[str]: 文件ID
        """
        try:
            if 'driveItem' in target:
                # 从类似 "items/1234567" 的格式中提取ID
                return target['driveItem']['name'].split('/')[-1]
            return None
        except Exception:
            return None
    
    def _check_changes(self) -> None:
        """检查文件变化"""
        try:
            current_time = datetime.utcnow()
            
            # 计算查询时间范围
            if self.last_check_time:
                # 使用上次检查时间作为起点
                start_time = self.last_check_time
            else:
                # 首次运行时，查询一个完整周期加缓冲时间的范围
                start_time = current_time - timedelta(
                    seconds=self.config.gdrive_polling_interval + self.config.gdrive_query_buffer_time
                )
            
            # 构建查询请求
            request = {
                'pageSize': 100,  # 每页活动数量
                'filter': f'''
                    time >= "{start_time.isoformat()}Z"
                    AND time <= "{current_time.isoformat()}Z"
                '''
            }

            # 如果指定了团队硬盘ID，添加相关参数
            if self.config.gdrive_team_drive_id:
                request['ancestorName'] = f'items/{self.config.gdrive_team_drive_id}'

            # 获取活动列表
            response = self.activity_service.activity().query(body=request).execute()
            activities = response.get('activities', [])

            # 处理每个活动
            for activity in activities:
                # 获取活动时间
                activity_time = datetime.fromisoformat(
                    activity['timestamp'].replace('Z', '+00:00')
                )

                # 处理活动目标
                for target in activity.get('targets', []):
                    file_id = self._get_file_id_from_activity(target)
                    if not file_id:
                        continue

                    # 获取文件信息
                    file_info = self._get_file_info(file_id)
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
        if self.drive_service:
            self.drive_service.close()
            self.drive_service = None
        if self.activity_service:
            self.activity_service.close()
            self.activity_service = None
        logger.info("Google Drive监控已停止")
    
    def run_forever(self) -> None:
        """持续运行监控"""
        try:
            self.start()
            
            while True:
                # 检查文件变化
                self._check_changes()
                # 等待下一次检查
                time.sleep(self.config.gdrive_polling_interval)
                
        except KeyboardInterrupt:
            logger.info("收到停止信号")
        finally:
            self.stop() 