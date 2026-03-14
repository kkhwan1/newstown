#!/bin/bash
# TyNewsauto 터널 헬스체크 스크립트
# crontab 등록: */5 * * * * /root/tynewsauto/deploy/check-tunnel.sh >> /var/log/tynewsauto-health.log 2>&1

API_URL="http://localhost:8001/health"
LOG_PREFIX="[$(date '+%Y-%m-%d %H:%M:%S')]"

# 1. API 서버 헬스체크
if curl -sf --max-time 5 "$API_URL" > /dev/null 2>&1; then
    echo "$LOG_PREFIX API OK"
else
    echo "$LOG_PREFIX API DOWN - restarting tynewsauto..."
    systemctl restart tynewsauto
    sleep 3

    if curl -sf --max-time 5 "$API_URL" > /dev/null 2>&1; then
        echo "$LOG_PREFIX API recovered after restart"
    else
        echo "$LOG_PREFIX API STILL DOWN after restart"
    fi
fi

# 2. cloudflared 프로세스 확인
if systemctl is-active --quiet cloudflared; then
    echo "$LOG_PREFIX Tunnel OK"
else
    echo "$LOG_PREFIX Tunnel DOWN - restarting cloudflared..."
    systemctl restart cloudflared
    sleep 3

    if systemctl is-active --quiet cloudflared; then
        echo "$LOG_PREFIX Tunnel recovered after restart"
    else
        echo "$LOG_PREFIX Tunnel STILL DOWN after restart"
    fi
fi
