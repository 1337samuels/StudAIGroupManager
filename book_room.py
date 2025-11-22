#!/usr/bin/env python3
"""
LBS Room Booking Script
Automatically books rooms on lbsmobile.london.edu based on configuration file
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from datetime import datetime
import time
import json


class RoomBooker:
    def __init__(self, config_file='room_booking_config.json'):
        self.driver = None
        self.cookies = {}
        self.config = self.load_config(config_file)

    # ==================== CONFIG MANAGEMENT ====================

    def load_config(self, config_file):
        """Load booking configuration from JSON file"""
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            print(f"✓ Loaded configuration from {config_file}")
            print(f"  Date: {config['booking_date']}")
            print(f"  Time: {config['start_time']}")
            print(f"  Duration: {config['duration_hours']} hours")
            print(f"  Attendees: {config['attendees']}")
            print(f"  Building: {config['building']}")
            return config
        except Exception as e:
            print(f"✗ Error loading config file: {e}")
            raise

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

    def load_and_restore_cookies(self, filename='lbsmobile_session.json'):
        """Load cookies from file and restore them to the browser"""
        try:
            with open(filename, 'r') as f:
                self.cookies = json.load(f)

            if not self.driver:
                return False

            # Navigate to the domain first (cookies need a domain context)
            self.driver.get("https://lbsmobile.london.edu")
            time.sleep(1)

            # Add each cookie to the browser
            for name, cookie_data in self.cookies.items():
                cookie = {
                    'name': name,
                    'value': cookie_data['value'],
                    'domain': cookie_data.get('domain', '.lbsmobile.london.edu'),
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

    def save_session(self, filename='lbsmobile_session.json'):
        """Save session cookies to a file"""
        try:
            with open(filename, 'w') as f:
                json.dump(self.cookies, f, indent=2)
            print(f"✓ Session saved to {filename}")
            return True
        except Exception as e:
            print(f"✗ Error saving session: {e}")
            return False

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

                    if 'lbsmobile.london.edu' in current_url:
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

            if 'lbsmobile.london.edu' in current_url:
                print("\n  You appear to be on the target site. Continuing...")
                return True

            return False

        except Exception as e:
            print(f"\n✗ Error during manual login wait: {e}")
            return False

    def login_with_cookies(self):
        """Login using existing cookies or manual login"""
        print("="*80)
        print("STEP 1: LOGIN TO LBSMOBILE.LONDON.EDU")
        print("="*80)

        if not self.setup_driver():
            return False

        # Try to restore cookies
        print("\nAttempting to restore session from cookies...")
        if self.load_and_restore_cookies():
            print("Testing if session is still valid...")
            self.driver.get("https://lbsmobile.london.edu")
            time.sleep(3)

            current_url = self.driver.current_url.lower()
            if 'lbsmobile.london.edu' in current_url and not any(word in current_url for word in ['login', 'auth', 'microsoft', 'saml']):
                print("✓ Session restored successfully! Already logged in.")
                return True
            else:
                print("  Session expired or invalid. Need to login manually.")

        # Manual login needed
        print("\nProceeding with manual login...")
        if not self.wait_for_manual_login("https://lbsmobile.london.edu"):
            return False

        # Save new session
        self.extract_cookies()
        self.save_session()

        return True

    # ==================== NAVIGATION ====================

    def navigate_to_bookings(self):
        """Click on 'My Bookings' from main page"""
        print("\n" + "="*80)
        print("STEP 2: NAVIGATE TO MY BOOKINGS")
        print("="*80)

        try:
            print("\nWaiting for main page to load...")
            time.sleep(3)

            # Click on "My Bookings" button
            print("Clicking 'My Bookings' button...")
            my_bookings_btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.ID, "userBookings"))
            )
            my_bookings_btn.click()
            time.sleep(2)

            print("✓ Navigated to My Bookings page")
            return True

        except Exception as e:
            print(f"✗ Error navigating to bookings: {e}")
            return False

    def click_book_room(self):
        """Click on 'Book Room' button"""
        print("\n" + "="*80)
        print("STEP 3: CLICK BOOK ROOM")
        print("="*80)

        try:
            print("\nLooking for 'Book Room' button...")
            book_room_btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CLASS_NAME, "toBookingPage"))
            )
            book_room_btn.click()
            time.sleep(2)

            print("✓ Clicked 'Book Room' button")
            return True

        except Exception as e:
            print(f"✗ Error clicking Book Room: {e}")
            return False

    # ==================== FORM FILLING ====================

    def fill_booking_form(self):
        """Fill out the new booking form with config values"""
        print("\n" + "="*80)
        print("STEP 4: FILL BOOKING FORM")
        print("="*80)

        try:
            # Wait for form to load
            print("\nWaiting for booking form to load...")
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "bookingdatepicker"))
            )
            time.sleep(2)

            # Fill Booking Date using JavaScript (datepicker is readonly)
            print(f"\nSetting booking date to {self.config['booking_date']}...")
            date_obj = datetime.strptime(self.config['booking_date'], '%Y-%m-%d')
            date_formatted = date_obj.strftime('%d/%m/%Y')  # Format as DD/MM/YYYY for UK format

            self.driver.execute_script(
                f"document.getElementById('bookingdatepicker').value = '{date_formatted}';"
            )
            print(f"✓ Date set to {date_formatted}")

            # Fill Start Time
            print(f"\nSetting start time to {self.config['start_time']}...")
            hour, minute = self.config['start_time'].split(':')

            # Select hour
            hour_select = Select(self.driver.find_element(By.ID, "starthourbox"))
            hour_select.select_by_value(hour)
            print(f"  ✓ Hour set to {hour}")

            # Select minute
            minute_select = Select(self.driver.find_element(By.ID, "startminutesbox"))
            minute_select.select_by_value(minute)
            print(f"  ✓ Minute set to {minute}")

            # Fill Duration (convert hours to minutes)
            print(f"\nSetting duration to {self.config['duration_hours']} hours...")
            duration_minutes = str(self.config['duration_hours'] * 60)
            duration_select = Select(self.driver.find_element(By.ID, "durationbox"))
            duration_select.select_by_value(duration_minutes)
            print(f"✓ Duration set to {duration_minutes} minutes ({self.config['duration_hours']} hours)")

            # Set Number of Attendees using JavaScript (it's a slider)
            print(f"\nSetting attendees to {self.config['attendees']}...")
            self.driver.execute_script(
                f"document.getElementById('noofattendees').value = {self.config['attendees']};"
            )
            # Trigger change event to update UI
            self.driver.execute_script(
                "document.getElementById('noofattendees').dispatchEvent(new Event('change'));"
            )
            print(f"✓ Attendees set to {self.config['attendees']}")

            # Fill Booking Title
            print(f"\nSetting booking title...")
            booking_title = f"{self.config['study_group_name']} - {self.config['project_name']}"
            title_input = self.driver.find_element(By.ID, "meetingTitlebox")
            title_input.clear()
            title_input.send_keys(booking_title)
            print(f"✓ Booking title set to '{booking_title}'")

            # Select Building
            print(f"\nSelecting building: {self.config['building']}...")
            building_map = {
                "North Building": "NB",
                "Sammy Ofer Centre": "SOC",
                "Sussex Place": "Susx Plc"
            }
            building_code = building_map.get(self.config['building'], "Susx Plc")

            building_select = Select(self.driver.find_element(By.ID, "sitebox"))
            building_select.select_by_value(building_code)
            print(f"✓ Building set to {self.config['building']} ({building_code})")

            # Submit the form
            print("\nSubmitting booking form...")
            time.sleep(1)
            submit_btn = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit'].lbs-btn-default")
            submit_btn.click()
            time.sleep(3)

            print("✓ Form submitted - waiting for available rooms...")
            return True

        except Exception as e:
            print(f"✗ Error filling booking form: {e}")
            import traceback
            traceback.print_exc()
            return False

    # ==================== ROOM SELECTION ====================

    def select_and_book_room(self):
        """Wait for available rooms page, select first room, and book it"""
        print("\n" + "="*80)
        print("STEP 5: SELECT AND BOOK ROOM")
        print("="*80)

        try:
            # Wait a few seconds for the page to load the rooms
            print("\nWaiting for available rooms to load...")
            time.sleep(5)  # Give extra time as mentioned in requirements

            # Wait for the available rooms container
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.ID, "availblerooms"))
            )

            # Find all room radio buttons
            print("Looking for available rooms...")
            room_radios = self.driver.find_elements(By.CSS_SELECTOR, "input.selectedRoom")

            if not room_radios:
                print("✗ No available rooms found!")
                return False

            print(f"✓ Found {len(room_radios)} available rooms")

            # Get the label for the first room to see its name
            first_room = room_radios[0]
            room_id = first_room.get_attribute('id')

            try:
                room_label = self.driver.find_element(By.CSS_SELECTOR, f"label[for='{room_id}']")
                room_name = room_label.text
                print(f"\nSelecting first available room: {room_name}")
            except:
                print(f"\nSelecting first available room (ID: {room_id})")

            # Click the first room radio button
            self.driver.execute_script("arguments[0].click();", first_room)
            time.sleep(1)

            # Click the Book button
            print("\nClicking 'Book' button...")
            book_btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.ID, "bookButton"))
            )
            book_btn.click()
            time.sleep(3)

            # Check for success or failure
            print("\nChecking booking result...")
            current_url = self.driver.current_url

            if 'bookingSuccessfulDialog' in current_url or 'bookingSuccessfulDialog' in self.driver.page_source:
                print("\n" + "="*80)
                print("✓ BOOKING SUCCESSFUL!")
                print("="*80)
                print(f"Room booked: {room_name if 'room_name' in locals() else room_id}")
                print(f"Date: {self.config['booking_date']}")
                print(f"Time: {self.config['start_time']}")
                print(f"Duration: {self.config['duration_hours']} hours")
                print(f"Title: {self.config['study_group_name']} - {self.config['project_name']}")
                return True
            elif 'bookingFailedDialog' in current_url or 'bookingFailedDialog' in self.driver.page_source:
                print("\n✗ BOOKING FAILED!")
                try:
                    error_msg = self.driver.find_element(By.ID, "failedBookingMessage").text
                    print(f"Error message: {error_msg}")
                except:
                    print("Could not retrieve error message")
                return False
            else:
                print("\n⚠ Booking status unclear - please check the browser")
                return True  # Assume success if no clear failure

        except Exception as e:
            print(f"\n✗ Error selecting and booking room: {e}")
            import traceback
            traceback.print_exc()
            return False

    # ==================== MAIN WORKFLOW ====================

    def run(self):
        """Execute the complete room booking workflow"""
        try:
            print("\n" + "="*80)
            print("LBS ROOM BOOKING AUTOMATION")
            print("="*80)

            # Step 1: Login
            if not self.login_with_cookies():
                print("\n✗ Login failed")
                return False

            # Step 2: Navigate to My Bookings
            if not self.navigate_to_bookings():
                print("\n✗ Failed to navigate to bookings page")
                return False

            # Step 3: Click Book Room
            if not self.click_book_room():
                print("\n✗ Failed to click Book Room button")
                return False

            # Step 4: Fill booking form
            if not self.fill_booking_form():
                print("\n✗ Failed to fill booking form")
                return False

            # Step 5: Select and book room
            if not self.select_and_book_room():
                print("\n✗ Failed to select and book room")
                return False

            print("\n" + "="*80)
            print("✓ ROOM BOOKING PROCESS COMPLETED!")
            print("="*80)

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
    print("LBS ROOM BOOKING SCRIPT")
    print("="*80)
    print("\nThis script will:")
    print("  1. Login to lbsmobile.london.edu (using saved session if available)")
    print("  2. Navigate to the room booking page")
    print("  3. Fill in booking details from room_booking_config.json")
    print("  4. Select the first available room")
    print("  5. Complete the booking")
    print("\n" + "="*80 + "\n")

    booker = RoomBooker()
    booker.run()


if __name__ == '__main__':
    main()
