import os
import json
import time
import pytz
import threading
import concurrent.futures
from queue import Queue
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from jinja2 import Environment, FileSystemLoader
from db_manager import DatabaseManager
from config import Config
from utils.logging_utils import logger

class ProgressTracker:
    """进度跟踪器"""
    
    def __init__(self, total: int, description: str = "处理进度"):
        self.total = total
        self.current = 0
        self.description = description
        self.start_time = time.time()
        self.last_update = 0
        self._lock = threading.Lock()
    
    def update(self, amount: int = 1) -> None:
        """更新进度"""
        with self._lock:
            self.current += amount
            current_time = time.time()
            # 每0.5秒更新一次日志
            if current_time - self.last_update >= 0.5:
                self._display_progress()
                self.last_update = current_time
    
    def _display_progress(self) -> None:
        """显示进度信息"""
        percentage = (self.current / self.total) * 100 if self.total > 0 else 0
        elapsed = time.time() - self.start_time
        speed = self.current / elapsed if elapsed > 0 else 0
        
        logger.info(
            f"{self.description}: {percentage:.1f}% "
            f"({self.current}/{self.total}) "
            f"速度: {speed:.1f} 项/秒"
        )

class HtmlExporter:
    """HTML导出器"""
    
    def __init__(self, db_manager: DatabaseManager, config: Config):
        """
        初始化HTML导出器
        
        Args:
            db_manager: 数据库管理器实例
            config: 配置实例
        """
        self.db_manager = db_manager
        self.config = config
        self.max_workers = os.cpu_count() or 4  # 线程池大小
        
        # 设置Jinja2模板环境
        template_dir = os.path.join(os.path.dirname(__file__), 'templates')
        self.jinja_env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=True
        )
    
    def _format_size(self, size: int) -> str:
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"
    
    def _format_time(self, timestamp: float) -> str:
        """格式化时间戳"""
        return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')

    def _normalize_path(self, path: str) -> str:
        """
        标准化路径，统一路径格式
        
        Args:
            path: 原始路径
            
        Returns:
            str: 标准化后的路径
        """
        # 统一使用正斜杠
        path = path.replace(os.sep, '/')
        
        # 移除开头的驱动器号(如 "C:")
        if len(path) > 2 and path[1] == ':':
            path = path[2:]
            
        # 确保路径以 / 开头
        if not path.startswith('/'):
            path = '/' + path
            
        return path

    def _build_directory_data(self) -> List[List[str]]:
        """构建与snap2HTML兼容的目录数据结构"""
        # 获取所有文件记录
        files = self.db_manager.list_all_files()
        logger.info(f"从数据库获取了 {len(files)} 个文件记录")

        # 初始化数据结构
        dirs_dict = {}  # 临时字典，用于构建目录结构
        dirs_list = []  # 最终的目录列表
        dir_id_map = {}  # 目录路径到ID的映射

        # 初始化根目录
        root_path = self._normalize_path(self.config.local_root_path)
        dirs_dict[root_path] = {
            'id': 0,
            'files': [],
            'size': 0,
            'subdirs': set()
        }
        dir_id_map[root_path] = 0
        next_dir_id = 1

        # 处理所有文件
        for file in files:
            try:
                file_path = self._normalize_path(file['path'])
                dir_path = os.path.dirname(file_path)
                file_size = file['size']
                file_mtime = int(file['modified_time'])

                # 确保目录存在
                current_path = dir_path
                while current_path and current_path not in dirs_dict:
                    parent_path = os.path.dirname(current_path)
                    dirs_dict[current_path] = {
                        'id': next_dir_id,
                        'files': [],
                        'size': 0,
                        'subdirs': set()
                    }
                    dir_id_map[current_path] = next_dir_id
                    next_dir_id += 1

                    if parent_path in dirs_dict:
                        dirs_dict[parent_path]['subdirs'].add(dirs_dict[current_path]['id'])

                    current_path = parent_path

                # 添加文件信息
                dirs_dict[dir_path]['files'].append({
                    'name': os.path.basename(file_path),
                    'size': file_size,
                    'mtime': file_mtime
                })

                # 更新目录大小
                current_path = dir_path
                while current_path in dirs_dict:
                    dirs_dict[current_path]['size'] += file_size
                    current_path = os.path.dirname(current_path)

            except Exception as e:
                logger.error(f"处理文件记录时出错: {e}, 文件: {file}")
                continue

        # 转换为snap2HTML格式
        for dir_path, dir_info in dirs_dict.items():
            dir_data = []
            
            # 添加目录信息 (path*0*mtime)
            dir_data.append(f"{dir_path}*0*{int(time.time())}")
            
            # 添加文件信息
            for file in sorted(dir_info['files'], key=lambda x: x['name'].lower()):
                dir_data.append(f"{file['name']}*{file['size']}*{file['mtime']}")
            
            # 添加目录总大小
            dir_data.append(str(dir_info['size']))
            
            # 添加子目录ID列表
            dir_data.append('*'.join(map(str, sorted(dir_info['subdirs']))))
            
            # 将目录数据添加到正确的位置
            dirs_list.append(dir_data)

        return dirs_list

    def generate_snapshot(self, output_path: str) -> bool:
        """生成HTML快照"""
        try:
            logger.info("开始生成HTML快照...")
            start_time = time.time()

            # 构建目录数据
            dirs_data = self._build_directory_data()
            
            # 计算统计信息
            total_files = sum(len(d) - 3 for d in dirs_data)  # -3 for dir info, size and subdirs
            total_dirs = len(dirs_data)
            total_size = sum(int(d[-2]) for d in dirs_data)  # -2 index is the total size

            # 生成JavaScript数据
            js_data = []
            for dir_data in dirs_data:
                js_data.append(f"D.p({json.dumps(dir_data)})")

            # 使用模板生成HTML
            template = self.jinja_env.get_template('snapshot_template.html')
            html_content = template.render(
                directory_data='\n'.join(js_data),
                total_files=total_files,
                total_dirs=total_dirs,
                total_size=total_size,
                generated_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            )

            # 确保输出目录存在
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # 写入文件
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html_content)

            elapsed_time = time.time() - start_time
            logger.info(f"HTML快照生成完成:")
            logger.info(f"- 处理的文件数: {total_files}")
            logger.info(f"- 处理的目录数: {total_dirs}")
            logger.info(f"- 总大小: {self._format_size(total_size)}")
            logger.info(f"- 生成时间: {elapsed_time:.2f} 秒")
            logger.info(f"- 平均处理速度: {total_files/elapsed_time:.1f} 文件/秒")
            logger.info(f"- 保存位置: {output_path}")
            
            return True

        except Exception as e:
            logger.error(f"生成HTML快照失败: {e}")
            return False

    def export_html(self, output_path: str) -> bool:
        """导出HTML快照（generate_snapshot的别名）"""
        return self.generate_snapshot(output_path)

    def export_json(self, output_path: str) -> bool:
        """导出JSON格式的快照"""
        try:
            logger.info("开始生成JSON快照...")
            start_time = time.time()

            # 使用相同的数据结构
            dirs_data = self._build_directory_data()

            # 转换为JSON格式
            data = {
                'generated_at': datetime.now().isoformat(),
                'dirs': dirs_data
            }

            # 确保输出目录存在
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # 保存JSON文件
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            elapsed_time = time.time() - start_time
            logger.info(f"JSON快照生成完成:")
            logger.info(f"- 生成时间: {elapsed_time:.2f} 秒")
            logger.info(f"- 保存位置: {output_path}")

            return True

        except Exception as e:
            logger.error(f"生成JSON快照失败: {e}")
            return False 