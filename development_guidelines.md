# GrayLink 项目开发规范

## 一、总体原则

1. **简单性原则**
   - 使用最简单的解决方案
   - 避免过度设计
   - 保持代码清晰易懂

2. **一致性原则**
   - 遵循统一的代码风格
   - 保持模块接口的一致性
   - 统一的错误处理方式

3. **可维护性原则**
   - 完整的文档和注释
   - 合理的模块划分
   - 清晰的代码结构

## 二、目录结构规范

```
graylink/
├── gdrive_api.py       # Google Drive 监控
├── local_monitor.py    # 本地目录监控
├── symlink_manager.py  # 软链接管理
├── emby_notifier.py    # Emby 通知
├── db_manager.py       # 数据库管理
├── snapshot_generator.py # 快照生成
├── config.py           # 配置文件
├── utils/              # 工具函数
│   ├── logging_utils.py
│   ├── file_utils.py
│   └── network_utils.py
└── README.md           # 项目文档
```

## 三、模块连通性规范

1. **模块间接口规范**
   ```python
   # 使用抽象基类定义接口
   from abc import ABC, abstractmethod
   
   class MonitorInterface(ABC):
       @abstractmethod
       def start_monitoring(self):
           pass
           
       @abstractmethod
       def stop_monitoring(self):
           pass
   ```

2. **数据流转规范**
   ```python
   # 统一的数据流转接口
   class FileEvent:
       def __init__(self, path: str, event_type: str):
           self.path = path
           self.event_type = event_type
           self.timestamp = datetime.now()
   ```

3. **事件处理规范**
   ```python
   # 统一的事件处理流程
   class EventHandler:
       def handle_event(self, event: FileEvent):
           try:
               # 1. 验证事件
               self.validate_event(event)
               # 2. 处理事件
               self.process_event(event)
               # 3. 通知其他模块
               self.notify_modules(event)
           except Exception as e:
               logger.error(f"Event handling failed: {e}")
   ```

## 四、引用规范

1. **导入顺序**
   ```python
   # 1. 标准库导入
   import os
   import sys
   from datetime import datetime
   
   # 2. 第三方库导入
   import requests
   from watchdog.observers import Observer
   
   # 3. 本地模块导入
   from app.core.monitor import FileMonitor
   from app.utils.logger import logger
   ```

2. **相对导入规范**
   ```python
   # 推荐使用相对导入
   from ..models import FileInfo
   from .utils import hash_file
   ```

## 五、数据模型规范

1. **基础数据模型**
   ```python
   from typing import Optional, Dict
   from datetime import datetime
   
   class BaseModel:
       def to_dict(self) -> dict:
           """转换为字典格式"""
           return self.__dict__
   
       @classmethod
       def from_dict(cls, data: dict) -> "BaseModel":
           """从字典创建实例"""
           instance = cls()
           for key, value in data.items():
               setattr(instance, key, value)
           return instance
   ```

2. **文件信息模型**
   ```python
   class FileInfo(BaseModel):
       def __init__(self):
           self.path: str = ""
           self.size: int = 0
           self.modified_time: datetime = datetime.now()
           self.hash: Optional[str] = None
           self.metadata: Dict[str, any] = {}
   ```

## 六、错误处理规范

1. **异常层次**
   ```python
   class GrayLinkError(Exception):
       """基础错误类型"""
       pass
   
   class MonitorError(GrayLinkError):
       """监控相关错误"""
       pass
   
   class SymlinkError(GrayLinkError):
       """软链接相关错误"""
       pass
   ```

2. **错误处理流程**
   ```python
   try:
       # 执行操作
       result = operation()
   except GrayLinkError as e:
       # 处理已知错误
       logger.error(f"Operation failed: {e}")
       # 进行错误恢复
       recover_from_error(e)
   except Exception as e:
       # 处理未知错误
       logger.critical(f"Unexpected error: {e}")
       # 通知管理员
       notify_admin(e)
   ```

## 七、配置管理规范

1. **配置结构**
   ```python
   class Config:
       def __init__(self):
           # 监控配置
           self.monitor_paths = []
           self.monitor_interval = 300
           
           # 软链接配置
           self.symlink_base = ""
           self.symlink_rules = {}
           
           # Emby配置
           self.emby_url = ""
           self.emby_api_key = ""
           
           # 数据库配置
           self.db_path = ""
   ```

2. **配置加载**
   ```python
   from pathlib import Path
   import yaml
   
   def load_config(config_path: Path) -> Config:
       """从YAML文件加载配置"""
       with config_path.open() as f:
           data = yaml.safe_load(f)
       return Config.from_dict(data)
   ```

## 八、日志规范

1. **日志配置**
   ```python
   import logging
   
   def setup_logging():
       logging.basicConfig(
           level=logging.INFO,
           format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
           handlers=[
               logging.FileHandler('graylink.log'),
               logging.StreamHandler()
           ]
       )
   ```

2. **日志使用**
   ```python
   logger = logging.getLogger(__name__)
   
   # 信息日志
   logger.info("Starting file monitoring...")
   
   # 错误日志
   logger.error("Failed to create symlink: %s", error)
   
   # 调试日志
   logger.debug("Processing file: %s", file_path)
   ```

## 九、代码风格规范

1. **命名规范**
   - 类名：使用 PascalCase
   - 函数名：使用 snake_case
   - 变量名：使用 snake_case
   - 常量名：使用 UPPER_CASE

2. **注释规范**
   ```python
   def process_file(file_path: str) -> Optional[FileInfo]:
       """
       处理文件并返回文件信息
       
       Args:
           file_path: 文件路径
           
       Returns:
           FileInfo: 文件信息对象，如果处理失败返回None
           
       Raises:
           FileNotFoundError: 文件不存在
           PermissionError: 没有访问权限
       """
       pass
   ```

## 十、测试规范

1. **测试文件结构**
   ```python
   # test_monitor.py
   class TestFileMonitor:
       def setup_method(self):
           """测试前准备"""
           pass
           
       def teardown_method(self):
           """测试后清理"""
           pass
           
       def test_file_change_detection(self):
           """测试文件变化检测"""
           pass
   ```

2. **测试命名**
   - 测试文件：`test_*.py`
   - 测试类：`Test*`
   - 测试方法：`test_*`

## 十一、版本控制规范

1. **分支管理**
   - main：主分支，用于发布
   - develop：开发分支
   - feature/*：功能分支
   - bugfix/*：修复分支

2. **提交信息**
   ```
   feat: 添加文件监控功能
   fix: 修复软链接创建失败的问题
   docs: 更新README文档
   test: 添加单元测试
   ```

## 十二、文档规范

1. **代码文档**
   - 每个模块都要有模块级别的文档
   - 每个公共函数都要有函数文档
   - 复杂的逻辑要有详细的注释

2. **项目文档**
   - README.md：项目概述
   - CONTRIBUTING.md：贡献指南
   - CHANGELOG.md：版本更新日志
   - development_guidelines.md：开发规范（本文档） 