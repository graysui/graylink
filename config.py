import os
from typing import Set, List, Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
import yaml
import logging

logger = logging.getLogger(__name__)

@dataclass
class Config:
    """配置类"""
    
    # 数据库配置
    db_path: str = "data/graylink.db"
    
    # 软链接配置
    symlink_base_path: str = "data/media"
    
    # 文件模式配置
    file_patterns: Set[str] = field(default_factory=lambda: {
        "*.mp4", "*.mkv", "*.avi", "*.m4v",  # 视频文件
        "*.srt", "*.ass", "*.ssa"  # 字幕文件
    })
    
    # 排除模式配置
    exclude_patterns: Set[str] = field(default_factory=lambda: {
        "**/BDMV/**",  # 蓝光目录
        "**/CERTIFICATE/**",  # 证书目录
        "**/@eaDir/**",  # Synology缩略图目录
        "**/lost+found/**"  # 系统恢复目录
    })
    
    # 挂载点配置
    mount_points: List[str] = field(default_factory=lambda: [
        "/mnt/9w"  # 本地挂载点
    ])
    mount_check_interval: int = 60  # 挂载点状态检查间隔（秒）
    mount_retry_count: int = 3      # 挂载点状态检查重试次数
    mount_retry_delay: int = 5      # 挂载点状态检查重试间隔（秒）
    
    # 监控目录配置
    monitor_paths: List[str] = field(default_factory=lambda: [
        "/mnt/9w/media/nastool"  # 实际需要监控的目录
    ])
    
    # Google Drive路径映射
    gdrive_root_path: str = "/media/nastool"
    local_root_path: str = "/mnt/9w/media/nastool"
    
    # Google Drive配置
    gdrive_client_id: str = ""
    gdrive_client_secret: str = ""
    gdrive_token: Dict[str, Any] = field(default_factory=dict)
    gdrive_team_drive_id: Optional[str] = None
    gdrive_root_folder_id: Optional[str] = None
    gdrive_scope: str = "https://www.googleapis.com/auth/drive.readonly"
    
    # Emby配置
    emby_host: str = "http://localhost:8096"
    emby_api_key: Optional[str] = None
    
    # Google Drive监控配置
    gdrive_polling_interval: int = 3600  # Google Drive查询间隔(秒)，默认1小时
    gdrive_query_buffer_time: int = 300  # Google Drive查询缓冲时间(秒)，默认5分钟
    
    # 本地监控配置
    local_polling_interval: int = 300  # 本地文件轮询间隔（秒）
    
    # 线程池配置
    thread_pool_size: int = 4  # 线程池大小，默认4个线程
    
    def __post_init__(self):
        """初始化后处理"""
        # 确保路径是绝对路径
        self.db_path = os.path.abspath(self.db_path)
        self.symlink_base_path = os.path.abspath(self.symlink_base_path)
        
        # 确保必要的目录存在
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        os.makedirs(self.symlink_base_path, exist_ok=True)
        
        # 验证Google Drive配置
        if self.gdrive_token:
            required_keys = {'access_token', 'refresh_token', 'token_type', 'expiry'}
            if not all(key in self.gdrive_token for key in required_keys):
                raise ValueError("Google Drive token格式不正确")
            
            # 确保expiry是字符串格式
            if isinstance(self.gdrive_token['expiry'], datetime):
                self.gdrive_token['expiry'] = self.gdrive_token['expiry'].isoformat()
        
        # 验证挂载点配置
        if not self.mount_points:
            raise ValueError("至少需要配置一个挂载点")
        
        # 确保挂载点路径是绝对路径
        self.mount_points = [os.path.abspath(p) for p in self.mount_points]
        
        # 验证监控目录配置
        if not self.monitor_paths:
            raise ValueError("至少需要配置一个监控目录")
        
        # 确保监控目录是绝对路径
        self.monitor_paths = [os.path.abspath(p) for p in self.monitor_paths]
        
        # 验证监控目录是否在挂载点下
        for monitor_path in self.monitor_paths:
            if not any(monitor_path.startswith(mount_point) for mount_point in self.mount_points):
                raise ValueError(f"监控目录必须在挂载点下: {monitor_path}")
        
        # 验证挂载点状态检查参数
        if self.mount_check_interval < 1:
            raise ValueError("挂载点状态检查间隔必须大于0秒")
        if self.mount_retry_count < 0:
            raise ValueError("挂载点状态检查重试次数必须大于等于0")
        if self.mount_retry_delay < 1:
            raise ValueError("挂载点状态检查重试间隔必须大于0秒")
        
        # 验证线程池大小
        if not isinstance(self.thread_pool_size, int):
            logger.error("线程池大小必须是整数")
            raise ValueError("线程池大小必须是整数")
        if self.thread_pool_size < 1:
            logger.error("线程池大小必须大于0")
            raise ValueError("线程池大小必须大于0")
        if self.thread_pool_size > 16:
            logger.warning("线程池大小过大可能影响性能")

    @classmethod
    def load_from_yaml(cls, config_path: str) -> 'Config':
        """从YAML文件加载配置"""
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"配置文件不存在: {config_path}")
            
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)
        
        # 处理集合类型
        if 'file_patterns' in config_data:
            config_data['file_patterns'] = set(config_data['file_patterns'])
        if 'exclude_patterns' in config_data:
            config_data['exclude_patterns'] = set(config_data['exclude_patterns'])
            
        # 创建配置实例
        config = cls()
        
        # 更新配置值
        for key, value in config_data.items():
            if hasattr(config, key):
                setattr(config, key, value)
        
        return config

    def save_to_yaml(self, config_path: str) -> None:
        """保存配置到YAML文件"""
        # 转换为可序列化的格式
        config_data = {}
        for key, value in self.__dict__.items():
            if key.startswith('_'):
                continue
                
            if isinstance(value, set):
                value = list(value)
            config_data[key] = value
        
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config_data, f, allow_unicode=True, default_flow_style=False)

    def validate(self) -> bool:
        """
        验证配置是否有效
        
        Returns:
            bool: 配置是否有效
        """
        try:
            # ... existing code ...
            
            # 验证线程池大小
            if not isinstance(self.thread_pool_size, int):
                logger.error("线程池大小必须是整数")
                return False
            if self.thread_pool_size < 1:
                logger.error("线程池大小必须大于0")
                return False
            if self.thread_pool_size > 16:
                logger.warning("线程池大小过大可能影响性能")
            
            return True
            
        except Exception as e:
            logger.error(f"验证配置失败: {e}")
            return False

# 创建默认配置实例
config = Config() 