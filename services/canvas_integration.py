#!/usr/bin/env python3
"""
Canvas LMS Integration Service
Direct API integration with Canvas LMS for assignment synchronization.
Gated behind ENABLE_CANVAS_LMS_INTEGRATION flag.

Also contains the legacy CSV-based member sync (LEGACY_MEMBER_SYNC)
and the legacy web scraper flag (USE_LEGACY_WEBSCRAPER).
"""

import os
import json
import csv
import logging
from datetime import datetime

from config.feature_flags import (
    ENABLE_CANVAS_LMS_INTEGRATION,
    LEGACY_MEMBER_SYNC,
    USE_LEGACY_WEBSCRAPER,
    is_flag_enabled,
    feature_flag,
)

logger = logging.getLogger(__name__)


# ==================== CANVAS API CLIENT ====================


class CanvasAPIClient:
    """
    Canvas LMS API client for direct integration.
    Gated behind ENABLE_CANVAS_LMS_INTEGRATION flag.
    """

    BASE_URL = "https://learning.london.edu/api/v1"

    def __init__(self):
        if not ENABLE_CANVAS_LMS_INTEGRATION:
            logger.debug("Canvas LMS integration is disabled")
            return

        self.api_token = os.environ.get('CANVAS_API_TOKEN', '')
        self.base_url = os.environ.get('CANVAS_BASE_URL', self.BASE_URL)

        if not self.api_token:
            logger.warning("Canvas API token not configured")

        logger.info(f"CanvasAPIClient initialized for {self.base_url}")

    def _headers(self):
        """Get authenticated headers"""
        return {
            'Authorization': f'Bearer {self.api_token}',
            'Content-Type': 'application/json',
        }

    @feature_flag('ENABLE_CANVAS_LMS_INTEGRATION')
    def get_courses(self):
        """Get enrolled courses"""
        # In production: requests.get(f"{self.base_url}/courses", headers=self._headers())
        logger.info("Canvas API: Fetching courses")
        return []

    @feature_flag('ENABLE_CANVAS_LMS_INTEGRATION')
    def get_assignments(self, course_id):
        """Get assignments for a course"""
        # In production: requests.get(f"{self.base_url}/courses/{course_id}/assignments", headers=self._headers())
        logger.info(f"Canvas API: Fetching assignments for course {course_id}")
        return []

    @feature_flag('ENABLE_CANVAS_LMS_INTEGRATION')
    def get_upcoming_assignments(self):
        """Get all upcoming assignments across courses"""
        # In production: requests.get(f"{self.base_url}/users/self/upcoming_events", headers=self._headers())
        logger.info("Canvas API: Fetching upcoming assignments")
        return []

    @feature_flag('ENABLE_CANVAS_LMS_INTEGRATION')
    def get_group_members(self, group_id):
        """Get members of a study group"""
        # In production: requests.get(f"{self.base_url}/groups/{group_id}/users", headers=self._headers())
        logger.info(f"Canvas API: Fetching group {group_id} members")
        return []

    @feature_flag('ENABLE_CANVAS_LMS_INTEGRATION')
    def get_calendar_events(self, start_date, end_date):
        """Get calendar events in a date range"""
        # In production: requests.get(f"{self.base_url}/calendar_events", params={...}, headers=self._headers())
        logger.info(f"Canvas API: Fetching calendar events {start_date} to {end_date}")
        return []

    @feature_flag('ENABLE_CANVAS_LMS_INTEGRATION')
    def get_user_profile(self, user_id='self'):
        """Get a user's profile"""
        # In production: requests.get(f"{self.base_url}/users/{user_id}/profile", headers=self._headers())
        logger.info(f"Canvas API: Fetching user profile {user_id}")
        return {}

    @feature_flag('ENABLE_CANVAS_LMS_INTEGRATION')
    def submit_assignment(self, course_id, assignment_id, submission_data):
        """Submit an assignment"""
        # In production: requests.post(f"{self.base_url}/courses/{course_id}/assignments/{assignment_id}/submissions", ...)
        logger.info(f"Canvas API: Submitting assignment {assignment_id} for course {course_id}")
        return {'status': 'submitted'}


