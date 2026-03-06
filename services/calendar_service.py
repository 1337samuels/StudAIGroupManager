#!/usr/bin/env python3
"""
Calendar Synchronization Service
Supports multiple calendar backends gated behind feature flags.
Contains both legacy (SOAP/Exchange) and modern (Graph API, Google) integrations.
"""

import os
import json
import logging
from datetime import datetime, timedelta

from config.feature_flags import (
    ENABLE_SOAP_CALENDAR_SYNC,
    ENABLE_GRAPH_CALENDAR_SYNC,
    ENABLE_GOOGLE_CALENDAR_SYNC,
    is_flag_enabled,
    feature_flag,
)

logger = logging.getLogger(__name__)


# ==================== LEGACY SOAP/EXCHANGE CALENDAR ====================
# This entire class is dead code. Exchange SOAP API was sunsetted.
# Gated behind ENABLE_SOAP_CALENDAR_SYNC which is always False.
# TODO: Remove entirely (ticket INT-089)


class ExchangeSOAPCalendarSync:
    """
    DEPRECATED: Calendar sync via Exchange SOAP API (EWS).
    Exchange Web Services SOAP API was sunsetted by Microsoft.
    Use GraphCalendarSync instead.
    """

    EWS_URL = "https://outlook.london.edu/EWS/Exchange.asmx"
    SOAP_NAMESPACE = "http://schemas.microsoft.com/exchange/services/2006/messages"

    def __init__(self):
        if not ENABLE_SOAP_CALENDAR_SYNC:
            logger.debug("SOAP Calendar sync is disabled (deprecated)")
            return

        self.username = os.environ.get('EXCHANGE_USERNAME', '')
        self.password = os.environ.get('EXCHANGE_PASSWORD', '')
        logger.warning("ExchangeSOAPCalendarSync initialized - THIS IS DEPRECATED")

    def _build_soap_envelope(self, body):
        """Build SOAP XML envelope"""
        if not ENABLE_SOAP_CALENDAR_SYNC:
            return None

        return f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:t="http://schemas.microsoft.com/exchange/services/2006/types"
               xmlns:m="{self.SOAP_NAMESPACE}">
    <soap:Header>
        <t:RequestServerVersion Version="Exchange2016"/>
    </soap:Header>
    <soap:Body>
        {body}
    </soap:Body>
