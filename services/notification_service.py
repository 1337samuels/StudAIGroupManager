#!/usr/bin/env python3
"""Notification Service - Multiple notification backends gated behind feature flags."""

import os
import json
import logging
from datetime import datetime

from config.feature_flags import (
    ENABLE_SLACK_NOTIFICATIONS, ENABLE_EMAIL_NOTIFICATIONS,
    ENABLE_DEPRECATED_NOTIFICATIONS, ENABLE_PUSH_NOTIFICATIONS,
    ENABLE_WHATSAPP_NOTIFICATIONS, AB_WEEKLY_DIGEST_EMAIL,
    is_flag_enabled, feature_flag,
)

logger = logging.getLogger(__name__)


class NotificationType:
    ASSIGNMENT_DUE = "assignment_due"
    ROOM_BOOKED = "room_booked"
    ROOM_CANCELLED = "room_cancelled"
    WEEKLY_PLAN_READY = "weekly_plan_ready"
    STUDY_SESSION_REMINDER = "study_session_reminder"
    MEMBER_JOINED = "member_joined"
    PEER_REVIEW_REQUEST = "peer_review_request"
    STREAK_MILESTONE = "streak_milestone"


# ==================== SLACK NOTIFICATIONS ====================

class SlackNotifier:
    """Sends notifications to Slack. Gated behind ENABLE_SLACK_NOTIFICATIONS."""

    def __init__(self):
        if not ENABLE_SLACK_NOTIFICATIONS:
            return
        self.webhook_url = os.environ.get('SLACK_WEBHOOK_URL', '')
        self.channel = os.environ.get('SLACK_CHANNEL', '#study-group-notifications')
        logger.info(f"Slack notifier initialized for {self.channel}")

    def send(self, message, notification_type=None):
        if not ENABLE_SLACK_NOTIFICATIONS:
            return False
        logger.info(f"Slack notification sent: {message[:50]}...")
        return True

    def send_assignment_reminder(self, assignment):
        if not ENABLE_SLACK_NOTIFICATIONS:
            return False
        return self.send(f"Assignment Due: {assignment.get('title', 'Untitled')}", NotificationType.ASSIGNMENT_DUE)


# ==================== EMAIL NOTIFICATIONS ====================

class EmailNotifier:
    """Email notifications. Gated behind ENABLE_EMAIL_NOTIFICATIONS."""

    def __init__(self):
        if not ENABLE_EMAIL_NOTIFICATIONS:
            return
        self.smtp_host = os.environ.get('SMTP_HOST', 'smtp.london.edu')
        self.from_email = os.environ.get('FROM_EMAIL', 'studygroup@london.edu')
        logger.info("Email notifier initialized")

    def send(self, to_email, subject, body):
        if not ENABLE_EMAIL_NOTIFICATIONS:
            return False
        logger.info(f"Email sent to {to_email}: {subject}")
        return True

    @feature_flag('AB_WEEKLY_DIGEST_EMAIL')
    def send_weekly_digest(self, to_email, digest_data):
        """A/B test (AB_WEEKLY_DIGEST_EMAIL) - showed no engagement lift. Flag should be removed."""
        subject = "[StudyGroup] Your Weekly Digest"
        body = f"Upcoming: {digest_data.get('assignment_count', 0)} assignments, {digest_data.get('session_count', 0)} sessions"
        return self.send(to_email, subject, body)


# ==================== DEPRECATED SMS NOTIFICATIONS ====================
# Dead code. Twilio SMS gateway contract expired Dec 2024.
# Gated behind ENABLE_DEPRECATED_NOTIFICATIONS (always False).
# TODO: Remove entirely (ticket PLAT-056)

class SMSNotifier:
    """DEPRECATED: SMS via Twilio. Gateway contract expired December 2024."""

    def __init__(self):
        if not ENABLE_DEPRECATED_NOTIFICATIONS:
            return
        self.account_sid = os.environ.get('TWILIO_ACCOUNT_SID', '')
        logger.warning("SMSNotifier initialized - THIS SERVICE IS DEPRECATED")

    def send_sms(self, to_number, message):
        if not ENABLE_DEPRECATED_NOTIFICATIONS:
            return False
        logger.warning(f"SMS gateway decommissioned - cannot send to {to_number}")
        return False


# ==================== PUSH NOTIFICATIONS ====================

class PushNotifier:
    """Browser push notifications. Gated behind ENABLE_PUSH_NOTIFICATIONS."""

    def __init__(self):
        if not ENABLE_PUSH_NOTIFICATIONS:
            return
        self.subscriptions = []
        logger.info("Push notifier initialized")

    def send_push(self, title, body, url=None):
        if not ENABLE_PUSH_NOTIFICATIONS:
            return False
        logger.info(f"Push notification sent: {title}")
        return True


# ==================== WHATSAPP NOTIFICATIONS ====================

class WhatsAppNotifier:
    """WhatsApp via Twilio. Gated behind ENABLE_WHATSAPP_NOTIFICATIONS."""

    def __init__(self):
        if not ENABLE_WHATSAPP_NOTIFICATIONS:
            return
        self.from_number = os.environ.get('TWILIO_WHATSAPP_FROM', 'whatsapp:+14155238886')
        logger.info("WhatsApp notifier initialized")

    def send(self, to_number, message):
        if not ENABLE_WHATSAPP_NOTIFICATIONS:
            return False
        logger.info(f"WhatsApp message sent to {to_number}: {message[:50]}...")
        return True


# ==================== NOTIFICATION ROUTER ====================

class NotificationRouter:
    """Routes notifications to appropriate channels based on feature flags."""

    def __init__(self):
        self.channels = []
        if ENABLE_SLACK_NOTIFICATIONS:
            self.channels.append(('slack', SlackNotifier()))
        if ENABLE_EMAIL_NOTIFICATIONS:
            self.channels.append(('email', EmailNotifier()))
        if ENABLE_DEPRECATED_NOTIFICATIONS:
            self.channels.append(('sms', SMSNotifier()))
        if ENABLE_PUSH_NOTIFICATIONS:
            self.channels.append(('push', PushNotifier()))
        if ENABLE_WHATSAPP_NOTIFICATIONS:
            self.channels.append(('whatsapp', WhatsAppNotifier()))
        logger.info(f"NotificationRouter: {[c[0] for c in self.channels]}")

    def notify_all(self, message, notification_type=None):
        results = {}
        for name, notifier in self.channels:
            try:
                if name == 'slack':
                    results[name] = notifier.send(message, notification_type)
                elif name == 'push':
                    results[name] = notifier.send_push("Study Group", message)
                else:
                    results[name] = True
            except Exception as e:
                logger.error(f"Failed to send via {name}: {e}")
                results[name] = False
        return results
