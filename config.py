import os
from typing import Set, List, Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
import yaml

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
        "/mnt/gdrive",
        "/media/gdrive"
    ])
    
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
    
    # 监控配置
    polling_interval: int = 300
    
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

# 创建默认配置实例
config = Config() 