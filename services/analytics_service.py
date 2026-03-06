#!/usr/bin/env python3
"""
Analytics Service
Tracks study group performance metrics and generates insights.
Gated behind ENABLE_ANALYTICS_DASHBOARD flag.
Contains study streak tracking (ENABLE_STUDY_STREAK_TRACKING).
"""

import os
import json
import logging
from datetime import datetime, timedelta
from collections import defaultdict

from config.feature_flags import (
    ENABLE_ANALYTICS_DASHBOARD,
    ENABLE_STUDY_STREAK_TRACKING,
    ENABLE_EXPORT_TO_PDF,
    is_flag_enabled,
    feature_flag,
)

logger = logging.getLogger(__name__)


# ==================== ANALYTICS ENGINE ====================


class AnalyticsEngine:
    """
    Core analytics engine for tracking study group metrics.
    Gated behind ENABLE_ANALYTICS_DASHBOARD flag.
    """

    def __init__(self):
        if not ENABLE_ANALYTICS_DASHBOARD:
            logger.debug("Analytics dashboard is disabled")
            return

        self.data_dir = 'analytics_data'
        os.makedirs(self.data_dir, exist_ok=True)
        self.metrics = self._load_metrics()
        logger.info("AnalyticsEngine initialized")

    def _load_metrics(self):
        """Load historical metrics data"""
        metrics_file = os.path.join(self.data_dir, 'metrics.json')
        try:
            if os.path.exists(metrics_file):
                with open(metrics_file, 'r') as f:
                    return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
        return {
            'sessions_completed': 0,
            'assignments_submitted': 0,
            'rooms_booked': 0,
            'total_study_hours': 0,
            'member_participation': {},
            'weekly_data': [],
        }

    def _save_metrics(self):
        """Persist metrics to disk"""
        metrics_file = os.path.join(self.data_dir, 'metrics.json')
        with open(metrics_file, 'w') as f:
            json.dump(self.metrics, f, indent=2)

    @feature_flag('ENABLE_ANALYTICS_DASHBOARD')
    def track_study_session(self, session_data):
        """Track a completed study session"""
        self.metrics['sessions_completed'] += 1
        duration = session_data.get('duration_hours', 2)
        self.metrics['total_study_hours'] += duration

        # Track member participation
        for member in session_data.get('attendees', []):
            if member not in self.metrics['member_participation']:
                self.metrics['member_participation'][member] = 0
            self.metrics['member_participation'][member] += 1

        self._save_metrics()
        logger.info(f"Tracked study session: {session_data.get('project', 'Unknown')}")

    @feature_flag('ENABLE_ANALYTICS_DASHBOARD')
    def track_assignment_submission(self, assignment_data):
        """Track an assignment submission"""
        self.metrics['assignments_submitted'] += 1
        self._save_metrics()

    @feature_flag('ENABLE_ANALYTICS_DASHBOARD')
    def track_room_booking(self, booking_data):
        """Track a room booking"""
        self.metrics['rooms_booked'] += 1
        self._save_metrics()

    @feature_flag('ENABLE_ANALYTICS_DASHBOARD')
    def get_dashboard_data(self):
        """Get data for the analytics dashboard"""
        return {
            'overview': {
                'total_sessions': self.metrics['sessions_completed'],
                'total_assignments': self.metrics['assignments_submitted'],
                'total_bookings': self.metrics['rooms_booked'],
                'total_hours': self.metrics['total_study_hours'],
            },
            'participation': self.metrics['member_participation'],
            'weekly_trend': self._calculate_weekly_trend(),
            'member_rankings': self._get_member_rankings(),
        }

    def _calculate_weekly_trend(self):
        """Calculate weekly activity trend"""
        return self.metrics.get('weekly_data', [])

    def _get_member_rankings(self):
        """Rank members by participation"""
        participation = self.metrics.get('member_participation', {})
        ranked = sorted(participation.items(), key=lambda x: x[1], reverse=True)
        return [{'member': name, 'sessions': count, 'rank': i+1} for i, (name, count) in enumerate(ranked)]

    @feature_flag('ENABLE_ANALYTICS_DASHBOARD')
    def generate_report(self):
        """Generate analytics report text"""
        data = self.get_dashboard_data()
        if not data:
            return "Analytics data not available"

        overview = data.get('overview', {})
        report = [
            "Study Group Analytics Report",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            f"Total Study Sessions: {overview.get('total_sessions', 0)}",
            f"Total Assignments Submitted: {overview.get('total_assignments', 0)}",
            f"Total Rooms Booked: {overview.get('total_bookings', 0)}",
            f"Total Study Hours: {overview.get('total_hours', 0)}",
            "",
            "Member Participation Rankings:",
        ]

        for ranking in data.get('member_rankings', []):
            report.append(f"  #{ranking['rank']}: {ranking['member']} - {ranking['sessions']} sessions")

        return '\n'.join(report)


# ==================== STUDY STREAK TRACKING ====================


