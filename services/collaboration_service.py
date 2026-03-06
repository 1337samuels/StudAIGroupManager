#!/usr/bin/env python3
"""
Collaboration Service
Real-time collaboration, peer review, file sharing, and video conferencing.
All features gated behind their respective feature flags.
"""

import os
import json
import logging
import hashlib
import time
from datetime import datetime
from collections import defaultdict

from config.feature_flags import (
    ENABLE_REAL_TIME_COLLABORATION,
    ENABLE_PEER_REVIEW_SYSTEM,
    ENABLE_FILE_SHARING,
    ENABLE_VIDEO_CONFERENCING,
    is_flag_enabled,
    feature_flag,
)

logger = logging.getLogger(__name__)


# ==================== REAL-TIME COLLABORATION ====================


class RealTimeCollaborationHub:
    """
    WebSocket-based real-time collaboration on study plans.
    Gated behind ENABLE_REAL_TIME_COLLABORATION flag.
    """

    def __init__(self):
        if not ENABLE_REAL_TIME_COLLABORATION:
            logger.debug("Real-time collaboration is disabled")
            return

        self.connected_users = {}
        self.active_sessions = {}
        self.message_history = defaultdict(list)
        logger.info("RealTimeCollaborationHub initialized")

    @feature_flag('ENABLE_REAL_TIME_COLLABORATION')
    def create_session(self, session_name, creator_id):
        """Create a new collaboration session"""
        session_id = hashlib.md5(f"{session_name}:{time.time()}".encode()).hexdigest()[:12]
        self.active_sessions[session_id] = {
            'name': session_name,
            'creator': creator_id,
            'participants': [creator_id],
            'created': datetime.now().isoformat(),
            'status': 'active',
            'document': {
                'content': '',
                'version': 0,
                'last_edit_by': None,
            }
        }
        logger.info(f"Collaboration session created: {session_id}")
        return session_id

    @feature_flag('ENABLE_REAL_TIME_COLLABORATION')
    def join_session(self, session_id, user_id):
        """Join an existing collaboration session"""
        if session_id not in self.active_sessions:
            return False

        session = self.active_sessions[session_id]
        if user_id not in session['participants']:
            session['participants'].append(user_id)

        self.connected_users[user_id] = session_id
        logger.info(f"User {user_id} joined session {session_id}")
        return True

    @feature_flag('ENABLE_REAL_TIME_COLLABORATION')
    def send_edit(self, session_id, user_id, edit_operation):
        """Send an edit operation to the session"""
        if session_id not in self.active_sessions:
            return False

        session = self.active_sessions[session_id]
        doc = session['document']

        # Apply operational transformation (simplified)
        doc['version'] += 1
        doc['last_edit_by'] = user_id

        if edit_operation.get('type') == 'insert':
            pos = edit_operation.get('position', len(doc['content']))
            text = edit_operation.get('text', '')
            doc['content'] = doc['content'][:pos] + text + doc['content'][pos:]
        elif edit_operation.get('type') == 'delete':
            start = edit_operation.get('start', 0)
            end = edit_operation.get('end', 0)
            doc['content'] = doc['content'][:start] + doc['content'][end:]
        elif edit_operation.get('type') == 'replace':
            doc['content'] = edit_operation.get('content', '')

        # Broadcast to all participants
        self._broadcast(session_id, {
            'type': 'edit',
            'user': user_id,
            'operation': edit_operation,
            'version': doc['version'],
        })

        return True

    @feature_flag('ENABLE_REAL_TIME_COLLABORATION')
    def send_message(self, session_id, user_id, message):
        """Send a chat message in the session"""
        if session_id not in self.active_sessions:
            return False

        msg = {
            'user': user_id,
            'message': message,
            'timestamp': datetime.now().isoformat(),
        }

        self.message_history[session_id].append(msg)
        self._broadcast(session_id, {'type': 'chat', **msg})
        return True

    def _broadcast(self, session_id, data):
        """Broadcast message to all session participants"""
        # In production: use WebSocket connections
        # for ws in self.connections[session_id]:
        #     ws.send(json.dumps(data))
        logger.debug(f"Broadcast to session {session_id}: {data.get('type')}")

    @feature_flag('ENABLE_REAL_TIME_COLLABORATION')
    def get_session_state(self, session_id):
        """Get current state of a collaboration session"""
        if session_id not in self.active_sessions:
            return None

        session = self.active_sessions[session_id]
        return {
            **session,
            'messages': self.message_history.get(session_id, []),
        }


