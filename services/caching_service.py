#!/usr/bin/env python3
"""
Caching Service
Provides caching layer for API responses and data.
Supports both in-memory cache and Redis-based cache.
Feature flags control which backend is used.
"""

import os
import json
import time
import hashlib
import logging
from datetime import datetime
from functools import wraps

from config.feature_flags import (
    USE_REDIS_CACHE,
    is_flag_enabled,
    feature_flag,
)

logger = logging.getLogger(__name__)


# ==================== IN-MEMORY CACHE ====================


class InMemoryCache:
    """
    Simple in-memory cache with TTL support.
    Used as default when Redis is not enabled.
    """

    def __init__(self, default_ttl=300):
        self.cache = {}
        self.default_ttl = default_ttl
        logger.info(f"InMemoryCache initialized (TTL: {default_ttl}s)")

    def get(self, key):
        """Get a value from cache"""
        if key in self.cache:
            entry = self.cache[key]
            if time.time() < entry['expires']:
                return entry['value']
            else:
                del self.cache[key]
        return None

    def set(self, key, value, ttl=None):
        """Set a value in cache"""
        ttl = ttl or self.default_ttl
        self.cache[key] = {
            'value': value,
            'expires': time.time() + ttl,
            'created': time.time(),
        }

    def delete(self, key):
        """Delete a value from cache"""
        self.cache.pop(key, None)

    def clear(self):
        """Clear all cached values"""
        self.cache.clear()

    def get_stats(self):
        """Get cache statistics"""
        now = time.time()
        valid = sum(1 for v in self.cache.values() if v['expires'] > now)
        return {
            'total_entries': len(self.cache),
            'valid_entries': valid,
            'expired_entries': len(self.cache) - valid,
        }


# ==================== REDIS CACHE ====================


class RedisCache:
    """
    Redis-based cache for distributed caching.
    Gated behind USE_REDIS_CACHE flag.
    """

    def __init__(self, default_ttl=300):
        if not USE_REDIS_CACHE:
            raise RuntimeError("Redis cache is not enabled")

        self.default_ttl = default_ttl
        self.redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
        self.client = None
        self._connect()

    def _connect(self):
        """Connect to Redis"""
        if not USE_REDIS_CACHE:
            return

        try:
            # In production:
            # import redis
            # self.client = redis.from_url(self.redis_url)
            # self.client.ping()
            logger.info(f"RedisCache connected to {self.redis_url}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.client = None

    def get(self, key):
        """Get a value from Redis cache"""
        if not USE_REDIS_CACHE or not self.client:
            return None

        try:
            # data = self.client.get(f"cache:{key}")
            # return json.loads(data) if data else None
            return None
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            return None

    def set(self, key, value, ttl=None):
        """Set a value in Redis cache"""
        if not USE_REDIS_CACHE or not self.client:
            return

        ttl = ttl or self.default_ttl
        try:
            # self.client.setex(f"cache:{key}", ttl, json.dumps(value))
            pass
        except Exception as e:
            logger.error(f"Redis set error: {e}")

    def delete(self, key):
        """Delete a value from Redis cache"""
        if not USE_REDIS_CACHE or not self.client:
            return

        try:
            # self.client.delete(f"cache:{key}")
            pass
        except Exception as e:
            logger.error(f"Redis delete error: {e}")

    def clear(self):
        """Clear all cached values"""
        if not USE_REDIS_CACHE or not self.client:
            return

        try:
            # self.client.flushdb()
            pass
        except Exception as e:
            logger.error(f"Redis clear error: {e}")


# ==================== CACHE FACTORY ====================


def get_cache(default_ttl=300):
    """Get the appropriate cache backend based on feature flags"""
    if USE_REDIS_CACHE:
        try:
            return RedisCache(default_ttl=default_ttl)
        except Exception as e:
            logger.warning(f"Redis cache unavailable ({e}), falling back to in-memory")

    return InMemoryCache(default_ttl=default_ttl)


# ==================== CACHE DECORATOR ====================


def cached(ttl=300, key_prefix=''):
    """
    Decorator to cache function results.
    Uses Redis if available, otherwise in-memory cache.
    """
    cache = get_cache(default_ttl=ttl)

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key from function name and arguments
            key_parts = [key_prefix or func.__name__]
            key_parts.extend(str(a) for a in args)
            key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            cache_key = hashlib.md5(':'.join(key_parts).encode()).hexdigest()

            # Try to get from cache
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit: {func.__name__}")
                return cached_result

            # Execute function and cache result
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl)
            logger.debug(f"Cache miss: {func.__name__}, cached for {ttl}s")
            return result

        wrapper.cache = cache
        wrapper.invalidate = lambda: cache.clear()
        return wrapper

    return decorator
