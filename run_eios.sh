#!/bin/sh
# #!/bin/sh：告诉系统使用 Shell 解释这个脚本
# 让一键程序从其他目录也能可靠启动：让它自己找到项目目录，再使用项目的虚拟环境运行一键程序

# 命令出错时停止脚本
set -e

# 找到当前脚本所在的项目目录
EIOS_PROJECT_DIR="$(CDPATH= cd "$(dirname "$0")" && pwd -P)"

# 切换到项目目录，确保程序读取正确的文件
cd "$EIOS_PROJECT_DIR"

# 使用项目虚拟环境运行一键程序，并传递日期参数
exec "$EIOS_PROJECT_DIR/.venv/bin/python" "$EIOS_PROJECT_DIR/run_and_save.py" "$@"