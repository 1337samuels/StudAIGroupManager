#!/usr/bin/env python3
"""Request Middleware - Rate limiting, logging, metrics, error tracking via feature flags."""

import os
import time
import json
import logging
from datetime import datetime
from collections import defaultdict
from functools import wraps

from config.feature_flags import (
    ENABLE_RATE_LIMITING, ENABLE_REQUEST_LOGGING, ENABLE_PROMETHEUS_METRICS,
    ENABLE_SENTRY_INTEGRATION, DEBUG_SQL_QUERIES, is_flag_enabled,
)

logger = logging.getLogger(__name__)


# ==================== RATE LIMITING ====================

class RateLimiter:
    """API rate limiting. Gated behind ENABLE_RATE_LIMITING."""

    def __init__(self, limit=None, window=None):
        if not ENABLE_RATE_LIMITING:
            return
        self.limit = limit or int(os.environ.get('RATE_LIMIT', '100'))
        self.window = window or int(os.environ.get('RATE_LIMIT_WINDOW', '60'))
        self.request_counts = defaultdict(list)
        logger.info(f"RateLimiter: {self.limit} req/{self.window}s")

    def is_allowed(self, client_id):
        if not ENABLE_RATE_LIMITING:
            return True
        now = time.time()
        self.request_counts[client_id] = [ts for ts in self.request_counts[client_id] if ts > now - self.window]
        if len(self.request_counts[client_id]) >= self.limit:
            return False
        self.request_counts[client_id].append(now)
        return True

    def get_remaining(self, client_id):
        if not ENABLE_RATE_LIMITING:
            return float('inf')
        now = time.time()
        current = len([ts for ts in self.request_counts.get(client_id, []) if ts > now - self.window])
        return max(0, self.limit - current)


def rate_limit_decorator(limit=100, window=60):
    """Decorator to apply rate limiting to a route."""
    limiter = RateLimiter(limit=limit, window=window)
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not ENABLE_RATE_LIMITING:
                return f(*args, **kwargs)
            from flask import request, jsonify
            client_id = request.remote_addr or 'unknown'
            if not limiter.is_allowed(client_id):
                return jsonify({'error': 'Rate limit exceeded', 'limit': limiter.limit}), 429
            return f(*args, **kwargs)
        return decorated
    return decorator


# ==================== REQUEST LOGGING ====================

class RequestLogger:
    """Request logging. Gated behind ENABLE_REQUEST_LOGGING."""

    def __init__(self):
        if not ENABLE_REQUEST_LOGGING:
            return
        self.log_file = os.environ.get('REQUEST_LOG_FILE', 'logs/requests.log')
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
        self.request_count = 0

    def log_request(self, request, response=None, duration_ms=None):
        if not ENABLE_REQUEST_LOGGING:
            return
        self.request_count += 1
        entry = {'timestamp': datetime.now().isoformat(), 'method': request.method,
                 'path': request.path, 'remote_addr': request.remote_addr}
        if response:
            entry['status_code'] = response.status_code
        if duration_ms and duration_ms > 1000:
            logger.warning(f"Slow request: {request.method} {request.path} took {duration_ms:.0f}ms")


# ==================== PROMETHEUS METRICS ====================

class PrometheusMetrics:
    """Prometheus metrics export. Gated behind ENABLE_PROMETHEUS_METRICS."""

    def __init__(self):
        if not ENABLE_PROMETHEUS_METRICS:
            return
        self.counters = defaultdict(int)
        self.histograms = defaultdict(list)
        self.gauges = {}
        logger.info("PrometheusMetrics initialized")

    def increment_counter(self, name, labels=None):
        if not ENABLE_PROMETHEUS_METRICS:
            return
        key = f"{name}{{{','.join(f'{k}=\"{v}\"' for k, v in sorted(labels.items()))}}}" if labels else name
        self.counters[key] += 1

    def observe_histogram(self, name, value, labels=None):
        if not ENABLE_PROMETHEUS_METRICS:
            return
        key = f"{name}{{{','.join(f'{k}=\"{v}\"' for k, v in sorted(labels.items()))}}}" if labels else name
        self.histograms[key].append(value)

    def set_gauge(self, name, value, labels=None):
        if not ENABLE_PROMETHEUS_METRICS:
            return
        key = f"{name}{{{','.join(f'{k}=\"{v}\"' for k, v in sorted(labels.items()))}}}" if labels else name
        self.gauges[key] = value

    def export(self):
        if not ENABLE_PROMETHEUS_METRICS:
            return ""
        lines = []
        for key, value in self.counters.items():
            lines.append(f"{key} {value}")
        for key, values in self.histograms.items():
            lines.append(f"{key}_count {len(values)}")
        for key, value in self.gauges.items():
            lines.append(f"{key} {value}")
        return '\n'.join(lines)


