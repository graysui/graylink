import os
from typing import Set, List, Optional
from dataclasses import dataclass
import yaml

@dataclass
class Config:
    """配置类"""
    
    # 数据库配置
    db_path: str = "data/graylink.db"
    
    # 软链接配置
    symlink_base_path: str = "data/media"
    
    # 文件模式配置
    file_patterns: Set[str] = {
        "*.mp4", "*.mkv", "*.avi", "*.m4v",  # 视频文件
        "*.srt", "*.ass", "*.ssa"  # 字幕文件
    }
    
    # 排除模式配置
    exclude_patterns: Set[str] = {
        "**/BDMV/**",  # 蓝光目录
        "**/CERTIFICATE/**",  # 证书目录
        "**/@eaDir/**",  # Synology缩略图目录
        "**/lost+found/**"  # 系统恢复目录
    }
    
    # 挂载点配置
    mount_points: List[str] = [
        "/mnt/gdrive",
        "/media/gdrive"
    ]
    
    # Google Drive配置
    gdrive_credentials_path: str = "config/credentials.json"
    gdrive_token_path: str = "config/token.pickle"
    gdrive_root_folder_id: Optional[str] = None
    
    # Emby配置
    emby_host: str = "http://localhost:8096"
    emby_api_key: Optional[str] = None
    
    # 监控配置
    polling_interval: int = 300  # 轮询间隔（秒）
    
    def __post_init__(self):
        """初始化后处理"""
        # 确保路径是绝对路径
        self.db_path = os.path.abspath(self.db_path)
        self.symlink_base_path = os.path.abspath(self.symlink_base_path)
        self.gdrive_credentials_path = os.path.abspath(self.gdrive_credentials_path)
        self.gdrive_token_path = os.path.abspath(self.gdrive_token_path)
        
        # 确保必要的目录存在
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        os.makedirs(self.symlink_base_path, exist_ok=True)
        os.makedirs(os.path.dirname(self.gdrive_credentials_path), exist_ok=True)

    @classmethod
    def load_from_yaml(cls, config_path: str) -> 'Config':
        """从YAML文件加载配置"""
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"配置文件不存在: {config_path}")
            
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)
            
        config = cls()
        for key, value in config_data.items():
            if hasattr(config, key):
                setattr(config, key, value)
                
        return config

    def save_to_yaml(self, config_path: str) -> None:
        """保存配置到YAML文件"""
        config_data = {
            key: value for key, value in self.__dict__.items()
            if not key.startswith('_')
        }
        
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config_data, f, allow_unicode=True, default_flow_style=False)

# 创建默认配置实例
config = Config() 