#!/usr/bin/env python3
"""
Feature Flag Management System
Centralized feature flag configuration with support for:
- JSON file-based flags
- Environment variable overrides
- Percentage-based rollouts
- Legacy flag detection
"""

import os
import json
import hashlib
import logging
from datetime import datetime
from functools import lru_cache

logger = logging.getLogger(__name__)

# ==================== HARDCODED LEGACY FLAGS ====================
# These flags are hardcoded and should have been cleaned up long ago.
# They were originally part of the v1 system before the config file was introduced.

ENABLE_LEGACY_AUTH = True  # TODO: Remove - ticket AUTH-142 from 2023
USE_SOAP_API = False  # SOAP endpoint decommissioned March 2024
ENABLE_V1_DASHBOARD = False  # v1 dashboard deleted, flag still checked in 3 places
LEGACY_COOKIE_FORMAT = True  # Blocking encrypted cookie migration
V1_SESSION_MANAGEMENT = True  # Should use Redis sessions instead
ENABLE_OLD_REPORT_FORMAT = False  # Old verbose report format, 3x larger
ENABLE_SOAP_CALENDAR_SYNC = False  # Exchange SOAP API sunsetted
LEGACY_MEMBER_SYNC = False  # CSV-based sync replaced by Canvas API
ENABLE_DEPRECATED_NOTIFICATIONS = False  # SMS gateway expired Dec 2024
USE_LEGACY_ROOM_API = False  # XML-based room API v1
USE_LEGACY_WEBSCRAPER = True  # Original Selenium scraper, should use Canvas API

# ==================== ENVIRONMENT VARIABLE FLAGS ====================
# These flags can be overridden via environment variables

ENABLE_DARK_MODE = os.environ.get('FEATURE_DARK_MODE', 'true').lower() == 'true'
ENABLE_RATE_LIMITING = os.environ.get('FEATURE_RATE_LIMITING', 'true').lower() == 'true'
ENABLE_REQUEST_LOGGING = os.environ.get('FEATURE_REQUEST_LOGGING', 'true').lower() == 'true'
ENABLE_SENTRY_INTEGRATION = os.environ.get('FEATURE_SENTRY', 'true').lower() == 'true'
DEBUG_SQL_QUERIES = os.environ.get('FEATURE_DEBUG_SQL', 'false').lower() == 'true'
USE_HEADLESS_BROWSER = os.environ.get('FEATURE_HEADLESS', 'false').lower() == 'true'
ENABLE_PROMETHEUS_METRICS = os.environ.get('FEATURE_PROMETHEUS', 'false').lower() == 'true'

# ==================== FEATURE FLAG CLASS ====================