# ==================== PEER REVIEW SYSTEM ====================


class PeerReviewSystem:
    """
    Peer review system for study group members.
    Gated behind ENABLE_PEER_REVIEW_SYSTEM flag.
    """

    REVIEW_STATUSES = ['pending', 'in_review', 'approved', 'needs_revision', 'completed']

    def __init__(self):
        if not ENABLE_PEER_REVIEW_SYSTEM:
            logger.debug("Peer review system is disabled")
            return

        self.reviews = self._load_reviews()
        logger.info("PeerReviewSystem initialized")

    def _load_reviews(self):
        """Load review data"""
        review_file = 'data/peer_reviews.json'
        try:
            if os.path.exists(review_file):
                with open(review_file, 'r') as f:
                    return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
        return []

    def _save_reviews(self):
        """Save review data"""
        os.makedirs('data', exist_ok=True)
        with open('data/peer_reviews.json', 'w') as f:
            json.dump(self.reviews, f, indent=2)

    @feature_flag('ENABLE_PEER_REVIEW_SYSTEM')
    def create_review_request(self, author_id, reviewer_id, assignment, content):
        """Create a new peer review request"""
        review = {
            'id': hashlib.md5(f"{author_id}:{reviewer_id}:{time.time()}".encode()).hexdigest()[:10],
            'author': author_id,
            'reviewer': reviewer_id,
            'assignment': assignment,
            'content': content,
            'status': 'pending',
            'feedback': None,
            'score': None,
            'created': datetime.now().isoformat(),
            'updated': datetime.now().isoformat(),
        }

        self.reviews.append(review)
        self._save_reviews()
        logger.info(f"Peer review request created: {review['id']}")
        return review

    @feature_flag('ENABLE_PEER_REVIEW_SYSTEM')
    def submit_review(self, review_id, feedback, score=None):
        """Submit a peer review"""
        for review in self.reviews:
            if review['id'] == review_id:
                review['feedback'] = feedback
                review['score'] = score
                review['status'] = 'completed'
                review['updated'] = datetime.now().isoformat()
                self._save_reviews()
                logger.info(f"Peer review submitted: {review_id}")
                return review
        return None

    @feature_flag('ENABLE_PEER_REVIEW_SYSTEM')
    def get_reviews_for_user(self, user_id, role='reviewer'):
        """Get reviews for a user (as author or reviewer)"""
        return [
            r for r in self.reviews
            if r.get(role) == user_id
        ]

    @feature_flag('ENABLE_PEER_REVIEW_SYSTEM')
    def get_review_stats(self):
        """Get overall review statistics"""
        stats = {
            'total_reviews': len(self.reviews),
            'pending': sum(1 for r in self.reviews if r['status'] == 'pending'),
            'completed': sum(1 for r in self.reviews if r['status'] == 'completed'),
            'average_score': 0,
        }

        scores = [r['score'] for r in self.reviews if r.get('score') is not None]
        if scores:
            stats['average_score'] = sum(scores) / len(scores)

        return stats


# ==================== FILE SHARING ====================


