import time
import re
import pandas as pd
from urllib.parse import urlparse, urljoin
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

def is_valid_email(email):
    email = email.lower().strip()
    
    # 1. Regex validation for standard format
    if not re.match(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,6}$', email):
        return False
        
    # 2. Exclude typical image/extension placeholders or false positives
    exclude_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.css', '.js', '.svg', '.tiff', '.bmp', '.pdf', '.zip']
    if any(email.endswith(ext) for ext in exclude_extensions):
        return False
        
    # 3. Exclude common system, developer or designer placeholder emails/domains
    exclude_keywords = ['wix', 'example', 'sentry', 'png', 'jpg', 'jpeg', 'gif', 'webp', 'bootstrap', 'jquery', 'font', 'awesome', 'googleapis', 'schema', 'git', 'github', 'mywix', 'domain', 'email', 'temp', 'noreply', 'no-reply', 'test','user','example']
    for kw in exclude_keywords:
        if kw in email:
            return False
            
    return True

def get_emails_from_page(driver):
    page_source = driver.page_source
    potential_emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z0-9-.]+', page_source)
    valid_emails = set()
    for email in potential_emails:
        email = email.rstrip('.,-/()[]{}')
        if is_valid_email(email):
            valid_emails.add(email)
    return valid_emails

def crawl_website_for_emails(driver, base_url):
    print(f"       [+] Crawling website for emails: {base_url}")
    emails = set()
    
    try:
        driver.get(base_url)
        time.sleep(3)
        
        # 1. Scrape homepage
        emails.update(get_emails_from_page(driver))
        
        # 2. Find contact/about links
        subpage_urls = set()
        parsed_base = urlparse(base_url)
        base_domain = parsed_base.netloc
        
        links = driver.find_elements(By.TAG_NAME, "a")
        for link in links:
            try:
                href = link.get_attribute("href")
                text = link.text.lower()
                
                if not href:
                    continue
                    
                resolved_url = urljoin(base_url, href)
                parsed_resolved = urlparse(resolved_url)
                
                # Check if it's the same domain
                if parsed_resolved.netloc != base_domain:
                    continue
                    
                href_lower = href.lower()
                keywords = ['contact', 'about', 'us', 'info', 'reach']
                if any(kw in href_lower or kw in text for kw in keywords):
                    subpage_urls.add(resolved_url)
            except Exception:
                continue
                
        subpages_to_visit = list(subpage_urls)[:4]
        for sub_url in subpages_to_visit:
            if sub_url == base_url:
                continue
            try:
                print(f"           -> Checking subpage: {sub_url}")
                driver.get(sub_url)
                time.sleep(3)
                emails.update(get_emails_from_page(driver))
            except Exception as e:
                print(f"           -> Failed to check {sub_url}: {e}")
                
    except Exception as e:
        print(f"       [-] Failed to crawl website {base_url}: {e}")
        
    return list(emails)

# Setup WebDriver
print("[+] Setting up Chrome WebDriver...")
options = Options()
options.add_argument("--start-maximized")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# Google Maps search
# search_query = "Pharmacies in Mwanza, Tanzania"
search_query = input("Enter search query (e.g., 'Pharmacies in Mwanza, Tanzania'): ")
print(f"[+] Searching for: {search_query}")
google_maps_url = f"https://www.google.com/maps/search/{search_query.replace(' ', '+')}"
print(f"[+] Opening Google Maps: {google_maps_url}")
driver.get(google_maps_url)
time.sleep(5)
input("Press Enter after  changing language to english...")

# Scroll to load all listings
print("[+] Scrolling to load all listings...")
scrollable_div = driver.find_element(By.CSS_SELECTOR, 'div[role=feed]')
prev_height = 0
same_scrolls = 0

while True:
    driver.execute_script("arguments[0].scrollBy(0, 1000);", scrollable_div)
    time.sleep(2)
    new_height = driver.execute_script("return arguments[0].scrollHeight;", scrollable_div)
    if new_height == prev_height:
        same_scrolls += 1
        print(f"    -> No new scroll content. ({same_scrolls})")
        if same_scrolls >= 3:
            print("    -> All listings loaded.")
            break
    else:
        same_scrolls = 0
        prev_height = new_height
        print("    -> More results loaded.")

# Collect all business links
print("[+] Collecting business URLs...")
cards = driver.find_elements(By.CSS_SELECTOR, 'a.hfpxzc')
urls = [card.get_attribute('href') for card in cards if card.get_attribute('href')]
print(f"[+] Found {len(urls)} listings.")

# DataFrame with correct fields
columns = ['Business Name', 'Address', 'Website', 'Email', 'Mobile Number', 'Review Count', 'Rating', 'latitude', 'longitude', 'Map Link']
df = pd.DataFrame(columns=columns)

