# -*- coding: utf-8 -*-
"""
Test script: Upload 3 articles to each platform (golftimes + bizwnews)
Reads from Google Sheets, uploads, marks completion.
"""
import os
import sys
import json
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.sheet_client import get_gspread_client
from utils.config_manager import get_config_manager
from utils.platforms import create_uploader

UPLOAD_COUNT = 3  # per platform


def main():
    print("=" * 60)
    print("Upload Test: 3 articles per platform")
    print("=" * 60)

    # Load config
    cm = get_config_manager()
    config = cm.get_all()

    sheet_url = config.get('google_sheet', {}).get('url', '')
    if not sheet_url:
        print("[ERROR] Google Sheet URL not configured")
        return

    # Connect to sheet
    print("[INFO] Connecting to Google Sheets...")
    client = get_gspread_client()
    doc = client.open_by_url(sheet_url)
    sheet = doc.sheet1
    all_data = sheet.get_all_values()
    print(f"[INFO] Sheet loaded: {len(all_data)} rows")

    # Platform configs
    platforms = {
        'golftimes': {
            'title_col': 5,    # F (0-based)
            'content_col': 6,  # G (0-based)
            'status_col': 7,   # H (0-based), cell col = 8
            'creds': config.get('golftimes', {}),
            'platform_config': config.get('upload_platforms', {}).get('golftimes', {}),
        },
        'bizwnews': {
            'title_col': 9,    # J (0-based)
            'content_col': 10, # K (0-based)
            'status_col': 11,  # L (0-based), cell col = 12
            'creds': config.get('bizwnews', {}),
            'platform_config': config.get('upload_platforms', {}).get('bizwnews', {}),
        },
    }

    for platform_id, pconf in platforms.items():
        print(f"\n{'=' * 60}")
        print(f"[{platform_id.upper()}] Starting upload ({UPLOAD_COUNT} articles)")
        print(f"{'=' * 60}")

        title_col = pconf['title_col']
        content_col = pconf['content_col']
        status_col = pconf['status_col']
        creds = pconf['creds']
        platform_config = pconf['platform_config']

        # Check credentials
        site_id = creds.get('site_id', '')
        site_pw = creds.get('site_pw', '')
        if not site_id or not site_pw:
            print(f"[{platform_id}] ERROR: No credentials configured")
            continue

        # Find rows to upload (skip header, check status)
        rows_to_upload = []
        for row_idx, row in enumerate(all_data[1:], start=2):
            if len(row) <= max(title_col, content_col):
                continue

            title = row[title_col].strip() if title_col < len(row) else ''
            content = row[content_col].strip() if content_col < len(row) else ''

            # Check if already completed
            if status_col < len(row):
                status = row[status_col].strip().lower()
                if status.startswith('완료') or status in ['completed', '업로드완료', '✓']:
                    continue

            if title and content:
                rows_to_upload.append((row_idx, title, content))

            if len(rows_to_upload) >= UPLOAD_COUNT:
                break

        if not rows_to_upload:
            print(f"[{platform_id}] No rows to upload")
            continue

        print(f"[{platform_id}] Found {len(rows_to_upload)} rows to upload")
        for i, (idx, title, _) in enumerate(rows_to_upload):
            print(f"  {i+1}. Row {idx}: {title[:50]}...")

        # Create uploader config
        uploader_config = {
            **platform_config,
            'site_id': site_id,
            'site_pw': site_pw,
            'golftimes_id': site_id,
            'golftimes_pw': site_pw,
            'headless': False,
            'timeout': 120,
        }

        # Create uploader and upload
        try:
            uploader = create_uploader(platform_id, uploader_config)
            if not uploader:
                print(f"[{platform_id}] ERROR: Failed to create uploader")
                continue

            print(f"[{platform_id}] Logging in...")
            if not uploader.login():
                print(f"[{platform_id}] ERROR: Login failed")
                continue
            print(f"[{platform_id}] Login successful!")

            success_count = 0
            for row_idx, title, content in rows_to_upload:
                print(f"\n[{platform_id}] Uploading row {row_idx}: {title[:40]}...")
                try:
                    result = uploader.upload(title, content, submit=True)
                    if result.success:
                        success_count += 1
                        # Mark as completed with timestamp
                        now = datetime.now().strftime('%Y-%m-%d %H:%M')
                        sheet.update_cell(row_idx, status_col + 1, f'완료 ({now})')
                        print(f"[{platform_id}] SUCCESS: Row {row_idx} uploaded and marked")
                    else:
                        print(f"[{platform_id}] FAILED: {result.error_message}")
                except Exception as e:
                    print(f"[{platform_id}] ERROR uploading row {row_idx}: {e}")

                time.sleep(5)  # Delay between uploads for session stability

            print(f"\n[{platform_id}] Result: {success_count}/{len(rows_to_upload)} uploaded")

            # Logout and close driver
            try:
                uploader.logout()
                uploader.close()
                print(f"[{platform_id}] Logged out and driver closed")
            except:
                pass

        except Exception as e:
            print(f"[{platform_id}] ERROR: {e}")
            import traceback
            traceback.print_exc()

    print(f"\n{'=' * 60}")
    print("Upload test complete!")
    print(f"{'=' * 60}")


if __name__ == '__main__':
    main()
