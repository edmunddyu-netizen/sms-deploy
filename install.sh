#!/data/data/com.termux/files/usr/bin/bash
set -e

BASE_DIR="/storage/emulated/0/sms_tool"
BASE_URL="https://raw.githubusercontent.com/edmunddyu-netizen/sms-deploy/main"
APP_DIR="$HOME/sms_tool"

echo "第0步：请先确保你已经执行过 termux-setup-storage 并授予存储权限"

echo "第1步：更新软件包列表"
pkg update -y

echo "第2步：安装需要的工具"
pkg install -y python termux-api curl nano

echo "第3步：创建程序目录"
mkdir -p "$APP_DIR"
mkdir -p "$BASE_DIR"

echo "第4步：下载主程序"
curl -fsSL "$BASE_URL/sms_tool.py" -o "$APP_DIR/sms_tool.py"

echo "第5步：创建启动脚本"
cat > "$APP_DIR/run.sh" <<'EOF'
#!/data/data/com.termux/files/usr/bin/bash
cd "$HOME/sms_tool"
python sms_tool.py
EOF

cat > "$APP_DIR/123.sh" <<'EOF'
#!/data/data/com.termux/files/usr/bin/bash
cd "$HOME/sms_tool"
python sms_tool.py round1
EOF

cat > "$APP_DIR/yzp.sh" <<'EOF'
#!/data/data/com.termux/files/usr/bin/bash
cd "$HOME/sms_tool"
python sms_tool.py round2
EOF

chmod +x "$APP_DIR/run.sh"
chmod +x "$APP_DIR/123.sh"
chmod +x "$APP_DIR/yzp.sh"

echo "第6步：创建快捷命令"
cat > "$PREFIX/bin/sd" <<'EOF'
#!/data/data/com.termux/files/usr/bin/bash
bash "$HOME/sms_tool/run.sh"
EOF

cat > "$PREFIX/bin/123.sh" <<'EOF'
#!/data/data/com.termux/files/usr/bin/bash
bash "$HOME/sms_tool/123.sh"
EOF

cat > "$PREFIX/bin/yzp.sh" <<'EOF'
#!/data/data/com.termux/files/usr/bin/bash
bash "$HOME/sms_tool/yzp.sh"
EOF

chmod +x "$PREFIX/bin/sd"
chmod +x "$PREFIX/bin/123.sh"
chmod +x "$PREFIX/bin/yzp.sh"

echo ""
echo "安装完成"
echo "菜单模式：sd"
echo "第一轮快捷发送：123.sh"
echo "第二轮快捷发送：yzp.sh"
echo ""
echo "共享文件目录：$BASE_DIR"
echo "这些文件会自动创建到共享目录里："
echo "1. number.txt"
echo "2. guanggao.txt"
echo "3. yzp huashu.txt"
echo "4. sent number.txt"
echo "5. yzp info.txt"
echo "6. config.json"
echo "7. logs.json"
