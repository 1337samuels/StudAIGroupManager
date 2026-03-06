#!/usr/bin/env python3
"""Collaboration Service - Real-time collaboration, peer review, file sharing, video conferencing."""

import os
import json
import logging
import hashlib
import time
from datetime import datetime

from config.feature_flags import (
    ENABLE_REAL_TIME_COLLABORATION, ENABLE_PEER_REVIEW_SYSTEM,
    ENABLE_FILE_SHARING, ENABLE_VIDEO_CONFERENCING,
    is_flag_enabled, feature_flag,
)

logger = logging.getLogger(__name__)


# ==================== REAL-TIME COLLABORATION ====================

class RealTimeCollaborationHub:
    """WebSocket-based real-time collaboration. Gated behind ENABLE_REAL_TIME_COLLABORATION."""

    def __init__(self):
        if not ENABLE_REAL_TIME_COLLABORATION:
            return
        self.active_sessions = {}
        logger.info("RealTimeCollaborationHub initialized")

    @feature_flag('ENABLE_REAL_TIME_COLLABORATION')
    def create_session(self, session_name, creator_id):
        session_id = hashlib.md5(f"{session_name}:{time.time()}".encode()).hexdigest()[:12]
        self.active_sessions[session_id] = {
            'name': session_name, 'creator': creator_id, 'participants': [creator_id],
            'created': datetime.now().isoformat(), 'status': 'active',
            'document': {'content': '', 'version': 0}}
        return session_id

    @feature_flag('ENABLE_REAL_TIME_COLLABORATION')
    def join_session(self, session_id, user_id):
        if session_id not in self.active_sessions:
            return False
        session = self.active_sessions[session_id]
        if user_id not in session['participants']:
            session['participants'].append(user_id)
        return True

    @feature_flag('ENABLE_REAL_TIME_COLLABORATION')
    def send_edit(self, session_id, user_id, edit_operation):
        if session_id not in self.active_sessions:
            return False
        doc = self.active_sessions[session_id]['document']
        doc['version'] += 1
        doc['last_edit_by'] = user_id
        if edit_operation.get('type') == 'replace':
            doc['content'] = edit_operation.get('content', '')
        return True

    @feature_flag('ENABLE_REAL_TIME_COLLABORATION')
    def get_session_state(self, session_id):
        return self.active_sessions.get(session_id)


# ==================== PEER REVIEW SYSTEM ====================

class PeerReviewSystem:
    """Peer review for study group members. Gated behind ENABLE_PEER_REVIEW_SYSTEM."""

    def __init__(self):
        if not ENABLE_PEER_REVIEW_SYSTEM:
            return
        self.reviews = []
        logger.info("PeerReviewSystem initialized")

    @feature_flag('ENABLE_PEER_REVIEW_SYSTEM')
    def create_review_request(self, author_id, reviewer_id, assignment, content):
        review = {'id': hashlib.md5(f"{author_id}:{time.time()}".encode()).hexdigest()[:10],
                  'author': author_id, 'reviewer': reviewer_id, 'assignment': assignment,
                  'content': content, 'status': 'pending', 'feedback': None,
                  'created': datetime.now().isoformat()}
        self.reviews.append(review)
        return review

    @feature_flag('ENABLE_PEER_REVIEW_SYSTEM')
    def submit_review(self, review_id, feedback, score=None):
        for review in self.reviews:
            if review['id'] == review_id:
                review.update({'feedback': feedback, 'score': score, 'status': 'completed'})
                return review
        return None

    @feature_flag('ENABLE_PEER_REVIEW_SYSTEM')
    def get_reviews_for_user(self, user_id, role='reviewer'):
        return [r for r in self.reviews if r.get(role) == user_id]

    @feature_flag('ENABLE_PEER_REVIEW_SYSTEM')
    def get_review_stats(self):
        scores = [r['score'] for r in self.reviews if r.get('score') is not None]
        return {'total_reviews': len(self.reviews),
                'pending': sum(1 for r in self.reviews if r['status'] == 'pending'),
                'completed': sum(1 for r in self.reviews if r['status'] == 'completed'),
                'average_score': sum(scores) / len(scores) if scores else 0}


# ==================== FILE SHARING ====================

class FileShareService:
    """File sharing within study group. Gated behind ENABLE_FILE_SHARING."""

    ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.xlsx', '.pptx', '.py', '.md', '.txt'}

    def __init__(self):
        if not ENABLE_FILE_SHARING:
            return
        self.file_index = []
        logger.info("FileShareService initialized")

    @feature_flag('ENABLE_FILE_SHARING')
    def upload_file(self, filename, file_data, uploader_id, description=None):
        ext = os.path.splitext(filename)[1].lower()
        if ext not in self.ALLOWED_EXTENSIONS:
            return {'error': f'File type {ext} not allowed'}
        file_id = hashlib.md5(f"{filename}:{time.time()}".encode()).hexdigest()[:10]
        entry = {'id': file_id, 'filename': filename, 'uploader': uploader_id,
                 'description': description, 'uploaded': datetime.now().isoformat()}
        self.file_index.append(entry)
        return entry

    @feature_flag('ENABLE_FILE_SHARING')
    def list_files(self, uploader_id=None):
        if uploader_id:
            return [f for f in self.file_index if f['uploader'] == uploader_id]
        return self.file_index

    @feature_flag('ENABLE_FILE_SHARING')
    def delete_file(self, file_id, requester_id):
        for i, entry in enumerate(self.file_index):
            if entry['id'] == file_id and entry['uploader'] == requester_id:
                self.file_index.pop(i)
                return True
        return False


# ==================== VIDEO CONFERENCING ====================

class VideoConferenceManager:
    """Jitsi video conferencing. Gated behind ENABLE_VIDEO_CONFERENCING."""

    JITSI_DOMAIN = "meet.jit.si"

    def __init__(self):
        if not ENABLE_VIDEO_CONFERENCING:
            return
        self.custom_domain = os.environ.get('JITSI_DOMAIN', self.JITSI_DOMAIN)
        self.active_rooms = {}
        logger.info(f"VideoConferenceManager: {self.custom_domain}")

    @feature_flag('ENABLE_VIDEO_CONFERENCING')
    def create_room(self, room_name, creator_id, password=None):
        room_id = hashlib.md5(f"lbs-sg-{room_name}:{time.time()}".encode()).hexdigest()[:10]
        room = {'id': room_id, 'name': room_name,
                'url': f"https://{self.custom_domain}/lbs-studygroup-{room_id}",
                'creator': creator_id, 'active': True}
        self.active_rooms[room_id] = room
        return room

    @feature_flag('ENABLE_VIDEO_CONFERENCING')
    def get_room_url(self, room_id):
        room = self.active_rooms.get(room_id)
        return room['url'] if room else None

    @feature_flag('ENABLE_VIDEO_CONFERENCING')
    def close_room(self, room_id):
        if room_id in self.active_rooms:
            self.active_rooms[room_id]['active'] = False
            return True
        return False

    @feature_flag('ENABLE_VIDEO_CONFERENCING')
    def list_active_rooms(self):
        return [r for r in self.active_rooms.values() if r.get('active')]
