import os
import json
import time
import pytz
import threading
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from jinja2 import Environment, FileSystemLoader
from utils.logging_utils import get_logger
from db_manager import DatabaseManager
from config import Config

logger = get_logger(__name__)

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
        self.running = False
        self.export_thread = None
        
        # 初始化Jinja2环境
        self.template_env = Environment(
            loader=FileSystemLoader('templates'),
            autoescape=True
        )
        
        # 注册自定义过滤器
        self.template_env.filters['format_size'] = self._format_size
        self.template_env.filters['format_time'] = self._format_time
    
    def _get_next_run_time(self) -> float:
        """计算下一次运行的时间
        
        Returns:
            float: 下一次运行的Unix时间戳
        """
        # 获取北京时间
        beijing_tz = pytz.timezone('Asia/Shanghai')
        now = datetime.now(beijing_tz)
        
        # 设置目标时间为今天或明天的8:00
        target = now.replace(hour=8, minute=0, second=0, microsecond=0)
        if now >= target:
            target += timedelta(days=1)
        
        return target.timestamp()
    
    def _schedule_export(self):
        """定时导出任务"""
        while self.running:
            try:
                # 计算下一次运行时间
                next_run = self._get_next_run_time()
                now = time.time()
                
                # 等待到指定时间
                sleep_time = next_run - now
                if sleep_time > 0:
                    logger.info(f"下次导出将在 {datetime.fromtimestamp(next_run)} 进行")
                    time.sleep(sleep_time)
                
                # 执行导出
                if self.running:  # 再次检查，防止在睡眠期间停止
                    logger.info("开始执行定时导出...")
                    
                    # 导出HTML快照
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    html_path = os.path.join('snapshots', f'snapshot_{timestamp}.html')
                    self.export_html(html_path)
                    
                    # 导出JSON快照
                    json_path = os.path.join('snapshots', f'snapshot_{timestamp}.json')
                    self.export_json(json_path)
                    
                    logger.info("定时导出完成")
            
            except Exception as e:
                logger.error(f"定时导出失败: {e}")
                # 出错后等待5分钟再重试
                time.sleep(300)
    
    def start_scheduler(self):
        """启动定时导出"""
        if not self.running:
            self.running = True
            
            # 确保快照目录存在
            os.makedirs('snapshots', exist_ok=True)
            
            # 启动定时器线程
            self.export_thread = threading.Thread(
                target=self._schedule_export,
                name="SnapshotExporter",
                daemon=True
            )
            self.export_thread.start()
            
            logger.info("定时导出服务已启动")
    
    def stop_scheduler(self):
        """停止定时导出"""
        if self.running:
            self.running = False
            if self.export_thread:
                self.export_thread.join()
            logger.info("定时导出服务已停止")
    
    def _build_directory_tree(self) -> Dict[str, Any]:
        """
        从数据库构建目录树
        
        Returns:
            Dict[str, Any]: 目录树数据
        """
        # 获取所有文件记录
        files = self.db_manager.list_all_files()
        
        # 初始化根节点
        root: Dict[str, Any] = {
            'name': 'root',
            'type': 'directory',
            'children': {}
        }
        
        # 构建目录树
        for file in files:
            path = file['path']
            size = file['size']
            mtime = file['mtime']
            
            # 分割路径
            parts = path.split(os.sep)
            current = root
            
            # 创建目录结构
            for i, part in enumerate(parts[:-1]):
                if part not in current['children']:
                    current['children'][part] = {
                        'name': part,
                        'type': 'directory',
                        'children': {}
                    }
                current = current['children'][part]
            
            # 添加文件节点
            filename = parts[-1]
            current['children'][filename] = {
                'name': filename,
                'type': 'file',
                'size': size,
                'mtime': mtime
            }
        
        return root
    
    def _convert_tree_to_list(self, node: Dict[str, Any], path: str = '') -> List[Dict[str, Any]]:
        """
        将树形结构转换为列表
        
        Args:
            node: 当前节点
            path: 当前路径
            
        Returns:
            List[Dict[str, Any]]: 文件和目录列表
        """
        result = []
        
        # 处理目录
        if node['type'] == 'directory':
            # 添加目录本身
            if path:  # 跳过根目录
                result.append({
                    'name': node['name'],
                    'type': 'directory',
                    'path': path,
                    'size': 0,
                    'mtime': 0
                })
            
            # 处理子节点
            for child in sorted(node['children'].values(), key=lambda x: x['name'].lower()):
                child_path = os.path.join(path, child['name']) if path else child['name']
                result.extend(self._convert_tree_to_list(child, child_path))
        
        # 处理文件
        else:
            result.append({
                'name': node['name'],
                'type': 'file',
                'path': path,
                'size': node['size'],
                'mtime': node['mtime']
            })
        
        return result
    
    def _format_size(self, size: int) -> str:
        """
        格式化文件大小
        
        Args:
            size: 文件大小（字节）
            
        Returns:
            str: 格式化后的大小
        """
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"
    
    def _format_time(self, timestamp: float) -> str:
        """
        格式化时间戳
        
        Args:
            timestamp: Unix时间戳
            
        Returns:
            str: 格式化后的时间
        """
        return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
    
    def export_html(self, output_path: str, title: Optional[str] = None) -> bool:
        """
        导出HTML快照
        
        Args:
            output_path: 输出文件路径
            title: 页面标题（可选）
            
        Returns:
            bool: 是否成功
        """
        try:
            logger.info("开始生成HTML快照...")
            start_time = time.time()
            
            # 构建目录树
            tree = self._build_directory_tree()
            
            # 转换为列表格式
            items = self._convert_tree_to_list(tree)
            
            # 计算统计信息
            total_files = sum(1 for item in items if item['type'] == 'file')
            total_dirs = sum(1 for item in items if item['type'] == 'directory')
            total_size = sum(item['size'] for item in items if item['type'] == 'file')
            
            # 准备模板数据
            template_data = {
                'title': title or '文件目录快照',
                'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'items': items,
                'stats': {
                    'total_files': total_files,
                    'total_dirs': total_dirs,
                    'total_size': self._format_size(total_size)
                },
                'format_size': self._format_size,
                'format_time': self._format_time
            }
            
            # 渲染模板
            template = self.template_env.get_template('snapshot.html')
            html = template.render(**template_data)
            
            # 确保输出目录存在
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # 保存HTML文件
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html)
            
            elapsed_time = time.time() - start_time
            logger.info(f"HTML快照生成完成:")
            logger.info(f"- 文件数: {total_files}")
            logger.info(f"- 目录数: {total_dirs}")
            logger.info(f"- 总大小: {self._format_size(total_size)}")
            logger.info(f"- 生成时间: {elapsed_time:.2f} 秒")
            logger.info(f"- 保存位置: {output_path}")
            
            return True
            
        except Exception as e:
            logger.error(f"生成HTML快照失败: {e}")
            return False
    
    def export_json(self, output_path: str) -> bool:
        """
        导出JSON快照
        
        Args:
            output_path: 输出文件路径
            
        Returns:
            bool: 是否成功
        """
        try:
            logger.info("开始生成JSON快照...")
            start_time = time.time()
            
            # 构建目录树
            tree = self._build_directory_tree()
            
            # 添加元数据
            data = {
                'generated_at': datetime.now().isoformat(),
                'tree': tree
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