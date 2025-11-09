#!/usr/bin/env python3
"""
Dashboard Analyzer
Extracts assignments and calendar events from the LBS learning dashboard.
"""

from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import json
import re


def parse_dashboard(html_file):
    """Parse the dashboard HTML file and extract assignments/events"""

    with open(html_file, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')

    # Find all planner items
    planner_items = soup.find_all('div', {'data-testid': 'planner-item-raw'})

    print(f"Found {len(planner_items)} planner items")

    assignments = []

    for item in planner_items:
        assignment = {}

        # Extract course and type from the type span
        type_span = item.find('span', class_=lambda x: x and 'css-65c5ma-text' in x)
        if type_span:
            full_type = type_span.get_text(strip=True)
            # Example: "C111   AUT25 Finance I Calendar event" or "C112   AUT25 Strategy Quiz"
            parts = full_type.rsplit(' ', 1)
            if len(parts) == 2:
                assignment['course'] = parts[0]
                assignment['type'] = parts[1]
            else:
                assignment['course'] = full_type
                assignment['type'] = 'Unknown'

        # Extract title from the link or button
        title_elem = item.find('a', class_=lambda x: x and 'css-3c4agm-view-link' in x)
        if not title_elem:
            title_elem = item.find('button', class_=lambda x: x and 'css-3c4agm-view-link' in x)

        if title_elem:
            # Get the aria-hidden span which contains the actual title
            title_span = title_elem.find('span', {'aria-hidden': 'true'})
            if title_span:
                assignment['title'] = title_span.get_text(strip=True)

            # Get the screen reader content which has more details including due date
            sr_span = title_elem.find('span', class_='css-r9cwls-screenReaderContent')
            if sr_span:
                sr_text = sr_span.get_text(strip=True)
                assignment['screen_reader_text'] = sr_text

                # Try to extract due date from screen reader text
                # Example: "Quiz Session 8 - Preparation Quiz, due Tuesday, 11 November 2025 16:00."
                # Example: "Calendar event Session 8, at Monday, 10 November 2025 16:00 until 18:45"

                if 'due' in sr_text.lower():
                    # Assignment with due date
                    match = re.search(r'due\s+(\w+),\s+(\d+\s+\w+\s+\d{4})\s+(\d{2}:\d{2})', sr_text, re.IGNORECASE)
                    if match:
                        day_name, date_str, time_str = match.groups()
                        assignment['due_date'] = f"{date_str} {time_str}"
                        assignment['due_day_name'] = day_name
                elif 'at' in sr_text.lower():
                    # Calendar event with time
                    match = re.search(r'at\s+(\w+),\s+(\d+\s+\w+\s+\d{4})\s+(\d{2}:\d{2})', sr_text, re.IGNORECASE)
                    if match:
                        day_name, date_str, time_str = match.groups()
                        assignment['event_date'] = f"{date_str} {time_str}"
                        assignment['event_day_name'] = day_name

        # Extract time/due information from the metrics section
        metrics_div = item.find('div', class_='PlannerItem-styles__metrics')
        if metrics_div:
            time_span = metrics_div.find('span', {'aria-hidden': 'true'})
            if time_span:
                time_text = time_span.get_text(strip=True)
                assignment['time_display'] = time_text

        # Extract location if present (for calendar events)
        location_div = item.find('div', class_='PlannerItem-styles__location')
        if location_div:
            location_span = location_div.find('span')
            if location_span:
                assignment['location'] = location_span.get_text(strip=True)

        # Extract URL if it's a link
        link_elem = item.find('a', href=True)
        if link_elem:
            assignment['url'] = link_elem['href']

        assignments.append(assignment)

    return assignments


def filter_assignments_next_week(assignments):
    """Filter assignments due in the next 7 days"""

    today = datetime.now()
    next_week = today + timedelta(days=7)

    upcoming = []

    for assignment in assignments:
        due_date_str = assignment.get('due_date') or assignment.get('event_date')

        if due_date_str:
            try:
                # Parse date like "11 November 2025 16:00"
                due_date = datetime.strptime(due_date_str, "%d %B %Y %H:%M")

                if today <= due_date <= next_week:
                    upcoming.append(assignment)
            except ValueError:
                # If parsing fails, include it anyway
                upcoming.append(assignment)

    return upcoming


def print_assignments(assignments):
    """Print assignments in a readable format"""

    print("\n" + "="*80)
    print("ASSIGNMENTS & EVENTS")
    print("="*80)

    for i, assignment in enumerate(assignments, 1):
        print(f"\n[{i}] {assignment.get('title', 'No Title')}")
        print(f"    Course: {assignment.get('course', 'Unknown')}")
        print(f"    Type: {assignment.get('type', 'Unknown')}")

        if 'due_date' in assignment:
            print(f"    Due: {assignment.get('due_day_name', '')} {assignment['due_date']}")
        elif 'event_date' in assignment:
            print(f"    Event: {assignment.get('event_day_name', '')} {assignment['event_date']}")

        if 'time_display' in assignment:
            print(f"    Time: {assignment['time_display']}")

        if 'location' in assignment:
            print(f"    Location: {assignment['location']}")

        if 'url' in assignment:
            print(f"    URL: {assignment['url']}")


def main():
    print("="*80)
    print("LBS Dashboard Analyzer")
    print("="*80)

    # Parse dashboard
    print("\nParsing Dashboard.html...")
    all_assignments = parse_dashboard('Dashboard.html')

    print(f"\nTotal items found: {len(all_assignments)}")

    # Get assignments due in next week
    print("\nFiltering assignments due in the next 7 days...")
    upcoming = filter_assignments_next_week(all_assignments)

    print(f"Found {len(upcoming)} upcoming assignments/events")

    # Print upcoming assignments
    print_assignments(upcoming)

    # Save to JSON for further processing
    print("\n" + "="*80)
    print("Saving data to files...")

    with open('all_assignments.json', 'w', encoding='utf-8') as f:
        json.dump(all_assignments, f, indent=2, ensure_ascii=False)
    print("✓ Saved all assignments to all_assignments.json")

    with open('upcoming_assignments.json', 'w', encoding='utf-8') as f:
        json.dump(upcoming, f, indent=2, ensure_ascii=False)
    print("✓ Saved upcoming assignments to upcoming_assignments.json")

    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Total assignments/events: {len(all_assignments)}")
    print(f"Due in next 7 days: {len(upcoming)}")

    # Count by type
    types = {}
    for a in all_assignments:
        t = a.get('type', 'Unknown')
        types[t] = types.get(t, 0) + 1

    print("\nBy type:")
    for type_name, count in sorted(types.items()):
        print(f"  {type_name}: {count}")

    # Count by course
    courses = {}
    for a in upcoming:
        c = a.get('course', 'Unknown')
        courses[c] = courses.get(c, 0) + 1

    print("\nUpcoming by course:")
    for course_name, count in sorted(courses.items()):
        print(f"  {course_name}: {count}")


if __name__ == '__main__':
    main()
