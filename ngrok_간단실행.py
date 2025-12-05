# -*- coding: utf-8 -*-
"""
ngrok 간단 실행 스크립트
포트 7777을 news.ngrok.app 도메인으로 터널링합니다.
"""
import sys
import io
import subprocess
import os

# Windows 콘솔에서 UTF-8 인코딩 설정
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

NGROK_DOMAIN = "news.ngrok.app"
LOCAL_PORT = 7777

def main():
    print("\n" + "="*60)
    print("  ngrok 터널 시작")
    print("="*60)
    print(f"\n도메인: {NGROK_DOMAIN}")
    print(f"로컬 포트: {LOCAL_PORT}")
    print(f"\n터널을 시작합니다...")
    print(f"Ctrl+C를 누르면 종료됩니다.\n")
    print("="*60 + "\n")
    
    # 현재 디렉토리의 ngrok.exe 또는 시스템 ngrok 사용
    if os.path.exists("ngrok.exe"):
        ngrok_cmd = "ngrok.exe"
    else:
        ngrok_cmd = "ngrok"
    
    try:
        # ngrok 실행 (도메인 사용)
        subprocess.run([ngrok_cmd, "http", str(LOCAL_PORT), "--domain", NGROK_DOMAIN])
    except KeyboardInterrupt:
        print("\n\n터널을 종료합니다...")
    except FileNotFoundError:
        print(f"\n❌ ngrok을 찾을 수 없습니다.")
        print(f"\n💡 해결 방법:")
        print(f"   1. ngrok을 설치하세요: https://ngrok.com/download")
        print(f"   2. 또는 ngrok.exe를 현재 폴더에 넣으세요")
        print(f"   3. 또는 PATH에 ngrok을 추가하세요")
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