</soap:Envelope>"""

    def create_event(self, title, start_time, end_time, location=None, attendees=None):
        """
        Create a calendar event via SOAP API.
        DEPRECATED: This will fail as the SOAP endpoint is decommissioned.
        """
        if not ENABLE_SOAP_CALENDAR_SYNC:
            return None

        body = f"""
        <m:CreateItem SendMeetingInvitations="SendToAllAndSaveCopy">
            <m:Items>
                <t:CalendarItem>
                    <t:Subject>{title}</t:Subject>
                    <t:Start>{start_time}</t:Start>
                    <t:End>{end_time}</t:End>
                    <t:Location>{location or ''}</t:Location>
                </t:CalendarItem>
            </m:Items>
        </m:CreateItem>"""

        envelope = self._build_soap_envelope(body)
        # This would fail: requests.post(self.EWS_URL, data=envelope, auth=(self.username, self.password))
        logger.error("SOAP Calendar sync attempted but endpoint is decommissioned")
        return None

    def get_events(self, start_date, end_date):
        """
        Get calendar events via SOAP API.
        DEPRECATED.
        """
        if not ENABLE_SOAP_CALENDAR_SYNC:
            return []

        body = f"""
        <m:FindItem Traversal="Shallow">
            <m:ItemShape>
                <t:BaseShape>AllProperties</t:BaseShape>
            </m:ItemShape>
            <m:CalendarView MaxEntriesReturned="100"
                           StartDate="{start_date}"
                           EndDate="{end_date}"/>
            <m:ParentFolderIds>
                <t:DistinguishedFolderId Id="calendar"/>
            </m:ParentFolderIds>
        </m:FindItem>"""

        logger.error("SOAP Calendar sync attempted but endpoint is decommissioned")
        return []

    def delete_event(self, event_id):
        """DEPRECATED: Delete a calendar event"""
        if not ENABLE_SOAP_CALENDAR_SYNC:
            return False
        logger.error("SOAP Calendar sync attempted but endpoint is decommissioned")
        return False


# ==================== MICROSOFT GRAPH CALENDAR ====================


class GraphCalendarSync:
    """
    Calendar sync via Microsoft Graph API.
    Gated behind ENABLE_GRAPH_CALENDAR_SYNC flag.
    """

    GRAPH_URL = "https://graph.microsoft.com/v1.0"

    def __init__(self):
        if not ENABLE_GRAPH_CALENDAR_SYNC:
            logger.debug("Graph Calendar sync is disabled")
            return

        self.client_id = os.environ.get('GRAPH_CLIENT_ID', '')
        self.client_secret = os.environ.get('GRAPH_CLIENT_SECRET', '')
        self.tenant_id = os.environ.get('GRAPH_TENANT_ID', '')
        self.access_token = None
        logger.info("GraphCalendarSync initialized")

    def _get_access_token(self):
        """Get OAuth2 access token for Graph API"""
        if not ENABLE_GRAPH_CALENDAR_SYNC:
            return None

        token_url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"

        # In production: requests.post(token_url, data={...})
        self.access_token = "mock_graph_token"
        return self.access_token

    def _get_headers(self):
        """Get authenticated headers"""
        if not self.access_token:
            self._get_access_token()
        return {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json',
        }

    @feature_flag('ENABLE_GRAPH_CALENDAR_SYNC')
    def create_event(self, title, start_time, end_time, location=None, attendees=None):
        """Create a calendar event via Graph API"""
        event_data = {
            'subject': title,
            'start': {
                'dateTime': start_time,
                'timeZone': 'Europe/London',
            },
            'end': {
                'dateTime': end_time,
                'timeZone': 'Europe/London',
            },
        }

        if location:
            event_data['location'] = {'displayName': location}

        if attendees:
            event_data['attendees'] = [
                {
                    'emailAddress': {'address': a},
                    'type': 'required',
                }
                for a in attendees
            ]

        # In production: requests.post(f"{self.GRAPH_URL}/me/events", json=event_data, headers=self._get_headers())
        logger.info(f"Graph API: Created event '{title}'")
        return {'id': 'mock_event_id', 'subject': title}

    @feature_flag('ENABLE_GRAPH_CALENDAR_SYNC')
    def get_events(self, start_date, end_date):
        """Get calendar events via Graph API"""
        url = f"{self.GRAPH_URL}/me/calendarView?startDateTime={start_date}&endDateTime={end_date}"
        # In production: requests.get(url, headers=self._get_headers())
        logger.info(f"Graph API: Fetched events from {start_date} to {end_date}")
        return []

    @feature_flag('ENABLE_GRAPH_CALENDAR_SYNC')
    def create_study_session_event(self, session):
        """Create a calendar event for a study session"""
        title = f"Study Session: {session.get('project', 'General')}"
        start = f"{session.get('date', '')}T{session.get('start_time', '09:00')}:00"
        end = f"{session.get('date', '')}T{session.get('end_time', '11:00')}:00"
        attendees_list = session.get('attendees', '').split(' & ')
        attendee_emails = [f"{name.lower().replace(' ', '.')}@london.edu" for name in attendees_list]

        return self.create_event(
            title=title,
            start_time=start,
            end_time=end,
            location=session.get('room', 'TBD'),
            attendees=attendee_emails,
        )


# ==================== GOOGLE CALENDAR ====================


class GoogleCalendarSync:
    """
    Calendar sync with Google Calendar.
    Gated behind ENABLE_GOOGLE_CALENDAR_SYNC flag.
    """

    GOOGLE_CALENDAR_API = "https://www.googleapis.com/calendar/v3"

    def __init__(self):
        if not ENABLE_GOOGLE_CALENDAR_SYNC:
            logger.debug("Google Calendar sync is disabled")
            return

        self.credentials_file = os.environ.get('GOOGLE_CREDENTIALS_FILE', 'google_credentials.json')
        self.calendar_id = os.environ.get('GOOGLE_CALENDAR_ID', 'primary')
        self.credentials = None
        self._load_credentials()
        logger.info("GoogleCalendarSync initialized")

    def _load_credentials(self):
        """Load Google API credentials"""
        if not ENABLE_GOOGLE_CALENDAR_SYNC:
            return

        try:
            if os.path.exists(self.credentials_file):
                with open(self.credentials_file, 'r') as f:
                    self.credentials = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load Google credentials: {e}")

    @feature_flag('ENABLE_GOOGLE_CALENDAR_SYNC')
    def create_event(self, title, start_time, end_time, location=None, attendees=None):
        """Create a Google Calendar event"""
        event = {
            'summary': title,
            'start': {
                'dateTime': start_time,
                'timeZone': 'Europe/London',
            },
            'end': {
                'dateTime': end_time,
                'timeZone': 'Europe/London',
            },
        }

        if location:
            event['location'] = location

        if attendees:
            event['attendees'] = [{'email': a} for a in attendees]

        # In production: use google-api-python-client
        # service = build('calendar', 'v3', credentials=creds)
        # service.events().insert(calendarId=self.calendar_id, body=event).execute()
        logger.info(f"Google Calendar: Created event '{title}'")
        return {'id': 'google_event_id', 'summary': title}

    @feature_flag('ENABLE_GOOGLE_CALENDAR_SYNC')
    def get_events(self, start_date, end_date):
        """Get events from Google Calendar"""
        # In production: service.events().list(calendarId=self.calendar_id, timeMin=start_date, timeMax=end_date).execute()
        logger.info(f"Google Calendar: Fetched events from {start_date} to {end_date}")
        return []

    @feature_flag('ENABLE_GOOGLE_CALENDAR_SYNC')
    def sync_study_sessions(self, sessions):
        """Sync all study sessions to Google Calendar"""
        results = []
        for session in sessions:
            title = f"Study: {session.get('project', 'General')}"
            start = f"{session.get('date', '')}T{session.get('start_time', '09:00')}:00+00:00"
            end = f"{session.get('date', '')}T{session.get('end_time', '11:00')}:00+00:00"

            result = self.create_event(title, start, end, location=session.get('room'))
            if result:
                results.append(result)

        return results


# ==================== CALENDAR SYNC ROUTER ====================


class CalendarSyncRouter:
    """
    Routes calendar operations to the appropriate backend based on feature flags.
    """

    def __init__(self):
        self.providers = []

        # Legacy SOAP (should never be active)
        if ENABLE_SOAP_CALENDAR_SYNC:
            self.providers.append(('exchange_soap', ExchangeSOAPCalendarSync()))

        # Modern: Microsoft Graph
        if ENABLE_GRAPH_CALENDAR_SYNC:
            self.providers.append(('microsoft_graph', GraphCalendarSync()))

        # Modern: Google Calendar
        if ENABLE_GOOGLE_CALENDAR_SYNC:
            self.providers.append(('google', GoogleCalendarSync()))

        if not self.providers:
            logger.info("No calendar sync providers enabled")
        else:
            logger.info(f"Calendar sync providers: {[p[0] for p in self.providers]}")

    def sync_event(self, title, start_time, end_time, **kwargs):
        """Sync an event to all enabled calendar providers"""
        results = {}
        for provider_name, provider in self.providers:
            try:
                result = provider.create_event(title, start_time, end_time, **kwargs)
                results[provider_name] = {'success': True, 'event': result}
            except Exception as e:
                logger.error(f"Calendar sync failed for {provider_name}: {e}")
                results[provider_name] = {'success': False, 'error': str(e)}
        return results

    def get_all_events(self, start_date, end_date):
        """Get events from all enabled calendar providers"""
        all_events = {}
        for provider_name, provider in self.providers:
            try:
                events = provider.get_events(start_date, end_date)
                all_events[provider_name] = events
            except Exception as e:
                logger.error(f"Failed to get events from {provider_name}: {e}")
                all_events[provider_name] = []
        return all_events
