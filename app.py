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

app = Flask(__name__)

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
            # Run the script
            process = subprocess.Popen(
                ['python3', 'run.py'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
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
            # Run the script
            process = subprocess.Popen(
                ['python3', 'book_room.py'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
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


@app.route('/api/query-llm', methods=['POST'])
def query_llm():
    """Query LBS AI LLM platform (placeholder implementation)"""
    if process_outputs['llm']['running']:
        return jsonify({'error': 'LLM query is already running'}), 400

    query = request.json.get('query', '') if request.json else ''

    if not query:
        return jsonify({'error': 'No query provided'}), 400

    def run_query():
        process_outputs['llm']['running'] = True
        process_outputs['llm']['output'] = f'Query: {query}\n\n'
        process_outputs['llm']['last_run'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        try:
            # TODO: Implement LBS AI LLM API integration
            # This is a placeholder implementation
            process_outputs['llm']['output'] += '⚠ LLM integration not yet implemented\n'
            process_outputs['llm']['output'] += 'Waiting for API details...\n'

        except Exception as e:
            process_outputs['llm']['output'] += f'\n✗ Error: {str(e)}\n'
        finally:
            process_outputs['llm']['running'] = False

    # Run in background thread
    thread = threading.Thread(target=run_query)
    thread.daemon = True
    thread.start()

    return jsonify({'message': 'LLM query started'}), 202


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
    print("\nStarting Flask server...")
    print("Open your browser and navigate to: http://localhost:5000")
    print("\nPress Ctrl+C to stop the server")
    print("=" * 80)

    app.run(debug=True, host='0.0.0.0', port=5000, threaded=True)
