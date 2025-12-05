# -*- coding: utf-8 -*-
"""
프로세스 생명주기 관리 모듈
서브프로세스 시작, 중지, 상태 추적을 담당
"""
import subprocess
import sys
import os
import signal
import json
import time
from datetime import datetime
from typing import Dict, Optional, Any


class ProcessManager:
    """서브프로세스 생명주기를 관리하는 클래스"""

    def __init__(self):
        self._processes: Dict[str, subprocess.Popen] = {}
        self._start_times: Dict[str, datetime] = {}
        self._configs: Dict[str, Dict[str, Any]] = {}

    def start_process(self, name: str, script_path: str, config: Optional[Dict[str, Any]] = None) -> bool:
        """프로세스 시작

        Args:
            name: 프로세스 식별자
            script_path: 실행할 스크립트 경로
            config: 환경 변수로 전달할 설정 (JSON 직렬화됨)

        Returns:
            bool: 시작 성공 여부
        """
        if self.is_running(name):
            print(f"⚠️ {name} 프로세스가 이미 실행 중입니다.")
            return False

        try:
            # 환경 변수 설정
            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'

            if config:
                env['PROCESS_CONFIG'] = json.dumps(config, ensure_ascii=False)
                self._configs[name] = config

            # Windows에서 프로세스 그룹 생성을 위한 플래그
            creation_flags = 0
            if sys.platform == 'win32':
                creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP

            # 프로세스 시작
            process = subprocess.Popen(
                [sys.executable, script_path],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=creation_flags if sys.platform == 'win32' else 0,
                cwd=os.path.dirname(script_path) or os.getcwd()
            )

            self._processes[name] = process
            self._start_times[name] = datetime.now()

            print(f"✅ {name} 프로세스 시작됨 (PID: {process.pid})")
            return True

        except Exception as e:
            print(f"❌ {name} 프로세스 시작 실패: {e}")
            return False

    def stop_process(self, name: str, timeout: float = 10.0) -> bool:
        """프로세스 중지 (graceful shutdown 시도)

        Args:
            name: 프로세스 식별자
            timeout: 종료 대기 시간 (초)

        Returns:
            bool: 중지 성공 여부
        """
        if not self.is_running(name):
            print(f"⚠️ {name} 프로세스가 실행 중이 아닙니다.")
            return True

        process = self._processes.get(name)
        if not process:
            return True

        try:
            # Windows에서는 CTRL_BREAK_EVENT, 그 외는 SIGTERM
            if sys.platform == 'win32':
                # Windows: CTRL_BREAK_EVENT 전송
                os.kill(process.pid, signal.CTRL_BREAK_EVENT)
            else:
                # Unix: SIGTERM 전송
                process.send_signal(signal.SIGTERM)

            # 종료 대기
            try:
                process.wait(timeout=timeout)
                print(f"✅ {name} 프로세스 정상 종료됨")
            except subprocess.TimeoutExpired:
                # 강제 종료
                print(f"⚠️ {name} 프로세스 응답 없음, 강제 종료 중...")
                process.kill()
                process.wait(timeout=5)
                print(f"✅ {name} 프로세스 강제 종료됨")

            # 정리
            self._cleanup_process(name)
            return True

        except Exception as e:
            print(f"❌ {name} 프로세스 중지 실패: {e}")
            self._cleanup_process(name)
            return False

    def _cleanup_process(self, name: str):
        """프로세스 관련 데이터 정리"""
        if name in self._processes:
            del self._processes[name]
        if name in self._start_times:
            del self._start_times[name]

    def is_running(self, name: str) -> bool:
        """프로세스 실행 상태 확인

        Args:
            name: 프로세스 식별자

        Returns:
            bool: 실행 중이면 True
        """
        process = self._processes.get(name)
        if not process:
            return False

        # poll()이 None이면 아직 실행 중
        if process.poll() is None:
            return True

        # 프로세스가 종료됨 - 정리
        self._cleanup_process(name)
        return False

    def get_runtime(self, name: str) -> Optional[str]:
        """프로세스 실행 시간 반환

        Args:
            name: 프로세스 식별자

        Returns:
            str: 실행 시간 문자열 (HH:MM:SS 형식) 또는 None
        """
        if not self.is_running(name):
            return None

        start_time = self._start_times.get(name)
        if not start_time:
            return None

        elapsed = datetime.now() - start_time
        hours, remainder = divmod(int(elapsed.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)

        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def get_status(self, name: str) -> Dict[str, Any]:
        """프로세스 상태 정보 반환

        Args:
            name: 프로세스 식별자

        Returns:
            dict: 상태 정보 (running, pid, runtime, config)
        """
        running = self.is_running(name)
        process = self._processes.get(name)

        return {
            'running': running,
            'pid': process.pid if process and running else None,
            'runtime': self.get_runtime(name),
            'config': self._configs.get(name),
            'start_time': self._start_times.get(name).isoformat() if name in self._start_times else None
        }

    def get_all_status(self) -> Dict[str, Dict[str, Any]]:
        """모든 프로세스 상태 반환"""
        all_names = set(self._processes.keys()) | set(self._start_times.keys())
        return {name: self.get_status(name) for name in all_names}

    def stop_all(self):
        """모든 프로세스 중지"""
        for name in list(self._processes.keys()):
            self.stop_process(name)


# 전역 프로세스 매니저 인스턴스 (Streamlit 세션 간 공유용)
_global_manager: Optional[ProcessManager] = None

def get_process_manager() -> ProcessManager:
    """전역 프로세스 매니저 인스턴스 반환"""
    global _global_manager
    if _global_manager is None:
        _global_manager = ProcessManager()
    return _global_manager
