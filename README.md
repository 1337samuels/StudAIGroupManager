# LBS StudAI Group Manager

Automation tools for managing London Business School (LBS) learning portal tasks.

## Overview

This project provides Python scripts to automate interactions with the LBS learning portal at https://learning.london.edu. It handles Microsoft Azure AD authentication with MFA and extracts useful information about assignments, calendar events, and study groups.

## Features

### 1. Automated Login (`login.py`)
- Opens Chrome browser with Selenium
- Navigates to https://learning.london.edu
- Waits for manual Microsoft login + MFA completion
- Detects successful authentication automatically
- Saves session cookies for potential reuse

### 2. Dashboard Analysis (`analyze_dashboard.py`)
- Parses the LBS dashboard HTML
- Extracts all assignments and calendar events
- Identifies items due in the next 7 days
- Outputs detailed information including:
  - Assignment/event titles
  - Course names
  - Due dates and times
  - Event locations
  - URLs

### 3. Groups Information (`get_groups.py`)
- Navigates to Groups page
- Extracts all group memberships
- Identifies Study Groups
- Retrieves member information
- Saves HTML pages for further analysis

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Ensure Chrome browser is installed
# ChromeDriver will be managed automatically by Selenium
```

## Usage

### Quick Start

```bash
# 1. Login and save session
python login.py
```

Follow the browser prompts:
1. Enter your Microsoft credentials
2. Complete MFA on your phone
3. Wait for the script to detect successful login

### Analyze Dashboard

```bash
# After logging in, get Dashboard.html from the browser
# Then run:
python analyze_dashboard.py
```

**Output:**
- `all_assignments.json` - All assignments/events found
- `upcoming_assignments.json` - Items due in next 7 days
- Console output with detailed information

### Get Study Group Members

```bash
python get_groups.py
```

**Output:**
- `groups_info.json` - All groups you're a member of
- `study_groups.json` - Study groups with member lists
- `groups_page.html` - Groups page for manual analysis
- `group_*_page.html` - Individual group pages

## Current Findings

### Dashboard Analysis Results

**Total Items:** 15 assignments/events tracked

**Upcoming (Next 7 Days):** 7 items

#### By Type:
- Assignments: 4
- Quizzes: 2
- Calendar Events: 9

#### Courses with Upcoming Items:
- **C101 AUT25 Accounting**
  - Session 8 (Calendar Event) - Wed, 12 Nov 2025 12:45-15:30 @ SOC LT15
  - MA Session 8 In-Class Workshop (Assignment) - Wed, 12 Nov 2025 16:00

- **C111 AUT25 Finance I**
  - Session 8 (Calendar Event) - Mon, 10 Nov 2025 16:00-18:45 @ SOC LT16
  - Trade Idea (Assignment) - Mon, 10 Nov 2025 16:00

- **C112 AUT25 Strategy**
  - Session 8 - Preparation Quiz (Quiz) - Tue, 11 Nov 2025 16:00
  - Session 8 (Calendar Event) - Wed, 12 Nov 2025 08:15-11:00 @ SOC LT16

- **C172 AUT25 Macroeconomics for Managers**
  - Session 3 (Calendar Event) - Thu, 13 Nov 2025 16:00-18:45 @ SOC LT16

## Project Structure

```
StudAIGroupManager/
├── login.py                    # Selenium-based login automation
├── analyze_dashboard.py        # Dashboard HTML parser
├── get_groups.py              # Groups information extractor
├── requirements.txt           # Python dependencies
├── .gitignore                # Ignore sensitive files
├── README.md                 # This file
│
├── session.json              # Saved browser cookies (gitignored)
├── Dashboard.html            # Dashboard page HTML (gitignored)
│
├── all_assignments.json      # All assignments (gitignored)
├── upcoming_assignments.json # Next week's items (gitignored)
├── groups_info.json          # Groups info (gitignored)
└── study_groups.json         # Study groups (gitignored)
```

## How It Works

### Login Process
1. Script opens Chrome with Selenium
2. Navigates to https://learning.london.edu
3. User manually enters credentials in browser
4. User completes MFA on phone
5. Script detects when URL changes to learning.london.edu without auth keywords
6. Session cookies are extracted and saved
7. Browser stays open for further operations

### Dashboard Parsing
1. Reads Dashboard.html file
2. Uses BeautifulSoup to find all `data-testid="planner-item-raw"` elements
3. Extracts:
   - Course name and type from `.css-65c5ma-text` spans
   - Title from aria-hidden spans
   - Due dates from screen reader text
   - Times and locations from metrics divs
4. Filters by date to find items due in next 7 days
5. Outputs results to JSON and console

### Groups Extraction
1. Uses Selenium to navigate to /groups
2. Finds group cards/links
3. For each Study Group:
   - Navigates to group page
   - Clicks on People/Members tab
   - Extracts member names
4. Saves HTML pages for manual analysis

## Technical Details

### Dashboard HTML Structure

The LBS dashboard uses Canvas LMS. Key elements:

**Planner Items:**
```html
<div data-testid="planner-item-raw" class="PlannerItem-styles__root">
  <div class="PlannerItem-styles__type">
    <span class="css-65c5ma-text">C111 AUT25 Finance I Quiz</span>
  </div>
  <a href="..." class="css-3c4agm-view-link">
    <span class="css-r9cwls-screenReaderContent">
      Quiz Session 8, due Tuesday, 11 November 2025 16:00.
    </span>
    <span aria-hidden="true">Session 8</span>
  </a>
  <div class="PlannerItem-styles__metrics">
    <span aria-hidden="true">Due: 16:00</span>
  </div>
</div>
```

**Date Grouping:**
```html
<div data-testid="day" class="Day-styles__root">
  <h2>
    <div data-testid="not-today">Wednesday, 12 November</div>
  </h2>
  <!-- planner items for this day -->
</div>
```

## Future Enhancements

Potential improvements:
- [ ] Automatic calendar sync (export to .ics)
- [ ] Email notifications for upcoming deadlines
- [ ] Study group scheduling assistant
- [ ] Assignment submission tracking
- [ ] Grade monitoring
- [ ] Automated assignment downloads

## Security Notes

- **Credentials:** Script uses manual browser login - no credentials stored
- **Session:** session.json contains authentication cookies - keep secure
- **Privacy:** All data stays local - not sent to external services
- **.gitignore:** Configured to prevent committing sensitive files

## Troubleshooting

**Chrome not found:**
- Install Chrome browser from https://www.google.com/chrome/

**ChromeDriver issues:**
- Update Selenium: `pip install --upgrade selenium`
- Selenium 4+ manages ChromeDriver automatically

**Login timeout:**
- Default timeout is 300 seconds (5 minutes)
- Modify `wait_for_manual_login(timeout=300)` in login.py

**Dashboard analysis fails:**
- Ensure Dashboard.html is recent
- Check HTML structure hasn't changed
- Look at all_assignments.json to debug parsing

## License

Educational use only. Respect LBS terms of service and privacy policies.
