#!/usr/bin/env python3
"""
Request Middleware
Handles cross-cutting concerns like rate limiting, logging, metrics, and error tracking.
All middleware is gated behind feature flags.
"""

import os
import time
import json
import logging
import hashlib
from datetime import datetime, timedelta
from collections import defaultdict
from functools import wraps

from config.feature_flags import (
    ENABLE_RATE_LIMITING,
    ENABLE_REQUEST_LOGGING,
    ENABLE_PROMETHEUS_METRICS,
    ENABLE_SENTRY_INTEGRATION,
    DEBUG_SQL_QUERIES,
    is_flag_enabled,
)

logger = logging.getLogger(__name__)


# ==================== RATE LIMITING ====================


class RateLimiter:
    """
    API rate limiting middleware.
    Gated behind ENABLE_RATE_LIMITING flag.
    """

    DEFAULT_LIMIT = 100  # requests per minute
    DEFAULT_WINDOW = 60  # seconds

    def __init__(self, limit=None, window=None):
        if not ENABLE_RATE_LIMITING:
            logger.debug("Rate limiting is disabled")
            return

        self.limit = limit or int(os.environ.get('RATE_LIMIT', str(self.DEFAULT_LIMIT)))
        self.window = window or int(os.environ.get('RATE_LIMIT_WINDOW', str(self.DEFAULT_WINDOW)))
        self.request_counts = defaultdict(list)
        logger.info(f"RateLimiter initialized: {self.limit} req/{self.window}s")

    def is_allowed(self, client_id):
        """Check if a request is allowed under rate limits"""
        if not ENABLE_RATE_LIMITING:
            return True

        now = time.time()
        window_start = now - self.window

        # Clean old entries
        self.request_counts[client_id] = [
            ts for ts in self.request_counts[client_id]
            if ts > window_start
        ]

        # Check limit
        if len(self.request_counts[client_id]) >= self.limit:
            logger.warning(f"Rate limit exceeded for client {client_id}")
            return False

        self.request_counts[client_id].append(now)
        return True

    def get_remaining(self, client_id):
        """Get remaining requests in current window"""
        if not ENABLE_RATE_LIMITING:
            return float('inf')

        now = time.time()
        window_start = now - self.window
        current = len([
            ts for ts in self.request_counts.get(client_id, [])
            if ts > window_start
        ])
        return max(0, self.limit - current)

    def get_reset_time(self, client_id):
        """Get time until rate limit resets"""
        if not ENABLE_RATE_LIMITING:
            return 0

        entries = self.request_counts.get(client_id, [])
        if not entries:
            return 0

        oldest = min(entries)
        return max(0, oldest + self.window - time.time())


def rate_limit_decorator(limit=100, window=60):
    """Decorator to apply rate limiting to a route"""
    limiter = RateLimiter(limit=limit, window=window)

    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not ENABLE_RATE_LIMITING:
                return f(*args, **kwargs)

            from flask import request, jsonify
            client_id = request.remote_addr or 'unknown'

            if not limiter.is_allowed(client_id):
                remaining = limiter.get_remaining(client_id)
                reset = limiter.get_reset_time(client_id)
                return jsonify({
                    'error': 'Rate limit exceeded',
                    'limit': limiter.limit,
                    'remaining': remaining,
                    'reset_in': round(reset, 1),
                }), 429

            return f(*args, **kwargs)

        return decorated
    return decorator


# ==================== REQUEST LOGGING ====================


class RequestLogger:
    """
    Detailed request logging middleware.
    Gated behind ENABLE_REQUEST_LOGGING flag.
    """

    def __init__(self):
        if not ENABLE_REQUEST_LOGGING:
            logger.debug("Request logging is disabled")
            return

        self.log_file = os.environ.get('REQUEST_LOG_FILE', 'logs/requests.log')
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
        self.request_count = 0
        logger.info(f"RequestLogger initialized, logging to {self.log_file}")

    def log_request(self, request, response=None, duration_ms=None):
        """Log an API request"""
        if not ENABLE_REQUEST_LOGGING:
            return

        self.request_count += 1

        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'request_id': self.request_count,
            'method': request.method,
            'path': request.path,
            'remote_addr': request.remote_addr,
            'user_agent': request.headers.get('User-Agent', 'unknown'),
            'content_type': request.content_type,
            'content_length': request.content_length,
        }

        if response:
            log_entry['status_code'] = response.status_code
            log_entry['response_size'] = response.content_length

        if duration_ms is not None:
            log_entry['duration_ms'] = round(duration_ms, 2)

        # Write to log file
        try:
            with open(self.log_file, 'a') as f:
                f.write(json.dumps(log_entry) + '\n')
        except IOError as e:
            logger.error(f"Failed to write request log: {e}")

        # Also log slow requests
        if duration_ms and duration_ms > 1000:
            logger.warning(f"Slow request: {request.method} {request.path} took {duration_ms:.0f}ms")

    def get_stats(self):
        """Get request statistics"""
        if not ENABLE_REQUEST_LOGGING:
            return {}

        return {
            'total_requests': self.request_count,
            'log_file': self.log_file,
        }