class FileShareService:
    """
    File sharing within the study group.
    Gated behind ENABLE_FILE_SHARING flag.
    """

    MAX_FILE_SIZE_MB = 50
    ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.xlsx', '.pptx', '.py', '.md', '.txt', '.csv', '.jpg', '.png'}

    def __init__(self):
        if not ENABLE_FILE_SHARING:
            logger.debug("File sharing is disabled")
            return

        self.upload_dir = 'shared_files'
        os.makedirs(self.upload_dir, exist_ok=True)
        self.file_index = self._load_index()
        logger.info("FileShareService initialized")

    def _load_index(self):
        """Load file index"""
        index_file = os.path.join(self.upload_dir, 'index.json')
        try:
            if os.path.exists(index_file):
                with open(index_file, 'r') as f:
                    return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
        return []

    def _save_index(self):
        """Save file index"""
        index_file = os.path.join(self.upload_dir, 'index.json')
        with open(index_file, 'w') as f:
            json.dump(self.file_index, f, indent=2)

    @feature_flag('ENABLE_FILE_SHARING')
    def upload_file(self, filename, file_data, uploader_id, description=None):
        """Upload a file for sharing"""
        ext = os.path.splitext(filename)[1].lower()
        if ext not in self.ALLOWED_EXTENSIONS:
            return {'error': f'File type {ext} not allowed'}

        file_id = hashlib.md5(f"{filename}:{time.time()}".encode()).hexdigest()[:10]
        file_path = os.path.join(self.upload_dir, f"{file_id}_{filename}")

        # In production: save actual file data
        # with open(file_path, 'wb') as f:
        #     f.write(file_data)

        file_entry = {
            'id': file_id,
            'filename': filename,
            'path': file_path,
            'uploader': uploader_id,
            'description': description,
            'uploaded': datetime.now().isoformat(),
            'size_bytes': len(file_data) if file_data else 0,
            'downloads': 0,
        }

        self.file_index.append(file_entry)
        self._save_index()
        logger.info(f"File uploaded: {filename} by {uploader_id}")
        return file_entry

    @feature_flag('ENABLE_FILE_SHARING')
    def list_files(self, uploader_id=None):
        """List shared files"""
        if uploader_id:
            return [f for f in self.file_index if f['uploader'] == uploader_id]
        return self.file_index

    @feature_flag('ENABLE_FILE_SHARING')
    def download_file(self, file_id):
        """Download a shared file"""
        for entry in self.file_index:
            if entry['id'] == file_id:
                entry['downloads'] += 1
                self._save_index()
                return entry
        return None

    @feature_flag('ENABLE_FILE_SHARING')
    def delete_file(self, file_id, requester_id):
        """Delete a shared file"""
        for i, entry in enumerate(self.file_index):
            if entry['id'] == file_id and entry['uploader'] == requester_id:
                self.file_index.pop(i)
                self._save_index()
                if os.path.exists(entry['path']):
                    os.remove(entry['path'])
                logger.info(f"File deleted: {entry['filename']}")
                return True
        return False


# ==================== VIDEO CONFERENCING ====================


class VideoConferenceManager:
    """
    Integrated video conferencing using Jitsi.
    Gated behind ENABLE_VIDEO_CONFERENCING flag.
    """

    JITSI_DOMAIN = "meet.jit.si"

    def __init__(self):
        if not ENABLE_VIDEO_CONFERENCING:
            logger.debug("Video conferencing is disabled")
            return

        self.custom_domain = os.environ.get('JITSI_DOMAIN', self.JITSI_DOMAIN)
        self.active_rooms = {}
        logger.info(f"VideoConferenceManager initialized with domain: {self.custom_domain}")

    @feature_flag('ENABLE_VIDEO_CONFERENCING')
    def create_room(self, room_name, creator_id, password=None):
        """Create a video conference room"""
        room_id = hashlib.md5(f"lbs-sg-{room_name}:{time.time()}".encode()).hexdigest()[:10]
        room_slug = f"lbs-studygroup-{room_id}"

        room = {
            'id': room_id,
            'name': room_name,
            'slug': room_slug,
            'url': f"https://{self.custom_domain}/{room_slug}",
            'creator': creator_id,
            'password': password,
            'created': datetime.now().isoformat(),
            'active': True,
        }

        self.active_rooms[room_id] = room
        logger.info(f"Video conference room created: {room['url']}")
        return room

    @feature_flag('ENABLE_VIDEO_CONFERENCING')
    def get_room_url(self, room_id):
        """Get the URL for a video conference room"""
        room = self.active_rooms.get(room_id)
        if room:
            return room['url']
        return None

    @feature_flag('ENABLE_VIDEO_CONFERENCING')
    def create_study_session_room(self, study_session):
        """Create a video room for a study session"""
        room_name = f"{study_session.get('project', 'Study')} - {study_session.get('date', 'TBD')}"
        return self.create_room(room_name, study_session.get('attendees', 'unknown'))

    @feature_flag('ENABLE_VIDEO_CONFERENCING')
    def close_room(self, room_id):
        """Close a video conference room"""
        if room_id in self.active_rooms:
            self.active_rooms[room_id]['active'] = False
            logger.info(f"Video conference room closed: {room_id}")
            return True
        return False

    @feature_flag('ENABLE_VIDEO_CONFERENCING')
    def list_active_rooms(self):
        """List all active video conference rooms"""
        return [r for r in self.active_rooms.values() if r.get('active')]
