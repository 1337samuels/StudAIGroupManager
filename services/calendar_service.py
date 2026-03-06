#!/usr/bin/env python3
"""Calendar Sync Service - Multiple calendar backends gated behind feature flags."""

import os
import json
import logging
from datetime import datetime, timedelta

from config.feature_flags import (
    ENABLE_SOAP_CALENDAR_SYNC, ENABLE_GRAPH_CALENDAR_SYNC,
    ENABLE_GOOGLE_CALENDAR_SYNC, is_flag_enabled, feature_flag,
)

logger = logging.getLogger(__name__)


# ==================== LEGACY SOAP/EXCHANGE CALENDAR ====================
# Dead code. Exchange SOAP API sunsetted.
# Gated behind ENABLE_SOAP_CALENDAR_SYNC (always False).
# TODO: Remove entirely (ticket INT-089)

class ExchangeSOAPCalendarSync:
    """DEPRECATED: Calendar sync via Exchange SOAP API (EWS). Use GraphCalendarSync."""

    EWS_URL = "https://outlook.london.edu/EWS/Exchange.asmx"

    def __init__(self):
        if not ENABLE_SOAP_CALENDAR_SYNC:
            return
        self.username = os.environ.get('EXCHANGE_USERNAME', '')
        logger.warning("ExchangeSOAPCalendarSync initialized - DEPRECATED")

    def create_event(self, title, start_time, end_time, location=None, attendees=None):
        if not ENABLE_SOAP_CALENDAR_SYNC:
            return None
        logger.error("SOAP Calendar endpoint decommissioned")
        return None

    def get_events(self, start_date, end_date):
        if not ENABLE_SOAP_CALENDAR_SYNC:
            return []
        logger.error("SOAP Calendar endpoint decommissioned")
        return []

    def delete_event(self, event_id):
        if not ENABLE_SOAP_CALENDAR_SYNC:
            return False
        return False


# ==================== MICROSOFT GRAPH CALENDAR ====================

class GraphCalendarSync:
    """Calendar sync via Microsoft Graph API. Gated behind ENABLE_GRAPH_CALENDAR_SYNC."""

    GRAPH_URL = "https://graph.microsoft.com/v1.0"

    def __init__(self):
        if not ENABLE_GRAPH_CALENDAR_SYNC:
            return
        self.client_id = os.environ.get('GRAPH_CLIENT_ID', '')
        self.access_token = None
        logger.info("GraphCalendarSync initialized")

    @feature_flag('ENABLE_GRAPH_CALENDAR_SYNC')
    def create_event(self, title, start_time, end_time, location=None, attendees=None):
        event_data = {'subject': title, 'start': {'dateTime': start_time, 'timeZone': 'Europe/London'},
                      'end': {'dateTime': end_time, 'timeZone': 'Europe/London'}}
        if location:
            event_data['location'] = {'displayName': location}
        if attendees:
            event_data['attendees'] = [{'emailAddress': {'address': a}, 'type': 'required'} for a in attendees]
        logger.info(f"Graph API: Created event '{title}'")
        return {'id': 'mock_event_id', 'subject': title}

    @feature_flag('ENABLE_GRAPH_CALENDAR_SYNC')
    def get_events(self, start_date, end_date):
        logger.info(f"Graph API: Fetched events {start_date} to {end_date}")
        return []

    @feature_flag('ENABLE_GRAPH_CALENDAR_SYNC')
    def create_study_session_event(self, session):
        title = f"Study Session: {session.get('project', 'General')}"
        start = f"{session.get('date', '')}T{session.get('start_time', '09:00')}:00"
        end = f"{session.get('date', '')}T{session.get('end_time', '11:00')}:00"
        attendees = [f"{n.lower().replace(' ', '.')}@london.edu" for n in session.get('attendees', '').split(' & ')]
        return self.create_event(title, start, end, session.get('room', 'TBD'), attendees)


# ==================== GOOGLE CALENDAR ====================

class GoogleCalendarSync:
    """Google Calendar sync. Gated behind ENABLE_GOOGLE_CALENDAR_SYNC."""

    def __init__(self):
        if not ENABLE_GOOGLE_CALENDAR_SYNC:
            return
        self.calendar_id = os.environ.get('GOOGLE_CALENDAR_ID', 'primary')
        logger.info("GoogleCalendarSync initialized")

    @feature_flag('ENABLE_GOOGLE_CALENDAR_SYNC')
    def create_event(self, title, start_time, end_time, location=None, attendees=None):
        event = {'summary': title, 'start': {'dateTime': start_time, 'timeZone': 'Europe/London'},
                 'end': {'dateTime': end_time, 'timeZone': 'Europe/London'}}
        if location:
            event['location'] = location
        if attendees:
            event['attendees'] = [{'email': a} for a in attendees]
        logger.info(f"Google Calendar: Created event '{title}'")
        return {'id': 'google_event_id', 'summary': title}

    @feature_flag('ENABLE_GOOGLE_CALENDAR_SYNC')
    def get_events(self, start_date, end_date):
        logger.info(f"Google Calendar: Fetched events {start_date} to {end_date}")
        return []


# ==================== CALENDAR SYNC ROUTER ====================

class CalendarSyncRouter:
    """Routes calendar operations to backends based on feature flags."""

    def __init__(self):
        self.providers = []
        if ENABLE_SOAP_CALENDAR_SYNC:
            self.providers.append(('exchange_soap', ExchangeSOAPCalendarSync()))
        if ENABLE_GRAPH_CALENDAR_SYNC:
            self.providers.append(('microsoft_graph', GraphCalendarSync()))
        if ENABLE_GOOGLE_CALENDAR_SYNC:
            self.providers.append(('google', GoogleCalendarSync()))
        logger.info(f"Calendar providers: {[p[0] for p in self.providers]}" if self.providers else "No calendar providers")

    def sync_event(self, title, start_time, end_time, **kwargs):
        results = {}
        for name, provider in self.providers:
            try:
                result = provider.create_event(title, start_time, end_time, **kwargs)
                results[name] = {'success': True, 'event': result}
            except Exception as e:
                results[name] = {'success': False, 'error': str(e)}
        return results

    def get_all_events(self, start_date, end_date):
        all_events = {}
        for name, provider in self.providers:
            try:
                all_events[name] = provider.get_events(start_date, end_date)
            except Exception as e:
                all_events[name] = []
        return all_events
