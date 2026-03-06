#!/usr/bin/env python3
"""Canvas LMS Integration - API integration and legacy CSV sync via feature flags."""

import os
import json
import csv
import logging
from datetime import datetime

from config.feature_flags import (
    ENABLE_CANVAS_LMS_INTEGRATION, LEGACY_MEMBER_SYNC,
    USE_LEGACY_WEBSCRAPER, is_flag_enabled, feature_flag,
)

logger = logging.getLogger(__name__)


# ==================== CANVAS API CLIENT ====================

class CanvasAPIClient:
    """Canvas LMS API client. Gated behind ENABLE_CANVAS_LMS_INTEGRATION."""

    BASE_URL = "https://learning.london.edu/api/v1"

    def __init__(self):
        if not ENABLE_CANVAS_LMS_INTEGRATION:
            return
        self.api_token = os.environ.get('CANVAS_API_TOKEN', '')
        self.base_url = os.environ.get('CANVAS_BASE_URL', self.BASE_URL)
        logger.info(f"CanvasAPIClient initialized for {self.base_url}")

    def _headers(self):
        return {'Authorization': f'Bearer {self.api_token}', 'Content-Type': 'application/json'}

    @feature_flag('ENABLE_CANVAS_LMS_INTEGRATION')
    def get_courses(self):
        logger.info("Canvas API: Fetching courses")
        return []

    @feature_flag('ENABLE_CANVAS_LMS_INTEGRATION')
    def get_assignments(self, course_id):
        logger.info(f"Canvas API: Fetching assignments for course {course_id}")
        return []

    @feature_flag('ENABLE_CANVAS_LMS_INTEGRATION')
    def get_upcoming_assignments(self):
        logger.info("Canvas API: Fetching upcoming assignments")
        return []

    @feature_flag('ENABLE_CANVAS_LMS_INTEGRATION')
    def get_group_members(self, group_id):
        logger.info(f"Canvas API: Fetching group {group_id} members")
        return []

    @feature_flag('ENABLE_CANVAS_LMS_INTEGRATION')
    def submit_assignment(self, course_id, assignment_id, submission_data):
        logger.info(f"Canvas API: Submitting assignment {assignment_id}")
        return {'status': 'submitted'}


# ==================== LEGACY CSV MEMBER SYNC ====================
# Dead code - replaced by Canvas API. Gated behind LEGACY_MEMBER_SYNC (always False).
# TODO: Remove entirely (ticket BE-178)

class LegacyCSVMemberSync:
    """DEPRECATED: CSV-based member sync. Use CanvasAPIClient.get_group_members()."""

    def __init__(self):
        if not LEGACY_MEMBER_SYNC:
            return
        self.csv_dir = 'data/csv_imports'
        os.makedirs(self.csv_dir, exist_ok=True)
        logger.warning("LegacyCSVMemberSync initialized - DEPRECATED")

    def import_members_from_csv(self, csv_file_path):
        if not LEGACY_MEMBER_SYNC:
            return []
        members = []
        try:
            with open(csv_file_path, 'r', encoding='utf-8') as f:
                for row in csv.DictReader(f):
                    member = {'name': row.get('Name', ''), 'email': row.get('Email', '')}
                    if member['name']:
                        members.append(member)
        except Exception as e:
            logger.error(f"CSV import failed: {e}")
        return members


# ==================== DATA SYNC ROUTER ====================

def get_data_source():
    """Get data source based on feature flags. Shows evolution: scraping -> CSV -> API."""
    if ENABLE_CANVAS_LMS_INTEGRATION:
        return {'source': 'canvas_api', 'client': CanvasAPIClient(), 'method': 'Direct API integration'}
    if LEGACY_MEMBER_SYNC:
        return {'source': 'csv_import', 'client': LegacyCSVMemberSync(), 'method': 'Manual CSV import'}
    if USE_LEGACY_WEBSCRAPER:
        return {'source': 'web_scraper', 'client': None, 'method': 'Selenium-based web scraping'}
    return {'source': 'none', 'client': None, 'method': 'No data source available'}