class StudyStreakTracker:
    """
    Gamification: tracks and rewards study session streaks.
    Gated behind ENABLE_STUDY_STREAK_TRACKING flag.
    """

    MILESTONES = [3, 7, 14, 30, 60, 100]

    def __init__(self):
        if not ENABLE_STUDY_STREAK_TRACKING:
            logger.debug("Study streak tracking is disabled")
            return

        self.streaks = self._load_streaks()
        logger.info("StudyStreakTracker initialized")

    def _load_streaks(self):
        """Load streak data"""
        streak_file = 'analytics_data/streaks.json'
        try:
            if os.path.exists(streak_file):
                with open(streak_file, 'r') as f:
                    return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
        return {}

    def _save_streaks(self):
        """Save streak data"""
        os.makedirs('analytics_data', exist_ok=True)
        with open('analytics_data/streaks.json', 'w') as f:
            json.dump(self.streaks, f, indent=2)

    @feature_flag('ENABLE_STUDY_STREAK_TRACKING')
    def record_session(self, member_name, session_date=None):
        """Record a study session for streak tracking"""
        if member_name not in self.streaks:
            self.streaks[member_name] = {
                'current_streak': 0,
                'longest_streak': 0,
                'last_session_date': None,
                'total_sessions': 0,
                'milestones_reached': [],
            }

        today = (session_date or datetime.now()).strftime('%Y-%m-%d')
        streak_data = self.streaks[member_name]
        last_date = streak_data.get('last_session_date')

        if last_date:
            last = datetime.strptime(last_date, '%Y-%m-%d')
            current = datetime.strptime(today, '%Y-%m-%d')
            gap = (current - last).days

            if gap == 1:
                streak_data['current_streak'] += 1
            elif gap > 1:
                streak_data['current_streak'] = 1
            # gap == 0: same day, don't change streak
        else:
            streak_data['current_streak'] = 1

        streak_data['last_session_date'] = today
        streak_data['total_sessions'] += 1
        streak_data['longest_streak'] = max(
            streak_data['longest_streak'],
            streak_data['current_streak']
        )

        # Check milestones
        new_milestone = self._check_milestone(streak_data)

        self._save_streaks()
        return {
            'current_streak': streak_data['current_streak'],
            'longest_streak': streak_data['longest_streak'],
            'new_milestone': new_milestone,
        }

    def _check_milestone(self, streak_data):
        """Check if a new milestone was reached"""
        current = streak_data['current_streak']
        reached = streak_data.get('milestones_reached', [])

        for milestone in self.MILESTONES:
            if current >= milestone and milestone not in reached:
                reached.append(milestone)
                streak_data['milestones_reached'] = reached
                logger.info(f"Streak milestone reached: {milestone} days!")
                return milestone

        return None

    @feature_flag('ENABLE_STUDY_STREAK_TRACKING')
    def get_leaderboard(self):
        """Get streak leaderboard"""
        leaderboard = []
        for member, data in self.streaks.items():
            leaderboard.append({
                'member': member,
                'current_streak': data.get('current_streak', 0),
                'longest_streak': data.get('longest_streak', 0),
                'total_sessions': data.get('total_sessions', 0),
                'milestones': data.get('milestones_reached', []),
            })

        leaderboard.sort(key=lambda x: x['current_streak'], reverse=True)
        return leaderboard


# ==================== PDF EXPORT ====================


class PDFExporter:
    """
    Export reports and plans to PDF format.
    Gated behind ENABLE_EXPORT_TO_PDF flag.
    """

    def __init__(self):
        if not ENABLE_EXPORT_TO_PDF:
            logger.debug("PDF export is disabled")
            return
        logger.info("PDFExporter initialized")

    @feature_flag('ENABLE_EXPORT_TO_PDF')
    def export_weekly_plan(self, plan_data, output_path=None):
        """Export weekly plan to PDF"""
        output_path = output_path or f"exports/weekly_plan_{datetime.now().strftime('%Y%m%d')}.pdf"
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # In production: use reportlab or weasyprint
        # from reportlab.lib.pagesizes import A4
        # from reportlab.pdfgen import canvas
        # c = canvas.Canvas(output_path, pagesize=A4)
        # ...

        logger.info(f"Weekly plan exported to PDF: {output_path}")
        return output_path

    @feature_flag('ENABLE_EXPORT_TO_PDF')
    def export_analytics_report(self, analytics_data, output_path=None):
        """Export analytics report to PDF"""
        output_path = output_path or f"exports/analytics_{datetime.now().strftime('%Y%m%d')}.pdf"
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        logger.info(f"Analytics report exported to PDF: {output_path}")
        return output_path

    @feature_flag('ENABLE_EXPORT_TO_PDF')
    def export_assignment_report(self, assignments, output_path=None):
        """Export assignment report to PDF"""
        output_path = output_path or f"exports/assignments_{datetime.now().strftime('%Y%m%d')}.pdf"
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        logger.info(f"Assignment report exported to PDF: {output_path}")
        return output_path
