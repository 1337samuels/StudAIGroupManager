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
        self.events = []  # Separate list for calendar events
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
        """Navigate to Calendar Agenda and extract upcoming assignments and events"""
        print("\n" + "="*80)
        print("STEP 2: EXTRACT UPCOMING ASSIGNMENTS AND EVENTS")
        print("="*80)

        def navigate_to_calendar_agenda():
            print("\nNavigating to Calendar Agenda view...")
            self.driver.get("https://learning.london.edu/calendar#view_name=agenda")
            time.sleep(3)
            return True

        self.smart_wait_and_retry(navigate_to_calendar_agenda)

        # Wait for agenda items to load
        print("Waiting for calendar agenda to load...")
        time.sleep(4)

        # Get page source and parse
        html = self.driver.page_source
        soup = BeautifulSoup(html, 'html.parser')

        # Find all agenda days and items
        agenda_items = soup.find_all('li', class_='agenda-event__item')
        print(f"Found {len(agenda_items)} agenda items")

        # Parse assignments and events
        today = datetime.now()
        two_weeks = today + timedelta(days=14)

        # Use sets to track unique items and avoid duplicates
        seen_assignments = set()
        seen_events = set()

        # Track current date context
        current_date = None

        for item in agenda_items:
            try:
                # Check if there's a preceding agenda-date element (find parent structure)
                parent = item.find_parent('div', class_='agenda-event__container')
                if parent:
                    date_div = parent.find_previous_sibling('div', class_='agenda-day')
                    if date_div:
                        date_elem = date_div.find('h3', class_='agenda-date')
                        if date_elem:
                            # Extract date from aria-hidden span (e.g., "Tue, 25 Nov")
                            date_text = date_elem.find('span', {'aria-hidden': 'true'})
                            if date_text:
                                current_date = date_text.get_text(strip=True)

                # Determine type by icon class
                icon = item.find('i')
                is_assignment = icon and 'icon-assignment' in icon.get('class', [])
                is_quiz = icon and 'icon-quiz' in icon.get('class', [])
                is_event = icon and 'icon-calendar-month' in icon.get('class', [])

                # Extract title from agenda-event__title span
                title_elem = item.find('span', class_='agenda-event__title')
                title = title_elem.get_text(strip=True) if title_elem else 'Untitled'

                # Extract time from agenda-event__time div
                time_elem = item.find('div', class_='agenda-event__time')
                time_str = time_elem.get_text(strip=True) if time_elem else None

                # Extract course from screenreader text containing "Calendar"
                course = 'Unknown Course'
                screenreader_spans = item.find_all('span', class_='screenreader-only')
                for span in screenreader_spans:
                    text = span.get_text(strip=True)
                    if text.startswith('Calendar '):
                        # Format: "Calendar C111   AUT25 Finance I"
                        course = text.replace('Calendar ', '').strip()
                        break

                # Parse datetime
                if not current_date or not time_str:
                    continue

                # Clean time string (e.g., "Due 16:00" -> "16:00" or "16:00" -> "16:00")
                time_clean = time_str.replace('Due ', '').replace('Starts at ', '').strip()

                # Parse date (e.g., "Tue, 25 Nov" with current year)
                try:
                    # Add current year to the date string
                    current_year = datetime.now().year
                    date_with_year = f"{current_date} {current_year}"
                    # Parse format: "Tue, 25 Nov 2025"
                    date_obj = datetime.strptime(date_with_year, "%a, %d %b %Y")
                    # Combine with time
                    time_obj = datetime.strptime(time_clean, "%H:%M").time()
                    event_datetime = datetime.combine(date_obj.date(), time_obj)
                except Exception as e:
                    print(f"  Warning: Could not parse date/time: {current_date} {time_clean} - {e}")
                    continue

                # Skip if outside our range
                if not (today <= event_datetime <= two_weeks):
                    continue

                # Create unique identifier to detect duplicates
                unique_id = f"{title}|{event_datetime.strftime('%Y-%m-%d %H:%M')}|{course}"

                # Categorize and add to appropriate list (avoiding duplicates)
                if (is_assignment or is_quiz) and unique_id not in seen_assignments:
                    seen_assignments.add(unique_id)
                    self.assignments.append({
                        'title': title,
                        'course': course,
                        'type': 'Quiz' if is_quiz else 'Assignment',
                        'due_date': event_datetime.strftime("%d %B %Y %H:%M"),
                        'due_day': event_datetime.strftime("%A"),
                        'due_datetime': event_datetime,
                        'location': '',  # Location not in agenda view
                        'url': ''  # URL extraction would need data-event-id lookup
                    })
                elif is_event and unique_id not in seen_events:
                    seen_events.add(unique_id)
                    self.events.append({
                        'title': title,
                        'course': course,
                        'type': 'Event',
                        'event_date': event_datetime.strftime("%d %B %Y %H:%M"),
                        'event_day': event_datetime.strftime("%A"),
                        'due_datetime': event_datetime,  # For sorting
                        'location': '',  # Location not in agenda view
                        'url': ''  # URL extraction would need data-event-id lookup
                    })

            except Exception as e:
                print(f"  Warning: Error parsing agenda item: {e}")
                continue

        print(f"✓ Found {len(self.assignments)} unique assignments")
        print(f"✓ Found {len(self.events)} unique events")

        # Sort both lists by date
        self.assignments.sort(key=lambda x: x.get('due_datetime', datetime.max))
        self.events.sort(key=lambda x: x.get('due_datetime', datetime.max))

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
        time.sleep(3)  # Reduced from 8 to 3 seconds

        # Try to switch to iframe
        try:
            iframes = self.driver.find_elements(By.TAG_NAME, 'iframe')
            print(f"  Found {len(iframes)} iframes")

            for iframe in iframes:
                try:
                    self.driver.switch_to.frame(iframe)
                    time.sleep(1)  # Reduced from 2 to 1 second

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
                            time.sleep(2)  # Reduced from 5 to 2 seconds
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
        """Generate concise report for LLM analysis (minified format)"""
        print("\n" + "="*80)
        print("STEP 5: GENERATE REPORT")
        print("="*80)

        report = []

        # Header - single line
        report.append(f"REPORT {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        report.append("")

        # Assignments - compact format
        report.append("ASSIGNMENTS:")
        if not self.assignments:
            report.append("None")
        else:
            for item in self.assignments:
                # Format: DATE TIME | COURSE | TYPE | TITLE
                date_str = item['due_datetime'].strftime('%Y-%m-%d %H:%M')
                course = item.get('course', 'Unknown')
                item_type = item.get('type', 'Assignment')
                title = item.get('title', 'Untitled')
                report.append(f"{date_str} | {course} | {item_type} | {title}")

        report.append("")

        # Events - compact format
        report.append("EVENTS:")
        if not self.events:
            report.append("None")
        else:
            for item in self.events:
                # Format: DATE TIME | COURSE | TITLE
                date_str = item['due_datetime'].strftime('%Y-%m-%d %H:%M')
                course = item.get('course', 'Unknown')
                title = item.get('title', 'Untitled')
                report.append(f"{date_str} | {course} | {title}")

        report.append("")

        # Members - compact format
        report.append("MEMBERS:")
        if not self.study_group_members:
            report.append("None")
        else:
            for i, member in enumerate(self.study_group_members, 1):
                # Format: NAME | ORIGIN | EDUCATION | OCCUPATION
                if member in self.member_details:
                    details = self.member_details[member]
                    origin = details.get('origin', 'N/A')
                    education = details.get('education', 'N/A')
                    occupation = details.get('previous_occupation', 'N/A')
                    report.append(f"{member} | {origin} | {education} | {occupation}")
                else:
                    report.append(f"{member} | N/A | N/A | N/A")

        # Write to file
        report_text = '\n'.join(report)

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report_text)

        char_count = len(report_text)
        print(f"✓ Report generated: {output_file}")
        print(f"✓ Report size: {char_count:,} characters (~{char_count//4:,} tokens)")

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

            # Auto-close when run from web UI (no user input needed)
            # input("\n\nPress Enter to close browser and exit...")

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
