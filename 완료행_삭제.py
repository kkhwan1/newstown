# -*- coding: utf-8 -*-
"""
완료된 행 자동 삭제 스크립트

구글 시트의 완료 표시 열을 지속적으로 감시하여
"완료"가 포함된 행을 주기적으로 삭제합니다.

@TASK T8 - 플랫폼별 완료행 삭제 분리
@SPEC CLAUDE.md#Google-Sheets-Structure
"""
import sys
import io
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time
import random
from datetime import datetime, timezone, timedelta
from typing import Optional

# 한국 시간대 (KST = UTC+9)
KST = timezone(timedelta(hours=9))


def get_kst_time():
    """현재 한국 시간을 문자열로 반환"""
    return datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')


# Windows 콘솔에서 UTF-8 인코딩 설정
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


# ==========================================
# 설정 구역
# ==========================================
# 1. 구글 시트 전체 주소
DEFAULT_SHEET_URL = "https://docs.google.com/spreadsheets/d/1H0aj-bN63LMMFcinfe51J-gwewzxIyzFOkqSA5POHkk/edit"

# 2. 완료 표시 열 (H열=8번째 열)
DEFAULT_COMPLETED_COLUMN = 8  # H열

# 3. 삭제 작업 실행 간격 (분 단위)
DEFAULT_DELETE_INTERVAL = 60  # 60분마다 완료된 행 삭제

# 4. 한 번에 삭제할 최대 행 개수
DEFAULT_MAX_DELETE_COUNT = 10

# 5. API 재시도 설정
MAX_RETRIES = 5
INITIAL_RETRY_DELAY = 60
MAX_RETRY_DELAY = 300
# ==========================================


