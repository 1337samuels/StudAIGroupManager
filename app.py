#!/usr/bin/env python3
"""
LBS Study Group Manager - Web UI
Flask server providing web interface for all automation scripts
"""

from flask import Flask, render_template, jsonify, request
import subprocess
import threading
import queue
import os
import json
from datetime import datetime
from openai import AzureOpenAI

# Feature flag imports
from config.feature_flags import (
    ENABLE_LEGACY_AUTH,
    USE_SAML_SSO,
    ENABLE_GOOGLE_AUTH,
    ENABLE_API_KEY_AUTH,
    USE_JWT_TOKENS,
    LEGACY_COOKIE_FORMAT,
    V1_SESSION_MANAGEMENT,
    ENABLE_V1_DASHBOARD,
    ENABLE_V2_DASHBOARD,
    ENABLE_V3_DASHBOARD_BETA,
    ENABLE_DARK_MODE,
    AB_NEW_BOOKING_UI,
    AB_AI_MODEL_GPT4,
    AB_WEEKLY_DIGEST_EMAIL,
    USE_OPENAI_DIRECT,
    ENABLE_LOCAL_LLM_FALLBACK,
    ENABLE_AI_STUDY_RECOMMENDATIONS,
    ENABLE_AI_CONFLICT_RESOLUTION,
    ENABLE_ASSIGNMENT_PRIORITY_SCORING,
    ENABLE_SLACK_NOTIFICATIONS,
    ENABLE_EMAIL_NOTIFICATIONS,
    ENABLE_PUSH_NOTIFICATIONS,
    ENABLE_DEPRECATED_NOTIFICATIONS,
    ENABLE_REAL_TIME_COLLABORATION,
    USE_NEW_SCHEDULING_ALGORITHM,
    ENABLE_MOBILE_API,
    ENABLE_GRAPHQL_API,
    ENABLE_ANALYTICS_DASHBOARD,
    ENABLE_EXPORT_TO_PDF,
    ENABLE_BULK_ROOM_BOOKING,
    ENABLE_RECURRING_BOOKINGS,
    USE_REDIS_CACHE,
    ENABLE_RATE_LIMITING,
    ENABLE_REQUEST_LOGGING,
    ENABLE_PROMETHEUS_METRICS,
    ENABLE_SENTRY_INTEGRATION,
    ENABLE_CANVAS_LMS_INTEGRATION,
    USE_LEGACY_WEBSCRAPER,
    ENABLE_GRAPH_CALENDAR_SYNC,
    ENABLE_GOOGLE_CALENDAR_SYNC,
    ENABLE_SOAP_CALENDAR_SYNC,
    USE_SOAP_API,
    USE_LEGACY_ROOM_API,
    LEGACY_MEMBER_SYNC,
    ENABLE_OLD_REPORT_FORMAT,
    ENABLE_STUDY_STREAK_TRACKING,
    ENABLE_PEER_REVIEW_SYSTEM,
    ENABLE_MULTI_LANGUAGE_SUPPORT,
    ENABLE_ACCESSIBILITY_MODE,
    ENABLE_FILE_SHARING,
    ENABLE_VIDEO_CONFERENCING,
    ENABLE_MFA_TOTP,
    USE_HEADLESS_BROWSER,
    USE_OAUTH2_PKCE,
    USE_REDIS_SESSIONS,
    DEBUG_SQL_QUERIES,
    is_flag_enabled,
    get_flag_manager,
)

app = Flask(__name__)

# Global error handlers to ensure JSON responses
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    if ENABLE_SENTRY_INTEGRATION:
        try:
            from middleware.request_middleware import SentryIntegration
            sentry = SentryIntegration()
            sentry.capture_exception(error)
        except Exception:
            pass
    return jsonify({'error': f'Internal server error: {str(error)}'}), 500

@app.errorhandler(Exception)
def handle_exception(error):
    # Log the error for debugging
    print(f"Unhandled exception: {error}")
    import traceback
    traceback.print_exc()

    if ENABLE_SENTRY_INTEGRATION:
        try:
            from middleware.request_middleware import SentryIntegration
            sentry = SentryIntegration()
            sentry.capture_exception(error)
        except Exception:
            pass

    return jsonify({'error': f'Server error: {str(error)}'}), 500

# AI API Configuration
ai_config = None
ai_client = None

