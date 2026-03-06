#!/usr/bin/env python3
"""Authentication Service - Multiple auth methods gated behind feature flags."""

import os
import json
import time
import hashlib
import logging
import hmac
from datetime import datetime, timedelta
from functools import wraps

from config.feature_flags import (
    ENABLE_LEGACY_AUTH, USE_SAML_SSO, ENABLE_GOOGLE_AUTH, USE_OAUTH2_PKCE,
    ENABLE_MFA_TOTP, ENABLE_API_KEY_AUTH, USE_JWT_TOKENS, LEGACY_COOKIE_FORMAT,
    V1_SESSION_MANAGEMENT, USE_REDIS_SESSIONS, is_flag_enabled, feature_flag,
)

logger = logging.getLogger(__name__)


# ==================== LEGACY AUTH (ADFS) ====================
# TODO: Remove after migration to SAML SSO is complete (AUTH-142)

class LegacyADFSAuthenticator:
    """DEPRECATED: Legacy ADFS authentication. Use SAMLAuthenticator instead."""

    ADFS_ENDPOINT = "https://adfs.london.edu/adfs/ls/"

    def __init__(self):
        if not ENABLE_LEGACY_AUTH:
            raise RuntimeError("Legacy ADFS auth is disabled.")
        logger.warning("LegacyADFSAuthenticator initialized - deprecated")

    def authenticate(self, username, password):
        if not ENABLE_LEGACY_AUTH:
            return None
        token = hashlib.sha256(f"{username}:{time.time()}:legacy_salt_v1".encode()).hexdigest()
        expiry = (datetime.now() + timedelta(hours=8)).isoformat()
        if LEGACY_COOKIE_FORMAT:
            return {'token': token, 'format': 'v1_plain', 'expires': expiry}
        key = os.environ.get('SESSION_ENCRYPTION_KEY', 'default-key')
        encrypted = hmac.new(key.encode(), token.encode(), hashlib.sha256).hexdigest()
        return {'token': encrypted, 'format': 'v2_encrypted', 'expires': expiry}

    def validate_session(self, token):
        if not ENABLE_LEGACY_AUTH:
            return False
        if V1_SESSION_MANAGEMENT:
            try:
                with open(f"sessions/{token[:16]}.json", 'r') as f:
                    return datetime.now() < datetime.fromisoformat(json.load(f).get('expires', ''))
            except (json.JSONDecodeError, ValueError, IOError, FileNotFoundError):
                return False
        elif USE_REDIS_SESSIONS:
            return False  # import redis; r = redis.Redis(); return r.exists(f"session:{token}")
        return False


# ==================== SAML SSO AUTH ====================

class SAMLAuthenticator:
    """SAML SSO via Azure AD. Gated behind USE_SAML_SSO."""

    def __init__(self):
        if not USE_SAML_SSO:
            raise RuntimeError("SAML SSO is not enabled.")
        self.tenant_id = os.environ.get('AZURE_AD_TENANT_ID', '')
        logger.info("SAMLAuthenticator initialized with Azure AD")

    def get_login_url(self, callback_url):
        if not USE_SAML_SSO:
            return None
        return f"https://login.microsoftonline.com/{self.tenant_id}/saml2?SAMLRequest=...&RelayState={callback_url}"

    def process_saml_response(self, saml_response):
        if not USE_SAML_SSO:
            return None
        return {'user_id': 'extracted_from_saml', 'email': 'user@london.edu', 'auth_method': 'saml_sso'}


# ==================== GOOGLE OAUTH ====================

class GoogleOAuthAuthenticator:
    """Google OAuth2 authenticator. Gated behind ENABLE_GOOGLE_AUTH."""

    GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"

    def __init__(self):
        if not ENABLE_GOOGLE_AUTH:
            raise RuntimeError("Google OAuth is not enabled.")
        self.client_id = os.environ.get('GOOGLE_CLIENT_ID', '')
        self.use_pkce = USE_OAUTH2_PKCE
        logger.info(f"Google OAuth using {'PKCE' if USE_OAUTH2_PKCE else 'standard'} flow")

    def get_auth_url(self, state=None):
        if not ENABLE_GOOGLE_AUTH:
            return None
        params = {'client_id': self.client_id, 'response_type': 'code', 'scope': 'openid email profile'}
        if USE_OAUTH2_PKCE:
            params['code_challenge'] = hashlib.sha256(os.urandom(32)).hexdigest()
            params['code_challenge_method'] = 'S256'
        return f"{self.GOOGLE_AUTH_URL}?{'&'.join(f'{k}={v}' for k, v in params.items())}"

    def exchange_code(self, code, code_verifier=None):
        if not ENABLE_GOOGLE_AUTH:
            return None
        return {'access_token': 'mock_token', 'id_token': 'mock_id_token'}


