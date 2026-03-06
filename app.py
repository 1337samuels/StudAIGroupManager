#!/usr/bin/env python3
"""LBS Study Group Manager - Web UI (Flask server)"""

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
    ENABLE_LEGACY_AUTH, USE_SAML_SSO, ENABLE_GOOGLE_AUTH,
    ENABLE_API_KEY_AUTH, USE_JWT_TOKENS, LEGACY_COOKIE_FORMAT,
    V1_SESSION_MANAGEMENT, ENABLE_V1_DASHBOARD, ENABLE_V2_DASHBOARD,
    ENABLE_V3_DASHBOARD_BETA, ENABLE_DARK_MODE, AB_NEW_BOOKING_UI,
    AB_AI_MODEL_GPT4, AB_WEEKLY_DIGEST_EMAIL, USE_OPENAI_DIRECT,
    ENABLE_LOCAL_LLM_FALLBACK, ENABLE_AI_STUDY_RECOMMENDATIONS,
    ENABLE_AI_CONFLICT_RESOLUTION, ENABLE_ASSIGNMENT_PRIORITY_SCORING,
    ENABLE_SLACK_NOTIFICATIONS, ENABLE_EMAIL_NOTIFICATIONS,
    ENABLE_PUSH_NOTIFICATIONS, ENABLE_DEPRECATED_NOTIFICATIONS,
    ENABLE_REAL_TIME_COLLABORATION, USE_NEW_SCHEDULING_ALGORITHM,
    ENABLE_MOBILE_API, ENABLE_GRAPHQL_API, ENABLE_ANALYTICS_DASHBOARD,
    ENABLE_EXPORT_TO_PDF, ENABLE_BULK_ROOM_BOOKING,
    ENABLE_RECURRING_BOOKINGS, USE_REDIS_CACHE,
    ENABLE_RATE_LIMITING, ENABLE_REQUEST_LOGGING,
    ENABLE_PROMETHEUS_METRICS, ENABLE_SENTRY_INTEGRATION,
    ENABLE_CANVAS_LMS_INTEGRATION, USE_LEGACY_WEBSCRAPER,
    ENABLE_GRAPH_CALENDAR_SYNC, ENABLE_GOOGLE_CALENDAR_SYNC,
    ENABLE_SOAP_CALENDAR_SYNC, USE_SOAP_API, USE_LEGACY_ROOM_API,
    LEGACY_MEMBER_SYNC, ENABLE_OLD_REPORT_FORMAT,
    ENABLE_STUDY_STREAK_TRACKING, ENABLE_PEER_REVIEW_SYSTEM,
    ENABLE_MULTI_LANGUAGE_SUPPORT, ENABLE_ACCESSIBILITY_MODE,
    ENABLE_FILE_SHARING, ENABLE_VIDEO_CONFERENCING,
    ENABLE_MFA_TOTP, USE_HEADLESS_BROWSER, USE_OAUTH2_PKCE,
    USE_REDIS_SESSIONS, DEBUG_SQL_QUERIES,
    is_flag_enabled, get_flag_manager,
)

app = Flask(__name__)


@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    if ENABLE_SENTRY_INTEGRATION:
        try:
            from middleware.request_middleware import SentryIntegration
            SentryIntegration().capture_exception(error)
        except Exception:
            pass
    return jsonify({'error': f'Internal server error: {str(error)}'}), 500


@app.errorhandler(Exception)
def handle_exception(error):
    if ENABLE_SENTRY_INTEGRATION:
        try:
            from middleware.request_middleware import SentryIntegration
            SentryIntegration().capture_exception(error)
        except Exception:
            pass
    return jsonify({'error': f'Server error: {str(error)}'}), 500


# AI API Configuration
ai_config = None
ai_client = None


