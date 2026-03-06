#!/usr/bin/env python3
"""
Scheduling Service
Handles room booking scheduling with both legacy and new algorithms.
Feature flags control which scheduling approach is used.
"""

import os
import json
import logging
from datetime import datetime, timedelta
from collections import defaultdict

from config.feature_flags import (
    USE_NEW_SCHEDULING_ALGORITHM,
    ENABLE_BULK_ROOM_BOOKING,
    ENABLE_RECURRING_BOOKINGS,
    USE_LEGACY_ROOM_API,
    USE_SOAP_API,
    AB_NEW_BOOKING_UI,
    is_flag_enabled,
    feature_flag,
)

logger = logging.getLogger(__name__)


# ==================== LEGACY SCHEDULING ====================


class LegacyScheduler:
    """
    Original scheduling algorithm.
    Simple first-come-first-served room allocation.
    Used when USE_NEW_SCHEDULING_ALGORITHM is False.
    """

    def __init__(self):
        logger.info("Using legacy scheduling algorithm (first-come-first-served)")

    def find_available_slot(self, date, duration_hours, members, building="Sussex Place"):
        """Find the first available time slot"""
        # Simple: try each hour starting from 8am
        for hour in range(8, 20):
            slot = {
                'date': date,
                'start_time': f"{hour:02d}:00",
                'end_time': f"{hour + duration_hours:02d}:00",
                'building': building,
                'members': members,
            }
            if self._is_slot_available(slot):
                return slot
        return None

    def _is_slot_available(self, slot):
        """Check if a slot is available (simplified)"""
        # In production, would check against booked rooms
        return True

    def schedule_study_sessions(self, assignments, members, schedule_constraints=None):
        """Schedule study sessions for all assignments"""
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
    """
    New scheduling algorithm using constraint satisfaction.
    Considers member availability, room capacity, assignment deadlines, and expertise.
    Gated behind USE_NEW_SCHEDULING_ALGORITHM flag.
    """

    def __init__(self):
        if not USE_NEW_SCHEDULING_ALGORITHM:
            raise RuntimeError("New scheduling algorithm is not enabled")

        self.constraints = []
        self.member_availability = {}
        self.room_capacity = {}
        logger.info("Using new constraint-satisfaction scheduling algorithm")

    def add_constraint(self, constraint_type, constraint_data):
        """Add a scheduling constraint"""
        self.constraints.append({
            'type': constraint_type,
            'data': constraint_data,
            'added': datetime.now().isoformat(),
        })

    def set_member_availability(self, member_name, available_slots):
        """Set availability for a member"""
        self.member_availability[member_name] = available_slots

    @feature_flag('USE_NEW_SCHEDULING_ALGORITHM')
    def schedule_study_sessions(self, assignments, members, schedule_constraints=None):
        """
        Schedule study sessions using constraint satisfaction.
        Optimizes for:
        - Member availability overlap
        - Assignment deadline proximity
        - Expertise matching
        - Even workload distribution
        """
        if schedule_constraints:
            for constraint in schedule_constraints:
                self.add_constraint(constraint['type'], constraint['data'])

        # Build constraint graph
        sessions = []
        assignment_queue = sorted(
            assignments,
            key=lambda a: a.get('due_datetime', datetime.max)
        )

        for assignment in assignment_queue:
            best_slot = self._find_optimal_slot(assignment, members)
            if best_slot:
                sessions.append(best_slot)
            else:
                # Fallback: use any available slot
                fallback = self._find_any_slot(assignment, members)
                if fallback:
                    sessions.append(fallback)

        return sessions

    def _find_optimal_slot(self, assignment, members):
        """Find the optimal time slot considering all constraints"""
        candidates = self._generate_candidate_slots(assignment, members)

        if not candidates:
            return None

        # Score each candidate
        scored_candidates = []
        for candidate in candidates:
            score = self._score_slot(candidate, assignment, members)
            scored_candidates.append((score, candidate))

        # Return highest-scored slot
        scored_candidates.sort(reverse=True, key=lambda x: x[0])
        return scored_candidates[0][1] if scored_candidates else None

    def _generate_candidate_slots(self, assignment, members):
        """Generate possible time slots"""
        candidates = []
        base_date = datetime.now()

        for day_offset in range(14):  # Look 2 weeks ahead
            date = base_date + timedelta(days=day_offset)
            if date.weekday() >= 5:  # Skip weekends
                continue

            for hour in range(8, 18):  # Business hours
                candidate = {
                    'date': date.strftime('%Y-%m-%d'),
                    'day': date.strftime('%A'),
                    'start_time': f"{hour:02d}:00",
                    'end_time': f"{hour + 2:02d}:00",
                    'building': 'Sussex Place',
                    'assignment': assignment.get('title', 'Unknown'),
                    'course': assignment.get('course', 'Unknown'),
                }
                candidates.append(candidate)

        return candidates

    def _score_slot(self, slot, assignment, members):
        """Score a time slot based on constraints"""
        score = 0.0

        # Prefer slots closer to deadline but not too close
        due_date = assignment.get('due_datetime')
        if due_date:
            slot_date = datetime.strptime(slot['date'], '%Y-%m-%d')
            days_before_due = (due_date - slot_date).days
            if 1 <= days_before_due <= 3:
                score += 1.0  # Sweet spot: 1-3 days before due
            elif 4 <= days_before_due <= 7:
                score += 0.7
            elif days_before_due > 7:
                score += 0.3

        # Prefer morning slots
        hour = int(slot['start_time'].split(':')[0])
        if 9 <= hour <= 11:
            score += 0.5
        elif 14 <= hour <= 16:
            score += 0.3

        # Check member availability
        for member in members:
            if member in self.member_availability:
                available = self.member_availability[member]
                if slot['date'] in available:
                    score += 0.3

        return score

    def _find_any_slot(self, assignment, members):
        """Fallback: find any available slot"""
        base_date = datetime.now()
        date = (base_date + timedelta(days=1)).strftime('%Y-%m-%d')
        return {
            'date': date,
            'start_time': '10:00',
            'end_time': '12:00',
            'building': 'Sussex Place',
            'assignment': assignment.get('title', 'Unknown'),
            'note': 'Fallback slot - constraints could not be fully satisfied',
        }