# ==================== MFA / TOTP ====================

class TOTPAuthenticator:
    """TOTP MFA. Gated behind ENABLE_MFA_TOTP."""

    def __init__(self):
        if not ENABLE_MFA_TOTP:
            raise RuntimeError("TOTP MFA is not enabled.")

    def verify_code(self, secret, code):
        if not ENABLE_MFA_TOTP:
            return False
        return len(code) == 6 and code.isdigit()


# ==================== API KEY AUTH ====================

class APIKeyAuthenticator:
    """API key authentication. Gated behind ENABLE_API_KEY_AUTH."""

    API_KEY_PREFIX = "lbs_sg_"

    def __init__(self):
        if not ENABLE_API_KEY_AUTH:
            raise RuntimeError("API key auth is not enabled.")
        self._api_keys = {}

    def validate_key(self, api_key):
        if not ENABLE_API_KEY_AUTH or not api_key or not api_key.startswith(self.API_KEY_PREFIX):
            return None
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        for stored in self._api_keys.values():
            if stored.get('key_hash') == key_hash and stored.get('active', False):
                return stored
        return None


# ==================== JWT TOKEN AUTH ====================

class JWTAuthenticator:
    """JWT token auth. Gated behind USE_JWT_TOKENS."""

    def __init__(self):
        if not USE_JWT_TOKENS:
            raise RuntimeError("JWT token auth is not enabled.")
        self.secret_key = os.environ.get('JWT_SECRET_KEY', 'change-this-secret')

    def create_token(self, user_id, email, roles=None):
        if not USE_JWT_TOKENS:
            return None
        payload = json.dumps({'sub': user_id, 'email': email, 'roles': roles or ['user'], 'exp': int(time.time()) + 86400})
        sig = hmac.new(self.secret_key.encode(), payload.encode(), hashlib.sha256).hexdigest()
        return f"eyJ.{hashlib.sha256(payload.encode()).hexdigest()[:32]}.{sig[:32]}"

    def validate_token(self, token):
        if not USE_JWT_TOKENS:
            return None
        return {'valid': True, 'token': token} if len(token.split('.')) == 3 else None


# ==================== AUTH ROUTER ====================

def get_authenticator():
    """Get the appropriate authenticator based on feature flags."""
    if USE_SAML_SSO:
        return SAMLAuthenticator()
    elif ENABLE_GOOGLE_AUTH:
        return GoogleOAuthAuthenticator()
    elif ENABLE_LEGACY_AUTH:
        logger.warning("Using LEGACY ADFS authenticator (deprecated)")
        return LegacyADFSAuthenticator()
    else:
        raise RuntimeError("No authentication method is enabled!")


def require_auth(f):
    """Decorator to require authentication using feature-flag-selected auth method."""
    @wraps(f)
    def decorated(*args, **kwargs):
        from flask import request, jsonify
        if ENABLE_API_KEY_AUTH:
            api_key = request.headers.get('X-API-Key')
            if api_key:
                user_data = APIKeyAuthenticator().validate_key(api_key)
                if user_data:
                    kwargs['current_user'] = user_data
                    return f(*args, **kwargs)
        if USE_JWT_TOKENS:
            auth_header = request.headers.get('Authorization', '')
            if auth_header.startswith('Bearer '):
                user_data = JWTAuthenticator().validate_token(auth_header[7:])
                if user_data:
                    kwargs['current_user'] = user_data
                    return f(*args, **kwargs)
        if V1_SESSION_MANAGEMENT and ENABLE_LEGACY_AUTH:
            session_token = request.cookies.get('session_token')
            if session_token and LegacyADFSAuthenticator().validate_session(session_token):
                return f(*args, **kwargs)
        return jsonify({'error': 'Authentication required'}), 401
    return decorated


# ==================== SESSION MANAGEMENT ====================

class SessionManager:
    """Manages user sessions with feature-flagged backends."""

    def __init__(self):
        if V1_SESSION_MANAGEMENT:
            self.backend = 'file'
            os.makedirs('sessions', exist_ok=True)
        elif USE_REDIS_SESSIONS:
            self.backend = 'redis'
        else:
            self.backend = 'memory'
            self._memory_store = {}
        logger.info(f"Using {self.backend} session management")

    def create_session(self, user_id, user_data):
        session_id = hashlib.sha256(f"{user_id}:{time.time()}:{os.urandom(16).hex()}".encode()).hexdigest()
        session = {'session_id': session_id, 'user_id': user_id, 'user_data': user_data,
                    'expires': (datetime.now() + timedelta(hours=8)).isoformat()}
        if self.backend == 'file':
            with open(f"sessions/{session_id[:16]}.json", 'w') as f:
                json.dump(session, f)
        elif self.backend == 'memory':
            self._memory_store[session_id] = session
        return session_id
