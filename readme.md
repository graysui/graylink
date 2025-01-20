# GrayLink

<div align="center">
    <h3>🚀 专业的文件监控和软链接管理系统</h3>
    <p>为无桌面环境的 Linux 系统打造的智能媒体文件管理解决方案</p>
</div>

## 🌟 特性

### 📂 文件监控
- 🔄 实时监控本地文件系统变化
- ☁️ 定期检查 Google Drive 文件更新
- 📌 支持多个挂载点同时监控
- 🎯 智能文件过滤（按扩展名和排除规则）

### 🔗 软链接管理
- ⚡ 自动创建和维护软链接
- 🧹 定期清理失效的软链接
- 📁 支持自定义软链接目标目录

### 📺 Emby 集成
- 📨 文件变更实时通知
- 🔄 自动刷新媒体库
- 🎬 智能识别媒体类型

### 📊 快照功能
- ⏰ 每天早上 8 点自动生成目录快照
- 🌐 支持 HTML 和 JSON 格式导出
- 🔍 可搜索和排序的 Web 界面
- 📈 完整的文件统计信息

## 💻 系统要求

- Python 3.8+
- Linux 系统（推荐 Ubuntu 20.04+）
- 足够的磁盘空间用于软链接
- （可选）Google Drive 挂载
- （可选）Emby 媒体服务器

## 🚀 快速开始

### 📥 安装

1. 克隆仓库：
```bash
git clone https://github.com/graysui/graylink.git
cd graylink
```

2. 运行安装脚本：
```bash
chmod +x setup.sh
./setup.sh
```

安装脚本会自动完成以下操作：
- ✅ 检查Python版本
- 📁 创建必要的目录结构
- 🐍 设置Python虚拟环境
- 📦 安装所需依赖
- ⚙️ 创建配置文件模板

### ⚙️ 配置

编辑 `config.yaml` 文件，设置以下参数：

```yaml
# 数据库设置
db_path: data/graylink.db

# 监控设置
mount_points:
  - /path/to/local/files
  - /path/to/gdrive/mount

# 文件过滤
file_patterns:
  - "*.mp4"
  - "*.mkv"
exclude_patterns:
  - "*.!qB"
  - ".recycle"

# 软链接设置
symlink_base: /path/to/media/library

# Emby设置
emby_host: http://localhost:8096
emby_api_key: your_api_key

# 日志设置
log_level: INFO
log_file: logs/graylink.log
```

### 🎮 使用方法

1. 启动服务：
```bash
./start.sh
```

2. 命令行选项：
```bash
./start.sh --help              # 显示帮助信息
./start.sh --full-scan        # 执行完整扫描
./start.sh --export-html path # 导出HTML快照
./start.sh --export-json path # 导出JSON快照
```

3. 交互式菜单功能：
   - 🚀 启动服务
   - 🔍 执行完整扫描
   - 📄 导出HTML快照
   - 📊 导出JSON快照
   - 🔧 修改日志级别
   - ❓ 查看帮助

## 📊 监控和日志

### 📝 日志系统
- 📄 日志文件：`logs/graylink.log`
- 🎨 彩色控制台输出
- 📊 详细的操作记录
- ⚠️ 错误追踪和警告

### 📸 快照系统
- 📂 存储位置：`snapshots` 目录
- 🌐 美观的HTML界面
- 🔍 强大的搜索功能
- 📊 JSON格式数据分析

## ❗ 故障排除

1. **日志检查**
   - 查看 `logs/graylink.log`
   - 检查错误信息
   - 分析警告内容

2. **权限问题**
   - 确保目录可读写
   - 检查软链接权限
   - 验证配置文件权限

3. **连接问题**
   - 测试Google Drive连接
   - 验证Emby服务器状态
   - 检查网络连接

4. **文件监控**
   - 验证挂载点状态
   - 检查文件过滤规则
   - 测试文件系统权限

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！我们期待您的贡献。

## 📄 许可证

本项目采用 MIT 许可证。

---

<div align="center">
    <p>Made with ❤️ by GrayLink Team</p>
</div>