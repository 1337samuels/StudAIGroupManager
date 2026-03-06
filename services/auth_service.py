#!/usr/bin/env python3
"""
Authentication Service
Handles multiple authentication methods gated behind feature flags.
Contains both legacy and modern auth implementations.
"""

import os
import json
import time
import hashlib
import logging
import hmac
from datetime import datetime, timedelta
from functools import wraps

from config.feature_flags import (
    ENABLE_LEGACY_AUTH,
    USE_SAML_SSO,
    ENABLE_GOOGLE_AUTH,
    USE_OAUTH2_PKCE,
    ENABLE_MFA_TOTP,
    ENABLE_API_KEY_AUTH,
    USE_JWT_TOKENS,
    LEGACY_COOKIE_FORMAT,
    V1_SESSION_MANAGEMENT,
    USE_REDIS_SESSIONS,
    is_flag_enabled,
    feature_flag,
)

logger = logging.getLogger(__name__)

# ==================== LEGACY AUTH (ADFS) ====================
# This entire section is gated behind ENABLE_LEGACY_AUTH
# TODO: Remove after migration to SAML SSO is complete (AUTH-142)


class LegacyADFSAuthenticator:
    """
    Legacy ADFS authentication handler.
    Uses the old Microsoft ADFS flow with WS-Federation.
    DEPRECATED: Use SAMLAuthenticator instead.
    """

    ADFS_ENDPOINT = "https://adfs.london.edu/adfs/ls/"
    ADFS_REALM = "urn:london:learning"

    def __init__(self):
        if not ENABLE_LEGACY_AUTH:
            raise RuntimeError(
                "Legacy ADFS auth is disabled. Use SAMLAuthenticator instead. "
                "Set ENABLE_LEGACY_AUTH=true to re-enable (not recommended)."
            )
        self.session_token = None
        self.token_expiry = None
        logger.warning("LegacyADFSAuthenticator initialized - this auth method is deprecated")

    def authenticate(self, username, password):
        """Authenticate via ADFS WS-Federation"""
        if not ENABLE_LEGACY_AUTH:
            return None

        logger.info(f"Attempting ADFS authentication for {username}")

        # Legacy: Build WS-Federation request
        ws_fed_params = {
            'wa': 'wsignin1.0',
            'wtrealm': self.ADFS_REALM,
            'wctx': f'https://learning.london.edu/login/callback',
            'username': username,
            'password': password,
        }

        # In production this would make an actual HTTP request
        # Simulated for demo purposes
        self.session_token = self._generate_legacy_token(username)
        self.token_expiry = datetime.now() + timedelta(hours=8)

        if LEGACY_COOKIE_FORMAT:
            # Old cookie format: plain text token
            # SECURITY ISSUE: Token is not encrypted
            return {
                'token': self.session_token,
                'format': 'v1_plain',
                'expires': self.token_expiry.isoformat()
            }
        else:
            # New cookie format: encrypted
            return {
                'token': self._encrypt_token(self.session_token),
                'format': 'v2_encrypted',
                'expires': self.token_expiry.isoformat()
            }

    def _generate_legacy_token(self, username):
        """Generate a legacy session token"""
        # Old token format - just a hash
        raw = f"{username}:{time.time()}:legacy_salt_v1"
        return hashlib.sha256(raw.encode()).hexdigest()

    def _encrypt_token(self, token):
        """Encrypt token for v2 cookie format"""
        # Simplified encryption for demo
        key = os.environ.get('SESSION_ENCRYPTION_KEY', 'default-key-change-me')
        return hmac.new(key.encode(), token.encode(), hashlib.sha256).hexdigest()

    def validate_session(self, token):
        """Validate a legacy session token"""
        if not ENABLE_LEGACY_AUTH:
            return False

        if V1_SESSION_MANAGEMENT:
            # v1: Check file-based session store
            return self._check_file_session(token)
        else:
            # v2: Check Redis session store
            return self._check_redis_session(token)

    def _check_file_session(self, token):
        """Check session in file-based store (legacy v1)"""
        session_file = f"sessions/{token[:16]}.json"
        try:
            if os.path.exists(session_file):
                with open(session_file, 'r') as f:
                    session_data = json.load(f)
                expiry = datetime.fromisoformat(session_data.get('expires', ''))
                return datetime.now() < expiry
        except (json.JSONDecodeError, ValueError, IOError):
            pass
        return False

    def _check_redis_session(self, token):
        """Check session in Redis store (v2)"""
        if not USE_REDIS_SESSIONS:
            logger.warning("Redis sessions not enabled, falling back to file sessions")
            return self._check_file_session(token)

        # Would use redis client here
        # import redis
        # r = redis.Redis()
        # return r.exists(f"session:{token}")
        return False