# Visit each listing
print("[+] Extracting business data...")
for idx, url in enumerate(urls, 1):
    print(f"    -> [{idx}/{len(urls)}] ")
    driver.get(url)
    time.sleep(4)

    try:
        name = driver.find_element(By.CSS_SELECTOR, '.lfPIob').text
    except NoSuchElementException:
        name = ""

    try:
        address = driver.find_element(By.XPATH,"//span[contains(@class, 'google-symbols') and contains(@class, 'PHazN')]/ancestor::div[@class='AeaXub']//div[contains(@class, 'Io6YTe')]").text
        # address = driver.find_element(By.CSS_SELECTOR, 'div[data-item-id="address"]').text
    except NoSuchElementException:
        address = ""

    try:
        # phone = driver.find_element(By.CSS_SELECTOR, 'div[data-item-id^="phone:tel"]').text
        phone = driver.find_element(By.XPATH,"//button[starts-with(@aria-label, 'Phone:')]").get_attribute('aria-label').split(': ')[1]
    except NoSuchElementException:
        phone = ""

    try:
        website = driver.find_element(By.XPATH,"//a[@data-tooltip='Open website']").get_attribute('href')
    except NoSuchElementException:
        website = ""

    try:
        rating_element = driver.find_element(By.CSS_SELECTOR, '.F7nice')
        try:
            rating = rating_element.find_element(By.CSS_SELECTOR, 'span[aria-hidden="true"]').text
        except NoSuchElementException:
            try:
                rating = rating_element.find_elements(By.XPATH, './span')[0].text.split()[0]
            except Exception:
                rating = ""
        
        try:
            reviews_text = rating_element.find_elements(By.XPATH, './span')[1].text
            reviews = reviews_text.strip('()').replace(',', '')
        except Exception:
            reviews = ""
    except NoSuchElementException:
        rating = ""
        reviews = ""

    # Extract Latitude and Longitude by right-clicking map canvas
    latitude = ""
    longitude = ""
    try:
        # Wait for map canvas to be loaded and interactive
        time.sleep(2)
        canvas = driver.find_element(By.TAG_NAME, "canvas")
        
        # Perform right click at the center of the canvas (where pin is centered)
        ActionChains(driver).context_click(canvas).perform()
        time.sleep(1.5)  # Wait for context menu to open
        
        try:
            menu = driver.find_element(By.CSS_SELECTOR, "ul[role='menu']")
            first_item = menu.find_element(By.CSS_SELECTOR, "li")
            coords_text = first_item.text.strip()
            
            if ',' in coords_text:
                parts = coords_text.split(',')
                # Validate coordinates are numeric
                float(parts[0].strip())
                float(parts[1].strip())
                latitude = parts[0].strip()
                longitude = parts[1].strip()
        except Exception:
            pass
            
        # Dismiss context menu using Escape key
        try:
            ActionChains(driver).send_keys(Keys.ESCAPE).perform()
        except Exception:
            pass
    except Exception:
        pass

    # Fallback to URL parsing if right-click was unsuccessful
    if not latitude or not longitude:
        try:
            current_url = driver.current_url
            match = re.search(r'@(-?\d+\.\d+),(-?\d+\.\d+)', current_url)
            if match:
                latitude = match.group(1)
                longitude = match.group(2)
        except Exception:
            pass

    print(f'       Business Name: {name}')
    print(f'       Rating: {rating}')
    print(f'       Review Count: {reviews}')
    print(f'       Latitude: {latitude}')
    print(f'       Longitude: {longitude}')
    print(f'       Address: {address}') 
    print(f'       Phone: {phone}')
    print(f'       Website: {website}')
    print(f'       Map Link: {url}')


    business = {
        'Business Name': name,
        'Address': address,
        'Website': website,
        'Email': "",
        'Mobile Number': phone,
        'Review Count': reviews,
        'Rating': rating,
        'latitude': latitude,
        'longitude': longitude,
        'Map Link': url
    }

    # Save real-time
    df = pd.concat([df, pd.DataFrame([business])], ignore_index=True)
    df.to_excel("mwanza_data.xlsx", index=False)
    print("       [✓] Saved.")

# Phase 2: Email Scraping from Websites
print("[+] Phase 2: Checking Excel data to crawl websites for emails...")
for index, row in df.iterrows():
    website = row['Website']
    if pd.notna(website) and website.strip():
        emails_list = crawl_website_for_emails(driver, website)
        emails_str = "; ".join(emails_list)
        df.at[index, 'Email'] = emails_str
        
        # Save real-time
        df.to_excel("mwanza_data.xlsx", index=False)
        print(f"       [✓] Scraped emails for {row['Business Name']}: {emails_list}")

driver.quit()
print("[✓] Done. Data saved to mwanza_data.xlsx")