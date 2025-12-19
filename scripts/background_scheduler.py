# -*- coding: utf-8 -*-
"""
백그라운드 스케줄러
대시보드와 독립적으로 실행되며, 설정된 간격에 따라 뉴스 수집을 자동 실행
"""
import sys
import os
import json
import time
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.config_manager import ConfigManager

DASHBOARD_CONFIG_PATH = Path(__file__).parent.parent / "config" / "dashboard_config.json"
SCHEDULER_LOG_FILE = "/tmp/scheduler.log"

def log(msg, level="INFO"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"[{timestamp}] [{level}] {msg}"
    print(log_msg)
    try:
        with open(SCHEDULER_LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(log_msg + "\n")
    except:
        pass

def load_config():
    try:
        if DASHBOARD_CONFIG_PATH.exists():
            with open(DASHBOARD_CONFIG_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        log(f"설정 로드 실패: {e}", "ERROR")
    return {}

def save_last_run(timestamp):
    try:
        config = load_config()
        if 'news_schedule' not in config:
            config['news_schedule'] = {}
        config['news_schedule']['last_run'] = timestamp
        with open(DASHBOARD_CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log(f"last_run 저장 실패: {e}", "ERROR")

def run_news_collection():
    log("뉴스 수집 시작...", "INFO")
    try:
        config = load_config()
        news_config = config.get('news_collection', {})
        category_keywords = config.get('category_keywords', {})
        
        process_config = {
            'keywords': news_config.get('keywords', {'연애': 14, '경제': 14, '스포츠': 14}),
            'display_count': news_config.get('display_count', 30),
            'sheet_url': news_config.get('sheet_url', ''),
            'naver_client_id': news_config.get('naver_client_id', ''),
            'naver_client_secret': news_config.get('naver_client_secret', ''),
            'sort': news_config.get('sort', 'date'),
            'category_keywords': category_keywords
        }
        
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        env['PROCESS_CONFIG'] = json.dumps(process_config, ensure_ascii=False)
        
        script_path = Path(__file__).parent / "run_news_collection.py"
        
        result = subprocess.run(
            [sys.executable, str(script_path)],
            env=env,
            cwd=str(Path(__file__).parent.parent),
            capture_output=True,
            text=True,
            timeout=600
        )
        
        if result.returncode == 0:
            log("뉴스 수집 완료", "SUCCESS")
        else:
            log(f"뉴스 수집 오류: {result.stderr[:500]}", "ERROR")
            
    except subprocess.TimeoutExpired:
        log("뉴스 수집 타임아웃 (10분)", "ERROR")
    except Exception as e:
        log(f"뉴스 수집 실행 실패: {e}", "ERROR")

def check_and_run():
    config = load_config()
    schedule_config = config.get('news_schedule', {})
    
    if not schedule_config.get('enabled', False):
        return False
    
    interval_hours = schedule_config.get('interval_hours', 2)
    last_run_str = schedule_config.get('last_run')
    
    now = datetime.now()
    
    if last_run_str:
        try:
            last_run = datetime.fromisoformat(last_run_str)
            next_run = last_run + timedelta(hours=interval_hours)
            
            if now < next_run:
                return False
        except:
            pass
    
    save_last_run(now.isoformat())
    run_news_collection()
    return True

def main():
    log("=" * 50)
    log("백그라운드 스케줄러 시작")
    log("=" * 50)
    
    check_interval = 60
    
    while True:
        try:
            config = load_config()
            schedule_config = config.get('news_schedule', {})
            
            if schedule_config.get('enabled', False):
                interval = schedule_config.get('interval_hours', 2)
                last_run = schedule_config.get('last_run', 'N/A')
                
                if check_and_run():
                    log(f"스케줄 실행 완료. 다음 실행: {interval}시간 후")
            
            time.sleep(check_interval)
            
        except KeyboardInterrupt:
            log("스케줄러 종료 (사용자 중단)")
            break
        except Exception as e:
            log(f"스케줄러 오류: {e}", "ERROR")
            time.sleep(check_interval)

if __name__ == "__main__":
    main()
