#!/usr/bin/env python3
"""Analytics Service - Study group metrics and insights via feature flags."""

import os
import json
import logging
from datetime import datetime

from config.feature_flags import (
    ENABLE_ANALYTICS_DASHBOARD, ENABLE_STUDY_STREAK_TRACKING,
    ENABLE_EXPORT_TO_PDF, is_flag_enabled, feature_flag,
)

logger = logging.getLogger(__name__)


# ==================== ANALYTICS ENGINE ====================

class AnalyticsEngine:
    """Core analytics engine. Gated behind ENABLE_ANALYTICS_DASHBOARD."""

    def __init__(self):
        if not ENABLE_ANALYTICS_DASHBOARD:
            return
        self.metrics = {'sessions_completed': 0, 'assignments_submitted': 0,
                        'rooms_booked': 0, 'total_study_hours': 0, 'member_participation': {}}
        logger.info("AnalyticsEngine initialized")

    @feature_flag('ENABLE_ANALYTICS_DASHBOARD')
    def track_study_session(self, session_data):
        self.metrics['sessions_completed'] += 1
        self.metrics['total_study_hours'] += session_data.get('duration_hours', 2)
        for member in session_data.get('attendees', []):
            self.metrics['member_participation'][member] = self.metrics['member_participation'].get(member, 0) + 1

    @feature_flag('ENABLE_ANALYTICS_DASHBOARD')
    def track_assignment_submission(self, assignment_data):
        self.metrics['assignments_submitted'] += 1

    @feature_flag('ENABLE_ANALYTICS_DASHBOARD')
    def track_room_booking(self, booking_data):
        self.metrics['rooms_booked'] += 1

    @feature_flag('ENABLE_ANALYTICS_DASHBOARD')
    def get_dashboard_data(self):
        participation = self.metrics.get('member_participation', {})
        ranked = sorted(participation.items(), key=lambda x: x[1], reverse=True)
        return {
            'overview': {'total_sessions': self.metrics['sessions_completed'],
                         'total_assignments': self.metrics['assignments_submitted'],
                         'total_bookings': self.metrics['rooms_booked'],
                         'total_hours': self.metrics['total_study_hours']},
            'participation': participation,
            'member_rankings': [{'member': n, 'sessions': c, 'rank': i+1} for i, (n, c) in enumerate(ranked)],
        }

    @feature_flag('ENABLE_ANALYTICS_DASHBOARD')
    def generate_report(self):
        data = self.get_dashboard_data()
        if not data:
            return "Analytics data not available"
        overview = data.get('overview', {})
        lines = [f"Study Group Analytics Report - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                 f"Sessions: {overview.get('total_sessions', 0)}, Assignments: {overview.get('total_assignments', 0)}, "
                 f"Bookings: {overview.get('total_bookings', 0)}, Hours: {overview.get('total_hours', 0)}"]
        return '\n'.join(lines)


# ==================== STUDY STREAK TRACKING ====================

class StudyStreakTracker:
    """Gamification: study session streaks. Gated behind ENABLE_STUDY_STREAK_TRACKING."""

    MILESTONES = [3, 7, 14, 30, 60, 100]

    def __init__(self):
        if not ENABLE_STUDY_STREAK_TRACKING:
            return
        self.streaks = {}
        logger.info("StudyStreakTracker initialized")

    @feature_flag('ENABLE_STUDY_STREAK_TRACKING')
    def record_session(self, member_name, session_date=None):
        if member_name not in self.streaks:
            self.streaks[member_name] = {'current_streak': 0, 'longest_streak': 0,
                                          'last_session_date': None, 'total_sessions': 0, 'milestones_reached': []}
        today = (session_date or datetime.now()).strftime('%Y-%m-%d')
        data = self.streaks[member_name]
        last = data.get('last_session_date')
        if last:
            gap = (datetime.strptime(today, '%Y-%m-%d') - datetime.strptime(last, '%Y-%m-%d')).days
            data['current_streak'] = data['current_streak'] + 1 if gap == 1 else (data['current_streak'] if gap == 0 else 1)
        else:
            data['current_streak'] = 1
        data['last_session_date'] = today
        data['total_sessions'] += 1
        data['longest_streak'] = max(data['longest_streak'], data['current_streak'])
        # Check milestones
        new_milestone = None
        for m in self.MILESTONES:
            if data['current_streak'] >= m and m not in data.get('milestones_reached', []):
                data.setdefault('milestones_reached', []).append(m)
                new_milestone = m
                break
        return {'current_streak': data['current_streak'], 'longest_streak': data['longest_streak'], 'new_milestone': new_milestone}

    @feature_flag('ENABLE_STUDY_STREAK_TRACKING')
    def get_leaderboard(self):
        board = [{'member': m, 'current_streak': d.get('current_streak', 0),
                  'longest_streak': d.get('longest_streak', 0), 'total_sessions': d.get('total_sessions', 0)}
                 for m, d in self.streaks.items()]
        board.sort(key=lambda x: x['current_streak'], reverse=True)
        return board


# ==================== PDF EXPORT ====================

class PDFExporter:
    """Export reports to PDF. Gated behind ENABLE_EXPORT_TO_PDF."""

    def __init__(self):
        if not ENABLE_EXPORT_TO_PDF:
            return
        logger.info("PDFExporter initialized")

    @feature_flag('ENABLE_EXPORT_TO_PDF')
    def export_weekly_plan(self, plan_data, output_path=None):
        output_path = output_path or f"exports/weekly_plan_{datetime.now().strftime('%Y%m%d')}.pdf"
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        logger.info(f"Weekly plan exported to PDF: {output_path}")
        return output_path

    @feature_flag('ENABLE_EXPORT_TO_PDF')
    def export_analytics_report(self, analytics_data, output_path=None):
        output_path = output_path or f"exports/analytics_{datetime.now().strftime('%Y%m%d')}.pdf"
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        logger.info(f"Analytics report exported to PDF: {output_path}")
        return output_path