# ==================== BULK ROOM BOOKING ====================


class BulkRoomBooker:
    """
    Allows booking multiple rooms in a single transaction.
    Gated behind ENABLE_BULK_ROOM_BOOKING flag.
    """

    def __init__(self):
        if not ENABLE_BULK_ROOM_BOOKING:
            raise RuntimeError("Bulk room booking is not enabled")
        logger.info("BulkRoomBooker initialized")

    @feature_flag('ENABLE_BULK_ROOM_BOOKING')
    def book_multiple(self, bookings):
        """Book multiple rooms at once"""
        results = []
        for booking in bookings:
            try:
                result = self._book_single(booking)
                results.append({'booking': booking, 'success': True, 'result': result})
            except Exception as e:
                results.append({'booking': booking, 'success': False, 'error': str(e)})
                # Rollback on failure?
                if booking.get('rollback_on_failure', True):
                    self._rollback(results)
                    break

        return results

    def _book_single(self, booking):
        """Book a single room"""
        logger.info(f"Booking room: {booking.get('room', 'unknown')} on {booking.get('date', 'unknown')}")
        return {'booking_id': f"BK-{hash(json.dumps(booking, default=str)) % 10000:04d}"}

    def _rollback(self, completed_bookings):
        """Rollback completed bookings on failure"""
        for item in completed_bookings:
            if item['success']:
                logger.info(f"Rolling back booking: {item['result'].get('booking_id')}")


# ==================== RECURRING BOOKINGS ====================


