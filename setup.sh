#!/bin/bash

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 检查Python版本
check_python() {
    echo -e "${BLUE}检查Python版本...${NC}"
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}错误: 未找到Python3${NC}"
        echo "请先安装Python 3.8或更高版本"
        exit 1
    fi
    
    version=$(python3 -V 2>&1 | awk '{print $2}')
    echo -e "${GREEN}找到Python版本: $version${NC}"
}

# 创建目录结构
create_directories() {
    echo -e "${BLUE}创建目录结构...${NC}"
    
    # 定义需要创建的目录
    directories=(
        "data"           # 数据库目录
        "logs"           # 日志目录
        "snapshots"      # 快照目录
        "templates"      # 模板目录
        "data/media"     # 媒体文件目录
        "data/cache"     # 缓存目录
        "logs/archive"   # 日志归档目录
        "snapshots/html" # HTML快照目录
        "snapshots/json" # JSON快照目录
    )
    
    # 创建目录
    for dir in "${directories[@]}"; do
        if [ ! -d "$dir" ]; then
            mkdir -p "$dir"
            echo -e "${GREEN}创建目录: $dir${NC}"
        else
            echo -e "${YELLOW}目录已存在: $dir${NC}"
        fi
    done
    
    # 设置目录权限
    echo -e "${BLUE}设置目录权限...${NC}"
    find . -type d -exec chmod 755 {} \;
    
    echo -e "${GREEN}目录结构创建完成${NC}"
    
    # 显示目录树
    echo -e "${BLUE}目录结构:${NC}"
    if command -v tree &> /dev/null; then
        tree -L 2
    else
        ls -R | grep ":$" | sed -e 's/:$//' -e 's/[^-][^\/]*\//  /g' -e 's/^/  /' -e 's/-/|/'
    fi
}

# 创建虚拟环境
create_venv() {
    echo -e "${BLUE}创建Python虚拟环境...${NC}"
    if [ -d "venv" ]; then
        echo -e "${YELLOW}虚拟环境已存在，跳过创建${NC}"
        return 0
    fi
    
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo -e "${RED}创建虚拟环境失败${NC}"
        exit 1
    fi
    echo -e "${GREEN}虚拟环境创建成功${NC}"
}

# 激活虚拟环境
activate_venv() {
    echo -e "${BLUE}激活虚拟环境...${NC}"
    source venv/bin/activate
    if [ $? -ne 0 ]; then
        echo -e "${RED}激活虚拟环境失败${NC}"
        exit 1
    fi
    echo -e "${GREEN}虚拟环境已激活${NC}"
}

# 安装依赖
install_dependencies() {
    echo -e "${BLUE}安装Python依赖...${NC}"
    pip install --upgrade pip
    pip install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo -e "${RED}安装依赖失败${NC}"
        exit 1
    fi
    echo -e "${GREEN}依赖安装完成${NC}"
}

# 配置文件处理
setup_config() {
    echo -e "${BLUE}设置配置文件...${NC}"
    if [ ! -f "config.yaml" ]; then
        if [ -f "config.yaml.template" ]; then
            cp config.yaml.template config.yaml
            echo -e "${YELLOW}已创建配置文件，请编辑 config.yaml 设置你的配置${NC}"
        else
            echo -e "${RED}错误: 未找到配置模板文件${NC}"
            exit 1
        fi
    else
        echo -e "${YELLOW}配置文件已存在，跳过创建${NC}"
    fi
}

# 设置权限
setup_permissions() {
    echo -e "${BLUE}设置文件权限...${NC}"
    chmod +x start.sh
    chmod 644 config.yaml
    chmod 644 requirements.txt
    chmod -R 755 *.py
    echo -e "${GREEN}权限设置完成${NC}"
}

# 主函数
main() {
    echo -e "${BLUE}=== GrayLink 安装程序 ===${NC}"
    echo
    
    # 检查是否为root用户
    if [ "$EUID" -eq 0 ]; then
        echo -e "${RED}警告: 不建议以root用户运行此安装程序${NC}"
        read -p "是否继续? [y/N] " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
    
    # 执行安装步骤
    check_python
    create_directories
    create_venv
    activate_venv
    install_dependencies
    setup_config
    setup_permissions
    
    echo
    echo -e "${GREEN}=== 安装完成 ===${NC}"
    
    # 询问是否立即启动服务
    echo -e "${YELLOW}是否立即启动 GrayLink 服务？[Y/n]${NC}"
    read -r response
    if [[ "$response" =~ ^([nN][oO]|[nN])$ ]]; then
        echo -e "${BLUE}您可以稍后通过以下命令启动服务：${NC}"
        echo "./start.sh"
    else
        echo -e "${BLUE}正在启动 GrayLink 服务...${NC}"
        ./start.sh
    fi
    
    echo
    echo -e "${BLUE}如需帮助，请查看 README.md 文件${NC}"
}

# 启动安装
main 