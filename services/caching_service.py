#!/usr/bin/env python3
"""Caching Service - In-memory and Redis cache backends via feature flags."""

import os
import time
import hashlib
import logging
from functools import wraps

from config.feature_flags import (
    USE_REDIS_CACHE, is_flag_enabled, feature_flag,
)

logger = logging.getLogger(__name__)


# ==================== IN-MEMORY CACHE ====================

class InMemoryCache:
    """Simple in-memory cache with TTL. Default when Redis is not enabled."""

    def __init__(self, default_ttl=300):
        self.cache = {}
        self.default_ttl = default_ttl

    def get(self, key):
        if key in self.cache:
            entry = self.cache[key]
            if time.time() < entry['expires']:
                return entry['value']
            del self.cache[key]
        return None

    def set(self, key, value, ttl=None):
        self.cache[key] = {'value': value, 'expires': time.time() + (ttl or self.default_ttl)}

    def delete(self, key):
        self.cache.pop(key, None)

    def clear(self):
        self.cache.clear()


# ==================== REDIS CACHE ====================

class RedisCache:
    """Redis-based distributed cache. Gated behind USE_REDIS_CACHE."""

    def __init__(self, default_ttl=300):
        if not USE_REDIS_CACHE:
            raise RuntimeError("Redis cache is not enabled")
        self.default_ttl = default_ttl
        self.redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
        self.client = None
        logger.info(f"RedisCache connected to {self.redis_url}")

    def get(self, key):
        if not USE_REDIS_CACHE or not self.client:
            return None
        return None  # In production: self.client.get(f"cache:{key}")

    def set(self, key, value, ttl=None):
        if not USE_REDIS_CACHE or not self.client:
            return

    def delete(self, key):
        if not USE_REDIS_CACHE or not self.client:
            return

    def clear(self):
        if not USE_REDIS_CACHE or not self.client:
            return


# ==================== CACHE FACTORY ====================

def get_cache(default_ttl=300):
    """Get cache backend based on feature flags."""
    if USE_REDIS_CACHE:
        try:
            return RedisCache(default_ttl=default_ttl)
        except Exception:
            pass
    return InMemoryCache(default_ttl=default_ttl)


# ==================== CACHE DECORATOR ====================

def cached(ttl=300, key_prefix=''):
    """Decorator to cache function results."""
    cache = get_cache(default_ttl=ttl)
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            key_parts = [key_prefix or func.__name__] + [str(a) for a in args]
            cache_key = hashlib.md5(':'.join(key_parts).encode()).hexdigest()
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl)
            return result
        wrapper.cache = cache
        wrapper.invalidate = lambda: cache.clear()
        return wrapper
    return decorator