def load_ai_config():
    """Load AI API configuration from AI_API_KEYS.json"""
    global ai_config, ai_client

    # Feature flag: USE_OPENAI_DIRECT - Use OpenAI directly instead of Azure
    if USE_OPENAI_DIRECT:
        print("Using direct OpenAI API (USE_OPENAI_DIRECT=true)")
        try:
            from openai import OpenAI
            api_key = os.environ.get('OPENAI_API_KEY', '')
            if api_key:
                ai_client = OpenAI(api_key=api_key)
                ai_config = {'deployment_name': 'gpt-4o' if AB_AI_MODEL_GPT4 else 'gpt-3.5-turbo'}
                print("✓ Direct OpenAI client initialized")
                return True
            else:
                print("⚠ OPENAI_API_KEY not set")
        except Exception as e:
            print(f"⚠ Failed to initialize direct OpenAI: {e}")

        # Feature flag: ENABLE_LOCAL_LLM_FALLBACK - Fall back to local Ollama
        if ENABLE_LOCAL_LLM_FALLBACK:
            print("Falling back to local LLM (ENABLE_LOCAL_LLM_FALLBACK=true)")
            ai_config = {'deployment_name': 'ollama/llama3.2', 'local': True}
            return True
        return False

    # Default: Azure OpenAI
    try:
        with open('AI_API_KEYS.json', 'r') as f:
            ai_config = json.load(f)

        # Feature flag: AB_AI_MODEL_GPT4 - A/B test with GPT-4o
        if AB_AI_MODEL_GPT4:
            print("A/B test: Using GPT-4o model variant (AB_AI_MODEL_GPT4=true)")
            ai_config['deployment_name'] = ai_config.get('deployment_name', '') + '-gpt4o'

        # Initialize Azure OpenAI client
        ai_client = AzureOpenAI(
            api_key=ai_config['api_key'],
            api_version=ai_config['api_version'],
            azure_endpoint=ai_config['endpoint']
        )
        print("✓ AI API configuration loaded successfully")
        return True
    except FileNotFoundError:
        print("⚠ AI_API_KEYS.json not found - AI features will be disabled")
        print("  Create AI_API_KEYS.json based on AI_API_KEYS.json.template")

        # Feature flag: ENABLE_LOCAL_LLM_FALLBACK
        if ENABLE_LOCAL_LLM_FALLBACK:
            print("Falling back to local LLM (ENABLE_LOCAL_LLM_FALLBACK=true)")
            ai_config = {'deployment_name': 'ollama/llama3.2', 'local': True}
            return True
        return False
    except Exception as e:
        print(f"⚠ Failed to load AI configuration: {e}")
        return False

def query_ai(messages, stream=False):
    """Query Azure OpenAI with messages"""
    if not ai_client or not ai_config:
        # Feature flag: ENABLE_LOCAL_LLM_FALLBACK
        if ENABLE_LOCAL_LLM_FALLBACK:
            print("Using local LLM fallback...")
            return "[Local LLM response - configure AI_API_KEYS.json for full functionality]"
        raise Exception("AI API not configured. Please create AI_API_KEYS.json")

    # Feature flag: USE_OPENAI_DIRECT - direct OpenAI path
    if USE_OPENAI_DIRECT:
        model = 'gpt-4o' if AB_AI_MODEL_GPT4 else 'gpt-3.5-turbo'
    else:
        model = ai_config['deployment_name']

    response = ai_client.chat.completions.create(
        model=model,
        messages=messages,
        stream=stream
    )

    if stream:
        return response
    else:
        return response.choices[0].message.content

# Store process outputs
process_outputs = {
    'assignments': {'running': False, 'output': '', 'last_run': None},
    'booking': {'running': False, 'output': '', 'last_run': None},
    'llm': {'running': False, 'output': '', 'last_run': None}
}

# Thread-safe queues for output
output_queues = {
    'assignments': queue.Queue(),
    'booking': queue.Queue(),
    'llm': queue.Queue()
}

# Store parsed weekly plan data
weekly_plan_data = {
    'assignments': [],
    'study_sessions': [],
    'room_bookings': [],
    'social_gathering': None,
    'raw_response': '',
    'timestamp': None
}