# ==================== LEGACY CSV MEMBER SYNC ====================
# Dead code - CSV-based sync replaced by Canvas API integration.
# Gated behind LEGACY_MEMBER_SYNC which is always False.
# TODO: Remove entirely (ticket BE-178)


class LegacyCSVMemberSync:
    """
    DEPRECATED: CSV-based member synchronization from Canvas LMS.
    This was used before the Canvas API integration was available.
    Members had to manually export CSV files from Canvas.
    """

    def __init__(self):
        if not LEGACY_MEMBER_SYNC:
            logger.debug("Legacy CSV member sync is disabled (deprecated)")
            return

        self.csv_dir = 'data/csv_imports'
        os.makedirs(self.csv_dir, exist_ok=True)
        logger.warning("LegacyCSVMemberSync initialized - THIS IS DEPRECATED")

    def import_members_from_csv(self, csv_file_path):
        """
        Import study group members from a CSV file.
        DEPRECATED: Use CanvasAPIClient.get_group_members() instead.
        """
        if not LEGACY_MEMBER_SYNC:
            return []

        members = []
        try:
            with open(csv_file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    member = {
                        'name': row.get('Name', row.get('name', '')),
                        'email': row.get('Email', row.get('email', '')),
                        'student_id': row.get('Student ID', row.get('student_id', '')),
                        'section': row.get('Section', row.get('section', '')),
                    }
                    if member['name']:
                        members.append(member)

            logger.info(f"CSV import: Found {len(members)} members in {csv_file_path}")
        except Exception as e:
            logger.error(f"CSV import failed: {e}")

        return members

    def export_members_to_csv(self, members, output_path=None):
        """
        Export members to a CSV file.
        DEPRECATED.
        """
        if not LEGACY_MEMBER_SYNC:
            return None

        output_path = output_path or os.path.join(self.csv_dir, 'members_export.csv')

        try:
            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=['name', 'email', 'student_id', 'section'])
                writer.writeheader()
                for member in members:
                    writer.writerow(member)

            logger.info(f"CSV export: {len(members)} members written to {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"CSV export failed: {e}")
            return None

    def sync_from_csv_directory(self):
        """
        Scan CSV directory for new import files.
        DEPRECATED: Use Canvas API instead.
        """
        if not LEGACY_MEMBER_SYNC:
            return []

        all_members = []
        for filename in os.listdir(self.csv_dir):
            if filename.endswith('.csv'):
                filepath = os.path.join(self.csv_dir, filename)
                members = self.import_members_from_csv(filepath)
                all_members.extend(members)

        return all_members


# ==================== DATA SYNC ROUTER ====================


def get_data_source():
    """
    Get the appropriate data source based on feature flags.
    Demonstrates the evolution from web scraping -> CSV import -> API integration.
    """
    if ENABLE_CANVAS_LMS_INTEGRATION:
        logger.info("Using Canvas API for data synchronization")
        return {
            'source': 'canvas_api',
            'client': CanvasAPIClient(),
            'method': 'Direct API integration',
        }

    if LEGACY_MEMBER_SYNC:
        logger.warning("Using legacy CSV member sync (deprecated)")
        return {
            'source': 'csv_import',
            'client': LegacyCSVMemberSync(),
            'method': 'Manual CSV import',
        }

    if USE_LEGACY_WEBSCRAPER:
        logger.warning("Using legacy web scraper (should migrate to Canvas API)")
        return {
            'source': 'web_scraper',
            'client': None,  # Uses run.py StudyGroupManager
            'method': 'Selenium-based web scraping',
        }

    logger.error("No data source configured!")
    return {
        'source': 'none',
        'client': None,
        'method': 'No data source available',
    }
