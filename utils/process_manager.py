# -*- coding: utf-8 -*-
"""
프로세스 생명주기 관리 모듈
서브프로세스 시작, 중지, 상태 추적을 담당
파일 기반 상태 저장으로 세션 간 프로세스 추적 유지
"""
import subprocess
import sys
import os
import signal
import json
import time
import tempfile
import platform
import threading
import logging
from datetime import datetime
from typing import Dict, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class ProcessManager:
    """서브프로세스 생명주기를 관리하는 클래스 (파일 기반 상태 저장)"""

    def __init__(self):
        # 크로스 플랫폼 기본 디렉토리 설정
        # Windows: %TEMP%\tynewsauto, Unix/Linux/macOS: /tmp/tynewsauto
        self._base_dir = Path(tempfile.gettempdir()) / "tynewsauto"
        self._base_dir.mkdir(parents=True, exist_ok=True)

        self.STATUS_FILE = self._base_dir / "process_status.json"
        self.LOG_DIR = self._base_dir / "process_logs"

        self._processes: Dict[str, subprocess.Popen] = {}
        self._log_files: Dict[str, Any] = {}
        self._lock = threading.Lock()
        self._ensure_log_dir()
        self._restore_processes()

    def _ensure_log_dir(self):
        """로그 디렉토리 생성"""
        Path(self.LOG_DIR).mkdir(parents=True, exist_ok=True)

    def _get_log_file(self, name: str) -> str:
        """프로세스별 로그 파일 경로"""
        return str(self.LOG_DIR / f"{name}.log")

    def _load_status_unlocked(self) -> Dict[str, Any]:
        """파일에서 상태 로드 (lock 없이 — 호출자가 lock을 보유해야 함)"""
        try:
            status_path = str(self.STATUS_FILE)
            if os.path.exists(status_path):
                with open(status_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning("상태 파일 로드 실패: %s", e)
        return {}

    def _load_status(self) -> Dict[str, Any]:
        """파일에서 상태 로드 (thread-safe)"""
        with self._lock:
            return self._load_status_unlocked()

    def _write_status_unlocked(self, status: Dict[str, Any]):
        """상태를 파일에 atomic write (lock 없이 — 호출자가 lock을 보유해야 함)"""
        tmp_path = self.STATUS_FILE.with_suffix('.tmp')
        with open(str(tmp_path), 'w', encoding='utf-8') as f:
            json.dump(status, f, ensure_ascii=False, indent=2)
        os.replace(str(tmp_path), str(self.STATUS_FILE))

    def _save_status(self, name: str, pid: int, start_time: str, config: Optional[Dict] = None):
        """상태를 파일에 저장 (atomic RMW with lock)"""
        with self._lock:
            try:
                status = self._load_status_unlocked()
                status[name] = {
                    'pid': pid,
                    'start_time': start_time,
                    'config': config
                }
                self._write_status_unlocked(status)
            except Exception as e:
                logger.error("상태 저장 실패: %s", e)

    def _remove_status(self, name: str):
        """상태에서 프로세스 제거 (atomic RMW with lock)"""
        with self._lock:
            try:
                status = self._load_status_unlocked()
                if name in status:
                    del status[name]
                    self._write_status_unlocked(status)
            except Exception as e:
                logger.warning("상태 제거 실패 (%s): %s", name, e)

    def _check_pid_exists(self, pid: int) -> bool:
        """PID가 실제로 존재하는지 확인"""
        if pid is None:
            return False
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def _restore_processes(self):
        """파일에서 저장된 프로세스 상태 복원"""
        status = self._load_status()
        for name, info in list(status.items()):
            # 호환성: info가 dict인지 확인 (기존 형식과의 호환)
            if not isinstance(info, dict):
                self._remove_status(name)
                continue

            pid = info.get('pid')
            if pid and self._check_pid_exists(pid):
                pass
            else:
                self._remove_status(name)

    def start_process(self, name: str, script_path: str, config: Optional[Dict[str, Any]] = None) -> bool:
        """프로세스 시작"""
        if self.is_running(name):
            logger.warning("%s 프로세스가 이미 실행 중입니다.", name)
            return False

        try:
            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'
            env['PYTHONUNBUFFERED'] = '1'

            if config:
                env['PROCESS_CONFIG'] = json.dumps(config, ensure_ascii=False)

            log_file_path = self._get_log_file(name)
            log_file = open(log_file_path, 'w', encoding='utf-8')

            script_abs_path = os.path.abspath(script_path)
            project_dir = os.path.dirname(os.path.dirname(script_abs_path))

            try:
                process = subprocess.Popen(
                    [sys.executable, script_abs_path],
                    env=env,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    cwd=project_dir,
                    start_new_session=True
                )
            except Exception:
                log_file.close()
                logger.error("%s Popen 실패, 로그 파일 정리 완료", name)
                raise

            self._processes[name] = process
            self._log_files[name] = log_file
            start_time = datetime.now().isoformat()
            self._save_status(name, process.pid, start_time, config)

            logger.info("%s 프로세스 시작됨 (PID: %d)", name, process.pid)
            return True

        except Exception as e:
            logger.error("%s 프로세스 시작 실패: %s", name, e)
            return False

    def stop_process(self, name: str, timeout: float = 10.0) -> bool:
        """프로세스 중지"""
        status = self._load_status()
        info = status.get(name, {})
        pid = info.get('pid')

        process = self._processes.get(name)

        if not pid and not process:
            logger.warning("%s 프로세스가 실행 중이 아닙니다.", name)
            return True

        try:
            target_pid = process.pid if process else pid

            if target_pid and self._check_pid_exists(target_pid):
                if sys.platform == 'win32':
                    # Windows: CTRL_BREAK_EVENT로 graceful shutdown 시도
                    try:
                        os.kill(target_pid, signal.CTRL_BREAK_EVENT)
                    except (ProcessLookupError, PermissionError, OSError):
                        pass
                    # Wait briefly for graceful shutdown
                    for _ in range(10):  # Wait up to 5 seconds
                        time.sleep(0.5)
                        if not self._check_pid_exists(target_pid):
                            break
                    else:
                        # Force kill if still running
                        try:
                            os.kill(target_pid, signal.SIGTERM)
                        except (ProcessLookupError, PermissionError, OSError):
                            pass
                else:
                    os.kill(target_pid, signal.SIGTERM)

                end_time = time.time() + timeout
                while time.time() < end_time:
                    if not self._check_pid_exists(target_pid):
                        break
                    time.sleep(0.5)

                if self._check_pid_exists(target_pid):
                    # Windows 호환성을 위해 try-catch
                    try:
                        os.kill(target_pid, signal.SIGKILL)
                    except AttributeError:
                        # Windows에서 SIGKILL가 없을 경우 TASKKILL 사용
                        subprocess.run(['taskkill', '/F', '/PID', str(target_pid)],
                                     capture_output=True)
                    time.sleep(1)

            # Close the log file handle if tracked
            log_file = self._log_files.pop(name, None)
            if log_file is not None:
                try:
                    log_file.close()
                except Exception as e:
                    logger.debug("로그 파일 닫기 실패 (%s): %s", name, e)

            self._cleanup_process(name)
            logger.info("%s 프로세스 종료됨", name)
            return True

        except Exception as e:
            logger.error("%s 프로세스 중지 실패: %s", name, e)
            self._cleanup_process(name)
            return False

    def _cleanup_process(self, name: str):
        """프로세스 관련 데이터 정리"""
        if name in self._processes:
            del self._processes[name]
        self._remove_status(name)

    def is_running(self, name: str) -> bool:
        """프로세스 실행 상태 확인 (파일 + 실제 PID 체크)"""
        process = self._processes.get(name)
        if process:
            if process.poll() is None:
                return True
            else:
                self._cleanup_process(name)
                return False
        
        status = self._load_status()
        info = status.get(name, {})
        pid = info.get('pid')
        
        if pid and self._check_pid_exists(pid):
            return True
        elif pid:
            self._remove_status(name)
        
        return False

    def get_runtime(self, name: str) -> Optional[str]:
        """프로세스 실행 시간 반환"""
        if not self.is_running(name):
            return None

        status = self._load_status()
        info = status.get(name, {})
        start_time_str = info.get('start_time')
        
        if not start_time_str:
            return None

        try:
            start_time = datetime.fromisoformat(start_time_str)
            elapsed = datetime.now() - start_time
            hours, remainder = divmod(int(elapsed.total_seconds()), 3600)
            minutes, seconds = divmod(remainder, 60)
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        except Exception:
            return None

    def get_status(self, name: str) -> Dict[str, Any]:
        """프로세스 상태 정보 반환"""
        running = self.is_running(name)
        status = self._load_status()
        info = status.get(name, {})

        return {
            'running': running,
            'pid': info.get('pid') if running else None,
            'runtime': self.get_runtime(name),
            'config': info.get('config'),
            'start_time': info.get('start_time')
        }

    def get_logs(self, name: str, lines: int = 50) -> str:
        """프로세스 로그 읽기"""
        log_file = self._get_log_file(name)
        try:
            if os.path.exists(log_file):
                with open(log_file, 'r', encoding='utf-8') as f:
                    all_lines = f.readlines()
                    return ''.join(all_lines[-lines:])
        except Exception as e:
            logger.warning("로그 읽기 실패 (%s): %s", name, e)
        return ""

    def get_all_status(self) -> Dict[str, Dict[str, Any]]:
        """모든 프로세스 상태 반환"""
        status = self._load_status()
        all_names = set(status.keys()) | set(self._processes.keys())
        return {name: self.get_status(name) for name in all_names}

    def stop_all(self):
        """모든 프로세스 중지"""
        status = self._load_status()
        for name in list(status.keys()):
            self.stop_process(name)


_global_manager: Optional[ProcessManager] = None

def get_process_manager() -> ProcessManager:
    """전역 프로세스 매니저 인스턴스 반환"""
    global _global_manager
    if _global_manager is None:
        _global_manager = ProcessManager()
    return _global_manager
