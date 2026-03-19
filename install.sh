#!/data/data/com.termux/files/usr/bin/bash
set -e

BASE_DIR="$HOME/sms_tool"
BASE_URL="https://raw.githubusercontent.com/edmunddyu-netizen/sms-deploy/main"

echo "第1步：更新软件包列表"
pkg update -y

echo "第2步：安装需要的工具"
pkg install -y python termux-api curl nano

echo "第3步：创建程序目录"
mkdir -p "$BASE_DIR"

echo "第4步：下载程序文件"
curl -fsSL "$BASE_URL/sms_tool.py" -o "$BASE_DIR/sms_tool.py"
curl -fsSL "$BASE_URL/run.sh" -o "$BASE_DIR/run.sh"

echo "第5步：赋予启动脚本权限"
chmod +x "$BASE_DIR/run.sh"

echo "第6步：创建快捷命令 sms-tool"
cat > "$PREFIX/bin/sms-tool" <<'EOF'
#!/data/data/com.termux/files/usr/bin/bash
bash "$HOME/sms_tool/run.sh"
EOF

chmod +x "$PREFIX/bin/sms-tool"

echo ""
echo "安装完成"
echo "现在输入：sms-tool"
