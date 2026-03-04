# -*- coding: utf-8 -*-
"""Test bizwnews CKEditor header/footer preservation (submit=False)."""
import os
import sys
import json
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.sheet_client import get_gspread_client
from utils.config_manager import get_config_manager
from utils.platforms import create_uploader


def main():
    print("=" * 60)
    print("Bizwnews Format Test (submit=False)")
    print("=" * 60)

    cm = get_config_manager()
    config = cm.get_all()

    sheet_url = config.get('google_sheet', {}).get('url', '')
    client = get_gspread_client()
    doc = client.open_by_url(sheet_url)
    sheet = doc.sheet1
    all_data = sheet.get_all_values()

    # Find first available bizwnews row (J=9, K=10, L=11, 0-based)
    for row_idx, row in enumerate(all_data[1:], start=2):
        if len(row) <= 10:
            continue
        title = row[9].strip() if 9 < len(row) else ''
        content = row[10].strip() if 10 < len(row) else ''
        status = row[11].strip().lower() if 11 < len(row) else ''
        if status.startswith('완료'):
            continue
        if title and content:
            break
    else:
        print("No rows available")
        return

    print(f"Row {row_idx}: {title[:50]}...")
    print(f"Content length: {len(content)} chars")

    # Create uploader
    creds = config.get('bizwnews', {})
    platform_config = config.get('upload_platforms', {}).get('bizwnews', {})
    uploader_config = {
        **platform_config,
        'site_id': creds.get('site_id', ''),
        'site_pw': creds.get('site_pw', ''),
        'headless': False,
        'timeout': 120,
    }

    uploader = create_uploader('bizwnews', uploader_config)
    if not uploader:
        print("Failed to create uploader")
        return

    try:
        print("Logging in...")
        if not uploader.login():
            print("Login failed")
            return
        print("Login successful!")

        # Upload with submit=False
        print(f"\nUploading (submit=False): {title[:40]}...")
        result = uploader.upload(title, content, submit=False)
        print(f"Result: success={result.success}")

        if result.success:
            # Read back CKEditor content for verification
            time.sleep(2)
            try:
                final_html = uploader._driver.execute_script(
                    "return CKEDITOR.instances['FCKeditor1'].getData();"
                )
                print(f"\n{'=' * 60}")
                print("CKEditor Final Content:")
                print(f"{'=' * 60}")
                print(final_html)
                print(f"{'=' * 60}")
            except Exception as e:
                print(f"Could not read CKEditor: {e}")

        # Keep browser open for visual inspection
        print("\nBrowser open for 60s - check the form in the browser...")
        time.sleep(60)

    finally:
        uploader.close()


if __name__ == '__main__':
    main()
