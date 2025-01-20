import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Any
from utils.logging_utils import logger

class DatabaseManager:
    def __init__(self, db_path: str):
        """
        初始化数据库管理器
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        self._init_db()
    
    def _get_connection(self):
        """
        获取数据库连接
        
        Returns:
            sqlite3.Connection: 数据库连接对象
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # 使用字典形式返回结果
            return conn
        except sqlite3.Error as e:
            logger.error(f"连接数据库失败: {e}")
            raise
    
    def _init_db(self) -> None:
        """初始化数据库"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 创建文件表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT UNIQUE NOT NULL,
                    size INTEGER NOT NULL,
                    modified_time TEXT NOT NULL,
                    hash TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            
            # 创建软链接表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS symlinks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_path TEXT NOT NULL,
                    link_path TEXT UNIQUE NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            
            # 创建扫描状态表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scan_status (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT UNIQUE NOT NULL,
                    status TEXT NOT NULL,  -- 'pending', 'scanning', 'completed', 'failed'
                    start_time TEXT,
                    end_time TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            
            conn.commit()
            logger.info("数据库初始化成功")
    
    def update_scan_status(self, path: str, status: str, error: str = None) -> None:
        """
        更新目录扫描状态
        
        Args:
            path: 目录路径
            status: 状态 ('pending', 'scanning', 'completed', 'failed')
            error: 错误信息
        """
        now = datetime.now().isoformat()
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO scan_status (path, status, error, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(path) DO UPDATE SET
                    status = ?,
                    error = ?,
                    updated_at = ?
            """, (path, status, error, now, now, status, error, now))
            
            conn.commit()
    
    def get_scan_status(self, path: str) -> Dict[str, Any]:
        """
        获取目录扫描状态
        
        Args:
            path: 目录路径
            
        Returns:
            Dict[str, Any]: 扫描状态信息
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT path, status, error, start_time, end_time, created_at, updated_at
                FROM scan_status
                WHERE path = ?
            """, (path,))
            
            row = cursor.fetchone()
            if row:
                return {
                    'path': row[0],
                    'status': row[1],
                    'error': row[2],
                    'start_time': row[3],
                    'end_time': row[4],
                    'created_at': row[5],
                    'updated_at': row[6]
                }
            return None
    
    def get_incomplete_scans(self) -> List[Dict[str, Any]]:
        """
        获取所有未完成的扫描
        
        Returns:
            List[Dict[str, Any]]: 未完成的扫描列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT path, status, error, start_time, end_time, created_at, updated_at
                FROM scan_status
                WHERE status IN ('pending', 'scanning', 'failed')
            """)
            
            return [{
                'path': row[0],
                'status': row[1],
                'error': row[2],
                'start_time': row[3],
                'end_time': row[4],
                'created_at': row[5],
                'updated_at': row[6]
            } for row in cursor.fetchall()]
    
    def add_file(self, path: str, size: int, modified_time: float, file_hash: Optional[str] = None) -> bool:
        """
        添加或更新文件信息
        
        Args:
            path: 文件路径
            size: 文件大小
            modified_time: 修改时间（Unix时间戳）
            file_hash: 文件哈希值（可选）
            
        Returns:
            bool: 操作是否成功
        """
        try:
            now = datetime.now().isoformat()
            with self._get_connection() as conn:
                cursor = conn.cursor()
                # 将时间戳转换为datetime对象
                dt = datetime.fromtimestamp(modified_time)
                cursor.execute("""
                    INSERT OR REPLACE INTO files 
                    (path, size, modified_time, hash, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (path, size, dt.isoformat(), file_hash, now, now))
                conn.commit()
                return True
        except sqlite3.Error as e:
            logger.error(f"添加文件记录失败 {path}: {e}")
            return False
    
    def add_symlink(self, source_path: str, link_path: str) -> bool:
        """
        添加软链接映射
        
        Args:
            source_path: 源文件路径
            link_path: 软链接路径
            
        Returns:
            bool: 操作是否成功
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                INSERT OR REPLACE INTO symlinks (source_path, link_path)
                VALUES (?, ?)
                ''', (source_path, link_path))
                conn.commit()
                return True
        except sqlite3.Error as e:
            logger.error(f"添加软链接记录失败 {source_path} -> {link_path}: {e}")
            return False
    
    def get_file_info(self, path: str) -> Optional[Dict]:
        """
        获取文件信息
        
        Args:
            path: 文件路径
            
        Returns:
            Dict: 文件信息字典，如果不存在返回None
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                SELECT path, size, modified_time, hash, created_at, updated_at
                FROM files WHERE path = ?
                ''', (path,))
                row = cursor.fetchone()
                
                if row:
                    return {
                        'path': row[0],
                        'size': row[1],
                        'modified_time': datetime.fromisoformat(row[2]),
                        'hash': row[3],
                        'created_at': datetime.fromisoformat(row[4]),
                        'updated_at': datetime.fromisoformat(row[5])
                    }
                return None
        except sqlite3.Error as e:
            logger.error(f"获取文件信息失败 {path}: {e}")
            return None
    
    def get_symlink_info(self, link_path: str) -> Optional[Dict]:
        """
        获取软链接信息
        
        Args:
            link_path: 软链接路径
            
        Returns:
            Dict: 软链接信息字典，如果不存在返回None
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                SELECT source_path, link_path, created_at
                FROM symlinks WHERE link_path = ?
                ''', (link_path,))
                row = cursor.fetchone()
                
                if row:
                    return {
                        'source_path': row[0],
                        'link_path': row[1],
                        'created_at': datetime.fromisoformat(row[2])
                    }
                return None
        except sqlite3.Error as e:
            logger.error(f"获取软链接信息失败 {link_path}: {e}")
            return None
    
    def list_modified_files(self, since: datetime) -> List[Dict]:
        """
        获取指定时间后修改的文件列表
        
        Args:
            since: 起始时间
            
        Returns:
            List[Dict]: 文件信息列表
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                SELECT path, size, modified_time, hash, created_at, updated_at
                FROM files WHERE modified_time > ?
                ''', (since.isoformat(),))
                
                return [{
                    'path': row[0],
                    'size': row[1],
                    'modified_time': datetime.fromisoformat(row[2]),
                    'hash': row[3],
                    'created_at': datetime.fromisoformat(row[4]),
                    'updated_at': datetime.fromisoformat(row[5])
                } for row in cursor.fetchall()]
        except sqlite3.Error as e:
            logger.error(f"获取修改文件列表失败: {e}")
            return []
    
    def remove_file(self, path: str) -> bool:
        """
        删除文件记录
        
        Args:
            path: 文件路径
            
        Returns:
            bool: 是否成功
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM files WHERE path = ?",
                    (path,)
                )
                return cursor.rowcount > 0
                
        except Exception as e:
            logger.error(f"删除文件记录失败 {path}: {e}")
            return False
    
    def remove_symlink(self, link_path: str) -> bool:
        """
        删除软链接记录
        
        Args:
            link_path: 软链接路径
            
        Returns:
            bool: 操作是否成功
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM symlinks WHERE link_path = ?', (link_path,))
                conn.commit()
                return True
        except sqlite3.Error as e:
            logger.error(f"删除软链接记录失败 {link_path}: {e}")
            return False
    
    def cleanup(self) -> Tuple[int, int]:
        """
        清理不存在的文件和软链接记录
        
        Returns:
            Tuple[int, int]: (清理的文件数, 清理的软链接数)
        """
        files_cleaned = 0
        symlinks_cleaned = 0
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 获取所有文件记录
                cursor.execute('SELECT path FROM files')
                for (path,) in cursor.fetchall():
                    if not os.path.exists(path):
                        if self.remove_file(path):
                            files_cleaned += 1
                
                # 获取所有软链接记录
                cursor.execute('SELECT link_path FROM symlinks')
                for (link_path,) in cursor.fetchall():
                    if not os.path.exists(link_path):
                        if self.remove_symlink(link_path):
                            symlinks_cleaned += 1
                
                logger.info(f"清理完成: 删除了 {files_cleaned} 个文件记录和 {symlinks_cleaned} 个软链接记录")
                return files_cleaned, symlinks_cleaned
                
        except sqlite3.Error as e:
            logger.error(f"清理数据库失败: {e}")
            return 0, 0
    
    def list_all_files(self) -> List[Dict[str, Any]]:
        """
        获取数据库中的所有文件记录
        
        Returns:
            List[Dict[str, Any]]: 文件信息列表，每个文件包含path、size和mtime
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT path, size, mtime
                    FROM files
                    ORDER BY path
                """)
                rows = cursor.fetchall()
                
                return [
                    {
                        'path': row[0],
                        'size': row[1],
                        'mtime': row[2]
                    }
                    for row in rows
                ]
                
        except Exception as e:
            logger.error(f"获取所有文件记录失败: {e}")
            return []
    
    def get_symlinks_by_source(self, source_path: str) -> List[str]:
        """
        获取源文件对应的所有软链接
        
        Args:
            source_path: 源文件路径
            
        Returns:
            List[str]: 软链接路径列表
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT link_path FROM symlinks WHERE source_path = ?",
                    (source_path,)
                )
                return [row[0] for row in cursor.fetchall()]
                
        except Exception as e:
            logger.error(f"查询软链接失败 {source_path}: {e}")
            return [] 