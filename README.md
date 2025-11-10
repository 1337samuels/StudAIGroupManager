# LBS StudAI Group Manager

One-click automation to analyze your study group and upcoming assignments.

## What It Does

This tool automatically:
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

## Quick Start

### Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Ensure Chrome is installed (ChromeDriver auto-managed)
```

### Run It

**That's it - just ONE command:**

```bash
python run.py
```

The script will:
1. Open Chrome browser
2. Ask you to login manually (or restore your previous session)
3. Extract all the data automatically
4. Generate `study_group_report.md`
5. Tell you when it's done!

### Upload to LLM

Take the generated `study_group_report.md` file and upload it to:
- ChatGPT (Claude Sonnet 3.5 or GPT-4)
- Claude AI
- Any other LLM

The LLM will analyze your assignments and team members, then suggest who should do what based on everyone's backgrounds!

## Features

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
├── run.py                     # ⭐ THE ONLY SCRIPT - All functionality in one file
├── requirements.txt           # Python dependencies
├── README.md                  # This file
├── .gitignore                 # Git ignore rules
│
├── resources/                 # HTML files for testing (gitignored)
│   └── README.md              # Info about resource files
│
└── Generated files (gitignored):
    ├── session.json           # Your saved session (auto-generated)
    └── study_group_report.md  # Generated markdown report
```

**Clean and simple:** Just one Python file (`run.py`) containing all the logic!

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
