# -*- coding: utf-8 -*-
"""
TyNewsauto Initialization Script

Creates required config files with default values.
Run once before first start: python init_db.py
"""
import json
from pathlib import Path

import bcrypt


def main():
    base_dir = Path(__file__).parent
    config_dir = base_dir / "config"
    config_dir.mkdir(exist_ok=True)

    # 1. Create config/users.json if missing
    users_file = config_dir / "users.json"
    if not users_file.exists():
        default_hash = bcrypt.hashpw(b"admin", bcrypt.gensalt()).decode("utf-8")
        users_data = {
            "users": {
                "admin": {
                    "id": 1,
                    "username": "admin",
                    "password_hash": default_hash,
                    "role": "admin",
                    "created_at": "2026-02-26T00:00:00"
                }
            },
            "next_id": 2
        }
        with open(users_file, "w", encoding="utf-8") as f:
            json.dump(users_data, f, ensure_ascii=False, indent=2)
        print(f"Created {users_file} (default: admin/admin)")
        print("WARNING: Change default password after first login!")
    else:
        print(f"{users_file} already exists, skipping")

    # 2. Create config/dashboard_config.json if missing
    config_file = config_dir / "dashboard_config.json"
    if not config_file.exists():
        from utils.config_manager import ConfigManager
        default_config = ConfigManager.DEFAULT_CONFIG
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(default_config, f, ensure_ascii=False, indent=2)
        print(f"Created {config_file}")
    else:
        print(f"{config_file} already exists, skipping")

    # 3. Ensure logs directory exists
    logs_dir = base_dir / "logs"
    logs_dir.mkdir(exist_ok=True)
    print(f"Logs directory: {logs_dir}")

    print("\nSetup complete!")
    print("Start the server: python run_api.py")


if __name__ == "__main__":
    main()
