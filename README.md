# LBS StudAI Group Manager

Comprehensive automation suite for LBS students - assignment extraction, room booking, and AI assistance.

## What It Does

This tool provides a **web UI dashboard** with three main features:

### 📚 Assignment Extraction
Automatically:
1. ✅ Logs into learning.london.edu (restores saved session if available)
2. ✅ Extracts your upcoming assignments (next 7 days)
3. ✅ Finds your Study Group members
4. ✅ Extracts member backgrounds from Class List
5. ✅ Generates a markdown report optimized for LLM analysis

**Output:** A markdown file you can upload to ChatGPT/Claude to get AI-powered recommendations for:
- Task allocation based on each member's strengths
- Workload distribution
- Collaboration strategies
- Timeline planning

### 🏢 Room Booking
Automatically:
1. ✅ Logs into lbsmobile.london.edu with Microsoft MFA
2. ✅ Navigates to room booking system
3. ✅ Fills in booking details from configuration file
4. ✅ Selects first available room matching criteria
5. ✅ Completes the booking process

**Configuration:** JSON file with date, time, duration, attendees, and building preference

### 🤖 LBS AI Assistant
Query LBS's AI platform for analysis (API integration coming soon)

## Quick Start

### Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Ensure Chrome is installed (ChromeDriver auto-managed)
```

### Option 1: Web UI (Recommended)

**Launch the web interface for easy access to all features:**

```bash
python app.py
```

Then open your browser to: **http://localhost:5000**

The web UI provides:
- 📚 **Assignment Extraction** - One-click extraction from learning.london.edu
- 🏢 **Room Booking** - Automated room booking on lbsmobile.london.edu
- 🤖 **LBS AI Assistant** - Query LBS's AI platform (coming soon)

### Option 2: Command Line

**Run individual scripts directly:**

```bash
# Extract assignments and study group info
python run.py

# Book a study room (configure room_booking_config.json first)
python book_room.py
```

The scripts will:
1. Open Chrome browser
2. Ask you to login manually (or restore your previous session)
3. Extract/process data automatically
4. Generate output files
5. Tell you when they're done!

### Upload to LLM

Take the generated `study_group_report.md` file and upload it to:
- ChatGPT (Claude Sonnet 3.5 or GPT-4)
- Claude AI
- Any other LLM

The LLM will analyze your assignments and team members, then suggest who should do what based on everyone's backgrounds!

## Features

### 🌐 Web UI Dashboard
- Clean, modern interface accessible via browser
- Real-time output streaming from all scripts
- Three main functions accessible with one click
- Runs on localhost:5000 for easy access

### 🔐 Smart Login
- Tries to restore your previous session from cookies
- Only asks for manual login if session expired
- Saves session for next time

### 📚 Assignment Extraction
- Finds all assignments/events due in next 7 days
- Extracts: title, course, due date, location, URL
- Sorts by chronological order

### 👥 Study Group Analysis
- Automatically finds your study group
- Extracts all member names
- Gets member backgrounds from Class List (when available)

### 🏢 Automated Room Booking
- Books study rooms on lbsmobile.london.edu
- Configurable via JSON file (date, time, duration, attendees, building)
- Automatically selects first available room
- Handles Microsoft MFA login flow
- See [ROOM_BOOKING_README.md](ROOM_BOOKING_README.md) for details

### 🤖 LLM-Optimized Output
The markdown report includes:
- Formatted assignment list grouped by date
- Member profiles with backgrounds
- Specific prompt asking LLM to suggest task allocation

### ⚡ Smart Retry Logic
- Tries fast first, retries with longer waits if needed
- Handles slow/unstable connections gracefully

## Project Structure

```
StudAIGroupManager/
├── app.py                     # 🌐 Web UI server (Flask)
├── run.py                     # 📚 Assignment extraction script
├── book_room.py               # 🏢 Room booking automation script
├── room_booking_config.json   # ⚙️  Room booking configuration
├── requirements.txt           # Python dependencies
├── README.md                  # This file
├── ROOM_BOOKING_README.md     # Room booking documentation
├── .gitignore                 # Git ignore rules
│
├── templates/                 # Web UI templates
│   └── index.html             # Main UI page
│
├── static/                    # Web UI static files
│   └── style.css              # UI styling
│
├── resources/                 # HTML files for testing (gitignored)
│   └── README.md              # Info about resource files
│
└── Generated files (gitignored):
    ├── session.json           # Your saved session (auto-generated)
    └── study_group_report.md  # Generated markdown report
```

## Example Output

```markdown
# Study Group Planning Report

## 📚 Upcoming Assignments (Next 7 Days)

### Monday, 10 November 2025
**C111 AUT25 Finance I**
- Type: Assignment
- Title: Trade Idea
- Due: 16:00
- URL: https://learning.london.edu/...

### Tuesday, 11 November 2025
**C112 AUT25 Strategy**
- Type: Quiz
- Title: Session 8 - Preparation Quiz
- Due: 16:00

[...]

## 👥 Study Group Members

1. **Raquel Garcia Meneses**
   - Origin: [extracted from Class List]
   - Education: [extracted from Class List]
   - Previous Occupation: [extracted from Class List]

2. **Aashna Kumar**
   [...]

## 🤖 Analysis Request for LLM

[Detailed prompt asking LLM to suggest task allocation...]
```

## Current Study Group

Based on latest extraction:
- Raquel Garcia Meneses
- Aashna Kumar
- Jonathan Reiter
- Marcos Saldarriaga
- Gilad Samuels
- Shruthi Swaminathan

## Troubleshooting

**"Chrome not found"**
- Install Chrome: https://www.google.com/chrome/

**"Session expired"**
- Normal! Just login manually when prompted
- Session will be saved for next time

**"Can't find Study Group"**
- Check that you're actually in a study group
- Try again with longer wait times (slow connection)

**"Class List not loading"**
- Normal if the iframe takes time to load
- Script will use placeholder data and continue
- You can still get the report without Class List details

## Technical Details

- **Language:** Python 3.7+
- **Browser:** Chrome (Selenium WebDriver)
- **Parsing:** BeautifulSoup4
- **Platform:** Cross-platform (Windows, Mac, Linux)

## License

Educational use only. Respect LBS terms of service.
