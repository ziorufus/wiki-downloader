import requests
import json
import time
import argparse
import logging
import random
import pandas as pd
import os

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By

from selenium_stealth import stealth

# Define the base URL
BASE_URL = "https://%LANG%.vikidia.org/w/api.php?format=json&action=query&prop=revisions&rvlimit=100&rvprop=ids&pageids="

# Set up logging
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,  # Change to DEBUG for more details
    datefmt="%Y-%m-%d %H:%M:%S"
)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

# Headers to make the request look like it's coming from a real browser
HEADERS = {
    "User-Agent": random.choice(USER_AGENTS),
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.google.com/",
    "Connection": "keep-alive"
}

def addStealth(driver):
    stealth(driver,
            languages=["it_IT", "it-IT", "it"],
            vendor="Google Inc.",
            platform="Win32",
            webgl_vendor="Intel Inc.",
            renderer="Intel Iris OpenGL Engine",
            fix_hairline=True,
            )

def fetch_page_data(url, start_page, end_page, max_retries, output_folder, driver):
    # Storage for extracted data
    collected_data = []
    os.makedirs(output_folder, exist_ok=True)
    logging.info(f"Starting scraping from Page {start_page} to {end_page}, max retries: {max_retries}")

    for pageID in range(start_page, end_page):
        url = f"{url}{pageID}"
        time.sleep(1)

        retries = 0

        while retries < max_retries:
            try:
                driver.get(url)

                pre = driver.find_elements(By.CSS_SELECTOR, "pre")

                try:
                    if len(pre):
                        json_data = json.loads(pre[0].get_attribute("innerHTML"))
                    else:
                        json.data = json.loads(driver.page_source)
                except:
                    logging.info("Error in parsing JSON, skipping.")
                    continue

                json_data = json.loads(pre[0].get_attribute("innerHTML"))

                pages = json_data.get("query", {}).get("pages", {})

                if str(pageID) in pages:
                    page_data = pages[str(pageID)]

                    # Check if the page is missing
                    if "missing" not in page_data:
                        title = page_data.get("title", "").replace("/", "_")  # Prevent invalid filename
                        collected_data.append({
                            "pageID": pageID,
                            "title": title,
                            "revisions_count": len(page_data.get("revisions", []))
                        })
                        logging.info(
                            f"Successfully scraped Page ID {pageID}: {page_data.get('title', 'Unknown Title')}")

                        # Save raw page content
                        save_page_content(title, pageID, output_folder, driver)
                    else:
                        collected_data.append({
                            "pageID": pageID,
                            "title": "",
                            "revisions_count": 0
                        })
                        logging.info(f"Page ID {pageID} is missing, skipping.")

                break  # Exit retry loop if request is successful

            except requests.exceptions.RequestException as e:
                retries += 1
                logging.error(f"Error fetching page {pageID} (Attempt {retries}/{max_retries}): {e}")
                if retries < max_retries:
                    time.sleep(2)  # Wait 2 seconds before retrying
                else:
                    logging.error(f"Skipping Page ID {pageID} after {max_retries} failed attempts.")

    logging.info(f"Scraping completed. Total pages collected: {len(collected_data)}")
    return collected_data


def save_page_content(title, pageID, output_folder, driver):
    """
    Fetches and saves the raw text content of a given page title.
    """
    raw_url = f"https://it.vikidia.org/w/index.php?title={title}&action=raw"

    try:
        driver.get(raw_url)
        content = driver.page_source
        pre = driver.find_elements(By.CSS_SELECTOR, "pre")
        if len(pre):
            content = pre[0].get_attribute("innerHTML")

        # Determine folder based on integer division of pageID by 1000
        subfolder = os.path.join(output_folder, str(pageID // 1000))
        os.makedirs(subfolder, exist_ok=True)  # Ensure subfolder exists

        file_path = os.path.join(subfolder, f"{pageID}.txt")

        with open(file_path, "w", encoding="utf-8") as file:
            file.write(content)

        logging.info(f"Saved raw content for Page ID {pageID} in {file_path}")

    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to fetch raw content for {title}: {e}")


def save_to_csv(data, filename="output.csv"):
    """Save the collected data to a CSV file."""
    if not data:
        logging.warning("No data collected, skipping CSV save.")
        return

    df = pd.DataFrame(data)
    df.to_csv(filename, index=False)
    logging.info(f"Data successfully saved to {filename}")


if __name__ == "__main__":
    # Argument parser
    parser = argparse.ArgumentParser(description="Scrape a website for page data using incremental page IDs.")
    parser.add_argument("START_PAGE_ID", type=int, help="The starting page ID.")
    parser.add_argument("END_PAGE_ID", type=int, help="The ending page ID.")
    parser.add_argument("--lang", default="it", help="Language (default: it).")
    parser.add_argument("--max_retries", type=int, default=5, help="Maximum retry attempts per page (default: 5).")
    parser.add_argument("--output", type=str, default="output.csv", help="Output CSV file name (default: output.csv)")
    parser.add_argument("--output-folder", type=str, default="pages", help="Folder to store raw page content (default: 'pages')")
    parser.add_argument('-d', metavar="PATH", help="Driver path", default="/usr/bin/chromedriver")

    args = parser.parse_args()

    chrome_service = Service(executable_path=args.d)
    chromeOptions = webdriver.ChromeOptions()
    chromeOptions.add_argument("start-maximized")
    chromeOptions.add_argument("--headless")
    driver = webdriver.Chrome(service=chrome_service, options=chromeOptions)
    driver.set_page_load_timeout(30)

    addStealth(driver)

    # Run the scraper with user-defined parameters
    url = BASE_URL.replace("%LANG%", args.lang)
    data = fetch_page_data(url, args.START_PAGE_ID, args.END_PAGE_ID, args.max_retries, args.output_folder, driver)

    # Save the data to a CSV file
    save_to_csv(data, args.output)