class FeatureFlagManager:
    """Manages feature flags from JSON config with environment variable overrides"""

    _instance = None
    _flags = {}
    _config_path = None
    _last_loaded = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._flags:
            self._load_flags()

    def _load_flags(self):
        """Load feature flags from JSON config file"""
        config_paths = [
            os.path.join(os.path.dirname(__file__), 'feature_flags.json'),
            os.path.join(os.path.dirname(__file__), '..', 'feature_flags.json'),
            os.environ.get('FEATURE_FLAGS_CONFIG', ''),
        ]

        for path in config_paths:
            if path and os.path.exists(path):
                try:
                    with open(path, 'r') as f:
                        config = json.load(f)
                    self._flags = config.get('flags', {})
                    self._config_path = path
                    self._last_loaded = datetime.now()
                    logger.info(f"Loaded {len(self._flags)} feature flags from {path}")
                    return
                except (json.JSONDecodeError, IOError) as e:
                    logger.error(f"Failed to load feature flags from {path}: {e}")

        logger.warning("No feature flags config file found, using defaults")
        self._flags = {}

    def is_enabled(self, flag_name, user_id=None):
        """
        Check if a feature flag is enabled.

        Args:
            flag_name: Name of the feature flag
            user_id: Optional user ID for percentage-based rollouts

        Returns:
            bool: Whether the flag is enabled
        """
        # Check environment variable override first
        env_key = f"FF_{flag_name}"
        env_value = os.environ.get(env_key)
        if env_value is not None:
            return env_value.lower() in ('true', '1', 'yes', 'on')

        # Check JSON config
        flag_config = self._flags.get(flag_name, {})
        if not flag_config:
            # Check module-level hardcoded flags as fallback
            return globals().get(flag_name, False)

        # Check if globally disabled
        if not flag_config.get('enabled', False):
            return False

        # Check percentage-based rollout
        rollout_pct = flag_config.get('rollout_percentage', 100)
        if rollout_pct < 100 and user_id:
            # Deterministic hash-based rollout
            hash_input = f"{flag_name}:{user_id}"
            hash_value = int(hashlib.md5(hash_input.encode()).hexdigest(), 16) % 100
            return hash_value < rollout_pct

        return flag_config.get('enabled', False)

    def get_flag_config(self, flag_name):
        """Get full configuration for a flag"""
        return self._flags.get(flag_name, {})

    def get_all_flags(self):
        """Get all flag configurations"""
        return dict(self._flags)

    def get_flags_by_category(self, category):
        """Get all flags in a specific category"""
        return {
            name: config
            for name, config in self._flags.items()
            if config.get('category') == category
        }

    def get_legacy_flags(self):
        """Get all flags that appear to be legacy/deprecated"""
        legacy = {}
        for name, config in self._flags.items():
            notes = config.get('notes', '').lower()
            if any(keyword in notes for keyword in ['deprecated', 'remove', 'legacy', 'dead', 'old']):
                legacy[name] = config
        return legacy

    def reload(self):
        """Force reload flags from config file"""
        self._flags = {}
        self._load_flags()


# Singleton instance
_flag_manager = None


def get_flag_manager():
    """Get the singleton FeatureFlagManager instance"""
    global _flag_manager
    if _flag_manager is None:
        _flag_manager = FeatureFlagManager()
    return _flag_manager


def is_flag_enabled(flag_name, user_id=None):
    """Convenience function to check if a flag is enabled"""
    return get_flag_manager().is_enabled(flag_name, user_id)


# ==================== DECORATOR FOR FEATURE-GATED FUNCTIONS ====================


