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

app = Flask(__name__)

# Global error handlers to ensure JSON responses
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': f'Internal server error: {str(error)}'}), 500

@app.errorhandler(Exception)
def handle_exception(error):
    # Log the error for debugging
    print(f"Unhandled exception: {error}")
    import traceback
    traceback.print_exc()
    return jsonify({'error': f'Server error: {str(error)}'}), 500

# AI API Configuration
ai_config = None
ai_client = None

def load_ai_config():
    """Load AI API configuration from AI_API_KEYS.json"""
    global ai_config, ai_client
    try:
        with open('AI_API_KEYS.json', 'r') as f:
            ai_config = json.load(f)

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
        return False
    except Exception as e:
        print(f"⚠ Failed to load AI configuration: {e}")
        return False

def query_ai(messages, stream=False):
    """Query Azure OpenAI with messages"""
    if not ai_client or not ai_config:
        raise Exception("AI API not configured. Please create AI_API_KEYS.json")

    response = ai_client.chat.completions.create(
        model=ai_config['deployment_name'],
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


@app.route('/')
def index():
    """Serve the main UI page"""
    return render_template('index.html')


@app.route('/api/status')
def get_status():
    """Get current status of all processes"""
    return jsonify(process_outputs)


@app.route('/api/run-assignments', methods=['POST'])
def run_assignments():
    """Execute run.py to extract assignments and study groups"""
    if process_outputs['assignments']['running']:
        return jsonify({'error': 'Assignment extraction is already running'}), 400

    def run_script():
        process_outputs['assignments']['running'] = True
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


@app.route('/api/book-room', methods=['POST'])
def book_room():
    """Execute book_room.py to book a study room"""
    if process_outputs['booking']['running']:
        return jsonify({'error': 'Room booking is already running'}), 400

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

            # Prepare messages for AI
            messages = [
                {
                    "role": "system",
                    "content": "You are an AI assistant helping LBS students plan their study schedule. "
                               "Analyze their upcoming assignments and study group information to create an optimal weekly plan."
                },
                {
                    "role": "user",
                    "content": f"""Based on the following study group report, please:

1. Analyze the upcoming assignments and their due dates
2. Create a weekly study plan prioritizing tasks
3. Suggest optimal times for group study sessions
4. Recommend a room booking configuration for the most critical study session

Here's the study group report:

{report_content}

Please provide:
- A structured weekly plan
- Task priorities
- Recommended study session times
- A room booking suggestion in JSON format with: booking_date (YYYY-MM-DD), start_time (HH:MM), duration_hours, attendees, study_group_name, project_name, building (Sussex Place)
"""
                }
            ]

            # Query AI
            response = query_ai(messages)

            process_outputs['llm']['output'] += '=' * 80 + '\n'
            process_outputs['llm']['output'] += 'AI WEEKLY PLAN\n'
            process_outputs['llm']['output'] += '=' * 80 + '\n\n'
            process_outputs['llm']['output'] += response + '\n\n'

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


if __name__ == '__main__':
    print("=" * 80)
    print("LBS STUDY GROUP MANAGER - WEB UI")
    print("=" * 80)

    # Load AI configuration
    print("\nLoading AI configuration...")
    load_ai_config()

    print("\nStarting Flask server...")
    print("Open your browser and navigate to: http://localhost:5000")
    print("\nPress Ctrl+C to stop the server")
    print("=" * 80)

    app.run(debug=True, host='0.0.0.0', port=5000, threaded=True)
