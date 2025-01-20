import os
import logging
import logging.handlers
from typing import Optional
from colorlog import ColoredFormatter

# 默认日志格式
DEFAULT_LOG_FORMAT = "%(asctime)s %(log_color)s%(levelname)-8s%(reset)s %(blue)s%(name)s%(reset)s: %(message)s"
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 日志颜色配置
LOG_COLORS = {
    'DEBUG': 'cyan',
    'INFO': 'green',
    'WARNING': 'yellow',
    'ERROR': 'red',
    'CRITICAL': 'red,bg_white'
}

def setup_logging(log_file: Optional[str] = None,
                 log_level: int = logging.INFO,
                 max_bytes: int = 10 * 1024 * 1024,  # 10MB
                 backup_count: int = 5) -> None:
    """
    设置日志系统
    
    Args:
        log_file: 日志文件路径，如果为None则只输出到控制台
        log_level: 日志级别
        max_bytes: 单个日志文件最大字节数
        backup_count: 保留的日志文件数量
    """
    # 创建根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # 清除现有的处理器
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    
    # 设置彩色格式化器
    formatter = ColoredFormatter(
        DEFAULT_LOG_FORMAT,
        datefmt=DEFAULT_DATE_FORMAT,
        log_colors=LOG_COLORS,
        reset=True,
        style='%'
    )
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # 如果指定了日志文件，创建文件处理器
    if log_file:
        # 确保日志目录存在
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        
        # 创建循环文件处理器
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(log_level)
        
        # 设置普通格式化器（文件中不需要颜色）
        file_formatter = logging.Formatter(
            DEFAULT_LOG_FORMAT.replace("%(log_color)s", "").replace("%(reset)s", "").replace("%(blue)s", ""),
            datefmt=DEFAULT_DATE_FORMAT
        )
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

def get_logger(name: str) -> logging.Logger:
    """
    获取指定名称的日志记录器
    
    Args:
        name: 日志记录器名称
        
    Returns:
        logging.Logger: 日志记录器实例
    """
    return logging.getLogger(name)

# 创建默认日志记录器
logger = get_logger('graylink') 