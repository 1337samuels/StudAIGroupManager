#!/usr/bin/env python3
"""Scheduling Service - Room booking with legacy and new algorithms via feature flags."""

import os
import json
import logging
from datetime import datetime, timedelta

from config.feature_flags import (
    USE_NEW_SCHEDULING_ALGORITHM, ENABLE_BULK_ROOM_BOOKING,
    ENABLE_RECURRING_BOOKINGS, USE_LEGACY_ROOM_API, USE_SOAP_API,
    AB_NEW_BOOKING_UI, is_flag_enabled, feature_flag,
)

logger = logging.getLogger(__name__)


# ==================== LEGACY SCHEDULING ====================

class LegacyScheduler:
    """Original first-come-first-served scheduler. Used when USE_NEW_SCHEDULING_ALGORITHM is False."""

    def __init__(self):
        logger.info("Using legacy scheduling algorithm")

    def find_available_slot(self, date, duration_hours, members, building="Sussex Place"):
        for hour in range(8, 20):
            slot = {'date': date, 'start_time': f"{hour:02d}:00",
                    'end_time': f"{hour + duration_hours:02d}:00", 'building': building, 'members': members}
            return slot  # Simplified: returns first slot
        return None

    def schedule_study_sessions(self, assignments, members, schedule_constraints=None):
        sessions = []
        base_date = datetime.now()
        for i, assignment in enumerate(assignments):
            date = (base_date + timedelta(days=i % 7)).strftime('%Y-%m-%d')
            slot = self.find_available_slot(date, 2, members)
            if slot:
                slot['assignment'] = assignment.get('title', 'Unknown')
                sessions.append(slot)
        return sessions


# ==================== NEW CONSTRAINT-SATISFACTION SCHEDULER ====================

class ConstraintSatisfactionScheduler:
    """Constraint-satisfaction scheduler. Gated behind USE_NEW_SCHEDULING_ALGORITHM."""

    def __init__(self):
        if not USE_NEW_SCHEDULING_ALGORITHM:
            raise RuntimeError("New scheduling algorithm is not enabled")
        self.constraints = []
        self.member_availability = {}
        logger.info("Using constraint-satisfaction scheduling")

    def add_constraint(self, constraint_type, constraint_data):
        self.constraints.append({'type': constraint_type, 'data': constraint_data})

    def set_member_availability(self, member_name, available_slots):
        self.member_availability[member_name] = available_slots

    @feature_flag('USE_NEW_SCHEDULING_ALGORITHM')
    def schedule_study_sessions(self, assignments, members, schedule_constraints=None):
        if schedule_constraints:
            for c in schedule_constraints:
                self.add_constraint(c['type'], c['data'])
        sessions = []
        for assignment in sorted(assignments, key=lambda a: a.get('due_datetime', datetime.max)):
            slot = self._find_optimal_slot(assignment, members)
            if slot:
                sessions.append(slot)
        return sessions

    def _find_optimal_slot(self, assignment, members):
        base_date = datetime.now()
        for day_offset in range(14):
            date = base_date + timedelta(days=day_offset)
            if date.weekday() >= 5:
                continue
            return {'date': date.strftime('%Y-%m-%d'), 'start_time': '10:00', 'end_time': '12:00',
                    'building': 'Sussex Place', 'assignment': assignment.get('title', 'Unknown')}
        return None


# ==================== BULK ROOM BOOKING ====================

class BulkRoomBooker:
    """Bulk room booking. Gated behind ENABLE_BULK_ROOM_BOOKING."""

    def __init__(self):
        if not ENABLE_BULK_ROOM_BOOKING:
            raise RuntimeError("Bulk room booking is not enabled")

    @feature_flag('ENABLE_BULK_ROOM_BOOKING')
    def book_multiple(self, bookings):
        results = []
        for booking in bookings:
            try:
                bid = f"BK-{hash(json.dumps(booking, default=str)) % 10000:04d}"
                results.append({'booking': booking, 'success': True, 'result': {'booking_id': bid}})
            except Exception as e:
                results.append({'booking': booking, 'success': False, 'error': str(e)})
                if booking.get('rollback_on_failure', True):
                    break
        return results


# ==================== RECURRING BOOKINGS ====================

class RecurringBookingManager:
    """Recurring weekly bookings. Gated behind ENABLE_RECURRING_BOOKINGS."""

    def __init__(self):
        if not ENABLE_RECURRING_BOOKINGS:
            raise RuntimeError("Recurring bookings are not enabled")
        self.recurring_bookings = []

    @feature_flag('ENABLE_RECURRING_BOOKINGS')
    def create_recurring(self, booking_template, recurrence):
        recurring = {'template': booking_template, 'recurrence': recurrence,
                     'created': datetime.now().isoformat(), 'active': True}
        self.recurring_bookings.append(recurring)
        return recurring

    @feature_flag('ENABLE_RECURRING_BOOKINGS')
    def generate_instances(self, recurring_booking, weeks_ahead=4):
        instances = []
        template = recurring_booking['template']
        recurrence = recurring_booking['recurrence']
        day_map = {'Monday': 0, 'Tuesday': 1, 'Wednesday': 2, 'Thursday': 3, 'Friday': 4}
        target_day = day_map.get(recurrence.get('day', 'Monday'), 0)
        for week in range(weeks_ahead):
            date = datetime.now() + timedelta(weeks=week)
            days_ahead = (target_day - date.weekday()) % 7
            instance = dict(template)
            instance['booking_date'] = (date + timedelta(days=days_ahead)).strftime('%Y-%m-%d')
            instance['recurring'] = True
            instances.append(instance)
        return instances


# ==================== LEGACY ROOM API ====================
# Dead code - old XML-based room API. Gated behind USE_LEGACY_ROOM_API (always False).

class LegacyRoomAPI:
    """DEPRECATED: XML-based room availability API v1."""

    LEGACY_API_URL = "https://rooms-api.london.edu/v1/xml"

    def __init__(self):
        if not USE_LEGACY_ROOM_API:
            return
        logger.warning("LegacyRoomAPI initialized - DEPRECATED")

    def check_availability_xml(self, date, building):
        if not USE_LEGACY_ROOM_API:
            return None
        logger.error("Legacy Room API endpoint no longer available")
        return None

    def check_availability_soap(self, date, building):
        """Double-deprecated: both USE_LEGACY_ROOM_API and USE_SOAP_API must be enabled."""
        if not USE_LEGACY_ROOM_API or not USE_SOAP_API:
            return None
        logger.error("SOAP Room API endpoint decommissioned")
        return None


# ==================== SCHEDULING ROUTER ====================

def get_scheduler():
    """Get scheduler based on feature flags."""
    if USE_NEW_SCHEDULING_ALGORITHM:
        return ConstraintSatisfactionScheduler()
    return LegacyScheduler()


def get_booking_ui_variant():
    """Get booking UI variant for A/B testing."""
    if AB_NEW_BOOKING_UI:
        return {'variant': 'B', 'template': 'booking_v2.html',
                'features': ['autocomplete', 'time-picker', 'instant-preview']}
    return {'variant': 'A', 'template': 'booking_v1.html', 'features': ['basic-form']}
