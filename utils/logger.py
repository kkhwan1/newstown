import os
import json
from datetime import datetime
from pathlib import Path
from threading import Lock

LOG_FILE = Path(__file__).parent.parent / "logs" / "activity.log"
MAX_LINES = 500

_lock = Lock()

def ensure_log_dir():
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

def add_log(message: str, level: str = "INFO", category: str = "SYSTEM"):
    ensure_log_dir()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = {
        "timestamp": timestamp,
        "level": level,
        "category": category,
        "message": message
    }
    
    with _lock:
        try:
            if LOG_FILE.exists():
                with open(LOG_FILE, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
            else:
                lines = []
            
            lines.append(json.dumps(log_entry, ensure_ascii=False) + "\n")
            
            if len(lines) > MAX_LINES:
                lines = lines[-MAX_LINES:]
            
            with open(LOG_FILE, 'w', encoding='utf-8') as f:
                f.writelines(lines)
        except Exception as e:
            print(f"Log error: {e}")

def get_logs(limit: int = 100, category: str = None):
    ensure_log_dir()
    logs = []
    
    try:
        if LOG_FILE.exists():
            with open(LOG_FILE, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            for line in reversed(lines):
                try:
                    entry = json.loads(line.strip())
                    if category is None or entry.get('category') == category:
                        logs.append(entry)
                    if len(logs) >= limit:
                        break
                except:
                    continue
    except Exception as e:
        print(f"Read log error: {e}")
    
    return logs

def clear_logs():
    ensure_log_dir()
    with _lock:
        try:
            with open(LOG_FILE, 'w', encoding='utf-8') as f:
                f.write("")
        except:
            pass
