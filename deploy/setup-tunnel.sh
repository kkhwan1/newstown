#!/bin/bash
# TyNewsauto Cloudflare Tunnel 설치 및 설정 스크립트
# 사용법: bash deploy/setup-tunnel.sh [quick|named]
#   quick  - Quick Tunnel (임시 URL, 재시작 시 변경됨)
#   named  - Named Tunnel (고정 URL, Cloudflare 로그인 필요)

set -euo pipefail

MODE="${1:-quick}"
PROJECT_DIR="/root/tynewsauto"
API_PORT=8001

echo "=== TyNewsauto Cloudflare Tunnel Setup ==="
echo "Mode: $MODE"

# 1. cloudflared 설치
if ! command -v cloudflared &> /dev/null; then
    echo ">> cloudflared 설치 중..."
    curl -fsSL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o /tmp/cloudflared.deb
    dpkg -i /tmp/cloudflared.deb
    rm /tmp/cloudflared.deb
    echo ">> cloudflared 설치 완료: $(cloudflared --version)"
else
    echo ">> cloudflared 이미 설치됨: $(cloudflared --version)"
fi

# 2. 모드별 설정
if [ "$MODE" = "named" ]; then
    echo ""
    echo ">> Named Tunnel 설정 (고정 URL)"
    echo ">> Cloudflare 로그인이 필요합니다..."
    cloudflared tunnel login

    TUNNEL_NAME="tynewsauto"

    # 기존 터널 확인
    if cloudflared tunnel list | grep -q "$TUNNEL_NAME"; then
        echo ">> 기존 터널 '$TUNNEL_NAME' 발견"
    else
        echo ">> 터널 생성 중..."
        cloudflared tunnel create "$TUNNEL_NAME"
    fi

    # config.yml 생성
    TUNNEL_ID=$(cloudflared tunnel list | grep "$TUNNEL_NAME" | awk '{print $1}')
    CRED_FILE="/root/.cloudflared/${TUNNEL_ID}.json"

    mkdir -p /root/.cloudflared
    cat > /root/.cloudflared/config.yml << EOF
tunnel: ${TUNNEL_ID}
credentials-file: ${CRED_FILE}

ingress:
  - hostname: tynewsauto.example.com
    service: http://localhost:${API_PORT}
  - service: http_status:404
EOF

    echo ""
    echo ">> /root/.cloudflared/config.yml 생성 완료"
    echo ">> 중요: config.yml의 hostname을 실제 도메인으로 변경하세요"
    echo ">> DNS 라우팅 설정:"
    echo ">>   cloudflared tunnel route dns $TUNNEL_NAME <your-subdomain.your-domain.com>"
    echo ""

    # Named Tunnel용 systemd 서비스
    cat > /etc/systemd/system/cloudflared.service << EOF
[Unit]
Description=Cloudflare Tunnel for TyNewsauto (Named)
After=network-online.target tynewsauto.service
Wants=network-online.target

[Service]
Type=simple
User=root
ExecStart=/usr/local/bin/cloudflared tunnel run ${TUNNEL_NAME}
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=cloudflared

[Install]
WantedBy=multi-user.target
EOF

else
    echo ""
    echo ">> Quick Tunnel 설정 (임시 URL)"

    # Quick Tunnel용 systemd 서비스
    cp "${PROJECT_DIR}/deploy/cloudflared.service" /etc/systemd/system/cloudflared.service
fi

# 3. systemd 등록 및 시작
echo ">> systemd 서비스 등록 중..."
systemctl daemon-reload
systemctl enable cloudflared
systemctl start cloudflared

echo ""
echo "=== 설정 완료 ==="
echo ""
echo "상태 확인: systemctl status cloudflared"
echo "로그 확인: journalctl -u cloudflared -f"
echo ""

if [ "$MODE" = "quick" ]; then
    echo "Quick Tunnel URL 확인:"
    echo "  journalctl -u cloudflared --no-pager | grep 'trycloudflare.com'"
    echo ""
    echo "주의: Quick Tunnel은 재시작 시 URL이 변경됩니다."
    echo "고정 URL이 필요하면: bash deploy/setup-tunnel.sh named"
fi
