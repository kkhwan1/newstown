# -*- coding: utf-8 -*-
"""
Platform Uploaders Package

@TASK T8 - 플랫폼 업로더 추상화
@SPEC docs/planning/02-trd.md#Platform-Abstraction

This package provides abstracted platform uploaders for news automation.
"""
from typing import Optional

from .base import (
    PlatformUploader,
    UploadResult,
    UploadStatus,
    PlatformConfig
)

from .golftimes import (
    GolftimesUploader,
    upload_to_golftimes
)

__all__ = [
    # Base classes
    'PlatformUploader',
    'UploadResult',
    'UploadStatus',
    'PlatformConfig',

    # Platform implementations
    'GolftimesUploader',

    # Convenience functions
    'upload_to_golftimes',

    # Factory
    'create_uploader',
    'DriverPool',
]


def create_uploader(platform_name: str, config: dict) -> PlatformUploader:
    """
    Factory function to create platform-specific uploader.

    Args:
        platform_name: Platform identifier ('golftimes')
        config: Configuration dictionary with platform settings.
                Can be either {platform_id: {...}} or direct {...} format.

    Returns:
        PlatformUploader instance for the specified platform

    Raises:
        ValueError: If platform_name is not supported
    """
    platform_map = {
        'golftimes': GolftimesUploader,
    }

    uploader_class = platform_map.get(platform_name.lower())
    if uploader_class is None:
        raise ValueError(f"Unsupported platform: {platform_name}. "
                        f"Supported platforms: {list(platform_map.keys())}")

    # Ensure config is in {platform_id: {...}} format for from_config()
    # If config doesn't have the platform_name key, wrap it
    if platform_name not in config:
        config = {platform_name: config}

    return uploader_class.from_config(config)


class DriverPool:
    """
    Driver pool for reusing Chrome browser instances across uploads.

    This improves performance by avoiding the overhead of creating
    new browser sessions for each upload.

    Usage:
        pool = DriverPool(max_size=2)

        # Get uploader with pooled driver
        uploader = pool.get_uploader('golftimes', config)
        result = uploader.upload(title, content)

        # Release uploader back to pool
        pool.release(uploader)

        # Or use context manager for automatic release
        with pool.uploader('golftimes', config) as uploader:
            result = uploader.upload(title, content)
    """

    def __init__(self, max_size: int = 2):
        """
        Initialize driver pool.

        Args:
            max_size: Maximum number of drivers to pool per platform
        """
        self.max_size = max_size
        self._pools: dict[str, list[PlatformUploader]] = {}
        self._in_use: dict[str, set[PlatformUploader]] = {}

    def _get_pool_key(self, platform_name: str, config: dict) -> str:
        """Generate a unique key for the pool based on platform and credentials."""
        # For simplicity, we pool by platform name only
        # In production, you might want to include credential hash
        return platform_name

    def get_uploader(self, platform_name: str, config: dict) -> PlatformUploader:
        """
        Get an uploader from the pool or create a new one.

        Args:
            platform_name: Platform identifier
            config: Configuration dictionary

        Returns:
            PlatformUploader instance ready for use
        """
        pool_key = self._get_pool_key(platform_name, config)

        if pool_key not in self._pools:
            self._pools[pool_key] = []
            self._in_use[pool_key] = set()

        pool = self._pools[pool_key]

        # Try to get an existing uploader from the pool
        if pool:
            uploader = pool.pop()
            self._in_use[pool_key].add(uploader)
            return uploader

        # Create a new uploader
        uploader = create_uploader(platform_name, config)
        self._in_use[pool_key].add(uploader)
        return uploader

    def release(self, uploader: PlatformUploader) -> None:
        """
        Release an uploader back to the pool.

        Args:
            uploader: The uploader to release
        """
        pool_key = self._get_pool_key(uploader.platform_name, {})

        if pool_key in self._in_use:
            self._in_use[pool_key].discard(uploader)

            # Check if we should keep it in the pool
            if pool_key in self._pools:
                pool = self._pools[pool_key]
                if len(pool) < self.max_size:
                    # Keep the session alive for reuse
                    pool.append(uploader)
                    return

        # Close if not pooling
        uploader.close()

    def uploader(self, platform_name: str, config: dict):
        """
        Context manager for automatic uploader release.

        Args:
            platform_name: Platform identifier
            config: Configuration dictionary

        Returns:
            Context manager for the uploader
        """
        class UploaderContext:
            def __init__(self, pool: DriverPool, plat_name: str, cfg: dict):
                self.pool = pool
                self.plat_name = plat_name
                self.cfg = cfg
                self._uploader: Optional[PlatformUploader] = None

            def __enter__(self) -> PlatformUploader:
                self._uploader = self.pool.get_uploader(self.plat_name, self.cfg)
                return self._uploader

            def __exit__(self, exc_type, exc_val, exc_tb):
                if self._uploader:
                    self.pool.release(self._uploader)
                return False

        return UploaderContext(self, platform_name, config)

    def close_all(self) -> None:
        """Close all pooled drivers and clear the pool."""
        for pool in self._pools.values():
            for uploader in pool:
                uploader.close()

        for uploader_set in self._in_use.values():
            for uploader in uploader_set:
                uploader.close()

        self._pools.clear()
        self._in_use.clear()

    def __del__(self):
        """Cleanup on deletion."""
        self.close_all()
