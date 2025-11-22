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

    # Load AI configuration
    print("\nLoading AI configuration...")
    load_ai_config()

    print("\nStarting Flask server...")
    print("Open your browser and navigate to: http://localhost:5000")
    print("\nPress Ctrl+C to stop the server")
    print("=" * 80)

    app.run(debug=True, host='0.0.0.0', port=5000, threaded=True)
