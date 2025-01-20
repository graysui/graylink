#!/bin/bash

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 检查Python虚拟环境
check_venv() {
    if [ ! -d "venv" ]; then
        echo -e "${RED}错误: 未找到Python虚拟环境${NC}"
        echo "请先运行: python -m venv venv"
        exit 1
    fi
}

# 检查配置文件
check_config() {
    if [ ! -f "config.yaml" ]; then
        echo -e "${RED}错误: 未找到配置文件 config.yaml${NC}"
        echo "请先复制 config.yaml.template 到 config.yaml 并进行配置"
        exit 1
    fi
}

# 激活虚拟环境
activate_venv() {
    source venv/bin/activate
}

# 显示菜单
show_menu() {
    clear
    echo -e "${BLUE}=== GrayLink 文件监控和软链接管理系统 ===${NC}"
    echo
    echo -e "${GREEN}1.${NC} 启动服务"
    echo -e "${GREEN}2.${NC} 执行完整扫描"
    echo -e "${GREEN}3.${NC} 导出HTML快照"
    echo -e "${GREEN}4.${NC} 导出JSON快照"
    echo -e "${GREEN}5.${NC} 修改日志级别"
    echo -e "${GREEN}6.${NC} 查看帮助"
    echo -e "${GREEN}0.${NC} 退出"
    echo
    echo -e "${YELLOW}请选择操作 [0-6]:${NC} "
}

# 设置日志级别
set_log_level() {
    echo -e "${BLUE}选择日志级别:${NC}"
    echo "1. DEBUG"
    echo "2. INFO"
    echo "3. WARNING"
    echo "4. ERROR"
    echo "5. CRITICAL"
    echo
    read -p "请选择 [1-5]: " choice
    
    case $choice in
        1) level="DEBUG" ;;
        2) level="INFO" ;;
        3) level="WARNING" ;;
        4) level="ERROR" ;;
        5) level="CRITICAL" ;;
        *) level="INFO" ;;
    esac
    
    echo -e "${GREEN}日志级别设置为: $level${NC}"
    return 0
}

# 导出快照
export_snapshot() {
    local type=$1
    echo -e "${BLUE}请输入导出路径:${NC}"
    read -p "路径: " path
    
    if [ -z "$path" ]; then
        echo -e "${RED}错误: 路径不能为空${NC}"
        return 1
    fi
    
    if [ "$type" = "html" ]; then
        python -c "
from main import GrayLink
app = GrayLink('config.yaml')
app.export_html('$path')
"
    else
        python -c "
from main import GrayLink
app = GrayLink('config.yaml')
app.export_json('$path')
"
    fi
}

# 运行服务
run_service() {
    local cmd="
from main import GrayLink
import logging

logging.basicConfig(
    level=logging.${level:-INFO},
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/graylink.log'),
        logging.StreamHandler()
    ]
)

app = GrayLink('config.yaml')
"
    
    if [ "$1" = "scan" ]; then
        cmd+="
app._full_scan()
"
    else
        cmd+="
app.run()
"
    fi
    
    python -c "$cmd"
}

# 显示帮助信息
show_help() {
    echo -e "${BLUE}GrayLink 使用帮助${NC}"
    echo
    echo "命令行参数:"
    echo "  --config/-c     : 指定配置文件路径"
    echo "  --full-scan     : 执行完整扫描"
    echo "  --export-html   : 导出HTML快照"
    echo "  --export-json   : 导出JSON快照"
    echo "  --log-level     : 设置日志级别"
    echo
    echo "示例:"
    echo "  ./start.sh -c custom_config.yaml"
    echo "  ./start.sh --full-scan"
    echo "  ./start.sh --export-html snapshot.html"
    echo
    read -p "按回车键继续..."
}

# 处理命令行参数
handle_args() {
    local config="config.yaml"
    local log_level="INFO"
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            -c|--config)
                config="$2"
                shift 2
                ;;
            --full-scan)
                python -c "
from main import GrayLink
import logging
logging.basicConfig(level=logging.${log_level})
app = GrayLink('${config}')
app._full_scan()
"
                exit $?
                ;;
            --export-html)
                python -c "
from main import GrayLink
app = GrayLink('${config}')
app.export_html('$2')
"
                exit $?
                ;;
            --export-json)
                python -c "
from main import GrayLink
app = GrayLink('${config}')
app.export_json('$2')
"
                exit $?
                ;;
            --log-level)
                log_level="$2"
                shift 2
                ;;
            *)
                echo -e "${RED}错误: 未知参数 $1${NC}"
                exit 1
                ;;
        esac
    done
}

# 主循环
main() {
    # 检查环境
    check_venv
    check_config
    activate_venv
    
    # 创建日志目录
    mkdir -p logs
    
    # 处理命令行参数
    if [ $# -gt 0 ]; then
        handle_args "$@"
        exit $?
    fi
    
    # 交互式菜单
    while true; do
        show_menu
        read choice
        
        case $choice in
            0)
                echo -e "${GREEN}感谢使用 GrayLink!${NC}"
                exit 0
                ;;
            1)
                echo -e "${BLUE}正在启动服务...${NC}"
                run_service
                ;;
            2)
                echo -e "${BLUE}正在执行完整扫描...${NC}"
                run_service "scan"
                ;;
            3)
                export_snapshot "html"
                ;;
            4)
                export_snapshot "json"
                ;;
            5)
                set_log_level
                ;;
            6)
                show_help
                ;;
            *)
                echo -e "${RED}无效的选择${NC}"
                sleep 1
                ;;
        esac
    done
}

# 启动程序
main "$@" 