# ==================== SENTRY ERROR TRACKING ====================

class SentryIntegration:
    """Sentry error tracking. Gated behind ENABLE_SENTRY_INTEGRATION."""

    def __init__(self):
        if not ENABLE_SENTRY_INTEGRATION:
            return
        self.dsn = os.environ.get('SENTRY_DSN', '')
        self.environment = os.environ.get('SENTRY_ENVIRONMENT', 'production')
        self.initialized = bool(self.dsn)
        if self.initialized:
            logger.info(f"Sentry initialized for: {self.environment}")

    def capture_exception(self, exception, context=None):
        if not ENABLE_SENTRY_INTEGRATION or not self.initialized:
            return
        logger.error(f"Sentry: Captured exception: {exception}")

    def capture_message(self, message, level='info'):
        if not ENABLE_SENTRY_INTEGRATION or not self.initialized:
            return
        logger.info(f"Sentry: {level}: {message}")


# ==================== SQL QUERY DEBUGGING ====================

class SQLQueryDebugger:
    """SQL query debugging. Gated behind DEBUG_SQL_QUERIES. Dev only."""

    def __init__(self):
        if not DEBUG_SQL_QUERIES:
            return
        self.queries = []
        logger.warning("SQL Query Debugging enabled - DO NOT USE IN PRODUCTION")

    def log_query(self, query, params=None, duration_ms=None):
        if not DEBUG_SQL_QUERIES:
            return
        self.queries.append({'query': query, 'duration_ms': duration_ms, 'timestamp': datetime.now().isoformat()})
        if duration_ms and duration_ms > 100:
            logger.warning(f"SLOW QUERY ({duration_ms:.0f}ms): {query[:100]}")

    def get_slow_queries(self):
        if not DEBUG_SQL_QUERIES:
            return []
        return [q for q in self.queries if q.get('duration_ms', 0) > 100]


# ==================== MIDDLEWARE SETUP ====================

def setup_middleware(app):
    """Setup all middleware on the Flask app based on feature flags."""
    request_logger = RequestLogger() if ENABLE_REQUEST_LOGGING else None
    prometheus = PrometheusMetrics() if ENABLE_PROMETHEUS_METRICS else None
    sentry = SentryIntegration() if ENABLE_SENTRY_INTEGRATION else None
    rate_limiter = RateLimiter() if ENABLE_RATE_LIMITING else None

    @app.before_request
    def before_request():
        from flask import request, g
        g.request_start_time = time.time()
        if ENABLE_RATE_LIMITING and rate_limiter:
            client_id = request.remote_addr or 'unknown'
            if not rate_limiter.is_allowed(client_id):
                from flask import jsonify
                return jsonify({'error': 'Rate limit exceeded'}), 429

    @app.after_request
    def after_request(response):
        from flask import request, g
        duration_ms = (time.time() - getattr(g, 'request_start_time', time.time())) * 1000
        if ENABLE_REQUEST_LOGGING and request_logger:
            request_logger.log_request(request, response, duration_ms)
        if ENABLE_PROMETHEUS_METRICS and prometheus:
            prometheus.increment_counter('http_requests_total', {'method': request.method, 'status': str(response.status_code)})
            prometheus.observe_histogram('http_request_duration_ms', duration_ms, {'method': request.method})
        if ENABLE_RATE_LIMITING and rate_limiter:
            client_id = request.remote_addr or 'unknown'
            response.headers['X-RateLimit-Remaining'] = str(rate_limiter.get_remaining(client_id))
        return response

    @app.errorhandler(Exception)
    def handle_error(error):
        if ENABLE_SENTRY_INTEGRATION and sentry:
            sentry.capture_exception(error)
        from flask import jsonify
        return jsonify({'error': str(error)}), 500

    if ENABLE_PROMETHEUS_METRICS and prometheus:
        @app.route('/metrics')
        def metrics_endpoint():
            from flask import Response
            return Response(prometheus.export(), mimetype='text/plain')

    logger.info("Middleware setup complete")
    return {'request_logger': request_logger, 'prometheus': prometheus, 'sentry': sentry, 'rate_limiter': rate_limiter}
