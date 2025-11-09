#!/usr/bin/env python3
"""
Groups Information Extractor
Uses Selenium to navigate to Groups page and extract Study Group member information.
"""

from login import AzureADLogin
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import json


def save_page_html(driver, filename):
    """Save the current page HTML to a file"""
    html = driver.page_source
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"✓ Saved page HTML to {filename}")


def navigate_to_groups(driver):
    """Navigate to the Groups page"""
    print("\nNavigating to Groups page...")

    # Try to find and click the Groups navigation link
    try:
        # Wait for page to load
        time.sleep(2)

        # Look for Groups link in navigation
        # Try different selectors
        groups_link = None

        # Try finding by href
        try:
            groups_link = driver.find_element(By.CSS_SELECTOR, 'a[href*="/groups"]')
        except:
            pass

        # Try finding by text
        if not groups_link:
            try:
                groups_link = driver.find_element(By.LINK_TEXT, 'Groups')
            except:
                pass

        # Try finding by partial text
        if not groups_link:
            try:
                groups_link = driver.find_element(By.PARTIAL_LINK_TEXT, 'Groups')
            except:
                pass

        if groups_link:
            print(f"✓ Found Groups link: {groups_link.get_attribute('href')}")
            groups_link.click()
            time.sleep(3)
            print(f"✓ Navigated to: {driver.current_url}")
            return True
        else:
            print("✗ Could not find Groups link in navigation")
            print(f"  Current URL: {driver.current_url}")

            # Direct navigation as fallback
            groups_url = "https://learning.london.edu/groups"
            print(f"\nTrying direct navigation to {groups_url}...")
            driver.get(groups_url)
            time.sleep(3)
            print(f"✓ Navigated to: {driver.current_url}")
            return True

    except Exception as e:
        print(f"✗ Error navigating to Groups: {e}")
        return False


def extract_groups_info(driver):
    """Extract information about groups from the current page"""
    print("\nExtracting groups information...")

    # Save the page for analysis
    save_page_html(driver, 'groups_page.html')

    groups = []

    try:
        # Try to find group elements
        # Canvas typically uses cards or list items for groups

        # Try finding group cards
        group_elements = driver.find_elements(By.CSS_SELECTOR, '[data-testid*="group"], .group-card, .ic-DashboardCard')

        if not group_elements:
            # Try finding links to groups
            group_elements = driver.find_elements(By.CSS_SELECTOR, 'a[href*="/groups/"]')

        print(f"Found {len(group_elements)} potential group elements")

        for elem in group_elements:
            try:
                group = {}

                # Try to get group name
                try:
                    group['name'] = elem.text.strip()
                except:
                    pass

                # Try to get group URL
                try:
                    group['url'] = elem.get_attribute('href')
                except:
                    pass

                if group and (group.get('name') or group.get('url')):
                    groups.append(group)

            except Exception as e:
                print(f"  Warning: Error extracting group info: {e}")
                continue

        return groups

    except Exception as e:
        print(f"✗ Error extracting groups: {e}")
        return groups


def get_group_members(driver, group_url):
    """Navigate to a specific group and extract member information"""
    print(f"\nNavigating to group: {group_url}")

    try:
        driver.get(group_url)
        time.sleep(3)

        # Save the group page
        group_id = group_url.split('/')[-1]
        save_page_html(driver, f'group_{group_id}_page.html')

        # Try to find the People/Members tab
        try:
            people_link = driver.find_element(By.PARTIAL_LINK_TEXT, 'People')
            people_link.click()
            time.sleep(2)
        except:
            try:
                people_link = driver.find_element(By.PARTIAL_LINK_TEXT, 'Members')
                people_link.click()
                time.sleep(2)
            except:
                print("  Note: Could not find People/Members tab, analyzing current page")

        # Save the members page
        save_page_html(driver, f'group_{group_id}_members.html')

        # Try to find member elements
        members = []

        # Try various selectors for member lists
        member_elements = driver.find_elements(By.CSS_SELECTOR, '.roster_user_name, .student, .user, [data-testid*="user"], [data-testid*="member"]')

        print(f"  Found {len(member_elements)} potential member elements")

        for elem in member_elements:
            try:
                member = {}
                member['name'] = elem.text.strip()
                members.append(member)
            except:
                continue

        return members

    except Exception as e:
        print(f"✗ Error getting group members: {e}")
        return []


def main():
    print("="*80)
    print("LBS Groups Information Extractor")
    print("="*80)

    # Use existing login instance
    with AzureADLogin() as login:
        # Login
        print("\n[1/4] Logging in...")
        driver = login.login()

        if not driver:
            print("\n✗ Login failed")
            return

        # Navigate to Groups
        print("\n[2/4] Navigating to Groups...")
        if not navigate_to_groups(driver):
            print("\n✗ Could not navigate to Groups page")
            # Continue anyway, maybe we're already there
            pass

        # Extract groups
        print("\n[3/4] Extracting groups information...")
        groups = extract_groups_info(driver)

        print(f"\nFound {len(groups)} groups:")
        for i, group in enumerate(groups, 1):
            print(f"  {i}. {group.get('name', 'Unknown')}")
            if 'url' in group:
                print(f"     URL: {group['url']}")

        # Save groups info
        with open('groups_info.json', 'w', encoding='utf-8') as f:
            json.dump(groups, f, indent=2, ensure_ascii=False)
        print("\n✓ Saved groups info to groups_info.json")

        # Try to get members for Study Group
        print("\n[4/4] Looking for Study Group members...")
        study_groups = [g for g in groups if 'study group' in g.get('name', '').lower()]

        if study_groups:
            print(f"\nFound {len(study_groups)} Study Groups:")
            for sg in study_groups:
                print(f"  - {sg.get('name')}")

                if 'url' in sg:
                    members = get_group_members(driver, sg['url'])
                    sg['members'] = members

                    print(f"\n    Members ({len(members)}):")
                    for member in members:
                        print(f"      - {member.get('name', 'Unknown')}")

            # Save study groups with members
            with open('study_groups.json', 'w', encoding='utf-8') as f:
                json.dump(study_groups, f, indent=2, ensure_ascii=False)
            print("\n✓ Saved study groups to study_groups.json")

        else:
            print("\n  No Study Groups found")
            print("  You may need to manually navigate to your Study Group")

        print("\n" + "="*80)
        print("COMPLETE")
        print("="*80)
        print("\nHTML files saved for analysis:")
        print("  - groups_page.html")
        print("  - group_*_page.html (for each group visited)")
        print("  - group_*_members.html (for each group's members page)")

        input("\n\nPress Enter to close the browser and exit...")


if __name__ == '__main__':
    main()
