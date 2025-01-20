
// graylink
// 用于高性能文件监控的软链接管理系统

// 项目概述
- 项目名称: graylink
- 项目目标: 监控 Google Drive 目录变化，生成软链接，并通知 Emby 刷新媒体库
- 支持平台: Linux (ARM, AMD)
- 部署环境: 无桌面环境
- 挂载方式: 使用 rclone 将 Google Drive 挂载到本地目录

// 技术选型
- 编程语言: Python
- 依赖库:
 watchdog: 用于监控本地文件系统变化。
google-api-python-client: 用于调用 Google Drive Activity API。
requests 或 aiohttp: 用于发送 HTTP 请求通知 Emby。
sqlite3: 用于本地数据库管理。
logging: 用于日志记录。
typing: 用于类型注解，提高代码可读性。
- 操作系统: Linux (ARM, AMD)

// 项目结构
- 项目根目录: graylink
graylink/
├── gdrive_api.py       # Google Drive 监控
├── local_monitor.py    # 本地目录监控
├── symlink_manager.py  # 软链接管理
├── emby_notifier.py    # Emby 通知
├── db_manager.py       # 数据库管理
├── snapshot_generator.py # 快照生成
├── config.py           # 配置文件（API 密钥、路径等）
├── utils/              # 工具函数
│   ├── logging_utils.py
│   ├── file_utils.py
│   └── network_utils.py
└── README.md           # 项目文档

// 代码风格与最佳实践
- 遵循 PEP 8 代码风格
- 使用类型注解提高代码可读性
- 使用 logger 进行日志记录，记录级别为 INFO 和 ERROR
- 使用 配置文件 或环境变量管理敏感信息（如 API 密钥）。

### 1. Google Drive 监控 (`gdrive_api.py`)
- **功能**：通过 **Google Drive Activity API** 监控指定文件夹的文件变化。
- **实现方式**：
  1. **定时调用**：根据配置的 API 调用时间（默认 1 小时），定期调用 Google Drive Activity API，获取文件活动数据。
  2. **数据解析**：解析 API 返回的数据，提取文件路径、大小、修改时间等信息。
  3. **对比数据库**：将解析后的文件信息与数据库中的记录进行对比，找出新增或修改的文件。
  4. **更新数据库**：将新增或修改的文件信息添加到数据库中。
  5. **生成软链接**：生成软链接。

- **输入**：
  - Google Drive 文件夹 ID。
  - Google Drive API 密钥。
    参考rclone配置储存方式rclone.conf
    [MP]
    type = drive
    client_id = 460886178493-iosmlmtfplblq1lreaunqk337s5jdtbn.apps.googleusercontent.com
    client_secret = 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
    scope = drive
    token = {"access_token":"ya29.a0ARW5m772lyjvst5b3qJGM476E9HHNwgArGalw9XPuhGEc40E-JkxvfjeBJkN_eDcIUOG-3suLrYhYIaRZjX-xYhO5kJKM--3NoSFJ9HpJ21JW8Wye1lnU2z7NR6H3CmM-ywS1OkEas8vIQtyoo0HW_Lb3z8tooeIvBiApMDONgaCgYKAcYSARESFQHGX2MiLa_yajboUM7NAwo549u4BA0177","token_type":"Bearer","refresh_token":"1//0ed-RDfT-pyOICgYIARAAGA4SNwF-L9IrkpD4Rg1N50vVjdCcT19ToQf4wjAYWC1zZgN81OtZlHMeFUvuUDWx62HwxIdxdxqibyY","expiry":"2025-01-18T04:24:32.19743-05:00"}
    team_drive = 
  - API 调用时间（可配置，默认 1 小时）。
- **输出**：获取api返回数据，根据api官方文档分析数据，提取文件路径、大小、修改时间等信息。
  - 检测到文件变化时，触发以下操作：
    1. **对比数据库**：将检测到的文件与数据库中的记录进行对比，找出新增或修改的文件。
    2. **更新数据库**：将新增或修改的文件信息添加到数据库中。
    3. **生成软链接**：生成软链接。