# ==================== SAML SSO AUTH ====================


class SAMLAuthenticator:
    """
    SAML-based Single Sign-On authenticator.
    Uses Azure AD as the Identity Provider.
    Gated behind USE_SAML_SSO flag.
    """

    SAML_METADATA_URL = "https://login.microsoftonline.com/{tenant}/federationmetadata/2007-06/federationmetadata.xml"
    SAML_SSO_URL = "https://login.microsoftonline.com/{tenant}/saml2"

    def __init__(self, tenant_id=None):
        if not USE_SAML_SSO:
            raise RuntimeError(
                "SAML SSO is not enabled. Set USE_SAML_SSO=true in feature flags."
            )
        self.tenant_id = tenant_id or os.environ.get('AZURE_AD_TENANT_ID', '')
        self.client_id = os.environ.get('AZURE_AD_CLIENT_ID', '')
        logger.info("SAMLAuthenticator initialized with Azure AD")

    def get_login_url(self, callback_url):
        """Generate SAML authentication request URL"""
        if not USE_SAML_SSO:
            return None

        saml_url = self.SAML_SSO_URL.format(tenant=self.tenant_id)
        return f"{saml_url}?SAMLRequest=...&RelayState={callback_url}"

    def process_saml_response(self, saml_response):
        """Process SAML assertion response from IdP"""
        if not USE_SAML_SSO:
            return None

        # Parse and validate SAML assertion
        # In production, this would use python3-saml or similar
        return {
            'user_id': 'extracted_from_saml',
            'email': 'user@london.edu',
            'groups': ['study-group-7'],
            'auth_method': 'saml_sso'
        }


# ==================== GOOGLE OAUTH ====================


class GoogleOAuthAuthenticator:
    """
    Google OAuth2 authenticator for external collaborators.
    Gated behind ENABLE_GOOGLE_AUTH flag.
    """

    GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
    GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

    def __init__(self):
        if not ENABLE_GOOGLE_AUTH:
            raise RuntimeError("Google OAuth is not enabled.")

        self.client_id = os.environ.get('GOOGLE_CLIENT_ID', '')
        self.client_secret = os.environ.get('GOOGLE_CLIENT_SECRET', '')
        self.redirect_uri = os.environ.get('GOOGLE_REDIRECT_URI', 'http://localhost:5000/auth/google/callback')

        if USE_OAUTH2_PKCE:
            logger.info("Google OAuth using PKCE flow")
            self.use_pkce = True
        else:
            logger.info("Google OAuth using standard flow")
            self.use_pkce = False

    def get_auth_url(self, state=None):
        """Generate Google OAuth authorization URL"""
        if not ENABLE_GOOGLE_AUTH:
            return None

        params = {
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'response_type': 'code',
            'scope': 'openid email profile',
            'state': state or hashlib.md5(str(time.time()).encode()).hexdigest(),
        }

        if USE_OAUTH2_PKCE:
            # PKCE flow - generate code verifier and challenge
            code_verifier = hashlib.sha256(os.urandom(32)).hexdigest()
            code_challenge = hashlib.sha256(code_verifier.encode()).hexdigest()
            params['code_challenge'] = code_challenge
            params['code_challenge_method'] = 'S256'

        query = '&'.join(f"{k}={v}" for k, v in params.items())
        return f"{self.GOOGLE_AUTH_URL}?{query}"

    def exchange_code(self, code, code_verifier=None):
        """Exchange authorization code for tokens"""
        if not ENABLE_GOOGLE_AUTH:
            return None

        token_data = {
            'code': code,
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'grant_type': 'authorization_code',
        }

        if USE_OAUTH2_PKCE and code_verifier:
            token_data['code_verifier'] = code_verifier
        else:
            token_data['client_secret'] = self.client_secret

        # In production: requests.post(self.GOOGLE_TOKEN_URL, data=token_data)
        return {'access_token': 'mock_token', 'id_token': 'mock_id_token'}


# ==================== MFA / TOTP ====================


