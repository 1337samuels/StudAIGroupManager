#!/usr/bin/env python3
"""
Study Group Manager - Complete Workflow
Orchestrates the complete flow:
1. Login (with cookie restoration)
2. Extract upcoming assignments from Dashboard
3. Find Study Group members
4. Extract member details from Class List (placeholder)
5. Generate markdown report for LLM analysis
"""

from login import AzureADLogin
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import time
import json
import re


class StudyGroupManager:
    def __init__(self):
        self.login_helper = None
        self.driver = None
        self.assignments = []
        self.study_group_members = []
        self.member_details = {}

    def smart_wait_and_retry(self, action_func, max_retries=3, initial_wait=0.5, retry_wait=5):
        """
        Try action fast first, then retry with longer waits if it fails

        Args:
            action_func: Function to execute
            max_retries: Maximum number of retries
            initial_wait: Initial wait time before first try
            retry_wait: Wait time before retries
        """
        for attempt in range(max_retries):
            try:
                if attempt == 0:
                    # First try - fast
                    if initial_wait > 0:
                        time.sleep(initial_wait)
                else:
                    # Retries - wait longer
                    print(f"  Retry {attempt}/{max_retries-1} after {retry_wait}s wait...")
                    time.sleep(retry_wait)

                return action_func()

            except Exception as e:
                if attempt == max_retries - 1:
                    # Last attempt failed
                    raise
                print(f"  Attempt {attempt+1} failed: {e}")

        return None

    def login_with_cookies(self):
        """Login using existing cookies or manual login"""
        print("="*80)
        print("STEP 1: LOGIN")
        print("="*80)

        self.login_helper = AzureADLogin()

        # Setup browser first
        if not self.login_helper.setup_driver():
            return False

        self.driver = self.login_helper.driver

        # Try to restore cookies
        print("\nAttempting to restore session from cookies...")
        if self.login_helper.load_and_restore_cookies():
            # Cookies loaded, try to navigate to dashboard
            print("Testing if session is still valid...")
            self.driver.get("https://learning.london.edu")
            time.sleep(3)

            # Check if we're logged in
            current_url = self.driver.current_url.lower()
            if 'learning.london.edu' in current_url and not any(word in current_url for word in ['login', 'auth', 'microsoft', 'saml']):
                print("✓ Session restored successfully! Already logged in.")
                return True
            else:
                print("  Session expired or invalid. Need to login manually.")

        # Manual login needed
        print("\nProceeding with manual login...")
        if not self.login_helper.wait_for_manual_login("https://learning.london.edu"):
            return False

        # Save new session
        self.login_helper.extract_cookies()
        self.login_helper.save_session()

        return True

    def extract_assignments_from_dashboard(self):
        """Navigate to dashboard and extract upcoming assignments"""
        print("\n" + "="*80)
        print("STEP 2: EXTRACT UPCOMING ASSIGNMENTS")
        print("="*80)

        def navigate_to_dashboard():
            print("\nNavigating to dashboard...")
            self.driver.get("https://learning.london.edu")
            time.sleep(2)
            return True

        self.smart_wait_and_retry(navigate_to_dashboard)

        # Wait for planner items to load
        print("Waiting for dashboard content to load...")
        time.sleep(5)  # Give it time to load

        # Get page source and parse
        html = self.driver.page_source
        soup = BeautifulSoup(html, 'html.parser')

        # Find all planner items
        planner_items = soup.find_all('div', {'data-testid': 'planner-item-raw'})
        print(f"Found {len(planner_items)} planner items")

        # Parse assignments
        today = datetime.now()
        next_week = today + timedelta(days=7)

        for item in planner_items:
            assignment = {}

            # Extract course and type
            type_span = item.find('span', class_=lambda x: x and 'css-65c5ma-text' in x)
            if type_span:
                full_type = type_span.get_text(strip=True)
                parts = full_type.rsplit(' ', 1)
                if len(parts) == 2:
                    assignment['course'] = parts[0]
                    assignment['type'] = parts[1]

            # Extract title and due date
            sr_span = item.find('span', class_='css-r9cwls-screenReaderContent')
            if sr_span:
                sr_text = sr_span.get_text(strip=True)

                # Extract title (first part before comma)
                title_match = re.match(r'^(.*?),', sr_text)
                if title_match:
                    assignment['title'] = title_match.group(1).replace('Quiz ', '').replace('Assignment ', '').replace('Calendar event ', '')

                # Extract due date
                if 'due' in sr_text.lower():
                    match = re.search(r'due\s+(\w+),\s+(\d+\s+\w+\s+\d{4})\s+(\d{2}:\d{2})', sr_text, re.IGNORECASE)
                    if match:
                        day_name, date_str, time_str = match.groups()
                        assignment['due_date'] = f"{date_str} {time_str}"
                        assignment['due_day'] = day_name

                        # Parse to filter by date
                        try:
                            due_datetime = datetime.strptime(assignment['due_date'], "%d %B %Y %H:%M")
                            assignment['due_datetime'] = due_datetime
                        except:
                            pass
                elif 'at' in sr_text.lower():
                    match = re.search(r'at\s+(\w+),\s+(\d+\s+\w+\s+\d{4})\s+(\d{2}:\d{2})', sr_text, re.IGNORECASE)
                    if match:
                        day_name, date_str, time_str = match.groups()
                        assignment['event_date'] = f"{date_str} {time_str}"
                        assignment['event_day'] = day_name

                        try:
                            event_datetime = datetime.strptime(assignment['event_date'], "%d %B %Y %H:%M")
                            assignment['due_datetime'] = event_datetime
                        except:
                            pass

            # Extract location
            location_div = item.find('div', class_='PlannerItem-styles__location')
            if location_div:
                location_span = location_div.find('span')
                if location_span:
                    assignment['location'] = location_span.get_text(strip=True)

            # Extract URL
            link = item.find('a', href=True)
            if link:
                assignment['url'] = link['href']

            # Filter - only upcoming items
            if 'due_datetime' in assignment:
                if today <= assignment['due_datetime'] <= next_week:
                    self.assignments.append(assignment)

        print(f"✓ Found {len(self.assignments)} upcoming assignments/events")

        # Sort by due date
        self.assignments.sort(key=lambda x: x.get('due_datetime', datetime.max))

        return True

    def find_study_group_members(self):
        """Navigate to a study group and extract member names"""
        print("\n" + "="*80)
        print("STEP 3: EXTRACT STUDY GROUP MEMBERS")
        print("="*80)

        def navigate_to_groups():
            print("\nNavigating to Groups page...")
            self.driver.get("https://learning.london.edu/groups")
            time.sleep(3)
            return True

        self.smart_wait_and_retry(navigate_to_groups)

        # Find a study group link
        print("Looking for Study Group...")

        def find_study_group():
            # Look for links containing "Study Group"
            study_group_links = self.driver.find_elements(By.PARTIAL_LINK_TEXT, 'Study Group')

            if study_group_links:
                # Click the first study group
                study_group_name = study_group_links[0].text
                print(f"  Found: {study_group_name}")
                study_group_links[0].click()
                time.sleep(3)
                return True
            return False

        if not self.smart_wait_and_retry(find_study_group, retry_wait=5):
            print("✗ Could not find Study Group")
            return False

        # Click on People tab
        def click_people_tab():
            print("Navigating to People tab...")
            try:
                people_link = self.driver.find_element(By.PARTIAL_LINK_TEXT, 'People')
                people_link.click()
                time.sleep(3)
                return True
            except:
                # Try alternate names
                try:
                    people_link = self.driver.find_element(By.PARTIAL_LINK_TEXT, 'Members')
                    people_link.click()
                    time.sleep(3)
                    return True
                except:
                    return False

        self.smart_wait_and_retry(click_people_tab, retry_wait=5)

        # Extract member names from page
        print("Extracting member names...")
        html = self.driver.page_source
        soup = BeautifulSoup(html, 'html.parser')

        # Find the student roster section
        roster_div = soup.find('div', class_='student_roster')
        if roster_div:
            # Find all user names
            user_links = roster_div.find_all('a', class_='user_name')
            for link in user_links:
                name = link.get_text(strip=True)
                if name:
                    self.study_group_members.append(name)

            print(f"✓ Found {len(self.study_group_members)} study group members:")
            for i, member in enumerate(self.study_group_members, 1):
                print(f"  {i}. {member}")
        else:
            print("  Warning: Could not find roster section")

        return True

    def extract_member_details_from_class_list(self):
        """
        Extract member details from Class List
        TODO: This is a placeholder - needs Class List HTML to implement
        """
        print("\n" + "="*80)
        print("STEP 4: EXTRACT MEMBER DETAILS FROM CLASS LIST")
        print("="*80)

        print("\n⚠ This feature requires Class List HTML structure")
        print("  Placeholder implementation - will be completed once Class List HTML is available")

        # For now, create placeholder data
        for member in self.study_group_members:
            self.member_details[member] = {
                'origin': 'TBD - needs Class List data',
                'education': 'TBD - needs Class List data',
                'previous_occupation': 'TBD - needs Class List data'
            }

        print("✓ Placeholder data created for all members")

        return True

    def generate_markdown_report(self, output_file='study_group_report.md'):
        """Generate markdown report for LLM analysis"""
        print("\n" + "="*80)
        print("STEP 5: GENERATE MARKDOWN REPORT")
        print("="*80)

        report = []
        report.append("# Study Group Planning Report")
        report.append(f"\n*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n")
        report.append("---\n")

        # Section 1: Upcoming Assignments
        report.append("## 📚 Upcoming Assignments (Next 7 Days)\n")

        if not self.assignments:
            report.append("*No assignments found in the next 7 days.*\n")
        else:
            # Group by date
            by_date = {}
            for assignment in self.assignments:
                if 'due_datetime' in assignment:
                    date_key = assignment['due_datetime'].strftime('%Y-%m-%d')
                    day_name = assignment.get('due_day') or assignment.get('event_day', '')

                    if date_key not in by_date:
                        by_date[date_key] = {
                            'date': assignment['due_datetime'].strftime('%A, %d %B %Y'),
                            'items': []
                        }
                    by_date[date_key]['items'].append(assignment)

            # Output by date
            for date_key in sorted(by_date.keys()):
                date_info = by_date[date_key]
                report.append(f"### {date_info['date']}\n")

                for item in date_info['items']:
                    course = item.get('course', 'Unknown Course')
                    title = item.get('title', 'Untitled')
                    item_type = item.get('type', 'Unknown')

                    report.append(f"**{course}**")
                    report.append(f"- **Type:** {item_type}")
                    report.append(f"- **Title:** {title}")

                    if 'due_date' in item:
                        time = item['due_date'].split()[-1]
                        report.append(f"- **Due:** {time}")
                    elif 'event_date' in item:
                        time = item['event_date'].split()[-1]
                        report.append(f"- **Time:** {time}")

                    if 'location' in item:
                        report.append(f"- **Location:** {item['location']}")

                    if 'url' in item:
                        report.append(f"- **URL:** {item['url']}")

                    report.append("")

        # Section 2: Study Group Members
        report.append("\n---\n")
        report.append("## 👥 Study Group Members\n")

        if not self.study_group_members:
            report.append("*No study group members found.*\n")
        else:
            report.append(f"**Total Members:** {len(self.study_group_members)}\n")
            for i, member in enumerate(self.study_group_members, 1):
                report.append(f"{i}. **{member}**")

                if member in self.member_details:
                    details = self.member_details[member]
                    report.append(f"   - Origin: {details.get('origin', 'N/A')}")
                    report.append(f"   - Education: {details.get('education', 'N/A')}")
                    report.append(f"   - Previous Occupation: {details.get('previous_occupation', 'N/A')}")

                report.append("")

        # Section 3: LLM Prompt
        report.append("\n---\n")
        report.append("## 🤖 Analysis Request for LLM\n")
        report.append("""
Please analyze the upcoming assignments and study group member profiles above, and provide:

1. **Task Allocation Strategy**: Based on each member's background (education, origin, previous occupation),
   suggest which members would be best suited for each assignment. Consider:
   - Technical vs. analytical vs. creative tasks
   - Subject matter expertise from previous roles
   - Educational background relevance
   - Complementary skill combinations

2. **Workload Distribution**: Ensure fair distribution of work across all members

3. **Collaboration Recommendations**: Suggest which assignments benefit from paired/group work vs. individual work

4. **Timeline Planning**: Identify potential scheduling conflicts and recommend prioritization

5. **Strengths Mapping**: Create a quick reference showing each member's key strengths relevant to these assignments

Please provide actionable recommendations that the study group can implement immediately.
""")

        # Write to file
        report_text = '\n'.join(report)

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report_text)

        print(f"✓ Report generated: {output_file}")
        print(f"  Total lines: {len(report)}")

        return report_text

    def run(self):
        """Execute the complete workflow"""
        try:
            # Step 1: Login
            if not self.login_with_cookies():
                print("\n✗ Login failed")
                return False

            # Step 2: Extract assignments
            if not self.extract_assignments_from_dashboard():
                print("\n✗ Failed to extract assignments")
                return False

            # Step 3: Find study group members
            if not self.find_study_group_members():
                print("\n✗ Failed to extract study group members")
                return False

            # Step 4: Extract member details (placeholder)
            self.extract_member_details_from_class_list()

            # Step 5: Generate report
            self.generate_markdown_report()

            print("\n" + "="*80)
            print("✓ COMPLETE!")
            print("="*80)
            print("\nReport saved to: study_group_report.md")
            print("You can now upload this file to an LLM for analysis and recommendations.")

            # Keep browser open for inspection
            input("\n\nPress Enter to close browser and exit...")

            return True

        except Exception as e:
            print(f"\n✗ Error during execution: {e}")
            import traceback
            traceback.print_exc()
            return False

        finally:
            # Cleanup
            if self.login_helper:
                self.login_helper.close()


def main():
    print("="*80)
    print("LBS STUDY GROUP MANAGER")
    print("="*80)
    print("\nThis script will:")
    print("  1. Login to learning.london.edu (using saved session if available)")
    print("  2. Extract upcoming assignments from Dashboard")
    print("  3. Find your Study Group members")
    print("  4. Extract member details from Class List (placeholder)")
    print("  5. Generate markdown report for LLM analysis")
    print("\n" + "="*80 + "\n")

    manager = StudyGroupManager()
    manager.run()


if __name__ == '__main__':
    main()
