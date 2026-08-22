#!/usr/bin/env bash
set -e

echo "================================================================="
echo "   ShoeMatch AI — Hostinger VPS Server Automated Setup"
echo "================================================================="

sudo apt update && sudo apt install -y python3-pip python3-venv python3-dev git libgl1 libglib2.0-0 ufw

sudo mkdir -p /var/www/shoematch

if [ ! -d "/var/www/shoematch/.git" ]; then
  git clone https://github.com/SIDDHARTHKAUSHIK1/Shoe-Design-Recognition-Matching-System.git /var/www/shoematch
else
  cd /var/www/shoematch && git pull origin main
fi

cd /var/www/shoematch

if [ ! -d "venv" ]; then
  python3 -m venv venv
fi

source venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt

sudo tee /etc/systemd/system/shoematch.service > /dev/null <<'EOF'
[Unit]
Description=ShoeMatch AI Backend Server
After=network.target network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=/var/www/shoematch
ExecStart=/var/www/shoematch/venv/bin/python -u run_server.py
Restart=always
RestartSec=5s
Environment=PYTHONUNBUFFERED=1
Environment=PORT=80
Environment=HOST=0.0.0.0

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now shoematch

sudo ufw allow 22/tcp
sudo ufw allow 8000/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable

echo "================================================================="
echo "   SUCCESS! ShoeMatch AI Backend is Live on Port 80"
echo "   Check Health: http://195.35.6.176/health"
echo "================================================================="
