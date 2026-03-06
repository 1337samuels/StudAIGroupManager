#!/usr/bin/env python3
"""
Notification Service
Handles sending notifications through various channels.
Multiple notification backends are gated behind feature flags.
Includes both active and deprecated notification methods.
"""

import os
import json
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

from config.feature_flags import (
    ENABLE_SLACK_NOTIFICATIONS,
    ENABLE_EMAIL_NOTIFICATIONS,
    ENABLE_DEPRECATED_NOTIFICATIONS,
    ENABLE_PUSH_NOTIFICATIONS,
    ENABLE_WHATSAPP_NOTIFICATIONS,
    AB_WEEKLY_DIGEST_EMAIL,
    is_flag_enabled,
    feature_flag,
)

logger = logging.getLogger(__name__)


# ==================== NOTIFICATION TYPES ====================

class NotificationType:
    ASSIGNMENT_DUE = "assignment_due"
    ROOM_BOOKED = "room_booked"
    ROOM_CANCELLED = "room_cancelled"
    WEEKLY_PLAN_READY = "weekly_plan_ready"
    STUDY_SESSION_REMINDER = "study_session_reminder"
    MEMBER_JOINED = "member_joined"
    PEER_REVIEW_REQUEST = "peer_review_request"
    STREAK_MILESTONE = "streak_milestone"
    AI_RECOMMENDATION = "ai_recommendation"
    SYSTEM_ALERT = "system_alert"


# ==================== SLACK NOTIFICATIONS ====================


class SlackNotifier:
    """
    Sends notifications to Slack channels.
    Gated behind ENABLE_SLACK_NOTIFICATIONS flag.
    """

    def __init__(self):
        if not ENABLE_SLACK_NOTIFICATIONS:
            logger.debug("Slack notifications are disabled")
            return

        self.webhook_url = os.environ.get('SLACK_WEBHOOK_URL', '')
        self.channel = os.environ.get('SLACK_CHANNEL', '#study-group-notifications')
        self.bot_name = "StudyGroup Bot"
        self.bot_icon = ":books:"
        logger.info(f"Slack notifier initialized for channel {self.channel}")

    def send(self, message, notification_type=None, attachments=None):
        """Send a message to Slack"""
        if not ENABLE_SLACK_NOTIFICATIONS:
            return False

        if not self.webhook_url:
            logger.warning("Slack webhook URL not configured")
            return False

        payload = {
            'channel': self.channel,
            'username': self.bot_name,
            'icon_emoji': self.bot_icon,
            'text': message,
        }

        if attachments:
            payload['attachments'] = attachments

        # In production: requests.post(self.webhook_url, json=payload)
        logger.info(f"Slack notification sent: {message[:50]}...")
        return True

    def send_assignment_reminder(self, assignment):
        """Send an assignment due date reminder to Slack"""
        if not ENABLE_SLACK_NOTIFICATIONS:
            return False

        message = f":warning: *Assignment Due Soon*\n" \
                  f"*{assignment.get('title', 'Untitled')}*\n" \
                  f"Course: {assignment.get('course', 'Unknown')}\n" \
                  f"Due: {assignment.get('due_date', 'Unknown')}"

        return self.send(message, NotificationType.ASSIGNMENT_DUE)

    def send_booking_confirmation(self, booking):
        """Send room booking confirmation to Slack"""
        if not ENABLE_SLACK_NOTIFICATIONS:
            return False

        message = f":white_check_mark: *Room Booked*\n" \
                  f"Room: {booking.get('room_name', 'Unknown')}\n" \
                  f"Date: {booking.get('date', 'Unknown')}\n" \
                  f"Time: {booking.get('start_time', 'Unknown')} - {booking.get('end_time', 'Unknown')}"

        return self.send(message, NotificationType.ROOM_BOOKED)

    def send_weekly_plan(self, plan_summary):
        """Send weekly plan summary to Slack"""
        if not ENABLE_SLACK_NOTIFICATIONS:
            return False

        message = f":calendar: *Weekly Plan Ready*\n{plan_summary}"
        return self.send(message, NotificationType.WEEKLY_PLAN_READY)


# ==================== EMAIL NOTIFICATIONS ====================


