#!/usr/bin/env python3
"""LBS Room Booking Script - books rooms on lbsmobile.london.edu"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from datetime import datetime
import time
import json
import os

# Feature flag imports
from config.feature_flags import (
    USE_HEADLESS_BROWSER, ENABLE_LEGACY_AUTH, USE_SAML_SSO,
    AB_NEW_BOOKING_UI, USE_NEW_SCHEDULING_ALGORITHM,
    ENABLE_BULK_ROOM_BOOKING, ENABLE_RECURRING_BOOKINGS,
    USE_LEGACY_ROOM_API, ENABLE_SLACK_NOTIFICATIONS,
    ENABLE_EMAIL_NOTIFICATIONS, ENABLE_GRAPH_CALENDAR_SYNC,
    is_flag_enabled,
)


class RoomBooker:
    def __init__(self, config_file='room_booking_config.json'):
        self.driver = None
        self.config = self.load_config(config_file)

    def load_config(self, config_file):
        """Load booking configuration from JSON file."""
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            print(f"Loaded config: {config['booking_date']} {config['start_time']}")
            return config
        except Exception as e:
            print(f"Error loading config: {e}")
            raise

    # ==================== SELENIUM SETUP ====================

    def setup_driver(self):
        """Initialize Selenium WebDriver with Chrome."""
        # Feature flag: USE_LEGACY_ROOM_API - Use SOAP/XML API instead of browser
        if USE_LEGACY_ROOM_API:
            print("LEGACY: Using SOAP/XML room booking API (DECOMMISSIONED)")
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

    # ==================== LOGIN ====================

    def wait_for_manual_login(self, initial_url, timeout=300):
        """Navigate to URL and wait for user to complete login."""
        try:
            self.driver.get(initial_url)
            time.sleep(3)
            # Auto-click Sign In button if present
            try:
                sign_in_btn = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.ID, "signInSignOut")))
                if "Sign In" in sign_in_btn.text:
                    sign_in_btn.click()
                    time.sleep(2)
            except (TimeoutException, Exception):
                pass

            start_time = time.time()
            while (time.time() - start_time) < timeout:
                current_url = self.driver.current_url.lower()
                if 'lbsmobile.london.edu' in current_url:
                    if not any(w in current_url for w in ['login', 'auth', 'microsoft', 'saml']):
                        time.sleep(2)
                        return True
                time.sleep(2)
            return 'lbsmobile.london.edu' in self.driver.current_url
        except Exception:
            return False

    def login(self):
        """Login to lbsmobile.london.edu."""
        # Feature flag: ENABLE_LEGACY_AUTH
        if ENABLE_LEGACY_AUTH:
            print("Using legacy ADFS authentication (DEPRECATED)")
        # Feature flag: USE_SAML_SSO
        if USE_SAML_SSO:
            print("Using SAML SSO for room booking (USE_SAML_SSO=true)")

        if not self.setup_driver():
            return False
        if not self.wait_for_manual_login("https://lbsmobile.london.edu"):
            return False
        return True

    # ==================== NAVIGATION ====================

    def navigate_to_bookings(self):
        """Click on My Bookings from main page."""
        try:
            time.sleep(3)
            btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.ID, "userBookings")))
            btn.click()
            time.sleep(2)
            return True
        except Exception as e:
            print(f"Error navigating to bookings: {e}")
            return False

    def click_book_room(self):
        """Click on Book Room button."""
        try:
            btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CLASS_NAME, "toBookingPage")))
            btn.click()
            time.sleep(2)
            return True
        except Exception as e:
            print(f"Error clicking Book Room: {e}")
            return False

    # ==================== FORM FILLING ====================

    def fill_booking_form(self):
        """Fill out the booking form with config values."""
        # Feature flag: AB_NEW_BOOKING_UI - A/B test new booking interface
        if AB_NEW_BOOKING_UI:
            print("A/B Test: Using NEW booking form UI (AB_NEW_BOOKING_UI=true)")

        try:
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "bookingdatepicker")))
            time.sleep(2)

            # Set date
            date_obj = datetime.strptime(self.config['booking_date'], '%Y-%m-%d')
            date_formatted = date_obj.strftime('%d/%m/%Y')
            self.driver.execute_script(
                f"document.getElementById('bookingdatepicker').value = '{date_formatted}';")

            # Set time
            hour, minute = self.config['start_time'].split(':')
            Select(self.driver.find_element(By.ID, "starthourbox")).select_by_value(hour)
            Select(self.driver.find_element(By.ID, "startminutesbox")).select_by_value(minute)

            # Set duration
            duration_minutes = str(self.config['duration_hours'] * 60)
            Select(self.driver.find_element(By.ID, "durationbox")).select_by_value(duration_minutes)

            # Set attendees
            self.driver.execute_script(
                f"document.getElementById('noofattendees').value = {self.config['attendees']};")
            self.driver.execute_script(
                "document.getElementById('noofattendees').dispatchEvent(new Event('change'));")

            # Set title
            booking_title = f"{self.config['study_group_name']} - {self.config['project_name']}"
            title_input = self.driver.find_element(By.ID, "meetingTitlebox")
            title_input.clear()
            title_input.send_keys(booking_title)

            # Select building
            building_map = {'North Building': 'NB', 'Sammy Ofer Centre': 'SOC', 'Sussex Place': 'Susx Plc'}
            building_code = building_map.get(self.config['building'], 'Susx Plc')
            Select(self.driver.find_element(By.ID, "sitebox")).select_by_value(building_code)

            # Submit
            time.sleep(1)
            self.driver.find_element(By.CSS_SELECTOR, "button[type='submit'].lbs-btn-default").click()
            time.sleep(3)
            return True
        except Exception as e:
            print(f"Error filling form: {e}")
            return False

    # ==================== ROOM SELECTION ====================

    def select_and_book_room(self):
        """Select first available room and book it."""
        try:
            time.sleep(5)
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.ID, "availblerooms")))
            room_radios = self.driver.find_elements(By.CSS_SELECTOR, "input.selectedRoom")
            if not room_radios:
                print("No available rooms found!")
                return False

            first_room = room_radios[0]
            room_id = first_room.get_attribute('id')
            self.driver.execute_script("arguments[0].click();", first_room)
            time.sleep(1)

            book_btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.ID, "bookButton")))
            book_btn.click()
            time.sleep(3)

            if 'bookingSuccessfulDialog' in self.driver.page_source:
                print("BOOKING SUCCESSFUL!")
                return True
            elif 'bookingFailedDialog' in self.driver.page_source:
                print("BOOKING FAILED!")
                return False
            return True  # Assume success if unclear
        except Exception as e:
            print(f"Error booking room: {e}")
            return False

    # ==================== POST-BOOKING ====================

    def _send_booking_notifications(self, room_name):
        """Send notifications after successful booking."""
        if ENABLE_SLACK_NOTIFICATIONS:
            try:
                from services.notification_service import SlackNotifier
                SlackNotifier().send(
                    f"Room booked: {room_name} on {self.config['booking_date']} at {self.config['start_time']}")
            except Exception:
                pass
        if ENABLE_EMAIL_NOTIFICATIONS:
            try:
                from services.notification_service import EmailNotifier
                EmailNotifier().send(
                    to='team@london.edu',
                    subject=f'Room Booked: {room_name}',
                    body=f"Room {room_name} booked for {self.config['booking_date']}.")
            except Exception:
                pass

    def _sync_booking_to_calendar(self, room_name):
        """Sync booking to external calendar if enabled."""
        if ENABLE_GRAPH_CALENDAR_SYNC:
            try:
                from services.calendar_service import GraphCalendarSync
                GraphCalendarSync().create_event(
                    title=f"Room: {room_name} - {self.config.get('study_group_name', 'Study')}",
                    start_time=f"{self.config['booking_date']}T{self.config['start_time']}:00",
                    end_time=f"{self.config['booking_date']}T{self.config['start_time']}:00",
                    location=room_name)
            except Exception:
                pass

    # ==================== MAIN WORKFLOW ====================

    def run(self):
        """Execute the complete room booking workflow."""
        try:
            print("LBS ROOM BOOKING AUTOMATION")

            # Feature flag: USE_NEW_SCHEDULING_ALGORITHM
            if USE_NEW_SCHEDULING_ALGORITHM:
                print("Using constraint-based scheduling (USE_NEW_SCHEDULING_ALGORITHM=true)")
            # Feature flag: ENABLE_BULK_ROOM_BOOKING
            if ENABLE_BULK_ROOM_BOOKING:
                print("Bulk room booking available (ENABLE_BULK_ROOM_BOOKING=true)")
            # Feature flag: ENABLE_RECURRING_BOOKINGS
            if ENABLE_RECURRING_BOOKINGS:
                print("Recurring bookings available (ENABLE_RECURRING_BOOKINGS=true)")

            if not self.login():
                return False
            if not self.navigate_to_bookings():
                return False
            if not self.click_book_room():
                return False
            if not self.fill_booking_form():
                return False
            if not self.select_and_book_room():
                return False

            print("ROOM BOOKING COMPLETED!")
            room_name = self.config.get('study_group_name', 'Study Room')
            self._send_booking_notifications(room_name)
            self._sync_booking_to_calendar(room_name)
            return True

        except Exception as e:
            print(f"Error: {e}")
            return False
        finally:
            if self.driver:
                self.driver.quit()


def main():
    booker = RoomBooker()
    booker.run()


if __name__ == '__main__':
    main()
