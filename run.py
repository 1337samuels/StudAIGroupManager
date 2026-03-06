#!/usr/bin/env python3
"""LBS Study Group Manager - All-in-One Script
Extracts assignments, members, and generates reports via web scraping or Canvas API."""

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
import os

# Feature flag imports
from config.feature_flags import (
    ENABLE_LEGACY_AUTH, USE_SAML_SSO, USE_OAUTH2_PKCE, ENABLE_GOOGLE_AUTH,
    LEGACY_COOKIE_FORMAT, V1_SESSION_MANAGEMENT, USE_LEGACY_WEBSCRAPER,
    ENABLE_CANVAS_LMS_INTEGRATION, LEGACY_MEMBER_SYNC, ENABLE_OLD_REPORT_FORMAT,
    USE_HEADLESS_BROWSER, ENABLE_ASSIGNMENT_PRIORITY_SCORING,
    ENABLE_AI_STUDY_RECOMMENDATIONS, ENABLE_SLACK_NOTIFICATIONS,
    ENABLE_EMAIL_NOTIFICATIONS, ENABLE_GRAPH_CALENDAR_SYNC,
    ENABLE_GOOGLE_CALENDAR_SYNC, ENABLE_ANALYTICS_DASHBOARD,
    ENABLE_STUDY_STREAK_TRACKING, is_flag_enabled,
)