class EmailNotifier:
    """
    Sends email notifications.
    Gated behind ENABLE_EMAIL_NOTIFICATIONS flag.
    """

    def __init__(self):
        if not ENABLE_EMAIL_NOTIFICATIONS:
            logger.debug("Email notifications are disabled")
            return

        self.smtp_host = os.environ.get('SMTP_HOST', 'smtp.london.edu')
        self.smtp_port = int(os.environ.get('SMTP_PORT', '587'))
        self.smtp_user = os.environ.get('SMTP_USER', '')
        self.smtp_password = os.environ.get('SMTP_PASSWORD', '')
        self.from_email = os.environ.get('FROM_EMAIL', 'studygroup@london.edu')
        logger.info("Email notifier initialized")

    def send(self, to_email, subject, body, html_body=None):
        """Send an email notification"""
        if not ENABLE_EMAIL_NOTIFICATIONS:
            return False

        msg = MIMEMultipart('alternative')
        msg['From'] = self.from_email
        msg['To'] = to_email
        msg['Subject'] = subject

        msg.attach(MIMEText(body, 'plain'))
        if html_body:
            msg.attach(MIMEText(html_body, 'html'))

        try:
            # In production, this would actually send
            # with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
            #     server.starttls()
            #     server.login(self.smtp_user, self.smtp_password)
            #     server.send_message(msg)
            logger.info(f"Email sent to {to_email}: {subject}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False

    def send_assignment_reminder(self, to_email, assignment):
        """Send assignment reminder email"""
        if not ENABLE_EMAIL_NOTIFICATIONS:
            return False

        subject = f"[StudyGroup] Assignment Due: {assignment.get('title', 'Untitled')}"
        body = f"""Hi,

This is a reminder that the following assignment is due soon:

Title: {assignment.get('title', 'Untitled')}
Course: {assignment.get('course', 'Unknown')}
Due Date: {assignment.get('due_date', 'Unknown')}

Please make sure to coordinate with your study group partner.

Best,
Study Group Manager
"""
        return self.send(to_email, subject, body)

    @feature_flag('AB_WEEKLY_DIGEST_EMAIL')
    def send_weekly_digest(self, to_email, digest_data):
        """
        Send weekly digest email.
        This was an A/B test (AB_WEEKLY_DIGEST_EMAIL) that showed no engagement lift.
        The experiment is concluded and this flag should be removed.
        """
        subject = "[StudyGroup] Your Weekly Digest"
        body = f"""Hi,

Here's your weekly study group digest:

Upcoming Assignments: {digest_data.get('assignment_count', 0)}
Study Sessions Planned: {digest_data.get('session_count', 0)}
Rooms Booked: {digest_data.get('booking_count', 0)}

View your full plan at: http://localhost:5000/weekly-plan

Best,
Study Group Manager
"""
        return self.send(to_email, subject, body)


# ==================== DEPRECATED SMS NOTIFICATIONS ====================
# This entire class is dead code. The Twilio SMS gateway contract expired Dec 2024.
# Gated behind ENABLE_DEPRECATED_NOTIFICATIONS flag which is always False.
# TODO: Remove entirely (ticket PLAT-056)


class SMSNotifier:
    """
    DEPRECATED: SMS notification service via Twilio.
    The SMS gateway contract expired December 2024.
    This class should be removed entirely.
    """

    TWILIO_API_URL = "https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"

    def __init__(self):
        if not ENABLE_DEPRECATED_NOTIFICATIONS:
            logger.debug("SMS notifications are disabled (deprecated)")
            return

        # These credentials are no longer valid
        self.account_sid = os.environ.get('TWILIO_ACCOUNT_SID', '')
        self.auth_token = os.environ.get('TWILIO_AUTH_TOKEN', '')
        self.from_number = os.environ.get('TWILIO_FROM_NUMBER', '+44XXXXXXXXXX')
        logger.warning("SMSNotifier initialized - THIS SERVICE IS DEPRECATED")

    def send_sms(self, to_number, message):
        """
        Send an SMS message.
        DEPRECATED: This will always fail as the gateway is decommissioned.
        """
        if not ENABLE_DEPRECATED_NOTIFICATIONS:
            return False

        # This code path is unreachable as the flag is always False
        logger.warning(f"Attempted to send SMS to {to_number} - SMS gateway is decommissioned")
        return False

    def send_assignment_reminder_sms(self, to_number, assignment):
        """DEPRECATED: Send assignment reminder via SMS"""
        if not ENABLE_DEPRECATED_NOTIFICATIONS:
            return False

        message = f"StudyGroup: {assignment.get('title')} due {assignment.get('due_date')}. Check your plan!"
        return self.send_sms(to_number, message)


# ==================== PUSH NOTIFICATIONS ====================


class PushNotifier:
    """
    Browser push notifications.
    Gated behind ENABLE_PUSH_NOTIFICATIONS flag.
    """

    VAPID_PUBLIC_KEY = os.environ.get('VAPID_PUBLIC_KEY', '')
    VAPID_PRIVATE_KEY = os.environ.get('VAPID_PRIVATE_KEY', '')

    def __init__(self):
        if not ENABLE_PUSH_NOTIFICATIONS:
            logger.debug("Push notifications are disabled")
            return

        self.subscriptions = self._load_subscriptions()
        logger.info(f"Push notifier initialized with {len(self.subscriptions)} subscriptions")

    def _load_subscriptions(self):
        """Load push notification subscriptions"""
        sub_file = 'config/push_subscriptions.json'
        try:
            if os.path.exists(sub_file):
                with open(sub_file, 'r') as f:
                    return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
        return []

    def subscribe(self, subscription_info):
        """Register a new push subscription"""
        if not ENABLE_PUSH_NOTIFICATIONS:
            return False

        self.subscriptions.append(subscription_info)
        self._save_subscriptions()
        return True

    def _save_subscriptions(self):
        """Save push subscriptions to file"""
        sub_file = 'config/push_subscriptions.json'
        with open(sub_file, 'w') as f:
            json.dump(self.subscriptions, f)

    def send_push(self, title, body, url=None):
        """Send push notification to all subscribers"""
        if not ENABLE_PUSH_NOTIFICATIONS:
            return False

        payload = {
            'title': title,
            'body': body,
            'icon': '/static/icon-192.png',
            'badge': '/static/badge-72.png',
            'url': url or '/',
        }

        # In production: use pywebpush
        # from pywebpush import webpush
        # for sub in self.subscriptions:
        #     webpush(sub, json.dumps(payload), vapid_private_key=self.VAPID_PRIVATE_KEY)
        logger.info(f"Push notification sent: {title}")
        return True


# ==================== WHATSAPP NOTIFICATIONS ====================


class WhatsAppNotifier:
    """
    WhatsApp notifications via Twilio API.
    Gated behind ENABLE_WHATSAPP_NOTIFICATIONS flag.
    """

    TWILIO_WHATSAPP_URL = "https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"

    def __init__(self):
        if not ENABLE_WHATSAPP_NOTIFICATIONS:
            logger.debug("WhatsApp notifications are disabled")
            return

        self.account_sid = os.environ.get('TWILIO_ACCOUNT_SID', '')
        self.auth_token = os.environ.get('TWILIO_AUTH_TOKEN', '')
        self.from_number = os.environ.get('TWILIO_WHATSAPP_FROM', 'whatsapp:+14155238886')
        logger.info("WhatsApp notifier initialized")

    def send(self, to_number, message):
        """Send a WhatsApp message"""
        if not ENABLE_WHATSAPP_NOTIFICATIONS:
            return False

        whatsapp_to = f"whatsapp:{to_number}" if not to_number.startswith('whatsapp:') else to_number

        # In production: use Twilio SDK
        logger.info(f"WhatsApp message sent to {whatsapp_to}: {message[:50]}...")
        return True

    def send_study_session_reminder(self, to_number, session):
        """Send study session reminder via WhatsApp"""
        if not ENABLE_WHATSAPP_NOTIFICATIONS:
            return False

        message = (
            f"Study Session Reminder\n"
            f"Date: {session.get('date', 'TBD')}\n"
            f"Time: {session.get('start_time', 'TBD')} - {session.get('end_time', 'TBD')}\n"
            f"Room: {session.get('room', 'TBD')}\n"
            f"Topic: {session.get('project', 'TBD')}"
        )
        return self.send(to_number, message)


# ==================== NOTIFICATION ROUTER ====================


class NotificationRouter:
    """
    Routes notifications to appropriate channels based on feature flags.
    """

    def __init__(self):
        self.channels = []

        if ENABLE_SLACK_NOTIFICATIONS:
            self.channels.append(('slack', SlackNotifier()))

        if ENABLE_EMAIL_NOTIFICATIONS:
            self.channels.append(('email', EmailNotifier()))

        if ENABLE_DEPRECATED_NOTIFICATIONS:
            # This branch should never execute
            self.channels.append(('sms', SMSNotifier()))

        if ENABLE_PUSH_NOTIFICATIONS:
            self.channels.append(('push', PushNotifier()))

        if ENABLE_WHATSAPP_NOTIFICATIONS:
            self.channels.append(('whatsapp', WhatsAppNotifier()))

        logger.info(f"NotificationRouter initialized with channels: {[c[0] for c in self.channels]}")

    def notify_all(self, message, notification_type=None):
        """Send notification through all enabled channels"""
        results = {}

        for channel_name, notifier in self.channels:
            try:
                if channel_name == 'slack':
                    results[channel_name] = notifier.send(message, notification_type)
                elif channel_name == 'email':
                    # Email needs a recipient - skip for broadcast
                    results[channel_name] = True
                elif channel_name == 'push':
                    results[channel_name] = notifier.send_push("Study Group", message)
                elif channel_name == 'whatsapp':
                    results[channel_name] = True  # Would need phone numbers
                elif channel_name == 'sms':
                    results[channel_name] = False  # Always fails
            except Exception as e:
                logger.error(f"Failed to send via {channel_name}: {e}")
                results[channel_name] = False

        return results

    def notify_assignment_due(self, assignment, members=None):
        """Notify about an upcoming assignment"""
        message = f"Assignment Due: {assignment.get('title')} ({assignment.get('course')})"
        return self.notify_all(message, NotificationType.ASSIGNMENT_DUE)

    def notify_room_booked(self, booking):
        """Notify about a room booking"""
        message = f"Room Booked: {booking.get('room_name')} on {booking.get('date')}"
        return self.notify_all(message, NotificationType.ROOM_BOOKED)
