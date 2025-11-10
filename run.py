#!/usr/bin/env python3
"""
LBS Study Group Manager - All-in-One Script
Run this single script to:
1. Login to learning.london.edu (restores cookies if available)
2. Extract upcoming assignments from Dashboard
3. Find Study Group members
4. Extract member background details from Class List
5. Generate markdown report for LLM analysis
"""

from selenium import webdriver
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
        self.driver = None
        self.cookies = {}
        self.assignments = []
        self.study_group_members = []
        self.member_details = {}

    # ==================== SELENIUM SETUP ====================

    def setup_driver(self):
        """Initialize Selenium WebDriver with Chrome"""
        print("Setting up Chrome WebDriver...")

        options = webdriver.ChromeOptions()
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

        try:
            self.driver = webdriver.Chrome(options=options)
            self.driver.maximize_window()
            print("✓ Chrome WebDriver initialized")
            return True
        except Exception as e:
            print(f"✗ Failed to initialize Chrome WebDriver: {e}")
            return False

    # ==================== COOKIE MANAGEMENT ====================

    def load_and_restore_cookies(self, filename='session.json'):
        """Load cookies from file and restore them to the browser"""
        try:
            with open(filename, 'r') as f:
                self.cookies = json.load(f)

            if not self.driver:
                return False

            # Navigate to the domain first (cookies need a domain context)
            self.driver.get("https://learning.london.edu")
            time.sleep(1)

            # Add each cookie to the browser
            for name, cookie_data in self.cookies.items():
                cookie = {
                    'name': name,
                    'value': cookie_data['value'],
                    'domain': cookie_data.get('domain', '.learning.london.edu'),
                    'path': cookie_data.get('path', '/'),
                }
                if 'secure' in cookie_data:
                    cookie['secure'] = cookie_data['secure']

                try:
                    self.driver.add_cookie(cookie)
                except Exception as e:
                    pass  # Some cookies might fail, that's okay

            print(f"✓ Loaded and restored cookies from {filename}")
            return True

        except FileNotFoundError:
            print(f"  No session file found at {filename}")
            return False
        except Exception as e:
            print(f"  Error loading session: {e}")
            return False

    def extract_cookies(self):
        """Extract cookies from the browser session"""
        try:
            print("Extracting session cookies...")
            cookies = self.driver.get_cookies()

            self.cookies = {}
            for cookie in cookies:
                self.cookies[cookie['name']] = {
                    'value': cookie['value'],
                    'domain': cookie.get('domain', ''),
                    'path': cookie.get('path', '/'),
                    'secure': cookie.get('secure', False)
                }

            print(f"✓ Extracted {len(self.cookies)} cookies")
            return self.cookies
        except Exception as e:
            print(f"✗ Error extracting cookies: {e}")
            return {}

    def save_session(self, filename='session.json'):
        """Save session cookies to a file"""
        try:
            with open(filename, 'w') as f:
                json.dump(self.cookies, f, indent=2)
            print(f"✓ Session saved to {filename}")
            return True
        except Exception as e:
            print(f"✗ Error saving session: {e}")
            return False

    # ==================== RETRY LOGIC ====================

    def smart_wait_and_retry(self, action_func, max_retries=3, initial_wait=0.5, retry_wait=5):
        """Try action fast first, then retry with longer waits if it fails"""
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
                    raise
                print(f"  Attempt {attempt+1} failed: {e}")

        return None

    # ==================== LOGIN ====================

    def wait_for_manual_login(self, initial_url, timeout=300):
        """Navigate to URL and wait for user to manually complete login"""
        try:
            print(f"\n{'='*60}")
            print("MANUAL LOGIN REQUIRED")
            print('='*60)
            print(f"\n📱 Opening browser to: {initial_url}")
            print("\nPlease complete the following steps:")
            print("  1. Enter your Microsoft credentials")
            print("  2. Complete MFA (Microsoft Authenticator)")
            print("  3. Wait for the page to fully load after login")
            print(f"\nTimeout: {timeout} seconds")
            print('='*60)

            self.driver.get(initial_url)

            start_time = time.time()
            check_interval = 2

            print("\n⏳ Waiting for you to complete login...")

            while (time.time() - start_time) < timeout:
                try:
                    current_url = self.driver.current_url.lower()

                    if ('learning.london.edu' in current_url or 'london.instructure.com' in current_url):
                        if not any(word in current_url for word in ['login', 'auth', 'microsoft', 'saml']):
                            print("\n✓ Login successful!")
                            print(f"  Current URL: {self.driver.current_url}")
                            return True

                    elapsed = int(time.time() - start_time)
                    if elapsed % 10 == 0 and elapsed > 0:
                        print(f"  Still waiting... ({elapsed}s elapsed)")

                    time.sleep(check_interval)

                except Exception as e:
                    print(f"  Warning during wait: {e}")
                    time.sleep(check_interval)

            print(f"\n⚠ Timeout after {timeout} seconds")

            current_url = self.driver.current_url
            print(f"  Current URL: {current_url}")

            if 'learning.london.edu' in current_url or 'london.instructure.com' in current_url:
                print("\n  You appear to be on the target site. Continuing...")
                return True

            return False

        except Exception as e:
            print(f"\n✗ Error during manual login wait: {e}")
            return False

    def login_with_cookies(self):
        """Login using existing cookies or manual login"""
        print("="*80)
        print("STEP 1: LOGIN")
        print("="*80)

        if not self.setup_driver():
            return False

        # Try to restore cookies
        print("\nAttempting to restore session from cookies...")
        if self.load_and_restore_cookies():
            print("Testing if session is still valid...")
            self.driver.get("https://learning.london.edu")
            time.sleep(3)

            current_url = self.driver.current_url.lower()
            if 'learning.london.edu' in current_url and not any(word in current_url for word in ['login', 'auth', 'microsoft', 'saml']):
                print("✓ Session restored successfully! Already logged in.")
                return True
            else:
                print("  Session expired or invalid. Need to login manually.")

        # Manual login needed
        print("\nProceeding with manual login...")
        if not self.wait_for_manual_login("https://learning.london.edu"):
            return False

        # Save new session
        self.extract_cookies()
        self.save_session()

        return True

    # ==================== ASSIGNMENTS EXTRACTION ====================

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
        time.sleep(5)

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
            # Note: There are multiple screenReader spans - one for checkbox, one for actual data
            # We need the one with date information (contains "due" or "at")
            sr_spans = item.find_all('span', class_='css-r9cwls-screenReaderContent')
            sr_text = None
            for span in sr_spans:
                text = span.get_text(strip=True)
                if 'due' in text.lower() or 'at' in text.lower():
                    sr_text = text
                    break

            if sr_text:
                # Extract title
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

            # Filter - only upcoming Assignment items (exclude calendar events)
            if 'due_datetime' in assignment and 'type' in assignment:
                # Only include Assignment and Quiz types, exclude calendar events
                if assignment['type'] in ['Assignment', 'Quiz']:
                    if today <= assignment['due_datetime'] <= next_week:
                        self.assignments.append(assignment)

        print(f"✓ Found {len(self.assignments)} upcoming assignments")

        # Sort by due date
        self.assignments.sort(key=lambda x: x.get('due_datetime', datetime.max))

        return True

    # ==================== STUDY GROUP MEMBERS ====================

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
            study_group_links = self.driver.find_elements(By.PARTIAL_LINK_TEXT, 'Study Group')

            if study_group_links:
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
                try:
                    people_link = self.driver.find_element(By.PARTIAL_LINK_TEXT, 'Members')
                    people_link.click()
                    time.sleep(3)
                    return True
                except:
                    return False

        self.smart_wait_and_retry(click_people_tab, retry_wait=5)

        # Extract member names
        print("Extracting member names...")
        html = self.driver.page_source
        soup = BeautifulSoup(html, 'html.parser')

        roster_div = soup.find('div', class_='student_roster')
        if roster_div:
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

    # ==================== CLASS LIST DATA ====================

    def extract_member_details_from_class_list(self):
        """Extract member details from Class List (dynamic iframe content)"""
        print("\n" + "="*80)
        print("STEP 4: EXTRACT MEMBER DETAILS FROM CLASS LIST")
        print("="*80)

        # Navigate to a course
        def navigate_to_course():
            print("\nNavigating to Accounting course...")
            self.driver.get("https://learning.london.edu/courses/11291")
            time.sleep(3)
            return True

        self.smart_wait_and_retry(navigate_to_course)

        # Click on Class List
        def click_class_list():
            print("Clicking on Class List...")
            try:
                class_list_link = self.driver.find_element(By.PARTIAL_LINK_TEXT, 'Class List')
                class_list_link.click()
                time.sleep(5)  # Wait for external tool to load
                return True
            except Exception as e:
                print(f"  Could not find Class List link: {e}")
                return False

        if not self.smart_wait_and_retry(click_class_list, retry_wait=5):
            print("⚠ Could not access Class List - using placeholder data")
            self._create_placeholder_member_details()
            return True

        # Wait for iframe to load and switch to it
        print("Waiting for Class List iframe to load...")
        time.sleep(8)  # Give iframe content time to load

        # Try to switch to iframe
        try:
            iframes = self.driver.find_elements(By.TAG_NAME, 'iframe')
            print(f"  Found {len(iframes)} iframes")

            for iframe in iframes:
                try:
                    self.driver.switch_to.frame(iframe)
                    time.sleep(2)

                    # Try to click the "Students" tab/button to load student data
                    print("  Looking for Students tab...")
                    try:
                        students_button = None

                        # Try CSS selector first (most specific)
                        try:
                            students_button = self.driver.find_element(By.CSS_SELECTOR, '#cl-profileLayoutTabs > li:nth-child(2) > a')
                            print("  Found Students button via CSS selector")
                        except:
                            pass

                        # Try by href attribute
                        if not students_button:
                            try:
                                students_button = self.driver.find_element(By.CSS_SELECTOR, 'a[href="/ClassList/DPO/Student/List"]')
                                print("  Found Students button via href")
                            except:
                                pass

                        # Try exact XPath
                        if not students_button:
                            try:
                                students_button = self.driver.find_element(By.XPATH, '/html/body/div[2]/div/div[2]/ul/li[2]/a')
                                print("  Found Students button via XPath")
                            except:
                                pass

                        # Fallback: Try finding by partial link text
                        if not students_button:
                            try:
                                students_button = self.driver.find_element(By.PARTIAL_LINK_TEXT, 'Students')
                                print("  Found Students button via partial link text")
                            except:
                                pass

                        if students_button:
                            print("  ✓ Clicking Students button...")
                            students_button.click()
                            time.sleep(5)  # Wait for student data to load
                            print("  ✓ Students data should now be loaded")
                        else:
                            print("  ⚠ Students button not found, trying to proceed anyway...")

                    except Exception as e:
                        print(f"  Warning: Could not click Students button: {e}")

                    # Get page source after clicking Students tab
                    page_source = self.driver.page_source

                    # Check if we have student data
                    if any(name in page_source for name in self.study_group_members[:2]):
                        print("  ✓ Found student data in iframe!")
                        self._parse_class_list_iframe(page_source)
                        self.driver.switch_to.default_content()
                        return True

                    # Switch back and try next iframe
                    self.driver.switch_to.default_content()
                except:
                    self.driver.switch_to.default_content()
                    continue

            print("  Could not find student data in iframes - using placeholder")
            self._create_placeholder_member_details()

        except Exception as e:
            print(f"  Error accessing iframe: {e}")
            self._create_placeholder_member_details()

        return True

    def _parse_class_list_iframe(self, html):
        """Parse the Class List iframe HTML to extract member details"""
        soup = BeautifulSoup(html, 'html.parser')

        print("  Parsing Class List data...")

        # Find all student profile cards
        # Each student is in an <li> with class 'profile-box list-group-item cl-profileItem'
        profile_cards = soup.find_all('li', class_='profile-box')

        print(f"  Found {len(profile_cards)} student profiles")

        # Create a mapping of student data
        student_data = {}

        for card in profile_cards:
            try:
                # Extract student name from displayName field
                name_elem = card.find('h5', {'name': 'displayName'})
                if not name_elem:
                    name_elem = card.find('div', {'name': 'displayName'})

                if not name_elem:
                    continue

                student_name = name_elem.get_text(strip=True)

                # Extract nationality/origin
                origin_elem = card.find('div', {'name': 'nationality-country'})
                origin = origin_elem.get_text(strip=True) if origin_elem else 'Not specified'

                # Extract job title and employer
                job_elem = card.find('div', {'name': 'jobTitle-employerName'})
                occupation = job_elem.get_text(strip=True) if job_elem and job_elem.get_text(strip=True) else 'Not specified'

                # Extract education
                edu_elem = card.find('div', {'name': 'education'})
                education = edu_elem.get_text(strip=True) if edu_elem and edu_elem.get_text(strip=True) else 'Not specified'

                # Store in mapping
                student_data[student_name] = {
                    'origin': origin,
                    'education': education,
                    'previous_occupation': occupation
                }

            except Exception as e:
                print(f"    Warning: Error parsing student card: {e}")
                continue

        # Match study group members with extracted data
        found_count = 0
        for member in self.study_group_members:
            if member in student_data:
                self.member_details[member] = student_data[member]
                found_count += 1
            else:
                # Try partial match (first name + last name)
                matched = False
                for full_name, data in student_data.items():
                    if member.lower() in full_name.lower() or full_name.lower() in member.lower():
                        self.member_details[member] = data
                        found_count += 1
                        matched = True
                        break

                if not matched:
                    # No match found
                    self.member_details[member] = {
                        'origin': 'Not found in Class List',
                        'education': 'Not found in Class List',
                        'previous_occupation': 'Not found in Class List'
                    }

        print(f"  ✓ Extracted details for {found_count}/{len(self.study_group_members)} members")

    def _create_placeholder_member_details(self):
        """Create placeholder data for members"""
        for member in self.study_group_members:
            self.member_details[member] = {
                'origin': 'TBD - needs Class List access',
                'education': 'TBD - needs Class List access',
                'previous_occupation': 'TBD - needs Class List access'
            }

        print(f"✓ Created placeholder data for {len(self.member_details)} members")

    # ==================== REPORT GENERATION ====================

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
                        time_str = item['due_date'].split()[-1]
                        report.append(f"- **Due:** {time_str}")
                    elif 'event_date' in item:
                        time_str = item['event_date'].split()[-1]
                        report.append(f"- **Time:** {time_str}")

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

        return report_text

    # ==================== MAIN WORKFLOW ====================

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

            # Step 4: Extract member details
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
            if self.driver:
                self.driver.quit()


def main():
    print("="*80)
    print("LBS STUDY GROUP MANAGER")
    print("="*80)
    print("\nThis script will:")
    print("  1. Login to learning.london.edu (using saved session if available)")
    print("  2. Extract upcoming assignments from Dashboard")
    print("  3. Find your Study Group members")
    print("  4. Extract member details from Class List")
    print("  5. Generate markdown report for LLM analysis")
    print("\n" + "="*80 + "\n")

    manager = StudyGroupManager()
    manager.run()


if __name__ == '__main__':
    main()