class CompletedRowDeleter:
    """완료된 행 삭제 클래스"""

    def __init__(
        self,
        sheet_url: str = DEFAULT_SHEET_URL,
        credentials_file: str = 'credentials.json',
        delete_interval: int = DEFAULT_DELETE_INTERVAL,
        max_delete_count: int = DEFAULT_MAX_DELETE_COUNT,
        completed_column: int = DEFAULT_COMPLETED_COLUMN
    ):
        """
        초기화

        Args:
            sheet_url: Google Sheets URL
            credentials_file: 서비스 계정 인증 파일 경로
            delete_interval: 삭제 작업 간격 (분)
            max_delete_count: 한 번에 삭제할 최대 행 개수
            completed_column: 완료 표시 열 번호 (1-based)
        """
        self.sheet_url = sheet_url
        self.credentials_file = credentials_file
        self.delete_interval = delete_interval
        self.max_delete_count = max_delete_count
        self.completed_column = completed_column
        self.client: Optional[gspread.Client] = None
        self.sheet: Optional[gspread.Worksheet] = None

    def _retry_with_backoff(self, func, *args, **kwargs):
        """API 호출 시 재시도 로직 (지수 백오프)

        Args:
            func: 실행할 함수
            *args, **kwargs: 함수에 전달할 인자

        Returns:
            함수 실행 결과
        """
        last_exception = None

        for attempt in range(MAX_RETRIES):
            try:
                return func(*args, **kwargs)
            except gspread.exceptions.APIError as e:
                last_exception = e
                error_code = e.response.status_code if hasattr(e, 'response') else None

                if error_code == 429 or "429" in str(e) or "Quota exceeded" in str(e):
                    if attempt < MAX_RETRIES - 1:
                        delay = min(INITIAL_RETRY_DELAY * (2 ** attempt), MAX_RETRY_DELAY)
                        jitter = random.uniform(0, 10)
                        total_delay = delay + jitter

                        print(f"   API 할당량 초과 (429) - {attempt + 1}/{MAX_RETRIES}번째 재시도")
                        print(f"   {int(total_delay)}초 후 재시도...")
                        time.sleep(total_delay)
                    else:
                        print(f"   최대 재시도 횟수({MAX_RETRIES}회) 초과")
                        raise
                else:
                    raise
            except Exception as e:
                raise

        if last_exception:
            raise last_exception

    def connect(self) -> bool:
        """Google Sheets에 연결"""
        try:
            scope = [
                'https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive'
            ]

            creds = ServiceAccountCredentials.from_json_keyfile_name(
                self.credentials_file, scope
            )
            self.client = gspread.authorize(creds)

            doc = self._retry_with_backoff(self.client.open_by_url, self.sheet_url)
            self.sheet = doc.sheet1

            return True

        except FileNotFoundError:
            print(f"   오류: '{self.credentials_file}' 파일을 찾을 수 없습니다.")
            return False
        except Exception as e:
            print(f"   연결 실패: {e}")
            return False

    def delete_completed_rows(self) -> int:
        """
        완료 표시 열에 "완료"가 포함된 행을 찾아서 삭제

        Returns:
            삭제된 행의 개수
        """
        try:
            rows = self._retry_with_backoff(self.sheet.get_all_values)
            rows_to_delete = []

            # 2번째 행부터 루프 (1행은 헤더)
            for i, row in enumerate(rows[1:], start=2):
                if len(row) < self.completed_column:
                    continue

                completed_status = row[self.completed_column - 1].strip() if row[self.completed_column - 1] else ""

                if completed_status and "완료" in completed_status:
                    rows_to_delete.append(i)

            if not rows_to_delete:
                return 0

            # 하위에서 위로 삭제
            rows_to_delete.sort(reverse=True)

            total_found = len(rows_to_delete)
            if total_found > self.max_delete_count:
                print(f"   삭제 대상: {total_found}개 행 (최대 {self.max_delete_count}개만 삭제)")
                rows_to_delete = rows_to_delete[:self.max_delete_count]
                print(f"   이번 삭제: {rows_to_delete} (나머지 {total_found - self.max_delete_count}개는 다음에)")
            else:
                print(f"   삭제 대상: {total_found}개 행")
                print(f"   행 번호: {rows_to_delete}")

            deleted_count = 0
            for row_num in rows_to_delete:
                try:
                    self._retry_with_backoff(self.sheet.delete_rows, row_num)
                    deleted_count += 1
                    print(f"   행 {row_num}번 삭제 완료")
                except Exception as e:
                    print(f"   행 {row_num}번 삭제 실패: {e}")

            return deleted_count

        except Exception as e:
            print(f"   완료된 행 확인 중 오류: {e}")
            return 0

    def run_once(self) -> int:
        """한 번만 실행하고 결과 반환"""
        if not self.sheet:
            if not self.connect():
                return 0

        print(f"[{get_kst_time()}] 완료된 행 확인 시작...")
        deleted = self.delete_completed_rows()

        if deleted > 0:
            print(f"   총 {deleted}개 행 삭제 완료")
        else:
            print(f"   삭제할 완료된 행 없음")

        return deleted

    def run(self):
        """지속적으로 실행"""
        print("=" * 60)
        print("  완료된 행 자동 삭제")
        print("=" * 60)
        print(f"\n 구글 시트 연결 중...")
        print(f" 간격: {self.delete_interval}분")
        print(f" 완료 표시 열: {chr(64 + self.completed_column)}열 ({self.completed_column}번째)")
        print(f" 종료: Ctrl+C\n")

        if not self.connect():
            print("연결 실패로 종료합니다.")
            return

        print("연결 성공")
        column_letter = chr(64 + self.completed_column)
        print(f"\n {column_letter}열(완료 표시 열) 감시 중...")
        print(f" {self.delete_interval}분마다 완료된 행 자동 삭제")
        print(f" 한 번에 최대 {self.max_delete_count}개 행만 삭제\n")

        delete_count = 0

        try:
            while True:
                try:
                    delete_count += 1
                    print(f"[{get_kst_time()}] {delete_count}번째 삭제 작업 시작...")

                    deleted_rows = self.delete_completed_rows()

                    if deleted_rows > 0:
                        print(f"   총 {deleted_rows}개 행 삭제 완료")
                    else:
                        print(f"   삭제할 완료된 행 없음")

                    wait_seconds = self.delete_interval * 60
                    print(f"   다음 작업까지 {self.delete_interval}분 대기...")
                    time.sleep(wait_seconds)

                except gspread.exceptions.APIError as e:
                    error_code = e.response.status_code if hasattr(e, 'response') else None
                    if error_code == 429 or "429" in str(e):
                        print(f"   API 할당량 초과 - {INITIAL_RETRY_DELAY}초 대기 후 재시도...")
                        time.sleep(INITIAL_RETRY_DELAY)
                        try:
                            doc = self._retry_with_backoff(self.client.open_by_url, self.sheet_url)
                            self.sheet = doc.sheet1
                            print("   시트 재연결 성공")
                        except Exception as reconnect_error:
                            print(f"   재연결 실패: {reconnect_error}")
                            time.sleep(wait_seconds)
                    else:
                        print(f"   API 오류: {e}")
                        time.sleep(wait_seconds)
                except Exception as e:
                    print(f"   오류 발생: {e}")
                    time.sleep(wait_seconds)

        except KeyboardInterrupt:
            print("\n\n사용자에 의해 종료되었습니다.")
            print("=" * 60)


def main():
    """메인 함수 - 환경 변수 또는 기본값으로 실행"""
    import os

    sheet_url = os.environ.get('GOOGLE_SHEET_URL', DEFAULT_SHEET_URL)
    delete_interval = int(os.environ.get('DELETE_INTERVAL', DEFAULT_DELETE_INTERVAL))
    max_delete_count = int(os.environ.get('MAX_DELETE_COUNT', DEFAULT_MAX_DELETE_COUNT))

    deleter = CompletedRowDeleter(
        sheet_url=sheet_url,
        delete_interval=delete_interval,
        max_delete_count=max_delete_count
    )
    deleter.run()


if __name__ == "__main__":
    main()
