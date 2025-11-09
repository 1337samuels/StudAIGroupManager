#!/usr/bin/env python3
"""
Microsoft Azure AD Login Script with Selenium
Opens a browser for manual authentication, then extracts the session.
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import json
import sys
import time


class AzureADLogin:
    def __init__(self):
        self.driver = None
        self.cookies = {}

    def setup_driver(self):
        """Initialize Selenium WebDriver with Chrome"""
        print("Setting up Chrome WebDriver...")

        options = webdriver.ChromeOptions()
        # Uncomment the line below to run headless (no GUI)
        # options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)

        # Set a realistic user agent
        options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

        try:
            self.driver = webdriver.Chrome(options=options)
            self.driver.maximize_window()
            print("✓ Chrome WebDriver initialized")
            return True
        except Exception as e:
            print(f"✗ Failed to initialize Chrome WebDriver: {e}")
            print("\nPlease ensure Chrome and chromedriver are installed:")
            print("  - Chrome browser: https://www.google.com/chrome/")
            print("  - ChromeDriver: Should be installed with selenium, or download from https://chromedriver.chromium.org/")
            return False

    def wait_for_manual_login(self, initial_url, timeout=300):
        """
        Navigate to the initial URL and wait for user to manually complete login

        Args:
            initial_url: The application URL (e.g., https://learning.london.edu)
            timeout: Maximum time to wait for login (seconds)

        Returns:
            bool: True if login successful, False otherwise
        """
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

            # Navigate to the initial URL
            self.driver.get(initial_url)

            # Wait for user to complete login
            # We'll check if we've reached the target domain (learning.london.edu or london.instructure.com)
            start_time = time.time()
            check_interval = 2  # Check every 2 seconds

            print("\n⏳ Waiting for you to complete login...")

            while (time.time() - start_time) < timeout:
                try:
                    current_url = self.driver.current_url.lower()

                    # Check if we've successfully logged in
                    # Success indicators:
                    # - URL contains learning.london.edu or london.instructure.com
                    # - URL doesn't contain 'login', 'auth', or 'microsoft'
                    if ('learning.london.edu' in current_url or 'london.instructure.com' in current_url):
                        if not any(word in current_url for word in ['login', 'auth', 'microsoft', 'saml']):
                            print("\n✓ Login successful!")
                            print(f"  Current URL: {self.driver.current_url}")
                            return True

                    # Show progress indicator
                    elapsed = int(time.time() - start_time)
                    if elapsed % 10 == 0 and elapsed > 0:
                        print(f"  Still waiting... ({elapsed}s elapsed)")

                    time.sleep(check_interval)

                except Exception as e:
                    print(f"  Warning during wait: {e}")
                    time.sleep(check_interval)

            print(f"\n⚠ Timeout after {timeout} seconds")
            print("  Login may not have completed successfully")

            # Ask user if they want to continue anyway
            current_url = self.driver.current_url
            print(f"\n  Current URL: {current_url}")

            if 'learning.london.edu' in current_url or 'london.instructure.com' in current_url:
                print("\n  You appear to be on the target site. Continuing...")
                return True

            return False

        except Exception as e:
            print(f"\n✗ Error during manual login wait: {e}")
            import traceback
            traceback.print_exc()
            return False

    def extract_cookies(self):
        """Extract cookies from the browser session"""
        try:
            print("\nExtracting session cookies...")
            cookies = self.driver.get_cookies()

            # Store cookies in a dictionary
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

    def get_page_source(self):
        """Get the current page HTML source"""
        try:
            return self.driver.page_source
        except Exception as e:
            print(f"✗ Error getting page source: {e}")
            return None

    def navigate(self, url):
        """Navigate to a URL"""
        try:
            print(f"\nNavigating to: {url}")
            self.driver.get(url)
            return True
        except Exception as e:
            print(f"✗ Error navigating to {url}: {e}")
            return False

    def find_element(self, by, value, timeout=10):
        """Find an element on the page"""
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
            return element
        except TimeoutException:
            print(f"✗ Element not found: {by}={value}")
            return None
        except Exception as e:
            print(f"✗ Error finding element: {e}")
            return None

    def login(self, initial_url="https://learning.london.edu"):
        """
        Perform the complete login flow using Selenium

        Args:
            initial_url: The initial login URL (default: https://learning.london.edu)

        Returns:
            webdriver.Chrome: Selenium WebDriver instance with active session, or None if failed
        """
        try:

            # Setup Selenium driver
            if not self.setup_driver():
                return None

            # Wait for user to manually complete login
            print("\n[1/3] Waiting for manual authentication...")
            if not self.wait_for_manual_login(initial_url):
                print("\n✗ Login failed or timed out")
                return None

            # Extract cookies
            print("\n[2/3] Extracting session data...")
            self.extract_cookies()

            # Save session
            print("\n[3/3] Saving session...")
            self.save_session()

            print("\n" + "="*60)
            print("✓ LOGIN COMPLETE")
            print("="*60)
            print(f"  Current URL: {self.driver.current_url}")
            print(f"  Cookies saved: {len(self.cookies)}")
            print("\n  The browser will remain open for scraping.")
            print("  You can now use self.driver to interact with the page.")
            print("="*60)

            return self.driver

        except Exception as e:
            print(f"\n✗ Error during login: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

    def close(self):
        """Close the browser"""
        if self.driver:
            print("\nClosing browser...")
            self.driver.quit()
            print("✓ Browser closed")

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()


def main():
    """Main entry point"""
    print("="*60)
    print("London Business School - Learning Portal Login")
    print("="*60)

    # Create login instance using context manager
    with AzureADLogin() as login:
        # Attempt login
        driver = login.login()

        if driver:
            print("\n✓ You can now use the 'driver' object to interact with the page")
            print("\nExample - Get page source:")
            print("  page_html = login.get_page_source()")
            print("\nExample - Find an element:")
            print("  element = login.find_element(By.ID, 'some-id')")
            print("\nExample - Navigate to another page:")
            print("  login.navigate('https://learning.london.edu/courses')")

            # Keep the browser open for manual inspection/debugging
            input("\n\nPress Enter to close the browser and exit...")

            return driver
        else:
            print("\n✗ Login failed")
            sys.exit(1)


if __name__ == '__main__':
    main()