class TOTPAuthenticator:
    """
    TOTP-based multi-factor authentication.
    Gated behind ENABLE_MFA_TOTP flag.
    """

    def __init__(self):
        if not ENABLE_MFA_TOTP:
            raise RuntimeError("TOTP MFA is not enabled.")

    def generate_secret(self, user_id):
        """Generate a TOTP secret for a user"""
        if not ENABLE_MFA_TOTP:
            return None

        # In production, use pyotp
        # import pyotp
        # return pyotp.random_base32()
        return hashlib.sha256(f"totp:{user_id}:{time.time()}".encode()).hexdigest()[:32]

    def verify_code(self, secret, code):
        """Verify a TOTP code"""
        if not ENABLE_MFA_TOTP:
            return False

        # In production:
        # import pyotp
        # totp = pyotp.TOTP(secret)
        # return totp.verify(code)
        return len(code) == 6 and code.isdigit()

    def get_provisioning_uri(self, secret, user_email):
        """Get provisioning URI for QR code generation"""
        if not ENABLE_MFA_TOTP:
            return None

        return f"otpauth://totp/LBS-StudyGroup:{user_email}?secret={secret}&issuer=LBS-StudyGroup"


# ==================== API KEY AUTH ====================


class APIKeyAuthenticator:
    """
    API key authentication for programmatic access.
    Gated behind ENABLE_API_KEY_AUTH flag.
    """

    API_KEY_PREFIX = "lbs_sg_"
    API_KEY_HEADER = "X-API-Key"

    def __init__(self):
        if not ENABLE_API_KEY_AUTH:
            raise RuntimeError("API key auth is not enabled.")

        self._api_keys = self._load_api_keys()

    def _load_api_keys(self):
        """Load valid API keys from config"""
        keys_file = os.path.join(os.path.dirname(__file__), '..', 'config', 'api_keys.json')
        try:
            if os.path.exists(keys_file):
                with open(keys_file, 'r') as f:
                    return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
        return {}

    def generate_key(self, user_id, scopes=None):
        """Generate a new API key"""
        if not ENABLE_API_KEY_AUTH:
            return None

        raw_key = f"{self.API_KEY_PREFIX}{hashlib.sha256(f'{user_id}:{time.time()}'.encode()).hexdigest()[:32]}"
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

        key_data = {
            'key_hash': key_hash,
            'user_id': user_id,
            'scopes': scopes or ['read'],
            'created': datetime.now().isoformat(),
            'active': True,
        }

        return {'api_key': raw_key, 'metadata': key_data}

    def validate_key(self, api_key):
        """Validate an API key"""
        if not ENABLE_API_KEY_AUTH:
            return None

        if not api_key or not api_key.startswith(self.API_KEY_PREFIX):
            return None

        key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        for stored_key_data in self._api_keys.values():
            if stored_key_data.get('key_hash') == key_hash and stored_key_data.get('active', False):
                return stored_key_data

        return None


# ==================== JWT TOKEN AUTH ====================


class JWTAuthenticator:
    """
    JWT token-based authentication.
    Gated behind USE_JWT_TOKENS flag.
    """

    JWT_ALGORITHM = "HS256"
    JWT_EXPIRY_HOURS = 24

    def __init__(self):
        if not USE_JWT_TOKENS:
            raise RuntimeError("JWT token auth is not enabled.")

        self.secret_key = os.environ.get('JWT_SECRET_KEY', 'change-this-secret')

    def create_token(self, user_id, email, roles=None):
        """Create a JWT token"""
        if not USE_JWT_TOKENS:
            return None

        payload = {
            'sub': user_id,
            'email': email,
            'roles': roles or ['user'],
            'iat': int(time.time()),
            'exp': int(time.time()) + (self.JWT_EXPIRY_HOURS * 3600),
        }

        # In production: import jwt; return jwt.encode(payload, self.secret_key, algorithm=self.JWT_ALGORITHM)
        # Simplified for demo
        payload_str = json.dumps(payload)
        signature = hmac.new(self.secret_key.encode(), payload_str.encode(), hashlib.sha256).hexdigest()
        return f"eyJ.{hashlib.sha256(payload_str.encode()).hexdigest()[:32]}.{signature[:32]}"

    def validate_token(self, token):
        """Validate a JWT token"""
        if not USE_JWT_TOKENS:
            return None

        # In production: import jwt; return jwt.decode(token, self.secret_key, algorithms=[self.JWT_ALGORITHM])
        parts = token.split('.')
        if len(parts) != 3:
            return None
        return {'valid': True, 'token': token}

    def refresh_token(self, token):
        """Refresh an expiring JWT token"""
        if not USE_JWT_TOKENS:
            return None

        validated = self.validate_token(token)
        if validated:
            return self.create_token(
                validated.get('sub', 'unknown'),
                validated.get('email', 'unknown@london.edu')
            )
        return None


# ==================== AUTH ROUTER ====================