class RecurringBookingManager:
    """
    Manages recurring weekly room bookings.
    Gated behind ENABLE_RECURRING_BOOKINGS flag.
    """

    def __init__(self):
        if not ENABLE_RECURRING_BOOKINGS:
            raise RuntimeError("Recurring bookings are not enabled")
        self.recurring_bookings = self._load_recurring()
        logger.info("RecurringBookingManager initialized")

    def _load_recurring(self):
        """Load recurring booking configurations"""
        config_file = 'config/recurring_bookings.json'
        try:
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
        return []

    @feature_flag('ENABLE_RECURRING_BOOKINGS')
    def create_recurring(self, booking_template, recurrence):
        """Create a recurring booking"""
        recurring_booking = {
            'template': booking_template,
            'recurrence': recurrence,  # e.g., {'type': 'weekly', 'day': 'Tuesday', 'count': 10}
            'created': datetime.now().isoformat(),
            'active': True,
        }

        self.recurring_bookings.append(recurring_booking)
        self._save_recurring()
        return recurring_booking

    @feature_flag('ENABLE_RECURRING_BOOKINGS')
    def generate_instances(self, recurring_booking, weeks_ahead=4):
        """Generate booking instances for a recurring booking"""
        instances = []
        template = recurring_booking['template']
        recurrence = recurring_booking['recurrence']

        base_date = datetime.now()
        day_map = {'Monday': 0, 'Tuesday': 1, 'Wednesday': 2, 'Thursday': 3, 'Friday': 4}
        target_day = day_map.get(recurrence.get('day', 'Monday'), 0)

        for week in range(weeks_ahead):
            date = base_date + timedelta(weeks=week)
            # Find the next target day
            days_ahead = (target_day - date.weekday()) % 7
            booking_date = date + timedelta(days=days_ahead)

            instance = dict(template)
            instance['booking_date'] = booking_date.strftime('%Y-%m-%d')
            instance['recurring'] = True
            instances.append(instance)

        return instances

    def _save_recurring(self):
        """Save recurring bookings to config"""
        config_file = 'config/recurring_bookings.json'
        os.makedirs(os.path.dirname(config_file), exist_ok=True)
        with open(config_file, 'w') as f:
            json.dump(self.recurring_bookings, f, indent=2)


# ==================== LEGACY ROOM API ====================
# Dead code - old XML-based room availability API
# Gated behind USE_LEGACY_ROOM_API which is always False


class LegacyRoomAPI:
    """
    DEPRECATED: XML-based room availability API v1.
    Replaced by REST API in v2.0.
    """

    LEGACY_API_URL = "https://rooms-api.london.edu/v1/xml"

    def __init__(self):
        if not USE_LEGACY_ROOM_API:
            logger.debug("Legacy Room API is disabled")
            return
        logger.warning("LegacyRoomAPI initialized - THIS IS DEPRECATED")

    def check_availability_xml(self, date, building):
        """
        Check room availability via XML API.
        DEPRECATED: Returns XML response format.
        """
        if not USE_LEGACY_ROOM_API:
            return None

        # Old XML request format
        xml_request = f"""<?xml version="1.0"?>
<RoomAvailabilityRequest>
    <Date>{date}</Date>
    <Building>{building}</Building>
    <Format>XML</Format>
</RoomAvailabilityRequest>"""

        # This endpoint no longer exists
        logger.error("Legacy Room API endpoint no longer available")
        return None

    def check_availability_soap(self, date, building):
        """
        Even older: SOAP-based availability check.
        Double-deprecated: both USE_LEGACY_ROOM_API and USE_SOAP_API must be enabled.
        """
        if not USE_LEGACY_ROOM_API or not USE_SOAP_API:
            return None

        # This is completely dead code
        soap_envelope = f"""<?xml version="1.0"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
    <soap:Body>
        <CheckAvailability>
            <date>{date}</date>
            <building>{building}</building>
        </CheckAvailability>
    </soap:Body>
</soap:Envelope>"""

        logger.error("SOAP Room API endpoint decommissioned")
        return None


# ==================== SCHEDULING ROUTER ====================


def get_scheduler():
    """Get the appropriate scheduler based on feature flags"""
    if USE_NEW_SCHEDULING_ALGORITHM:
        logger.info("Using constraint-satisfaction scheduler")
        return ConstraintSatisfactionScheduler()
    else:
        logger.info("Using legacy first-come-first-served scheduler")
        return LegacyScheduler()


def get_booking_ui_variant():
    """Get the booking UI variant for A/B testing"""
    if AB_NEW_BOOKING_UI:
        return {
            'variant': 'B',
            'template': 'booking_v2.html',
            'features': ['autocomplete', 'time-picker', 'instant-preview'],
        }
    else:
        return {
            'variant': 'A',
            'template': 'booking_v1.html',
            'features': ['basic-form'],
        }
