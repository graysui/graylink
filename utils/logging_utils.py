import os
import logging
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from datetime import datetime

def setup_logging(log_dir: str = "logs", log_level: int = logging.INFO) -> None:
    """
    设置日志配置
    
    Args:
        log_dir: 日志目录
        log_level: 日志级别
    """
    try:
        # 确保日志目录存在
        os.makedirs(log_dir, exist_ok=True)
        
        # 创建日志格式
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # 设置按日期轮转的文件处理器
        daily_handler = TimedRotatingFileHandler(
            filename=os.path.join(log_dir, "graylink.log"),
            when='midnight',  # 每天午夜轮转
            interval=1,       # 每1天轮转一次
            backupCount=30,   # 保留30天的日志
            encoding='utf-8'
        )
        daily_handler.setFormatter(formatter)
        
        # 设置按大小轮转的文件处理器
        size_handler = RotatingFileHandler(
            os.path.join(log_dir, "graylink_current.log"),
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        size_handler.setFormatter(formatter)
        
        # 设置控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        
        # 配置根日志记录器
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)
        
        # 移除所有现有的处理器
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
            
        # 添加新的处理器
        root_logger.addHandler(daily_handler)
        root_logger.addHandler(size_handler)
        root_logger.addHandler(console_handler)
        
        # 创建应用日志记录器
        logger = logging.getLogger('graylink')
        logger.setLevel(log_level)
        
        # 设置其他模块的日志级别
        logging.getLogger('googleapiclient').setLevel(logging.WARNING)
        logging.getLogger('google_auth_oauthlib').setLevel(logging.WARNING)
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        
        # 记录日志系统启动信息
        logger.info("日志系统初始化完成")
        logger.info(f"日志目录: {os.path.abspath(log_dir)}")
        logger.info(f"日志级别: {logging.getLevelName(log_level)}")
        
    except Exception as e:
        print(f"初始化日志系统失败: {e}")
        raise

# 创建全局日志记录器
logger = logging.getLogger('graylink') 