- **参考文档**：[Google Drive Activity API 官方文档](https://developers.google.cn/drive/activity/v2?hl=zh-cn)

### 2. 本地目录监控 (`local_monitor.py`)
- **功能**：使用 `watchdog` 库和轮询机制监控本地目录的文件变化。
- **监控方式**：
  - **实时监控**：使用 `watchdog` 库监听文件系统事件（如创建、修改、删除）。
  - **轮询监控**：根据配置的轮询时间（默认 5 分钟），定期扫描目录，检测文件变化。
- **输入**：
  - 本地监控目录路径（rclone 挂载点）。
  - 轮询时间（可配置，默认 5 分钟）。
- **输出**：
  - 检测到文件变化时，触发以下操作：
    1. **对比数据库**：将检测到的文件与数据库中的记录进行对比，找出新增或修改的文件。
    2. **更新数据库**：将新增或修改的文件信息添加到数据库中。
    3. **生成软链接**：生成软链接。
- **优化措施**：
  - **增量扫描**：只扫描最近修改时间变化的目录。
  - **缓存机制**：在内存中缓存文件列表，减少 I/O 操作。
  - **并行处理**：使用多线程或异步 I/O 并行扫描多个二级分类目录。
- **参考实现**: [MoviePilot/monitor.py](https://github.com/jxxghp/MoviePilot/blob/app/monitor.py)

### 3. 软链接管理 (`symlink_manager.py`)
- **功能**：根据文件变化生成软链接，保持源文件目录结构。
- **输入**：源文件路径和目标软链接路径。
- **规则**：只对视频文件生成软连接（视频文件按照扩展名判断，扩展名要包含齐全所有视频扩展），路径中包含BDMV，此路径下任何文件都不进行操作
- **输出**：1.在目标路径生成软链接。
                   2. **通知 Emby**：刷新媒体库。
- **参考实现**: [MoviePilot-Plugins/filesoftlink](https://github.com/thsrite/MoviePilot-Plugins/blob/main/plugins.v2/filesoftlink/__init__.py)

### 4. Emby 通知 (`emby_notifier.py`)
- **功能**：通过 HTTP 请求通知 Emby 刷新媒体库。
- **输入**：Emby 服务器地址和 API 密钥。
- **输出**：发送刷新请求，并处理响应状态码。
- **参考实现**: [MoviePilot/emby.py](https://github.com/jxxghp/MoviePilot/blob/app/modules/emby/emby.py)

### 5. 数据库管理 (`db_manager.py`)
- **功能**：使用 SQLite 数据库记录文件目录结构。
- **输入**：文件路径、大小、修改时间等信息。
- **输出**：将文件信息存储到数据库中，并支持快照功能。
- **关键方法**：
  - `compare_files(current_files)`：将当前文件列表与数据库中的记录进行对比，返回新增或修改的文件。
  - `update_database(new_files)`：将新增或修改的文件信息添加到数据库中。

### 6. 快照生成 (`snapshot_generator.py`)
- **功能**：根据数据库生成文件目录的快照，并生成 HTML 页面。
- **输入**：数据库路径和模板目录。
- **输出**：生成 HTML 快照文件。
- **参考**：https://github.com/rlv-dan/Snap2HTML/tree/master/Snap2HTML

###7.首次运行全量扫描
 - **功能**：首次运行全量扫描，完善数据库，生成软连接
 - **输出**：参照开源项目Snap2HTML生成目录树，根据目录树完善数据库并生成软连接，目标文件存在的则跳过，生成软连接规则遵循软连接模块
 - **参考**：https://github.com/rlv-dan/Snap2HTML/tree/master/Snap2HTML
// 监控机制
- 同时使用以下三种监控方式：
  1. **本地目录监控**：
     - 使用 `watchdog` 库实时监听文件系统事件。
     - 使用轮询机制定期扫描目录，检测文件变化。
  2. **Google Drive Activity API 监控**：
     - 通过 Drive Activity API 监听 Google Drive 文件变化。
- 在任何一种监控方式检测到文件变化时，触发以下操作：
  1. **对比数据库**：将检测到的文件与数据库中的记录进行对比，找出新增或修改的文件。
  2. **更新数据库**：将新增或修改的文件信息添加到数据库中。
  3. **生成软链接**：生成软链接。
 - 生成软连接后通知emby刷新媒体库

// 错误处理与日志记录
- 使用 try-except 块捕获异常，并记录错误日志。
- 记录关键操作的日志，方便排查问题。
- 挂载点检查：定期检查 rclone 挂载点是否正常挂载，如果挂载点丢失，尝试重新挂载。
- 网络异常处理：增加重试机制（如重试 3 次），并记录网络异常日志。

// 性能优化
- 使用线程或异步编程提高监控效率。
- 优化数据库查询，减少 I/O 操作。
- 并行处理：使用多线程或异步 I/O 并行扫描多个二级分类目录。


# GrayLink 项目开发计划

## 一、项目准备阶段

### 2. 项目初始化
- [ ] 创建项目基础结构
- [ ] 配置依赖管理（requirements.txt）
- [ ] 设置日志系统
- [ ] 创建配置文件模板

## 二、核心功能开发阶段

### 1. 数据库模块（第1周）
- [ ] 设计数据库表结构
  - 文件信息表
  - 软链接映射表
  - 监控配置表
- [ ] 实现数据库管理类
  - CRUD 操作
  - 数据迁移
  - 备份恢复
- [ ] 编写单元测试

### 2. Google Drive 监控模块（第2周）
- [ ] 实现 Google Drive API 认证
- [ ] 开发文件变更监控
  - Activity API 集成
  - 变更事件处理
  - 数据同步逻辑
- [ ] 实现重试机制和错误处理
- [ ] 编写单元测试

### 3. 本地文件监控模块（第3周）
- [ ] 实现 watchdog 监控
  - 文件系统事件处理
  - 增量扫描逻辑
- [ ] 开发轮询监控
  - 定时扫描机制
  - 文件对比逻辑
- [ ] 实现并行处理优化
- [ ] 编写单元测试

### 4. 软链接管理模块（第4周）
- [ ] 实现软链接生成逻辑
  - 路径映射
  - 文件类型过滤
  - 目录结构维护
- [ ] 开发冲突处理机制
- [ ] 实现错误恢复
- [ ] 编写单元测试

### 5. Emby 通知模块（第4周）
- [ ] 实现 Emby API 集成
- [ ] 开发媒体库刷新逻辑
- [ ] 实现状态检查和重试
- [ ] 编写单元测试

### 6. 快照生成模块（第5周）
- [ ] 实现目录树生成
- [ ] 开发 HTML 模板
- [ ] 实现快照导出
- [ ] 编写单元测试

## 三、集成测试阶段（第6周）

### 1. 模块集成
- [ ] 整合所有模块
- [ ] 实现模块间通信
- [ ] 开发主程序流程

### 2. 系统测试
- [ ] 编写集成测试
- [ ] 性能测试
- [ ] 压力测试
- [ ] 异常场景测试

### 3. 问题修复
- [ ] 修复发现的 bug
- [ ] 优化性能问题
- [ ] 完善错误处理

## 四、文档和部署阶段（第7周）

### 1. 文档编写
- [ ] 完善代码注释
- [ ] 编写技术文档
- [ ] 编写用户手册
- [ ] 编写部署文档

### 2. 部署准备
- [ ] 制作部署脚本，通过github actions部署docker镜像，并发布到docker hub
- [ ] 准备 Docker 镜像
- [ ] 编写部署指南

### 3. 发布准备
- [ ] 版本号管理
- [ ] 更新日志
- [ ] 发布清单

## 五、维护和优化阶段（持续）

### 1. 性能优化
- [ ] 监控系统性能
- [ ] 优化数据库查询
- [ ] 优化文件处理
- [ ] 内存使用优化

### 2. 功能扩展
- [ ] 收集用户反馈
- [ ] 规划新功能
- [ ] 迭代开发

### 3. 问题修复
- [ ] 监控系统运行
- [ ] 处理用户反馈
- [ ] 修复发现的问题

## 关键技术点

1. **文件监控机制**
   - Watchdog 实时监控
   - 定时轮询扫描
   - Google Drive API 监控
   - 三重监控协同工作

2. **数据同步策略**
   - 增量更新
   - 全量对比
   - 冲突处理
   - 数据一致性

3. **性能优化方案**
   - 多线程处理
   - 异步 IO
   - 数据库索引
   - 缓存机制

4. **错误处理机制**
   - 自动重试
   - 状态恢复
   - 日志记录
   - 异常通知


## 质量保证

1. **代码质量**
   - 遵循 PEP 8 规范
   - 完整的单元测试
   - 代码审查机制
   - 持续集成/部署

2. **测试覆盖**
   - 单元测试 > 80%
   - 集成测试场景完整
   - 性能测试达标
   - 用户场景测试

3. **文档完整性**
   - 详细的接口文档
   - 完整的部署文档
   - 清晰的用户指南
   - 运维手册

## 后续规划

1. **功能扩展**
   - 支持更多云存储服务
   - 添加 Web 管理界面
   - 支持更多媒体服务器
   - 优化监控机制

2. **性能提升**
   - 优化文件处理效率
   - 提升监控响应速度
   - 降低资源占用
   - 提高并发处理能力

3. **用户体验**
   - 简化配置流程
   - 优化错误提示
   - 添加可视化监控
   - 完善使用文档 