def load_ai_config():
    """Load AI API configuration."""
    global ai_config, ai_client

    # Feature flag: USE_OPENAI_DIRECT
    if USE_OPENAI_DIRECT:
        try:
            from openai import OpenAI
            api_key = os.environ.get('OPENAI_API_KEY', '')
            if api_key:
                ai_client = OpenAI(api_key=api_key)
                ai_config = {'deployment_name': 'gpt-4o' if AB_AI_MODEL_GPT4 else 'gpt-3.5-turbo'}
                return True
        except Exception:
            pass
        # Feature flag: ENABLE_LOCAL_LLM_FALLBACK
        if ENABLE_LOCAL_LLM_FALLBACK:
            ai_config = {'deployment_name': 'ollama/llama3.2', 'local': True}
            return True
        return False

    # Default: Azure OpenAI
    try:
        with open('AI_API_KEYS.json', 'r') as f:
            ai_config = json.load(f)
        # Feature flag: AB_AI_MODEL_GPT4
        if AB_AI_MODEL_GPT4:
            ai_config['deployment_name'] = ai_config.get('deployment_name', '') + '-gpt4o'
        ai_client = AzureOpenAI(
            api_key=ai_config['api_key'],
            api_version=ai_config['api_version'],
            azure_endpoint=ai_config['endpoint'])
        return True
    except FileNotFoundError:
        if ENABLE_LOCAL_LLM_FALLBACK:
            ai_config = {'deployment_name': 'ollama/llama3.2', 'local': True}
            return True
        return False
    except Exception:
        return False


def query_ai(messages, stream=False):
    """Query AI with messages."""
    if not ai_client or not ai_config:
        if ENABLE_LOCAL_LLM_FALLBACK:
            return "[Local LLM response - configure AI_API_KEYS.json for full functionality]"
        raise Exception("AI API not configured")

    # Feature flag: USE_OPENAI_DIRECT
    model = ('gpt-4o' if AB_AI_MODEL_GPT4 else 'gpt-3.5-turbo') if USE_OPENAI_DIRECT else ai_config['deployment_name']
    response = ai_client.chat.completions.create(model=model, messages=messages, stream=stream)
    return response if stream else response.choices[0].message.content


# Store process outputs
process_outputs = {
    'assignments': {'running': False, 'output': '', 'last_run': None},
    'booking': {'running': False, 'output': '', 'last_run': None},
    'llm': {'running': False, 'output': '', 'last_run': None}
}

weekly_plan_data = {
    'assignments': [], 'study_sessions': [], 'room_bookings': [],
    'social_gathering': None, 'raw_response': '', 'timestamp': None
}


