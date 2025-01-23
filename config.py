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
    symlink_base_path: str = "/mnt/media"
    
    # 文件模式配置
    file_patterns: Set[str] = field(default_factory=lambda: {
        "*.mp4",   # 视频文件
        "*.mkv",
        "*.avi",
        "*.m4v",
        "*.srt",   # 字幕文件
        "*.ass",
        "*.ssa"
    })
    
    # 排除模式配置
    exclude_patterns: List[str] = field(default_factory=lambda: [
        "**/BDMV/**",          # 蓝光目录
        "**/CERTIFICATE/**",    # 证书目录
        "**/@eaDir/**",        # Synology缩略图目录
        "**/lost+found/**"     # 系统恢复目录
    ])
    
    # 挂载点配置
    mount_points: List[str] = field(default_factory=list)  # 挂载点列表
    mount_check_interval: int = 60  # 挂载点状态检查间隔（秒）
    mount_retry_count: int = 3      # 挂载点状态检查重试次数
    mount_retry_delay: int = 5      # 挂载点状态检查重试间隔（秒）
    
    # 监控目录配置
    monitor_paths: List[str] = field(default_factory=list)  # 监控目录列表
    
    # Google Drive配置
    enable_gdrive: bool = False  # 是否启用Google Drive监控
    gdrive_root_path: str = ""  # Google Drive根路径
    local_root_path: str = ""   # 本地挂载路径
    gdrive_polling_interval: int = 3600  # Google Drive查询间隔(秒)
    gdrive_query_buffer_time: int = 300  # Google Drive查询缓冲时间(秒)
    gdrive_token: Optional[Dict[str, Any]] = None  # Google Drive访问令牌
    gdrive_client_id: Optional[str] = None  # 客户端ID
    gdrive_client_secret: Optional[str] = None  # 客户端密钥
    gdrive_root_folder_id: Optional[str] = None  # 根文件夹ID
    gdrive_team_drive_id: Optional[str] = None  # 团队云端硬盘ID
    gdrive_scope: str = "https://www.googleapis.com/auth/drive.readonly"  # API权限范围
    
    # Emby配置
    emby_host: str = "http://localhost:8096"
    emby_api_key: Optional[str] = None
    
    # 本地监控配置
    local_polling_interval: int = 300  # 本地文件轮询间隔（秒）
    
    # 性能配置
    thread_pool_size: int = 8  # 线程池大小，默认为8个线程
    batch_size: int = 100  # 批处理文件数量
    progress_interval: int = 10  # 进度日志更新间隔（秒）
    
    def __post_init__(self):
        """初始化后处理"""
        # 确保路径是绝对路径
        self.db_path = os.path.abspath(self.db_path)
        self.symlink_base_path = os.path.abspath(self.symlink_base_path)
        
        # 确保必要的目录存在
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        os.makedirs(self.symlink_base_path, exist_ok=True)
        
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
        
        # 验证性能配置
        if not isinstance(self.thread_pool_size, int):
            raise ValueError("线程池大小必须是整数")
        if self.thread_pool_size < 1:
            raise ValueError("线程池大小必须大于0")
        if self.thread_pool_size > 16:
            logger.warning("线程池大小过大可能影响性能")
            
        if not isinstance(self.batch_size, int):
            raise ValueError("批处理文件数量必须是整数")
        if self.batch_size < 1:
            raise ValueError("批处理文件数量必须大于0")
        if self.batch_size > 1000:
            logger.warning("批处理文件数量过大可能影响性能")
            
        if not isinstance(self.progress_interval, int):
            raise ValueError("进度日志更新间隔必须是整数")
        if self.progress_interval < 1:
            raise ValueError("进度日志更新间隔必须大于0秒")
        if self.progress_interval > 60:
            logger.warning("进度日志更新间隔过长可能影响用户体验")
    
    def validate(self) -> bool:
        """
        验证配置是否有效
        
        Returns:
            bool: 配置是否有效
        """
        try:
            # 验证线程池大小
            if not isinstance(self.thread_pool_size, int):
                logger.error("线程池大小必须是整数")
                return False
            if self.thread_pool_size < 1:
                logger.error("线程池大小必须大于0")
                return False
            if self.thread_pool_size > 16:
                logger.warning("线程池大小过大可能影响性能")
            
            # 验证 Google Drive 配置
            if self.enable_gdrive:
                if not self.gdrive_root_path:
                    raise ValueError("Google Drive 根路径不能为空")
                if not self.local_root_path:
                    raise ValueError("本地挂载路径不能为空")
                if not os.path.isabs(self.gdrive_root_path):
                    raise ValueError("Google Drive 根路径必须是绝对路径")
                if not os.path.isabs(self.local_root_path):
                    raise ValueError("本地挂载路径必须是绝对路径")
                if self.gdrive_polling_interval < 30:
                    logger.warning("Google Drive 轮询间隔过短，建议设置为 30 秒以上")
                if not self.gdrive_client_id or not self.gdrive_client_secret:
                    raise ValueError("启用Google Drive监控需要配置client_id和client_secret")
            
            return True
            
        except Exception as e:
            logger.error(f"验证配置失败: {e}")
            return False

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
            config_data['exclude_patterns'] = list(config_data['exclude_patterns'])
            
        # 直接使用配置数据创建实例
        return cls(**config_data)

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
# config = Config() 

# 导出类
__all__ = ['Config'] 