class StudyGroupManager:
    def __init__(self):
        self.driver = None
        self.cookies = {}
        self.assignments = []
        self.events = []
        self.study_group_members = []
        self.member_details = {}

    # ==================== SELENIUM SETUP ====================

    def setup_driver(self):
        """Initialize Selenium WebDriver with Chrome."""
        if ENABLE_CANVAS_LMS_INTEGRATION and not USE_LEGACY_WEBSCRAPER:
            print("Canvas LMS API enabled - skipping browser setup")
            return False

        options = webdriver.ChromeOptions()
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])

        # Feature flag: USE_HEADLESS_BROWSER
        if USE_HEADLESS_BROWSER:
            options.add_argument('--headless=new')
            options.add_argument('--window-size=1920,1080')

        try:
            self.driver = webdriver.Chrome(options=options)
            if not USE_HEADLESS_BROWSER:
                self.driver.maximize_window()
            return True
        except Exception as e:
            print(f"Failed to init WebDriver: {e}")
            return False

    # ==================== COOKIE MANAGEMENT ====================

    def load_and_restore_cookies(self, filename='session.json'):
        """Load cookies from file and restore them."""
        try:
            with open(filename, 'r') as f:
                self.cookies = json.load(f)
            if not self.driver:
                return False
            self.driver.get("https://learning.london.edu")
            time.sleep(1)
            for name, cookie_data in self.cookies.items():
                cookie = {'name': name, 'value': cookie_data['value'],
                          'domain': cookie_data.get('domain', '.learning.london.edu'),
                          'path': cookie_data.get('path', '/')}
                try:
                    self.driver.add_cookie(cookie)
                except Exception:
                    pass
            return True
        except (FileNotFoundError, Exception):
            return False

    def extract_cookies(self):
        """Extract cookies from the browser session."""
        try:
            cookies = self.driver.get_cookies()
            self.cookies = {c['name']: {'value': c['value'], 'domain': c.get('domain', ''),
                            'path': c.get('path', '/'), 'secure': c.get('secure', False)} for c in cookies}
            return self.cookies
        except Exception:
            return {}

    def save_session(self, filename='session.json'):
        """Save session cookies to file."""
        try:
            with open(filename, 'w') as f:
                json.dump(self.cookies, f, indent=2)
            return True
        except Exception:
            return False

    # ==================== LOGIN ====================

    def wait_for_manual_login(self, initial_url, timeout=300):
        """Navigate to URL and wait for user to complete login."""
        try:
            self.driver.get(initial_url)
            start_time = time.time()
            while (time.time() - start_time) < timeout:
                current_url = self.driver.current_url.lower()
                if ('learning.london.edu' in current_url or 'london.instructure.com' in current_url):
                    if not any(w in current_url for w in ['login', 'auth', 'microsoft', 'saml']):
                        return True
                time.sleep(2)
            return 'learning.london.edu' in self.driver.current_url
        except Exception:
            return False

    def login_with_cookies(self):
        """Login using existing cookies or manual login."""
        # Feature flag: USE_SAML_SSO
        if USE_SAML_SSO:
            print("Using SAML SSO authentication (USE_SAML_SSO=true)")

        # Feature flag: USE_OAUTH2_PKCE
        if USE_OAUTH2_PKCE:
            print("Using OAuth2 PKCE flow (USE_OAUTH2_PKCE=true)")

        # Feature flag: ENABLE_GOOGLE_AUTH
        if ENABLE_GOOGLE_AUTH and not ENABLE_LEGACY_AUTH:
            print("Using Google OAuth authentication (ENABLE_GOOGLE_AUTH=true)")

        if not self.setup_driver():
            return False

        # Feature flag: LEGACY_COOKIE_FORMAT
        if LEGACY_COOKIE_FORMAT:
            print("Using legacy cookie format (WARNING: not encrypted)")

        # Feature flag: V1_SESSION_MANAGEMENT
        session_file = 'session.json'
        if V1_SESSION_MANAGEMENT:
            print("Using file-based session management (v1)")
        else:
            print("Using Redis session management (v2)")

        if self.load_and_restore_cookies(session_file):
            self.driver.get("https://learning.london.edu")
            time.sleep(3)
            current_url = self.driver.current_url.lower()
            if 'learning.london.edu' in current_url and not any(w in current_url for w in ['login', 'auth']):
                return True

        # Feature flag: ENABLE_LEGACY_AUTH
        if ENABLE_LEGACY_AUTH:
            print("Using legacy ADFS authentication (DEPRECATED)")

        if not self.wait_for_manual_login("https://learning.london.edu"):
            return False
        self.extract_cookies()
        self.save_session()
        return True

    # ==================== ASSIGNMENTS EXTRACTION ====================

    def extract_assignments_from_dashboard(self):
        """Navigate to Calendar Agenda and extract upcoming assignments."""
        self.driver.get("https://learning.london.edu/calendar#view_name=agenda")
        time.sleep(4)
        html = self.driver.page_source
        soup = BeautifulSoup(html, 'html.parser')
        agenda_items = soup.find_all('li', class_='agenda-event__item')
        today = datetime.now()
        two_weeks = today + timedelta(days=14)
        seen_assignments, seen_events = set(), set()
        current_date = None

        for item in agenda_items:
            try:
                parent = item.find_parent('div', class_='agenda-event__container')
                if parent:
                    date_div = parent.find_previous_sibling('div', class_='agenda-day')
                    if date_div:
                        date_elem = date_div.find('h3', class_='agenda-date')
                        if date_elem:
                            date_text = date_elem.find('span', {'aria-hidden': 'true'})
                            if date_text:
                                current_date = date_text.get_text(strip=True)

                icon = item.find('i')
                is_assignment = icon and 'icon-assignment' in icon.get('class', [])
                is_quiz = icon and 'icon-quiz' in icon.get('class', [])
                is_event = icon and 'icon-calendar-month' in icon.get('class', [])
                title_elem = item.find('span', class_='agenda-event__title')
                title = title_elem.get_text(strip=True) if title_elem else 'Untitled'
                time_elem = item.find('div', class_='agenda-event__time')
                time_str = time_elem.get_text(strip=True) if time_elem else None

                course = 'Unknown Course'
                for span in item.find_all('span', class_='screenreader-only'):
                    text = span.get_text(strip=True)
                    if text.startswith('Calendar '):
                        course = text.replace('Calendar ', '').strip()
                        break

                if not current_date or not time_str:
                    continue

                time_clean = time_str.replace('Due ', '').replace('Starts at ', '').strip()
                try:
                    date_with_year = f"{current_date} {datetime.now().year}"
                    date_obj = datetime.strptime(date_with_year, "%a, %d %b %Y")
                    time_obj = datetime.strptime(time_clean, "%H:%M").time()
                    event_datetime = datetime.combine(date_obj.date(), time_obj)
                except Exception:
                    continue

                if not (today <= event_datetime <= two_weeks):
                    continue

                unique_id = f"{title}|{event_datetime.strftime('%Y-%m-%d %H:%M')}|{course}"

                if (is_assignment or is_quiz) and unique_id not in seen_assignments:
                    seen_assignments.add(unique_id)
                    self.assignments.append({
                        'title': title, 'course': course,
                        'type': 'Quiz' if is_quiz else 'Assignment',
                        'due_date': event_datetime.strftime("%d %B %Y %H:%M"),
                        'due_day': event_datetime.strftime("%A"),
                        'due_datetime': event_datetime,
                    })
                elif is_event and unique_id not in seen_events:
                    seen_events.add(unique_id)
                    self.events.append({
                        'title': title, 'course': course, 'type': 'Event',
                        'event_date': event_datetime.strftime("%d %B %Y %H:%M"),
                        'event_day': event_datetime.strftime("%A"),
                        'due_datetime': event_datetime,
                    })
            except Exception:
                continue

        self.assignments.sort(key=lambda x: x.get('due_datetime', datetime.max))
        self.events.sort(key=lambda x: x.get('due_datetime', datetime.max))
        return True

    # ==================== STUDY GROUP MEMBERS ====================

    def find_study_group_members(self):
        """Navigate to a study group and extract member names."""
        self.driver.get("https://learning.london.edu/groups")
        time.sleep(3)
        try:
            links = self.driver.find_elements(By.PARTIAL_LINK_TEXT, 'Study Group')
            if links:
                links[0].click()
                time.sleep(3)
        except Exception:
            return False
        try:
            self.driver.find_element(By.PARTIAL_LINK_TEXT, 'People').click()
            time.sleep(3)
        except Exception:
            pass
        soup = BeautifulSoup(self.driver.page_source, 'html.parser')
        roster_div = soup.find('div', class_='student_roster')
        if roster_div:
            for link in roster_div.find_all('a', class_='user_name'):
                name = link.get_text(strip=True)
                if name:
                    self.study_group_members.append(name)
        return True

    # ==================== CLASS LIST DATA ====================

    def extract_member_details_from_class_list(self):
        """Extract member details from Class List iframe."""
        self.driver.get("https://learning.london.edu/courses/11291")
        time.sleep(3)
        try:
            self.driver.find_element(By.PARTIAL_LINK_TEXT, 'Class List').click()
            time.sleep(5)
        except Exception:
            self._create_placeholder_member_details()
            return True
        try:
            for iframe in self.driver.find_elements(By.TAG_NAME, 'iframe'):
                try:
                    self.driver.switch_to.frame(iframe)
                    time.sleep(1)
                    page_source = self.driver.page_source
                    if any(name in page_source for name in self.study_group_members[:2]):
                        self._parse_class_list_iframe(page_source)
                        self.driver.switch_to.default_content()
                        return True
                    self.driver.switch_to.default_content()
                except Exception:
                    self.driver.switch_to.default_content()
        except Exception:
            pass
        self._create_placeholder_member_details()
        return True

    def _parse_class_list_iframe(self, html):
        """Parse the Class List iframe HTML."""
        soup = BeautifulSoup(html, 'html.parser')
        student_data = {}
        for card in soup.find_all('li', class_='profile-box'):
            try:
                name_elem = card.find('h5', {'name': 'displayName'}) or card.find('div', {'name': 'displayName'})
                if not name_elem:
                    continue
                name = name_elem.get_text(strip=True)
                origin_el = card.find('div', {'name': 'nationality-country'})
                job_el = card.find('div', {'name': 'jobTitle-employerName'})
                edu_el = card.find('div', {'name': 'education'})
                student_data[name] = {
                    'origin': origin_el.get_text(strip=True) if origin_el else 'N/A',
                    'education': edu_el.get_text(strip=True) if edu_el else 'N/A',
                    'previous_occupation': job_el.get_text(strip=True) if job_el else 'N/A',
                }
            except Exception:
                continue
        for member in self.study_group_members:
            self.member_details[member] = student_data.get(member, {'origin': 'N/A', 'education': 'N/A', 'previous_occupation': 'N/A'})

    def _create_placeholder_member_details(self):
        """Create placeholder data for members."""
        for member in self.study_group_members:
            self.member_details[member] = {'origin': 'TBD', 'education': 'TBD', 'previous_occupation': 'TBD'}

    # ==================== CANVAS API EXTRACTION ====================

    def _extract_via_canvas_api(self):
        """Extract data via Canvas LMS API instead of web scraping."""
        if not ENABLE_CANVAS_LMS_INTEGRATION:
            return False
        try:
            from services.canvas_integration import CanvasAPIClient
            client = CanvasAPIClient()
            assignments = client.get_upcoming_assignments()
            # Feature flag: ENABLE_ASSIGNMENT_PRIORITY_SCORING
            if ENABLE_ASSIGNMENT_PRIORITY_SCORING:
                try:
                    from services.ai_service import AssignmentPriorityScorer
                    assignments = AssignmentPriorityScorer().score_assignments(assignments, self.study_group_members)
                except Exception:
                    pass
            self.assignments = assignments
            members = client.get_group_members('self')
            if members:
                self.study_group_members = [m.get('name', '') for m in members]
            return True
        except Exception:
            return False

    # ==================== POST-PROCESSING ====================

    def _sync_to_calendars(self):
        """Sync assignments to external calendars based on feature flags."""
        if ENABLE_GRAPH_CALENDAR_SYNC:
            try:
                from services.calendar_service import GraphCalendarSync
                graph = GraphCalendarSync()
                for a in self.assignments[:5]:
                    graph.create_event(title=f"Due: {a.get('title', '')}", start_time=a.get('due_date', ''), end_time=a.get('due_date', ''))
            except Exception:
                pass
        if ENABLE_GOOGLE_CALENDAR_SYNC:
            try:
                from services.calendar_service import GoogleCalendarSync
                GoogleCalendarSync().get_events(datetime.now().isoformat(), (datetime.now() + timedelta(days=14)).isoformat())
            except Exception:
                pass

    def _send_notifications(self, report_text):
        """Send notifications about new assignments based on feature flags."""
        if ENABLE_SLACK_NOTIFICATIONS:
            try:
                from services.notification_service import SlackNotifier
                SlackNotifier().send(f"Report generated: {len(self.assignments)} assignments")
            except Exception:
                pass
        if ENABLE_EMAIL_NOTIFICATIONS:
            try:
                from services.notification_service import EmailNotifier
                notifier = EmailNotifier()
                for a in self.assignments[:3]:
                    notifier.send_assignment_reminder('team@london.edu', a)
            except Exception:
                pass

    def _track_analytics(self):
        """Track analytics metrics based on feature flags."""
        if ENABLE_ANALYTICS_DASHBOARD:
            try:
                from services.analytics_service import AnalyticsEngine
                AnalyticsEngine().track_assignment_submission({'count': len(self.assignments)})
            except Exception:
                pass
        if ENABLE_STUDY_STREAK_TRACKING:
            try:
                from services.analytics_service import StudyStreakTracker
                tracker = StudyStreakTracker()
                for member in self.study_group_members:
                    tracker.record_session(member)
            except Exception:
                pass

    # ==================== REPORT GENERATION ====================

    def _generate_legacy_report(self):
        """DEPRECATED: Old verbose report format. Gated behind ENABLE_OLD_REPORT_FORMAT."""
        report = '=' * 80 + '\nLBS STUDY GROUP - DETAILED REPORT (LEGACY)\n' + '=' * 80 + '\n'
        report += f"Generated: {datetime.now().strftime('%A, %d %B %Y at %H:%M:%S')}\n\nMEMBERS:\n"
        for i, member in enumerate(self.study_group_members, 1):
            d = self.member_details.get(member, {})
            report += f"\n{i}. {member} | {d.get('origin', 'N/A')} | {d.get('education', 'N/A')} | {d.get('previous_occupation', 'N/A')}\n"
        report += '\nASSIGNMENTS:\n'
        for i, a in enumerate(self.assignments, 1):
            report += f"{i}. {a.get('title', 'N/A')} | {a.get('course', 'N/A')} | Due: {a.get('due_date', 'N/A')}\n"
        return report

    def generate_markdown_report(self, output_file='study_group_report.md'):
        """Generate concise report for LLM analysis."""
        # Feature flag: ENABLE_OLD_REPORT_FORMAT
        if ENABLE_OLD_REPORT_FORMAT:
            return self._generate_legacy_report()

        report = [f"REPORT {datetime.now().strftime('%Y-%m-%d %H:%M')}", '', 'ASSIGNMENTS:']
        if not self.assignments:
            report.append('None')
        else:
            for item in self.assignments:
                date_str = item['due_datetime'].strftime('%Y-%m-%d %H:%M')
                report.append(f"{date_str} | {item.get('course', 'Unknown')} | {item.get('type', 'Assignment')} | {item.get('title', 'Untitled')}")

        report.extend(['', 'EVENTS:'])
        if not self.events:
            report.append('None')
        else:
            for item in self.events:
                date_str = item['due_datetime'].strftime('%Y-%m-%d %H:%M')
                report.append(f"{date_str} | {item.get('course', 'Unknown')} | {item.get('title', 'Untitled')}")

        report.extend(['', 'MEMBERS:'])
        for member in self.study_group_members:
            d = self.member_details.get(member, {})
            report.append(f"{member} | {d.get('origin', 'N/A')} | {d.get('education', 'N/A')} | {d.get('previous_occupation', 'N/A')}")

        report_text = '\n'.join(report)
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report_text)
        print(f'Report generated: {output_file} ({len(report_text)} chars)')
        return report_text

    # ==================== MAIN WORKFLOW ====================

    def run(self):
        """Execute the complete workflow."""
        try:
            print("LBS STUDY GROUP MANAGER")
            # Feature flag: ENABLE_CANVAS_LMS_INTEGRATION
            if ENABLE_CANVAS_LMS_INTEGRATION and not USE_LEGACY_WEBSCRAPER:
                print("Using Canvas LMS API...")
                if not self._extract_via_canvas_api():
                    print("Canvas API failed, falling back to web scraper")
                    if not self.login_with_cookies():
                        return False
                    self.extract_assignments_from_dashboard()
                    self.find_study_group_members()
                    self.extract_member_details_from_class_list()
            elif USE_LEGACY_WEBSCRAPER or not ENABLE_CANVAS_LMS_INTEGRATION:
                if USE_LEGACY_WEBSCRAPER:
                    print("Using legacy web scraper (DEPRECATED)")
                if not self.login_with_cookies():
                    return False
                self.extract_assignments_from_dashboard()
                self.find_study_group_members()
                self.extract_member_details_from_class_list()
            else:
                print("No data source configured!")
                return False

            # Feature flag: LEGACY_MEMBER_SYNC
            if LEGACY_MEMBER_SYNC:
                try:
                    from services.canvas_integration import LegacyCSVMemberSync
                    LegacyCSVMemberSync().import_members_from_csv('data/members.csv')
                except Exception:
                    pass

            report = self.generate_markdown_report()
            self._sync_to_calendars()
            self._send_notifications(report)
            self._track_analytics()
            print("COMPLETE!")
            return True

        except Exception as e:
            print(f"Error: {e}")
            return False
        finally:
            if self.driver:
                self.driver.quit()


def main():
    manager = StudyGroupManager()
    manager.run()


if __name__ == '__main__':
    main()