def feature_flag(flag_name, fallback=None):
    """
    Decorator to gate a function behind a feature flag.

    Usage:
        @feature_flag('ENABLE_NEW_FEATURE')
        def my_new_feature():
            ...

        @feature_flag('ENABLE_NEW_FEATURE', fallback=old_feature_func)
        def my_new_feature():
            ...
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            if is_flag_enabled(flag_name):
                return func(*args, **kwargs)
            elif fallback:
                return fallback(*args, **kwargs)
            else:
                logger.debug(f"Feature '{flag_name}' is disabled, skipping {func.__name__}")
                return None
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper
    return decorator


# ==================== INLINE FLAG CHECKS (used throughout codebase) ====================
# These are convenience booleans loaded at import time.
# WARNING: These won't update if flags are changed at runtime.

_fm = get_flag_manager()

ENABLE_GOOGLE_AUTH = _fm.is_enabled('ENABLE_GOOGLE_AUTH')
USE_SAML_SSO = _fm.is_enabled('USE_SAML_SSO')
USE_OAUTH2_PKCE = _fm.is_enabled('USE_OAUTH2_PKCE')
ENABLE_MFA_TOTP = _fm.is_enabled('ENABLE_MFA_TOTP')
ENABLE_API_KEY_AUTH = _fm.is_enabled('ENABLE_API_KEY_AUTH')
USE_JWT_TOKENS = _fm.is_enabled('USE_JWT_TOKENS')
USE_REDIS_SESSIONS = _fm.is_enabled('USE_REDIS_SESSIONS')
ENABLE_V2_DASHBOARD = _fm.is_enabled('ENABLE_V2_DASHBOARD')
ENABLE_V3_DASHBOARD_BETA = _fm.is_enabled('ENABLE_V3_DASHBOARD_BETA')
AB_NEW_BOOKING_UI = _fm.is_enabled('AB_NEW_BOOKING_UI')
AB_AI_MODEL_GPT4 = _fm.is_enabled('AB_AI_MODEL_GPT4')
AB_WEEKLY_DIGEST_EMAIL = _fm.is_enabled('AB_WEEKLY_DIGEST_EMAIL')
USE_OPENAI_DIRECT = _fm.is_enabled('USE_OPENAI_DIRECT')
ENABLE_LOCAL_LLM_FALLBACK = _fm.is_enabled('ENABLE_LOCAL_LLM_FALLBACK')
ENABLE_AI_STUDY_RECOMMENDATIONS = _fm.is_enabled('ENABLE_AI_STUDY_RECOMMENDATIONS')
ENABLE_AI_CONFLICT_RESOLUTION = _fm.is_enabled('ENABLE_AI_CONFLICT_RESOLUTION')
ENABLE_SLACK_NOTIFICATIONS = _fm.is_enabled('ENABLE_SLACK_NOTIFICATIONS')
ENABLE_EMAIL_NOTIFICATIONS = _fm.is_enabled('ENABLE_EMAIL_NOTIFICATIONS')
ENABLE_PUSH_NOTIFICATIONS = _fm.is_enabled('ENABLE_PUSH_NOTIFICATIONS')
ENABLE_WHATSAPP_NOTIFICATIONS = _fm.is_enabled('ENABLE_WHATSAPP_NOTIFICATIONS')
ENABLE_REAL_TIME_COLLABORATION = _fm.is_enabled('ENABLE_REAL_TIME_COLLABORATION')
USE_NEW_SCHEDULING_ALGORITHM = _fm.is_enabled('USE_NEW_SCHEDULING_ALGORITHM')
ENABLE_MOBILE_API = _fm.is_enabled('ENABLE_MOBILE_API')
ENABLE_GRAPHQL_API = _fm.is_enabled('ENABLE_GRAPHQL_API')
ENABLE_ANALYTICS_DASHBOARD = _fm.is_enabled('ENABLE_ANALYTICS_DASHBOARD')
ENABLE_EXPORT_TO_PDF = _fm.is_enabled('ENABLE_EXPORT_TO_PDF')
ENABLE_BULK_ROOM_BOOKING = _fm.is_enabled('ENABLE_BULK_ROOM_BOOKING')
ENABLE_RECURRING_BOOKINGS = _fm.is_enabled('ENABLE_RECURRING_BOOKINGS')
USE_REDIS_CACHE = _fm.is_enabled('USE_REDIS_CACHE')
ENABLE_CANVAS_LMS_INTEGRATION = _fm.is_enabled('ENABLE_CANVAS_LMS_INTEGRATION')
ENABLE_GRAPH_CALENDAR_SYNC = _fm.is_enabled('ENABLE_GRAPH_CALENDAR_SYNC')
ENABLE_GOOGLE_CALENDAR_SYNC = _fm.is_enabled('ENABLE_GOOGLE_CALENDAR_SYNC')
ENABLE_ASSIGNMENT_PRIORITY_SCORING = _fm.is_enabled('ENABLE_ASSIGNMENT_PRIORITY_SCORING')
ENABLE_STUDY_STREAK_TRACKING = _fm.is_enabled('ENABLE_STUDY_STREAK_TRACKING')
ENABLE_PEER_REVIEW_SYSTEM = _fm.is_enabled('ENABLE_PEER_REVIEW_SYSTEM')
ENABLE_MULTI_LANGUAGE_SUPPORT = _fm.is_enabled('ENABLE_MULTI_LANGUAGE_SUPPORT')
ENABLE_ACCESSIBILITY_MODE = _fm.is_enabled('ENABLE_ACCESSIBILITY_MODE')
ENABLE_FILE_SHARING = _fm.is_enabled('ENABLE_FILE_SHARING')
ENABLE_VIDEO_CONFERENCING = _fm.is_enabled('ENABLE_VIDEO_CONFERENCING')
