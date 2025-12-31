# -*- coding: utf-8 -*-
"""
백그라운드 스케줄러
대시보드와 독립적으로 실행되며, 설정된 간격에 따라 뉴스 수집을 자동 실행
PostgreSQL DB에서 설정을 읽어와 배포 환경에서도 동작
"""
import sys
import os
import json
import time
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

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

def get_db_connection():
    try:
        import psycopg2
        db_url = os.environ.get('DATABASE_URL')
        if db_url:
            return psycopg2.connect(db_url)
    except Exception as e:
        log(f"DB 연결 실패: {e}", "ERROR")
    return None

def load_config_from_db():
    conn = get_db_connection()
    if not conn:
        return {}
    
    config = {}
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT key, value FROM settings")
            rows = cur.fetchall()
            for key, value in rows:
                try:
                    config[key] = json.loads(value)
                except json.JSONDecodeError:
                    config[key] = value
        log(f"DB에서 설정 로드: {len(config)}개 섹션")
    except Exception as e:
        log(f"DB 설정 로드 실패: {e}", "ERROR")
    finally:
        conn.close()
    return config

def save_last_run_to_db(timestamp):
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT value FROM settings WHERE key = 'news_schedule'")
            row = cur.fetchone()
            if row:
                schedule_config = json.loads(row[0])
            else:
                schedule_config = {'enabled': True, 'interval_hours': 2}
            
            schedule_config['last_run'] = timestamp
            value = json.dumps(schedule_config, ensure_ascii=False)
            
            cur.execute("""
                INSERT INTO settings (key, value, updated_at)
                VALUES ('news_schedule', %s, CURRENT_TIMESTAMP)
                ON CONFLICT (key)
                DO UPDATE SET value = EXCLUDED.value, updated_at = CURRENT_TIMESTAMP
            """, (value,))
            conn.commit()
        return True
    except Exception as e:
        log(f"last_run 저장 실패: {e}", "ERROR")
        return False
    finally:
        conn.close()

def run_news_collection():
    log("뉴스 수집 시작...", "INFO")
    try:
        config = load_config_from_db()
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
    config = load_config_from_db()
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
    
    save_last_run_to_db(now.isoformat())
    run_news_collection()
    return True

def main():
    log("=" * 50)
    log("백그라운드 스케줄러 시작 (DB 기반)")
    log("=" * 50)
    
    check_interval = 60
    
    while True:
        try:
            config = load_config_from_db()
            schedule_config = config.get('news_schedule', {})
            
            if schedule_config.get('enabled', False):
                interval = schedule_config.get('interval_hours', 2)
                
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