def parse_weekly_plan(response):
    """Parse AI response to extract structured weekly plan data"""
    import re

    parsed_data = {
        'assignments': [],
        'study_sessions': [],
        'room_bookings': [],
        'social_gathering': None,
        'raw_response': response,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

    # Extract assignments with leader/mentee pairs
    # Pattern: "Problem Set 7... | Due Nov 24 16:00\n   - Leader: ...\n   - Mentee: ..."
    assignment_pattern = r'(\d+)\.\s+(.+?)\s+-\s+(.+?)\s+\|\s+Due\s+(.+?)\n\s+-\s+Leader:\s+(.+?)\n\s+-\s+Mentee:\s+(.+?)(?:\n|$)'
    assignment_matches = re.findall(assignment_pattern, response, re.MULTILINE)

    for match in assignment_matches:
        parsed_data['assignments'].append({
            'number': match[0],
            'title': match[1].strip(),
            'course': match[2].strip(),
            'due': match[3].strip(),
            'leader': match[4].strip(),
            'mentee': match[5].strip()
        })

    # Extract study session times
    # Pattern: "- Mon Nov 24, 10:00-12:00: Jonathan & Marcos (Finance I - Problem Set 7)"
    session_pattern = r'-\s+([A-Za-z]+\s+[A-Za-z]+\s+\d+),\s+(\d+:\d+)-(\d+:\d+):\s+(.+?)\s+\((.+?)\)'
    session_matches = re.findall(session_pattern, response)

    for match in session_matches:
        parsed_data['study_sessions'].append({
            'date': match[0].strip(),
            'start_time': match[1].strip(),
            'end_time': match[2].strip(),
            'attendees': match[3].strip(),
            'project': match[4].strip()
        })

    # Extract room bookings JSON
    json_pattern = r'```json\s*(\[[\s\S]*?\])\s*```'
    json_matches = re.findall(json_pattern, response)

    if json_matches:
        try:
            parsed_data['room_bookings'] = json.loads(json_matches[0])
        except:
            pass

    # Extract social gathering
    social_pattern = r'Social Gathering Suggestion:[\s\S]*?-\s+Date:\s+(.+?)\n\s+-\s+Venue:\s+(.+?)\n\s+-\s+Purpose:\s+(.+?)(?:\n\n|$)'
    social_match = re.search(social_pattern, response)

    if social_match:
        parsed_data['social_gathering'] = {
            'date': social_match.group(1).strip(),
            'venue': social_match.group(2).strip(),
            'purpose': social_match.group(3).strip()
        }

    return parsed_data


@app.route('/')
def index():
    """Serve the main UI page"""
    # Feature flag: dashboard version selection
    if ENABLE_V3_DASHBOARD_BETA:
        template = 'index_v3_beta.html'
    elif ENABLE_V2_DASHBOARD:
        template = 'index.html'  # v2 is the current default
    elif ENABLE_V1_DASHBOARD:
        # DEAD CODE: v1 dashboard template was deleted but flag check remains
        template = 'index_v1.html'
    else:
        template = 'index.html'

    # Build template context with feature flags
    context = {
        'dark_mode_enabled': ENABLE_DARK_MODE,
        'analytics_enabled': ENABLE_ANALYTICS_DASHBOARD,
        'export_pdf_enabled': ENABLE_EXPORT_TO_PDF,
        'collaboration_enabled': ENABLE_REAL_TIME_COLLABORATION,
        'file_sharing_enabled': ENABLE_FILE_SHARING,
        'video_conferencing_enabled': ENABLE_VIDEO_CONFERENCING,
        'peer_review_enabled': ENABLE_PEER_REVIEW_SYSTEM,
        'streak_tracking_enabled': ENABLE_STUDY_STREAK_TRACKING,
        'multi_language_enabled': ENABLE_MULTI_LANGUAGE_SUPPORT,
        'accessibility_enabled': ENABLE_ACCESSIBILITY_MODE,
        'ab_new_booking_ui': AB_NEW_BOOKING_UI,
        'push_notifications_enabled': ENABLE_PUSH_NOTIFICATIONS,
    }

    try:
        return render_template(template, **context)
    except Exception:
        # Fallback to default template if feature-flagged template doesn't exist
        return render_template('index.html', **context)


@app.route('/api/status')
def get_status():
    """Get current status of all processes"""
    status = dict(process_outputs)

    # Feature flag: include feature flag status in API response
    status['feature_flags'] = {
        'dark_mode': ENABLE_DARK_MODE,
        'analytics': ENABLE_ANALYTICS_DASHBOARD,
        'ai_recommendations': ENABLE_AI_STUDY_RECOMMENDATIONS,
        'canvas_integration': ENABLE_CANVAS_LMS_INTEGRATION,
        'legacy_webscraper': USE_LEGACY_WEBSCRAPER,
        'new_scheduling': USE_NEW_SCHEDULING_ALGORITHM,
        'slack_notifications': ENABLE_SLACK_NOTIFICATIONS,
        'email_notifications': ENABLE_EMAIL_NOTIFICATIONS,
        'export_pdf': ENABLE_EXPORT_TO_PDF,
        'mobile_api': ENABLE_MOBILE_API,
        'graphql_api': ENABLE_GRAPHQL_API,
        'bulk_booking': ENABLE_BULK_ROOM_BOOKING,
        'recurring_bookings': ENABLE_RECURRING_BOOKINGS,
        'real_time_collaboration': ENABLE_REAL_TIME_COLLABORATION,
        'study_streaks': ENABLE_STUDY_STREAK_TRACKING,
        'peer_review': ENABLE_PEER_REVIEW_SYSTEM,
        'video_conferencing': ENABLE_VIDEO_CONFERENCING,
        'file_sharing': ENABLE_FILE_SHARING,
        'multi_language': ENABLE_MULTI_LANGUAGE_SUPPORT,
        'accessibility': ENABLE_ACCESSIBILITY_MODE,
        # Auth flags
        'legacy_auth': ENABLE_LEGACY_AUTH,
        'saml_sso': USE_SAML_SSO,
        'google_auth': ENABLE_GOOGLE_AUTH,
        'api_key_auth': ENABLE_API_KEY_AUTH,
        'jwt_tokens': USE_JWT_TOKENS,
        'mfa_totp': ENABLE_MFA_TOTP,
        # Legacy flags (should be cleaned up)
        'legacy_cookie_format': LEGACY_COOKIE_FORMAT,
        'v1_session_management': V1_SESSION_MANAGEMENT,
        'soap_api': USE_SOAP_API,
        'legacy_room_api': USE_LEGACY_ROOM_API,
        'soap_calendar': ENABLE_SOAP_CALENDAR_SYNC,
        'deprecated_notifications': ENABLE_DEPRECATED_NOTIFICATIONS,
        'legacy_member_sync': LEGACY_MEMBER_SYNC,
        'old_report_format': ENABLE_OLD_REPORT_FORMAT,
    }

    return jsonify(status)


@app.route('/api/run-assignments', methods=['POST'])
def run_assignments():
    """Execute run.py to extract assignments and study groups"""
    if process_outputs['assignments']['running']:
        return jsonify({'error': 'Assignment extraction is already running'}), 400

    # Feature flag: ENABLE_CANVAS_LMS_INTEGRATION - use Canvas API instead of scraping
    if ENABLE_CANVAS_LMS_INTEGRATION and not USE_LEGACY_WEBSCRAPER:
        return _run_canvas_api_extraction()

    def run_script():
        process_outputs['assignments']['running'] = True

        if USE_LEGACY_WEBSCRAPER:
            process_outputs['assignments']['output'] = 'Starting assignment extraction (legacy web scraper)...\n'
        else:
            process_outputs['assignments']['output'] = 'Starting assignment extraction...\n'

        process_outputs['assignments']['last_run'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        try:
            # Set environment to force UTF-8 encoding
            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'

            # Run the script
            process = subprocess.Popen(
                ['python', 'run.py'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace',  # Replace invalid characters instead of crashing
                bufsize=1,
                env=env
            )

            # Stream output
            for line in iter(process.stdout.readline, ''):
                if line:
                    process_outputs['assignments']['output'] += line

            process.wait()

            if process.returncode == 0:
                process_outputs['assignments']['output'] += '\n✓ Assignment extraction completed successfully!\n'
            else:
                process_outputs['assignments']['output'] += f'\n✗ Process exited with code {process.returncode}\n'

        except Exception as e:
            process_outputs['assignments']['output'] += f'\n✗ Error: {str(e)}\n'
        finally:
            process_outputs['assignments']['running'] = False

    # Run in background thread
    thread = threading.Thread(target=run_script)
    thread.daemon = True
    thread.start()

    return jsonify({'message': 'Assignment extraction started'}), 202


def _run_canvas_api_extraction():
    """
    Extract assignments via Canvas LMS API instead of web scraping.
    Used when ENABLE_CANVAS_LMS_INTEGRATION is True and USE_LEGACY_WEBSCRAPER is False.
    """
    def run_api_extraction():
        process_outputs['assignments']['running'] = True
        process_outputs['assignments']['output'] = 'Starting Canvas API assignment extraction...\n'
        process_outputs['assignments']['last_run'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        try:
            from services.canvas_integration import CanvasAPIClient
            client = CanvasAPIClient()

            process_outputs['assignments']['output'] += 'Fetching courses from Canvas API...\n'
            courses = client.get_courses()
            process_outputs['assignments']['output'] += f'Found {len(courses)} courses\n'

            process_outputs['assignments']['output'] += 'Fetching upcoming assignments...\n'
            assignments = client.get_upcoming_assignments()
            process_outputs['assignments']['output'] += f'Found {len(assignments)} upcoming assignments\n'

            # Feature flag: ENABLE_ASSIGNMENT_PRIORITY_SCORING
            if ENABLE_ASSIGNMENT_PRIORITY_SCORING:
                process_outputs['assignments']['output'] += 'Scoring assignment priorities (AI-powered)...\n'
                try:
                    from services.ai_service import AssignmentPriorityScorer
                    scorer = AssignmentPriorityScorer()
                    scored = scorer.score_assignments(assignments, [])
                    process_outputs['assignments']['output'] += f'Priority scores calculated for {len(scored)} assignments\n'
                except Exception as e:
                    process_outputs['assignments']['output'] += f'Priority scoring failed: {e}\n'

            process_outputs['assignments']['output'] += '\n\u2713 Canvas API extraction completed!\n'

        except Exception as e:
            process_outputs['assignments']['output'] += f'\n\u2717 Error: {str(e)}\n'
        finally:
            process_outputs['assignments']['running'] = False

    thread = threading.Thread(target=run_api_extraction)
    thread.daemon = True
    thread.start()

    return jsonify({'message': 'Canvas API extraction started'}), 202


@app.route('/api/book-room', methods=['POST'])
def book_room():
    """Execute book_room.py to book a study room"""
    if process_outputs['booking']['running']:
        return jsonify({'error': 'Room booking is already running'}), 400

    # Feature flag: ENABLE_BULK_ROOM_BOOKING
    if ENABLE_BULK_ROOM_BOOKING and request.json and request.json.get('bulk'):
        return _handle_bulk_booking(request.json.get('bookings', []))

    # Feature flag: ENABLE_RECURRING_BOOKINGS
    if ENABLE_RECURRING_BOOKINGS and request.json and request.json.get('recurring'):
        return _handle_recurring_booking(request.json)

    # Feature flag: USE_NEW_SCHEDULING_ALGORITHM
    if USE_NEW_SCHEDULING_ALGORITHM and request.json and request.json.get('auto_schedule'):
        return _handle_auto_schedule(request.json)

    # Get optional config updates from request
    config_updates = request.json if request.json else {}

    # Update config file if changes provided
    if config_updates:
        try:
            with open('room_booking_config.json', 'r') as f:
                config = json.load(f)

            config.update(config_updates)

            with open('room_booking_config.json', 'w') as f:
                json.dump(config, f, indent=2)

            process_outputs['booking']['output'] = f'Updated configuration: {config_updates}\n'
        except Exception as e:
            return jsonify({'error': f'Failed to update config: {str(e)}'}), 400

    def run_script():
        process_outputs['booking']['running'] = True
        if not config_updates:
            process_outputs['booking']['output'] = 'Starting room booking...\n'
        process_outputs['booking']['last_run'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        try:
            # Set environment to force UTF-8 encoding
            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'

            # Run the script
            process = subprocess.Popen(
                ['python', 'book_room.py'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace',  # Replace invalid characters instead of crashing
                bufsize=1,
                env=env
            )

            # Stream output
            for line in iter(process.stdout.readline, ''):
                if line:
                    process_outputs['booking']['output'] += line

            process.wait()

            if process.returncode == 0:
                process_outputs['booking']['output'] += '\n✓ Room booking process completed!\n'
            else:
                process_outputs['booking']['output'] += f'\n✗ Process exited with code {process.returncode}\n'

        except Exception as e:
            process_outputs['booking']['output'] += f'\n✗ Error: {str(e)}\n'
        finally:
            process_outputs['booking']['running'] = False

    # Run in background thread
    thread = threading.Thread(target=run_script)
    thread.daemon = True
    thread.start()

    return jsonify({'message': 'Room booking started'}), 202


def _handle_bulk_booking(bookings):
    """Handle bulk room booking. Gated behind ENABLE_BULK_ROOM_BOOKING."""
    if not ENABLE_BULK_ROOM_BOOKING:
        return jsonify({'error': 'Bulk booking not enabled'}), 403

    try:
        from services.scheduling_service import BulkRoomBooker
        booker = BulkRoomBooker()
        results = booker.book_multiple(bookings)
        return jsonify({'results': results}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def _handle_recurring_booking(config):
    """Handle recurring booking. Gated behind ENABLE_RECURRING_BOOKINGS."""
    if not ENABLE_RECURRING_BOOKINGS:
        return jsonify({'error': 'Recurring bookings not enabled'}), 403

    try:
        from services.scheduling_service import RecurringBookingManager
        manager = RecurringBookingManager()
        recurring = manager.create_recurring(config.get('template', {}), config.get('recurrence', {}))
        instances = manager.generate_instances(recurring)
        return jsonify({'recurring_booking': recurring, 'instances': instances}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def _handle_auto_schedule(config):
    """Handle auto-scheduling. Gated behind USE_NEW_SCHEDULING_ALGORITHM."""
    if not USE_NEW_SCHEDULING_ALGORITHM:
        return jsonify({'error': 'New scheduling algorithm not enabled'}), 403

    try:
        from services.scheduling_service import get_scheduler
        scheduler = get_scheduler()
        sessions = scheduler.schedule_study_sessions(
            config.get('assignments', []),
            config.get('members', []),
            config.get('constraints', [])
        )
        return jsonify({'scheduled_sessions': sessions}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/plan-week', methods=['POST'])
def plan_week():
    """Use AI to plan the upcoming week and suggest room booking"""
    if process_outputs['llm']['running']:
        return jsonify({'error': 'AI query is already running'}), 400

    if not ai_client:
        return jsonify({'error': 'AI API not configured. Please create AI_API_KEYS.json'}), 400

    def run_query():
        process_outputs['llm']['running'] = True
        process_outputs['llm']['output'] = '🤖 Planning your week with AI...\n\n'
        process_outputs['llm']['last_run'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        try:
            # Read study group report
            if not os.path.exists('study_group_report.md'):
                process_outputs['llm']['output'] += '⚠ study_group_report.md not found!\n'
                process_outputs['llm']['output'] += 'Please run assignment extraction first.\n'
                return

            with open('study_group_report.md', 'r') as f:
                report_content = f.read()

            process_outputs['llm']['output'] += '✓ Loaded study group report\n\n'

            # Read current room booking config if exists
            booking_config = {}
            if os.path.exists('room_booking_config.json'):
                with open('room_booking_config.json', 'r') as f:
                    booking_config = json.load(f)
                process_outputs['llm']['output'] += f'✓ Current booking config: {json.dumps(booking_config, indent=2)}\n\n'

            process_outputs['llm']['output'] += '📡 Querying AI...\n\n'

            # Prepare system message
            system_message = {
                "role": "system",
                "content": "You are an AI Study group administrator designed to help study groups reach maximum cohesion by reducing the overhead of logistics and dispute management. Note that all members are busy people so try to be very concise and deliver only the important information.\n\n"
                           "You can familiarize yourself with the team members and their diverse backgrounds using a file called study_group_report.md, containing the members' names, pre-mba education and experience and country of origin.\n"
                           "Under the same file you'll find the team's upcoming schedule (classes, general announcement) and tasks for submission.\n"
                           "Moreover, the team had signed a team agreement of how they expect to manage their joint responsibilities which you can find under finalized_team_agreement_2025.docx which provides guidelines on how the team's expectations of the group dynamics should look like.\n"
                           "To help with room booking admin, you're provided with a json file named room_booking_config that specifies the structure required for the school's room booking system. NEVER TRY TO BOOK A ROOM FOR OVER 3 HOURS."
            }

            # Rough token estimation (1 token ≈ 4 characters)
            def estimate_tokens(text):
                return len(text) // 4

            # Check if we need to chunk the report
            max_tokens = 1200  # Increased limit after report minification
            system_tokens = estimate_tokens(system_message['content'])
            base_prompt = """What is my work allocation for the upcoming week?

Please provide:
- A structured weekly plan with assignment allocations (leader + mentee pairs)
- Task priorities based on professional backgrounds
- Recommended study session times for each duo
- Room booking - for each group member duo, while taking into account the lecture schedule provided (and avoid schedule conflicts), output a json file under the same structure given under the config file. building name under "building" can ONLY be either "Sussex Place". assume a lecture is 3 hours long so if a lecture starts at a certain hour the members are unavailable for 3 hours.
- A social gathering suggestion for the team
"""
            base_tokens = estimate_tokens(base_prompt)
            report_tokens = estimate_tokens(report_content)
            total_tokens = system_tokens + base_tokens + report_tokens

            process_outputs['llm']['output'] += f'📊 Estimated tokens: {total_tokens:,}\n'

            if total_tokens > max_tokens:
                # Need to chunk the report
                # Use a reasonable buffer (10% of max_tokens, capped at 500)
                buffer = min(int(max_tokens * 0.1), 500)
                chunk_size = max_tokens - system_tokens - base_tokens - buffer

                # Safety check: ensure chunk_size is positive and reasonable
                if chunk_size <= 0 or chunk_size < 100:
                    process_outputs['llm']['output'] += f'\n⚠️ Warning: Report is too large to chunk safely (chunk_size would be {chunk_size} tokens)\n'
                    process_outputs['llm']['output'] += f'Please reduce the report size or increase max_tokens limit.\n'
                    process_outputs['llm']['output'] += f'System tokens: {system_tokens}, Base tokens: {base_tokens}, Report tokens: {report_tokens}\n'
                    return

                chunks = []
                current_pos = 0
                max_iterations = 1000  # Safety limit to prevent infinite loops
                iteration = 0

                while current_pos < len(report_content) and iteration < max_iterations:
                    iteration += 1

                    # Find a good breaking point (end of line)
                    end_pos = min(current_pos + chunk_size * 4, len(report_content))  # *4 because chars to tokens

                    # Safety check: ensure we make progress
                    if end_pos <= current_pos:
                        process_outputs['llm']['output'] += f'\n⚠️ Error: Chunking failed - no progress at position {current_pos}\n'
                        break

                    if end_pos < len(report_content):
                        # Try to break at newline
                        newline_pos = report_content.rfind('\n', current_pos, end_pos)
                        if newline_pos > current_pos:
                            end_pos = newline_pos
                        # If no newline found, use end_pos as is (don't get stuck)

                    chunk_content = report_content[current_pos:end_pos]

                    # Safety check: ensure chunk is not empty
                    if not chunk_content or len(chunk_content) == 0:
                        process_outputs['llm']['output'] += f'\n⚠️ Error: Empty chunk generated at position {current_pos}\n'
                        break

                    chunks.append(chunk_content)
                    current_pos = end_pos

                # Check if we hit the iteration limit
                if iteration >= max_iterations:
                    process_outputs['llm']['output'] += f'\n⚠️ Error: Maximum iterations ({max_iterations}) reached during chunking\n'
                    process_outputs['llm']['output'] += f'This is a safety check to prevent infinite loops. Please contact support.\n'
                    return

                num_chunks = len(chunks)

                # Safety check: ensure we have chunks
                if num_chunks == 0:
                    process_outputs['llm']['output'] += f'\n⚠️ Error: No chunks were created\n'
                    return

                process_outputs['llm']['output'] += f'⚠️ Report too large! Splitting into {num_chunks} chunks...\n\n'

                # Send chunks
                conversation_history = [system_message]

                for i, chunk in enumerate(chunks):
                    chunk_num = i + 1
                    process_outputs['llm']['output'] += f'📤 Sending chunk {chunk_num}/{num_chunks}...\n'

                    if chunk_num == 1:
                        chunk_message = f"""I will send you the study group report in {num_chunks} parts due to its size. Please wait for all parts before responding.

PART {chunk_num}/{num_chunks}:

{chunk}

[Continued in next message...]"""
                    elif chunk_num < num_chunks:
                        chunk_message = f"""PART {chunk_num}/{num_chunks} (continued):

{chunk}

[Continued in next message...]"""
                    else:
                        chunk_message = f"""PART {chunk_num}/{num_chunks} (final):

{chunk}

---

Now that you have received all {num_chunks} parts of the study group report, please provide:
- A structured weekly plan with assignment allocations (leader + mentee pairs)
- Task priorities based on professional backgrounds
- Recommended study session times for each duo
- Room booking - for each group member duo, while taking into account the lecture schedule provided (and avoid schedule conflicts), output a json file under the same structure given under the config file. building name under "building" can ONLY be either "Sussex Place". assume a lecture is 3 hours long so if a lecture starts at a certain hour the members are unavailable for 3 hours.
- A social gathering suggestion for the team"""

                    conversation_history.append({"role": "user", "content": chunk_message})

                    # Get acknowledgment from AI (except for last chunk)
                    if chunk_num < num_chunks:
                        ack_response = query_ai(conversation_history)
                        conversation_history.append({"role": "assistant", "content": ack_response})
                        process_outputs['llm']['output'] += f'✓ Chunk {chunk_num} acknowledged\n'

                # Get final response
                process_outputs['llm']['output'] += f'\n⏳ Generating final response...\n\n'
                response = query_ai(conversation_history)

            else:
                # Send as single message
                messages = [
                    system_message,
                    {
                        "role": "user",
                        "content": f"""What is my work allocation for the upcoming week?

Here's the study group report:
{report_content}

Please provide:
- A structured weekly plan with assignment allocations (leader + mentee pairs)
- Task priorities based on professional backgrounds
- Recommended study session times for each duo
- Room booking - for each group member duo, while taking into account the lecture schedule provided (and avoid schedule conflicts), output a json file under the same structure given under the config file. building name under "building" can ONLY be either "Sussex Place". assume a lecture is 3 hours long so if a lecture starts at a certain hour the members are unavailable for 3 hours.
- A social gathering suggestion for the team
"""
                    }
                ]

                # Query AI
                response = query_ai(messages)

            process_outputs['llm']['output'] += '=' * 80 + '\n'
            process_outputs['llm']['output'] += 'AI WEEKLY PLAN\n'
            process_outputs['llm']['output'] += '=' * 80 + '\n\n'
            process_outputs['llm']['output'] += response + '\n\n'

            # Parse the weekly plan into structured data
            try:
                global weekly_plan_data
                weekly_plan_data = parse_weekly_plan(response)
                process_outputs['llm']['output'] += f'\n✓ Parsed weekly plan: {len(weekly_plan_data["assignments"])} assignments, {len(weekly_plan_data["study_sessions"])} sessions, {len(weekly_plan_data["room_bookings"])} room bookings\n'
            except Exception as e:
                process_outputs['llm']['output'] += f'\n⚠ Could not parse weekly plan structure: {str(e)}\n'

            # Try to extract JSON config from response
            try:
                import re
                # Look for JSON objects in the response
                json_pattern = r'\{[^{}]*"booking_date"[^{}]*\}'
                json_matches = re.findall(json_pattern, response, re.DOTALL)

                if json_matches:
                    # Try to parse the first match as JSON
                    config_json = json.loads(json_matches[0])
                    # Save to room_booking_config.json
                    with open('room_booking_config.json', 'w') as f:
                        json.dump(config_json, f, indent=2)
                    process_outputs['llm']['output'] += '\n✓ Extracted and saved room booking configuration to room_booking_config.json\n'
                    process_outputs['llm']['output'] += f'Config: {json.dumps(config_json, indent=2)}\n'
            except Exception as e:
                process_outputs['llm']['output'] += f'\n⚠ Could not extract booking config from AI response: {str(e)}\n'

            process_outputs['llm']['output'] += '\n' + '=' * 80 + '\n'
            process_outputs['llm']['output'] += '✓ Planning completed!\n'

        except Exception as e:
            process_outputs['llm']['output'] += f'\n✗ Error: {str(e)}\n'
            import traceback
            process_outputs['llm']['output'] += f'\nStack trace:\n{traceback.format_exc()}\n'
        finally:
            process_outputs['llm']['running'] = False

    # Run in background thread
    thread = threading.Thread(target=run_query)
    thread.daemon = True
    thread.start()

    return jsonify({'message': 'AI planning started'}), 202


@app.route('/api/query-llm', methods=['POST'])
def query_llm():
    """Query LBS AI LLM platform with free text"""
    if process_outputs['llm']['running']:
        return jsonify({'error': 'AI query is already running'}), 400

    if not ai_client:
        return jsonify({'error': 'AI API not configured. Please create AI_API_KEYS.json'}), 400

    query = request.json.get('query', '') if request.json else ''

    if not query:
        return jsonify({'error': 'No query provided'}), 400

    def run_query():
        process_outputs['llm']['running'] = True
        process_outputs['llm']['output'] = f'🤖 Processing query: {query}\n\n'
        process_outputs['llm']['last_run'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        try:
            # Read study group report if it exists
            context = ""
            if os.path.exists('study_group_report.md'):
                with open('study_group_report.md', 'r') as f:
                    report_content = f.read()
                context += f"\n\nSTUDY GROUP REPORT:\n{report_content}\n"
                process_outputs['llm']['output'] += '✓ Loaded study group report as context\n'

            # Read room booking config if it exists
            if os.path.exists('room_booking_config.json'):
                with open('room_booking_config.json', 'r') as f:
                    booking_config = json.load(f)
                context += f"\n\nCURRENT ROOM BOOKING CONFIG:\n{json.dumps(booking_config, indent=2)}\n"
                process_outputs['llm']['output'] += '✓ Loaded room booking config as context\n'

            process_outputs['llm']['output'] += '\n📡 Querying AI...\n\n'

            # Prepare messages for AI
            messages = [
                {
                    "role": "system",
                    "content": "You are an AI assistant helping LBS students with their studies. "
                               "You have access to their assignment data and room booking information."
                },
                {
                    "role": "user",
                    "content": f"{query}{context}"
                }
            ]

            # Query AI
            response = query_ai(messages)

            process_outputs['llm']['output'] += '=' * 80 + '\n'
            process_outputs['llm']['output'] += 'AI RESPONSE\n'
            process_outputs['llm']['output'] += '=' * 80 + '\n\n'
            process_outputs['llm']['output'] += response + '\n\n'
            process_outputs['llm']['output'] += '=' * 80 + '\n'
            process_outputs['llm']['output'] += '✓ Query completed!\n'

        except Exception as e:
            process_outputs['llm']['output'] += f'\n✗ Error: {str(e)}\n'
        finally:
            process_outputs['llm']['running'] = False

    # Run in background thread
    thread = threading.Thread(target=run_query)
    thread.daemon = True
    thread.start()

    return jsonify({'message': 'AI query started'}), 202


@app.route('/api/output/<process_type>')
def get_output(process_type):
    """Get current output for a specific process"""
    if process_type not in process_outputs:
        return jsonify({'error': 'Invalid process type'}), 400

    return jsonify(process_outputs[process_type])


@app.route('/api/clear/<process_type>', methods=['POST'])
def clear_output(process_type):
    """Clear output for a specific process"""
    if process_type not in process_outputs:
        return jsonify({'error': 'Invalid process type'}), 400

    if not process_outputs[process_type]['running']:
        process_outputs[process_type]['output'] = ''
        return jsonify({'message': 'Output cleared'})
    else:
        return jsonify({'error': 'Cannot clear output while process is running'}), 400


@app.route('/weekly-plan')
def weekly_plan():
    """Serve the weekly plan visualization page"""
    return render_template('weekly_plan.html')


@app.route('/api/weekly-plan-data')
def get_weekly_plan_data():
    """Get parsed weekly plan data"""
    return jsonify(weekly_plan_data)


if __name__ == '__main__':
    print("=" * 80)
    print("LBS STUDY GROUP MANAGER - WEB UI")
    print("=" * 80)

    # Print active feature flags
    print("\n--- Active Feature Flags ---")
    flag_manager = get_flag_manager()
    active_flags = flag_manager.get_all_flags()
    enabled_count = sum(1 for f in active_flags.values() if f.get('enabled', False))
    print(f"Total flags: {len(active_flags)}, Enabled: {enabled_count}")

    # Load AI configuration
    print("\nLoading AI configuration...")
    load_ai_config()

    # Feature flag: Setup middleware
    if ENABLE_RATE_LIMITING or ENABLE_REQUEST_LOGGING or ENABLE_PROMETHEUS_METRICS or ENABLE_SENTRY_INTEGRATION:
        print("\nSetting up middleware...")
        try:
            from middleware.request_middleware import setup_middleware
            middleware = setup_middleware(app)
            print("✓ Middleware configured")
        except Exception as e:
            print(f"⚠ Middleware setup failed: {e}")

    # Feature flag: Register mobile API
    if ENABLE_MOBILE_API:
        print("\nRegistering Mobile API endpoints...")
        try:
            from api.mobile_api import register_mobile_api
            register_mobile_api(app)
            print("✓ Mobile API registered at /api/v2/")
        except Exception as e:
            print(f"⚠ Mobile API registration failed: {e}")

    # Feature flag: Register GraphQL API
    if ENABLE_GRAPHQL_API:
        print("\nRegistering GraphQL API endpoint...")
        try:
            from api.mobile_api import register_graphql_api
            register_graphql_api(app)
            print("✓ GraphQL API registered at /graphql")
        except Exception as e:
            print(f"⚠ GraphQL API registration failed: {e}")

    print("\nStarting Flask server...")
    print("Open your browser and navigate to: http://localhost:5000")
    print("\nPress Ctrl+C to stop the server")
    print("=" * 80)

    app.run(debug=True, host='0.0.0.0', port=5000, threaded=True)