# ==================== PROMETHEUS METRICS ====================


class PrometheusMetrics:
    """
    Export application metrics in Prometheus format.
    Gated behind ENABLE_PROMETHEUS_METRICS flag.
    """

    def __init__(self):
        if not ENABLE_PROMETHEUS_METRICS:
            logger.debug("Prometheus metrics are disabled")
            return

        self.counters = defaultdict(int)
        self.histograms = defaultdict(list)
        self.gauges = {}
        logger.info("PrometheusMetrics initialized")

    def increment_counter(self, name, labels=None):
        """Increment a counter metric"""
        if not ENABLE_PROMETHEUS_METRICS:
            return

        key = self._make_key(name, labels)
        self.counters[key] += 1

    def observe_histogram(self, name, value, labels=None):
        """Record a histogram observation"""
        if not ENABLE_PROMETHEUS_METRICS:
            return

        key = self._make_key(name, labels)
        self.histograms[key].append(value)

    def set_gauge(self, name, value, labels=None):
        """Set a gauge value"""
        if not ENABLE_PROMETHEUS_METRICS:
            return

        key = self._make_key(name, labels)
        self.gauges[key] = value

    def _make_key(self, name, labels=None):
        """Create a metric key from name and labels"""
        if labels:
            label_str = ','.join(f'{k}="{v}"' for k, v in sorted(labels.items()))
            return f'{name}{{{label_str}}}'
        return name

    def export(self):
        """Export metrics in Prometheus text format"""
        if not ENABLE_PROMETHEUS_METRICS:
            return ""

        lines = []

        for key, value in self.counters.items():
            lines.append(f"# TYPE {key.split('{')[0]} counter")
            lines.append(f"{key} {value}")

        for key, values in self.histograms.items():
            name = key.split('{')[0]
            lines.append(f"# TYPE {name} histogram")
            lines.append(f"{key}_count {len(values)}")
            if values:
                lines.append(f"{key}_sum {sum(values)}")

        for key, value in self.gauges.items():
            lines.append(f"# TYPE {key.split('{')[0]} gauge")
            lines.append(f"{key} {value}")

        return '\n'.join(lines)


# ==================== SENTRY ERROR TRACKING ====================


class SentryIntegration:
    """
    Error tracking via Sentry.
    Gated behind ENABLE_SENTRY_INTEGRATION flag.
    """

    def __init__(self):
        if not ENABLE_SENTRY_INTEGRATION:
            logger.debug("Sentry integration is disabled")
            return

        self.dsn = os.environ.get('SENTRY_DSN', '')
        self.environment = os.environ.get('SENTRY_ENVIRONMENT', 'production')
        self.initialized = False

        if self.dsn:
            self._initialize()
        else:
            logger.warning("Sentry DSN not configured")

    def _initialize(self):
        """Initialize Sentry SDK"""
        if not ENABLE_SENTRY_INTEGRATION:
            return

        try:
            # In production:
            # import sentry_sdk
            # from sentry_sdk.integrations.flask import FlaskIntegration
            # sentry_sdk.init(
            #     dsn=self.dsn,
            #     environment=self.environment,
            #     integrations=[FlaskIntegration()],
            #     traces_sample_rate=0.1,
            # )
            self.initialized = True
            logger.info(f"Sentry initialized for environment: {self.environment}")
        except Exception as e:
            logger.error(f"Failed to initialize Sentry: {e}")

    def capture_exception(self, exception, context=None):
        """Capture an exception to Sentry"""
        if not ENABLE_SENTRY_INTEGRATION or not self.initialized:
            return

        # In production: sentry_sdk.capture_exception(exception)
        logger.error(f"Sentry: Captured exception: {exception}")

    def capture_message(self, message, level='info'):
        """Send a message to Sentry"""
        if not ENABLE_SENTRY_INTEGRATION or not self.initialized:
            return

        # In production: sentry_sdk.capture_message(message, level=level)
        logger.info(f"Sentry: {level}: {message}")

    def set_user(self, user_data):
        """Set user context for Sentry"""
        if not ENABLE_SENTRY_INTEGRATION or not self.initialized:
            return

        # In production: sentry_sdk.set_user(user_data)
        pass


