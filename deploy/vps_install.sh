#!/usr/bin/env bash
set -e

echo "================================================================="
echo "   ShoeMatch AI — Hostinger VPS Server Automated Setup"
echo "================================================================="

sudo apt update && sudo apt install -y python3-pip python3-venv python3-dev git libgl1 libglib2.0-0 ufw nginx

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

# 1. Setup backend systemd service on port 8000
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
Environment=PORT=8000
Environment=HOST=127.0.0.1

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now shoematch

# 2. Setup Nginx Reverse Proxy on Port 80
sudo tee /etc/nginx/sites-available/shoematch > /dev/null <<'EOF'
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;

    client_max_body_size 50M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

sudo rm -f /etc/nginx/sites-enabled/default
sudo ln -sf /etc/nginx/sites-available/shoematch /etc/nginx/sites-enabled/shoematch
sudo systemctl restart nginx

sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable

echo "================================================================="
echo "   SUCCESS! ShoeMatch AI Backend & Nginx are Live on Port 80"
echo "   Check Health: http://195.35.6.176/health"
echo "================================================================="