def parse_weekly_plan(response):
    """Parse AI response to extract structured weekly plan data."""
    import re
    parsed_data = {
        'assignments': [], 'study_sessions': [], 'room_bookings': [],
        'social_gathering': None, 'raw_response': response,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    # Extract room bookings JSON from ```json blocks
    json_pattern = r'```json\s*(\[[\s\S]*?\])\s*```'
    json_matches = re.findall(json_pattern, response)
    if json_matches:
        try:
            parsed_data['room_bookings'] = json.loads(json_matches[0])
        except Exception:
            pass
    return parsed_data


@app.route('/')
def index():
    """Serve the main UI page."""
    # Feature flag: dashboard version selection
    if ENABLE_V3_DASHBOARD_BETA:
        template = 'index_v3_beta.html'
    elif ENABLE_V2_DASHBOARD:
        template = 'index.html'
    elif ENABLE_V1_DASHBOARD:
        # DEAD CODE: v1 dashboard template was deleted but flag check remains
        template = 'index_v1.html'
    else:
        template = 'index.html'

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
        return render_template('index.html', **context)


@app.route('/api/status')
def get_status():
    """Get current status of all processes and feature flags."""
    status = dict(process_outputs)
    status['feature_flags'] = {
        'dark_mode': ENABLE_DARK_MODE, 'analytics': ENABLE_ANALYTICS_DASHBOARD,
        'ai_recommendations': ENABLE_AI_STUDY_RECOMMENDATIONS,
        'canvas_integration': ENABLE_CANVAS_LMS_INTEGRATION,
        'legacy_webscraper': USE_LEGACY_WEBSCRAPER,
        'new_scheduling': USE_NEW_SCHEDULING_ALGORITHM,
        'slack_notifications': ENABLE_SLACK_NOTIFICATIONS,
        'email_notifications': ENABLE_EMAIL_NOTIFICATIONS,
        'export_pdf': ENABLE_EXPORT_TO_PDF,
        'mobile_api': ENABLE_MOBILE_API, 'graphql_api': ENABLE_GRAPHQL_API,
        'bulk_booking': ENABLE_BULK_ROOM_BOOKING,
        'recurring_bookings': ENABLE_RECURRING_BOOKINGS,
        'real_time_collaboration': ENABLE_REAL_TIME_COLLABORATION,
        'study_streaks': ENABLE_STUDY_STREAK_TRACKING,
        'peer_review': ENABLE_PEER_REVIEW_SYSTEM,
        'video_conferencing': ENABLE_VIDEO_CONFERENCING,
        'file_sharing': ENABLE_FILE_SHARING,
        'multi_language': ENABLE_MULTI_LANGUAGE_SUPPORT,
        'accessibility': ENABLE_ACCESSIBILITY_MODE,
        'legacy_auth': ENABLE_LEGACY_AUTH, 'saml_sso': USE_SAML_SSO,
        'google_auth': ENABLE_GOOGLE_AUTH, 'api_key_auth': ENABLE_API_KEY_AUTH,
        'jwt_tokens': USE_JWT_TOKENS, 'mfa_totp': ENABLE_MFA_TOTP,
        'legacy_cookie_format': LEGACY_COOKIE_FORMAT,
        'v1_session_management': V1_SESSION_MANAGEMENT,
        'soap_api': USE_SOAP_API, 'legacy_room_api': USE_LEGACY_ROOM_API,
        'soap_calendar': ENABLE_SOAP_CALENDAR_SYNC,
        'deprecated_notifications': ENABLE_DEPRECATED_NOTIFICATIONS,
        'legacy_member_sync': LEGACY_MEMBER_SYNC,
        'old_report_format': ENABLE_OLD_REPORT_FORMAT,
    }
    return jsonify(status)


@app.route('/api/run-assignments', methods=['POST'])
def run_assignments():
    """Execute run.py to extract assignments."""
    if process_outputs['assignments']['running']:
        return jsonify({'error': 'Already running'}), 400
    # Feature flag: ENABLE_CANVAS_LMS_INTEGRATION
    if ENABLE_CANVAS_LMS_INTEGRATION and not USE_LEGACY_WEBSCRAPER:
        return _run_canvas_api_extraction()

    def run_script():
        process_outputs['assignments']['running'] = True
        process_outputs['assignments']['output'] = 'Starting assignment extraction...\n'
        process_outputs['assignments']['last_run'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        try:
            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'
            process = subprocess.Popen(['python', 'run.py'], stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace', bufsize=1, env=env)
            for line in iter(process.stdout.readline, ''):
                if line:
                    process_outputs['assignments']['output'] += line
            process.wait()
        except Exception as e:
            process_outputs['assignments']['output'] += f'\nError: {str(e)}\n'
        finally:
            process_outputs['assignments']['running'] = False

    thread = threading.Thread(target=run_script, daemon=True)
    thread.start()
    return jsonify({'message': 'Assignment extraction started'}), 202


def _run_canvas_api_extraction():
    """Extract assignments via Canvas LMS API."""
    def run_api_extraction():
        process_outputs['assignments']['running'] = True
        process_outputs['assignments']['output'] = 'Starting Canvas API extraction...\n'
        process_outputs['assignments']['last_run'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        try:
            from services.canvas_integration import CanvasAPIClient
            client = CanvasAPIClient()
            courses = client.get_courses()
            assignments = client.get_upcoming_assignments()
            process_outputs['assignments']['output'] += f'Found {len(assignments)} assignments\n'
            # Feature flag: ENABLE_ASSIGNMENT_PRIORITY_SCORING
            if ENABLE_ASSIGNMENT_PRIORITY_SCORING:
                try:
                    from services.ai_service import AssignmentPriorityScorer
                    AssignmentPriorityScorer().score_assignments(assignments, [])
                except Exception:
                    pass
        except Exception as e:
            process_outputs['assignments']['output'] += f'Error: {str(e)}\n'
        finally:
            process_outputs['assignments']['running'] = False

    thread = threading.Thread(target=run_api_extraction, daemon=True)
    thread.start()
    return jsonify({'message': 'Canvas API extraction started'}), 202


@app.route('/api/book-room', methods=['POST'])
def book_room():
    """Execute book_room.py to book a study room."""
    if process_outputs['booking']['running']:
        return jsonify({'error': 'Already running'}), 400

    # Feature flag: ENABLE_BULK_ROOM_BOOKING
    if ENABLE_BULK_ROOM_BOOKING and request.json and request.json.get('bulk'):
        return _handle_bulk_booking(request.json.get('bookings', []))
    # Feature flag: ENABLE_RECURRING_BOOKINGS
    if ENABLE_RECURRING_BOOKINGS and request.json and request.json.get('recurring'):
        return _handle_recurring_booking(request.json)
    # Feature flag: USE_NEW_SCHEDULING_ALGORITHM
    if USE_NEW_SCHEDULING_ALGORITHM and request.json and request.json.get('auto_schedule'):
        return _handle_auto_schedule(request.json)

    config_updates = request.json if request.json else {}
    if config_updates:
        try:
            with open('room_booking_config.json', 'r') as f:
                config = json.load(f)
            config.update(config_updates)
            with open('room_booking_config.json', 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            return jsonify({'error': str(e)}), 400

    def run_script():
        process_outputs['booking']['running'] = True
        process_outputs['booking']['output'] = 'Starting room booking...\n'
        process_outputs['booking']['last_run'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        try:
            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'
            process = subprocess.Popen(['python', 'book_room.py'], stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace', bufsize=1, env=env)
            for line in iter(process.stdout.readline, ''):
                if line:
                    process_outputs['booking']['output'] += line
            process.wait()
        except Exception as e:
            process_outputs['booking']['output'] += f'\nError: {str(e)}\n'
        finally:
            process_outputs['booking']['running'] = False

    thread = threading.Thread(target=run_script, daemon=True)
    thread.start()
    return jsonify({'message': 'Room booking started'}), 202


def _handle_bulk_booking(bookings):
    """Handle bulk room booking. Gated behind ENABLE_BULK_ROOM_BOOKING."""
    if not ENABLE_BULK_ROOM_BOOKING:
        return jsonify({'error': 'Not enabled'}), 403
    try:
        from services.scheduling_service import BulkRoomBooker
        return jsonify({'results': BulkRoomBooker().book_multiple(bookings)}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def _handle_recurring_booking(config):
    """Handle recurring booking. Gated behind ENABLE_RECURRING_BOOKINGS."""
    if not ENABLE_RECURRING_BOOKINGS:
        return jsonify({'error': 'Not enabled'}), 403
    try:
        from services.scheduling_service import RecurringBookingManager
        manager = RecurringBookingManager()
        recurring = manager.create_recurring(config.get('template', {}), config.get('recurrence', {}))
        return jsonify({'recurring_booking': recurring, 'instances': manager.generate_instances(recurring)}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def _handle_auto_schedule(config):
    """Handle auto-scheduling. Gated behind USE_NEW_SCHEDULING_ALGORITHM."""
    if not USE_NEW_SCHEDULING_ALGORITHM:
        return jsonify({'error': 'Not enabled'}), 403
    try:
        from services.scheduling_service import get_scheduler
        scheduler = get_scheduler()
        sessions = scheduler.schedule_study_sessions(config.get('assignments', []), config.get('members', []), config.get('constraints', []))
        return jsonify({'scheduled_sessions': sessions}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/plan-week', methods=['POST'])
def plan_week():
    """Use AI to plan the upcoming week."""
    if process_outputs['llm']['running']:
        return jsonify({'error': 'Already running'}), 400
    if not ai_client:
        return jsonify({'error': 'AI not configured'}), 400

    def run_query():
        process_outputs['llm']['running'] = True
        process_outputs['llm']['output'] = 'Planning your week with AI...\n'
        process_outputs['llm']['last_run'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        try:
            if not os.path.exists('study_group_report.md'):
                process_outputs['llm']['output'] += 'study_group_report.md not found!\n'
                return
            with open('study_group_report.md', 'r') as f:
                report_content = f.read()

            system_message = {"role": "system", "content": "You are an AI Study group administrator."}
            messages = [system_message, {"role": "user", "content": f"Plan my week:\n{report_content}"}]
            response = query_ai(messages)

            process_outputs['llm']['output'] += response + '\n'

            try:
                global weekly_plan_data
                weekly_plan_data = parse_weekly_plan(response)
            except Exception:
                pass

            # Try to extract booking config from response
            try:
                import re
                json_pattern = r'\{[^{}]*"booking_date"[^{}]*\}'
                json_matches = re.findall(json_pattern, response, re.DOTALL)
                if json_matches:
                    config_json = json.loads(json_matches[0])
                    with open('room_booking_config.json', 'w') as f:
                        json.dump(config_json, f, indent=2)
            except Exception:
                pass

        except Exception as e:
            process_outputs['llm']['output'] += f'Error: {str(e)}\n'
        finally:
            process_outputs['llm']['running'] = False

    thread = threading.Thread(target=run_query, daemon=True)
    thread.start()
    return jsonify({'message': 'AI planning started'}), 202


@app.route('/api/query-llm', methods=['POST'])
def query_llm():
    """Query AI with free text."""
    if process_outputs['llm']['running']:
        return jsonify({'error': 'Already running'}), 400
    if not ai_client:
        return jsonify({'error': 'AI not configured'}), 400
    query = request.json.get('query', '') if request.json else ''
    if not query:
        return jsonify({'error': 'No query provided'}), 400

    def run_query():
        process_outputs['llm']['running'] = True
        process_outputs['llm']['output'] = f'Processing: {query}\n'
        process_outputs['llm']['last_run'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        try:
            context = ''
            if os.path.exists('study_group_report.md'):
                with open('study_group_report.md', 'r') as f:
                    context = f'\nReport:\n{f.read()}'
            messages = [
                {"role": "system", "content": "You are an AI assistant helping LBS students."},
                {"role": "user", "content": f"{query}{context}"}]
            response = query_ai(messages)
            process_outputs['llm']['output'] += response + '\n'
        except Exception as e:
            process_outputs['llm']['output'] += f'Error: {str(e)}\n'
        finally:
            process_outputs['llm']['running'] = False

    thread = threading.Thread(target=run_query, daemon=True)
    thread.start()
    return jsonify({'message': 'AI query started'}), 202


@app.route('/api/output/<process_type>')
def get_output(process_type):
    """Get current output for a specific process."""
    if process_type not in process_outputs:
        return jsonify({'error': 'Invalid process type'}), 400
    return jsonify(process_outputs[process_type])


@app.route('/api/clear/<process_type>', methods=['POST'])
def clear_output(process_type):
    """Clear output for a specific process."""
    if process_type not in process_outputs:
        return jsonify({'error': 'Invalid process type'}), 400
    if not process_outputs[process_type]['running']:
        process_outputs[process_type]['output'] = ''
        return jsonify({'message': 'Output cleared'})
    return jsonify({'error': 'Cannot clear while running'}), 400


@app.route('/weekly-plan')
def weekly_plan():
    return render_template('weekly_plan.html')


@app.route('/api/weekly-plan-data')
def get_weekly_plan_data():
    return jsonify(weekly_plan_data)


if __name__ == '__main__':
    print("LBS STUDY GROUP MANAGER - WEB UI")

    # Print active feature flags
    flag_manager = get_flag_manager()
    active_flags = flag_manager.get_all_flags()
    enabled_count = sum(1 for f in active_flags.values() if f.get('enabled', False))
    print(f"Total flags: {len(active_flags)}, Enabled: {enabled_count}")

    load_ai_config()

    # Feature flag: Setup middleware
    if ENABLE_RATE_LIMITING or ENABLE_REQUEST_LOGGING or ENABLE_PROMETHEUS_METRICS or ENABLE_SENTRY_INTEGRATION:
        try:
            from middleware.request_middleware import setup_middleware
            setup_middleware(app)
        except Exception:
            pass

    # Feature flag: Register mobile API
    if ENABLE_MOBILE_API:
        try:
            from api.mobile_api import register_mobile_api
            register_mobile_api(app)
        except Exception:
            pass

    # Feature flag: Register GraphQL API
    if ENABLE_GRAPHQL_API:
        try:
            from api.mobile_api import register_graphql_api
            register_graphql_api(app)
        except Exception:
            pass

    app.run(debug=True, host='0.0.0.0', port=5000, threaded=True)