# ==================== SQL QUERY DEBUGGING ====================


class SQLQueryDebugger:
    """
    Debug SQL queries with execution timing.
    Gated behind DEBUG_SQL_QUERIES flag.
    Development only - should never be enabled in production.
    """

    def __init__(self):
        if not DEBUG_SQL_QUERIES:
            return

        self.queries = []
        self.slow_query_threshold_ms = 100
        logger.warning("SQL Query Debugging enabled - DO NOT USE IN PRODUCTION")

    def log_query(self, query, params=None, duration_ms=None):
        """Log a SQL query"""
        if not DEBUG_SQL_QUERIES:
            return

        entry = {
            'query': query,
            'params': params,
            'duration_ms': duration_ms,
            'timestamp': datetime.now().isoformat(),
        }

        self.queries.append(entry)

        if duration_ms and duration_ms > self.slow_query_threshold_ms:
            logger.warning(f"SLOW QUERY ({duration_ms:.0f}ms): {query[:100]}")

    def get_query_log(self):
        """Get all logged queries"""
        if not DEBUG_SQL_QUERIES:
            return []
        return self.queries

    def get_slow_queries(self):
        """Get queries exceeding the slow query threshold"""
        if not DEBUG_SQL_QUERIES:
            return []
        return [
            q for q in self.queries
            if q.get('duration_ms', 0) > self.slow_query_threshold_ms
        ]

    def get_stats(self):
        """Get query statistics"""
        if not DEBUG_SQL_QUERIES:
            return {}

        durations = [q.get('duration_ms', 0) for q in self.queries if q.get('duration_ms')]
        return {
            'total_queries': len(self.queries),
            'slow_queries': len(self.get_slow_queries()),
            'avg_duration_ms': sum(durations) / len(durations) if durations else 0,
            'max_duration_ms': max(durations) if durations else 0,
        }


# ==================== MIDDLEWARE SETUP ====================


def setup_middleware(app):
    """
    Setup all middleware on the Flask app based on feature flags.
    Call this during app initialization.
    """
    request_logger = None
    prometheus = None
    sentry = None
    rate_limiter = None

    if ENABLE_REQUEST_LOGGING:
        request_logger = RequestLogger()

    if ENABLE_PROMETHEUS_METRICS:
        prometheus = PrometheusMetrics()

    if ENABLE_SENTRY_INTEGRATION:
        sentry = SentryIntegration()

    if ENABLE_RATE_LIMITING:
        rate_limiter = RateLimiter()

    @app.before_request
    def before_request():
        from flask import request, g
        g.request_start_time = time.time()

        # Rate limiting
        if ENABLE_RATE_LIMITING and rate_limiter:
            client_id = request.remote_addr or 'unknown'
            if not rate_limiter.is_allowed(client_id):
                from flask import jsonify
                return jsonify({'error': 'Rate limit exceeded'}), 429

    @app.after_request
    def after_request(response):
        from flask import request, g

        duration_ms = (time.time() - getattr(g, 'request_start_time', time.time())) * 1000

        # Request logging
        if ENABLE_REQUEST_LOGGING and request_logger:
            request_logger.log_request(request, response, duration_ms)

        # Prometheus metrics
        if ENABLE_PROMETHEUS_METRICS and prometheus:
            prometheus.increment_counter('http_requests_total', {
                'method': request.method,
                'path': request.path,
                'status': str(response.status_code),
            })
            prometheus.observe_histogram('http_request_duration_ms', duration_ms, {
                'method': request.method,
                'path': request.path,
            })

        # Add rate limit headers
        if ENABLE_RATE_LIMITING and rate_limiter:
            client_id = request.remote_addr or 'unknown'
            response.headers['X-RateLimit-Limit'] = str(rate_limiter.limit)
            response.headers['X-RateLimit-Remaining'] = str(rate_limiter.get_remaining(client_id))

        return response

    @app.errorhandler(Exception)
    def handle_error(error):
        # Sentry error tracking
        if ENABLE_SENTRY_INTEGRATION and sentry:
            sentry.capture_exception(error)

        from flask import jsonify
        return jsonify({'error': str(error)}), 500

    # Prometheus metrics endpoint
    if ENABLE_PROMETHEUS_METRICS and prometheus:
        @app.route('/metrics')
        def metrics_endpoint():
            from flask import Response
            return Response(prometheus.export(), mimetype='text/plain')

    logger.info("Middleware setup complete")
    return {
        'request_logger': request_logger,
        'prometheus': prometheus,
        'sentry': sentry,
        'rate_limiter': rate_limiter,
    }