def get_authenticator():
    """
    Get the appropriate authenticator based on feature flags.
    This demonstrates the complexity of having multiple auth methods
    gated behind different flags.
    """
    if USE_SAML_SSO:
        logger.info("Using SAML SSO authenticator")
        return SAMLAuthenticator()
    elif ENABLE_GOOGLE_AUTH:
        logger.info("Using Google OAuth authenticator")
        return GoogleOAuthAuthenticator()
    elif ENABLE_LEGACY_AUTH:
        logger.warning("Using LEGACY ADFS authenticator (deprecated)")
        return LegacyADFSAuthenticator()
    else:
        raise RuntimeError(
            "No authentication method is enabled! "
            "Enable at least one of: USE_SAML_SSO, ENABLE_GOOGLE_AUTH, ENABLE_LEGACY_AUTH"
        )


def require_auth(f):
    """
    Decorator to require authentication on a route.
    Uses different auth methods based on feature flags.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        from flask import request, jsonify

        # Try API key auth first if enabled
        if ENABLE_API_KEY_AUTH:
            api_key = request.headers.get('X-API-Key')
            if api_key:
                auth = APIKeyAuthenticator()
                user_data = auth.validate_key(api_key)
                if user_data:
                    kwargs['current_user'] = user_data
                    return f(*args, **kwargs)

        # Try JWT auth if enabled
        if USE_JWT_TOKENS:
            auth_header = request.headers.get('Authorization', '')
            if auth_header.startswith('Bearer '):
                token = auth_header[7:]
                auth = JWTAuthenticator()
                user_data = auth.validate_token(token)
                if user_data:
                    kwargs['current_user'] = user_data
                    return f(*args, **kwargs)

        # Fall back to session-based auth
        if V1_SESSION_MANAGEMENT:
            # Legacy: check session cookie
            session_token = request.cookies.get('session_token')
            if session_token:
                if ENABLE_LEGACY_AUTH:
                    auth = LegacyADFSAuthenticator()
                    if auth.validate_session(session_token):
                        return f(*args, **kwargs)

        return jsonify({'error': 'Authentication required'}), 401

    return decorated


# ==================== SESSION MANAGEMENT ====================


class SessionManager:
    """
    Manages user sessions with feature-flagged backends.
    """

    def __init__(self):
        if V1_SESSION_MANAGEMENT:
            self.backend = 'file'
            self.session_dir = 'sessions'
            os.makedirs(self.session_dir, exist_ok=True)
            logger.info("Using file-based session management (v1)")
        elif USE_REDIS_SESSIONS:
            self.backend = 'redis'
            logger.info("Using Redis session management")
        else:
            self.backend = 'memory'
            self._memory_store = {}
            logger.info("Using in-memory session management")

    def create_session(self, user_id, user_data):
        """Create a new session"""
        session_id = hashlib.sha256(
            f"{user_id}:{time.time()}:{os.urandom(16).hex()}".encode()
        ).hexdigest()

        session = {
            'session_id': session_id,
            'user_id': user_id,
            'user_data': user_data,
            'created': datetime.now().isoformat(),
            'expires': (datetime.now() + timedelta(hours=8)).isoformat(),
        }

        if self.backend == 'file':
            self._save_file_session(session_id, session)
        elif self.backend == 'redis':
            self._save_redis_session(session_id, session)
        else:
            self._memory_store[session_id] = session

        return session_id

    def _save_file_session(self, session_id, session):
        """Save session to file (legacy v1)"""
        filepath = os.path.join(self.session_dir, f"{session_id[:16]}.json")
        with open(filepath, 'w') as f:
            json.dump(session, f)

    def _save_redis_session(self, session_id, session):
        """Save session to Redis"""
        if not USE_REDIS_SESSIONS:
            return
        # import redis
        # r = redis.Redis()
        # r.setex(f"session:{session_id}", 28800, json.dumps(session))
        pass

    def get_session(self, session_id):
        """Retrieve a session"""
        if self.backend == 'file':
            filepath = os.path.join(self.session_dir, f"{session_id[:16]}.json")
            try:
                with open(filepath, 'r') as f:
                    return json.load(f)
            except (IOError, json.JSONDecodeError):
                return None
        elif self.backend == 'redis':
            # import redis
            # r = redis.Redis()
            # data = r.get(f"session:{session_id}")
            # return json.loads(data) if data else None
            return None
        else:
            return self._memory_store.get(session_id)

    def destroy_session(self, session_id):
        """Destroy a session"""
        if self.backend == 'file':
            filepath = os.path.join(self.session_dir, f"{session_id[:16]}.json")
            if os.path.exists(filepath):
                os.remove(filepath)
        elif self.backend == 'redis':
            pass  # r.delete(f"session:{session_id}")
        else:
            self._memory_store.pop(session_id, None)
