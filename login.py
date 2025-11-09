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

    def make_absolute_url(self, url, base_url):
        """Convert relative URL to absolute URL"""
        if not url:
            return url

        if url.startswith('http://') or url.startswith('https://'):
            return url

        # Relative URL - construct absolute
        parsed = urlparse(base_url)
        return f"{parsed.scheme}://{parsed.netloc}{url}"

    def extract_config_from_script(self, html_content):
        """Extract configuration data from JavaScript in the page"""
        soup = BeautifulSoup(html_content, 'html.parser')
        config = {}

        # Try to find the $Config object
        scripts = soup.find_all('script')
        for script in scripts:
            if script.string and '$Config=' in script.string:
                # Extract JSON-like config
                match = re.search(r'\$Config\s*=\s*({.*?});', script.string, re.DOTALL)
                if match:
                    try:
                        config_str = match.group(1)
                        # Handle escaped characters
                        config = json.loads(config_str)
                    except Exception as e:
                        print(f"  Warning: Could not parse $Config: {e}")
                        pass

        return config

    def build_form_data_from_config(self, config, username=None, password=None):
        """Build form data from the $Config object"""
        form_data = {}

        # Prefer using oPostParams if available (pre-filled by server)
        if 'oPostParams' in config:
            form_data = config['oPostParams'].copy()
            print(f"  Using oPostParams with {len(form_data)} fields")

            # Override username and password if provided
            if username:
                form_data['login'] = username
                form_data['loginfmt'] = username
            if password:
                form_data['passwd'] = password

            return form_data

        # Fallback: build form data manually from config fields
        # Essential fields from config
        if 'sFT' in config:
            ft_name = config.get('sFTName', 'flowToken')
            form_data[ft_name] = config['sFT']

        if 'sCtx' in config:
            form_data['ctx'] = config['sCtx']

        if 'canary' in config:
            form_data['canary'] = config['canary']
        elif 'apiCanary' in config:
            form_data['canary'] = config['apiCanary']

        if 'hpgrequestid' in config or 'sessionId' in config:
            form_data['hpgrequestid'] = config.get('hpgrequestid', config.get('sessionId', ''))

        # Additional common fields
        form_data['i13'] = '0'
        form_data['login'] = username if username else ''
        form_data['loginfmt'] = username if username else ''
        form_data['type'] = '11'
        form_data['LoginOptions'] = '3'
        form_data['lrt'] = ''
        form_data['lrtPartition'] = ''
        form_data['hisRegion'] = ''
        form_data['hisScaleUnit'] = ''
        form_data['passwd'] = password if password else ''
        form_data['ps'] = '2'
        form_data['psRNGCDefaultType'] = ''
        form_data['psRNGCEntropy'] = ''
        form_data['psRNGCSLK'] = ''
        form_data['PPSX'] = ''
        form_data['NewUser'] = '1'
        form_data['FoundMSAs'] = ''
        form_data['fspost'] = '0'
        form_data['i21'] = '0'
        form_data['CookieDisclosure'] = '0'
        form_data['IsFidoSupported'] = '1'
        form_data['isSignupPost'] = '0'
        form_data['isRecoveryAttemptPost'] = '0'
        form_data['i19'] = '1234'  # Some random number

        return form_data

    def extract_form_data(self, html_content, form_id=None):
        """Extract all hidden input fields from the form (fallback method)"""
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

            if not initial_url:
                print("Error: initial_url must be provided in credentials.json")
                return None

            response = self.session.get(initial_url, allow_redirects=True)

            if response.status_code != 200:
                print(f"Error: Failed to get login page (status {response.status_code})")
                return None

            print(f"  Loaded: {response.url}")

            # Step 2: Extract config and submit username
            print("[2/4] Submitting username...")

            config = self.extract_config_from_script(response.text)

            if not config:
                print("  Warning: Could not extract $Config, trying fallback method")
                form_data, action_url = self.extract_form_data(response.text)
                if not form_data:
                    print("Error: Could not extract form data")
                    return None
                form_data['loginfmt'] = self.username
                form_data['login'] = self.username
            else:
                print(f"  Extracted config with {len(config)} keys")
                # Build form data from config
                form_data = self.build_form_data_from_config(config, username=self.username)
                # Get action URL from config
                action_url = config.get('urlPost') or config.get('urlPostAad')
                # Make URL absolute if needed
                action_url = self.make_absolute_url(action_url, response.url)

            if not action_url:
                print("Error: Could not determine post URL")
                return None

            print(f"  Posting to: {action_url}")

            # Post username
            response = self.session.post(action_url, data=form_data, allow_redirects=True)

            if response.status_code != 200:
                print(f"Error: Username submission failed (status {response.status_code})")
                return None

            print(f"  Response URL: {response.url}")

            # Step 3: Submit password
            print("[3/4] Submitting password...")

            config = self.extract_config_from_script(response.text)

            if not config:
                print("  Warning: Could not extract $Config, trying fallback method")
                form_data, action_url = self.extract_form_data(response.text)
                if not form_data:
                    print("Error: Could not extract password form data")
                    return None
                form_data['passwd'] = self.password
            else:
                print(f"  Extracted config with {len(config)} keys")
                # Build form data from config
                form_data = self.build_form_data_from_config(config, username=self.username, password=self.password)
                # Get action URL from config
                action_url = config.get('urlPost') or config.get('urlPostAad')
                # Make URL absolute if needed
                action_url = self.make_absolute_url(action_url, response.url)

            if not action_url:
                print("Error: Could not determine post URL for password")
                return None

            print(f"  Posting to: {action_url}")

            # Post password
            response = self.session.post(action_url, data=form_data, allow_redirects=True)

            if response.status_code != 200:
                print(f"Error: Password submission failed (status {response.status_code})")
                return None

            print(f"  Response URL: {response.url}")

            # Step 4: Handle "Stay signed in?" prompt if present
            print("[4/4] Completing login flow...")

            if 'Stay signed in' in response.text or 'KmsiInterrupt' in response.text:
                print("  Handling 'Stay signed in?' prompt...")

                config = self.extract_config_from_script(response.text)

                if config:
                    form_data = self.build_form_data_from_config(config)
                    form_data['LoginOptions'] = '1'  # Don't stay signed in
                    action_url = config.get('urlPost')
                    # Make URL absolute if needed
                    action_url = self.make_absolute_url(action_url, response.url)
                else:
                    form_data, action_url = self.extract_form_data(response.text)
                    if form_data:
                        form_data['LoginOptions'] = '1'

                if form_data and action_url:
                    response = self.session.post(action_url, data=form_data, allow_redirects=True)
                    print(f"  Response URL: {response.url}")

            # Check for successful login
            final_url = response.url.lower()

            if 'learning.london.edu' in final_url or 'london.instructure.com' in final_url:
                print("✓ Login successful!")
                print(f"  Final URL: {response.url}")
                print(f"  Cookies: {len(self.session.cookies)} cookie(s) stored")
                return self.session
            elif 'sign out' in response.text.lower() or 'logout' in response.text.lower():
                print("✓ Login successful!")
                print(f"  Final URL: {response.url}")
                print(f"  Cookies: {len(self.session.cookies)} cookie(s) stored")
                return self.session
            else:
                # Check for error messages
                if 'error' in response.text.lower() or 'incorrect' in response.text.lower():
                    soup = BeautifulSoup(response.text, 'html.parser')
                    error_div = soup.find('div', {'id': 'errorText'}) or soup.find('div', {'id': 'passwordError'})
                    if error_div:
                        print(f"✗ Login failed: {error_div.get_text(strip=True)}")
                    else:
                        print("✗ Login failed: Check your credentials")
                    return None
                else:
                    print("✓ Login appears successful (verification ambiguous)")
                    print(f"  Final URL: {response.url}")
                    print(f"  Cookies: {len(self.session.cookies)} cookie(s) stored")

                    # Save response for debugging
                    with open('last_response.html', 'w', encoding='utf-8') as f:
                        f.write(response.text)
                    print(f"  Saved response to last_response.html for inspection")

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
