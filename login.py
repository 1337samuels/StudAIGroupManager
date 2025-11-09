#!/usr/bin/env python3
"""
Microsoft Azure AD Login Script
Logs into the platform using HTTP requests without Selenium.
"""

import requests
from bs4 import BeautifulSoup
import json
import re
from urllib.parse import urlparse, parse_qs
import sys


class AzureADLogin:
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })

    def extract_form_data(self, html_content, form_id=None):
        """Extract all hidden input fields from the form"""
        soup = BeautifulSoup(html_content, 'html.parser')

        if form_id:
            form = soup.find('form', {'id': form_id})
        else:
            form = soup.find('form')

        if not form:
            return None, None

        form_data = {}

        # Extract all input fields
        for input_field in form.find_all('input'):
            name = input_field.get('name')
            value = input_field.get('value', '')
            if name:
                form_data[name] = value

        # Get form action URL
        action_url = form.get('action')

        return form_data, action_url

    def extract_config_from_script(self, html_content):
        """Extract configuration data from JavaScript in the page"""
        soup = BeautifulSoup(html_content, 'html.parser')
        config = {}

        # Try to find the $Config object
        scripts = soup.find_all('script')
        for script in scripts:
            if script.string and '$Config' in script.string:
                # Extract JSON-like config
                match = re.search(r'\$Config\s*=\s*({.*?});', script.string, re.DOTALL)
                if match:
                    try:
                        config = json.loads(match.group(1))
                    except:
                        pass

        return config

    def login(self, initial_url=None):
        """
        Perform the complete login flow

        Args:
            initial_url: The initial login URL. If None, uses the one from the HTML file.

        Returns:
            requests.Session: Authenticated session object
        """
        try:
            # Step 1: Get the initial login page
            print("[1/4] Getting initial login page...")

            if initial_url:
                response = self.session.get(initial_url, allow_redirects=True)
            else:
                # Read from the HTML file to get the initial URL
                with open('Sign in to your account.html', 'r', encoding='utf-8') as f:
                    html_content = f.read()
                soup = BeautifulSoup(html_content, 'html.parser')
                form = soup.find('form', {'id': 'i0281'})
                if form:
                    initial_url = form.get('action')
                    response = self.session.get(initial_url, allow_redirects=True)
                else:
                    print("Error: Could not find login form in HTML file")
                    return None

            if response.status_code != 200:
                print(f"Error: Failed to get login page (status {response.status_code})")
                return None

            # Step 2: Submit username
            print("[2/4] Submitting username...")
            form_data, action_url = self.extract_form_data(response.text, 'i0281')

            if not form_data:
                print("Error: Could not extract form data")
                return None

            # Add username
            form_data['loginfmt'] = self.username
            form_data['login'] = self.username

            # Post username
            if not action_url.startswith('http'):
                # Relative URL, build absolute
                parsed = urlparse(response.url)
                action_url = f"{parsed.scheme}://{parsed.netloc}{action_url}"

            response = self.session.post(action_url, data=form_data, allow_redirects=True)

            if response.status_code != 200:
                print(f"Error: Username submission failed (status {response.status_code})")
                return None

            # Check if we need to enter password
            if 'passwd' in response.text or 'password' in response.text.lower():
                # Step 3: Submit password
                print("[3/4] Submitting password...")
                form_data, action_url = self.extract_form_data(response.text, 'i0281')

                if not form_data:
                    print("Error: Could not extract password form data")
                    return None

                # Add password
                form_data['passwd'] = self.password

                # Post password
                if not action_url.startswith('http'):
                    parsed = urlparse(response.url)
                    action_url = f"{parsed.scheme}://{parsed.netloc}{action_url}"

                response = self.session.post(action_url, data=form_data, allow_redirects=True)

                if response.status_code != 200:
                    print(f"Error: Password submission failed (status {response.status_code})")
                    return None

            # Step 4: Handle "Stay signed in?" prompt if present
            print("[4/4] Completing login flow...")
            if 'Stay signed in' in response.text or 'KmsiInterrupt' in response.text:
                form_data, action_url = self.extract_form_data(response.text)

                if form_data and action_url:
                    # Choose to stay signed in
                    form_data['DontShowAgain'] = 'true'

                    if not action_url.startswith('http'):
                        parsed = urlparse(response.url)
                        action_url = f"{parsed.scheme}://{parsed.netloc}{action_url}"

                    response = self.session.post(action_url, data=form_data, allow_redirects=True)

            # Check for successful login
            if 'sign out' in response.text.lower() or 'logout' in response.text.lower():
                print("✓ Login successful!")
                print(f"  Final URL: {response.url}")
                print(f"  Cookies: {len(self.session.cookies)} cookie(s) stored")
                return self.session
            else:
                # Check for error messages
                if 'error' in response.text.lower():
                    soup = BeautifulSoup(response.text, 'html.parser')
                    error_div = soup.find('div', {'id': 'errorText'})
                    if error_div:
                        print(f"✗ Login failed: {error_div.get_text(strip=True)}")
                    else:
                        print("✗ Login failed: Unknown error")
                else:
                    print("✓ Login appears successful (verification ambiguous)")
                    print(f"  Final URL: {response.url}")
                    print(f"  Cookies: {len(self.session.cookies)} cookie(s) stored")
                    return self.session

        except Exception as e:
            print(f"Error during login: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

    def save_session(self, filename='session.json'):
        """Save session cookies to a file"""
        cookies = {}
        for cookie in self.session.cookies:
            cookies[cookie.name] = {
                'value': cookie.value,
                'domain': cookie.domain,
                'path': cookie.path
            }

        with open(filename, 'w') as f:
            json.dump(cookies, f, indent=2)

        print(f"Session saved to {filename}")

    def load_session(self, filename='session.json'):
        """Load session cookies from a file"""
        try:
            with open(filename, 'r') as f:
                cookies = json.load(f)

            for name, cookie_data in cookies.items():
                self.session.cookies.set(
                    name=name,
                    value=cookie_data['value'],
                    domain=cookie_data.get('domain'),
                    path=cookie_data.get('path', '/')
                )

            print(f"Session loaded from {filename}")
            return True
        except FileNotFoundError:
            print(f"Session file {filename} not found")
            return False
        except Exception as e:
            print(f"Error loading session: {str(e)}")
            return False


def main():
    """Main entry point"""
    # Load credentials from config file
    try:
        with open('credentials.json', 'r') as f:
            creds = json.load(f)
            username = creds.get('username')
            password = creds.get('password')
            initial_url = creds.get('initial_url')
    except FileNotFoundError:
        print("Error: credentials.json not found")
        print("Please create a credentials.json file with your login details:")
        print('''{
  "username": "your.email@domain.com",
  "password": "your_password",
  "initial_url": "https://login.microsoftonline.com/..."
}''')
        sys.exit(1)

    if not username or not password:
        print("Error: username and password must be provided in credentials.json")
        sys.exit(1)

    # Create login instance
    login = AzureADLogin(username, password)

    # Attempt login
    session = login.login(initial_url)

    if session:
        # Save session for reuse
        login.save_session()

        print("\n✓ You can now use the 'session' object to make authenticated requests")
        print("Example:")
        print("  response = session.get('https://your-platform-url.com/dashboard')")

        return session
    else:
        print("\n✗ Login failed")
        sys.exit(1)


if __name__ == '__main__':
    main()
