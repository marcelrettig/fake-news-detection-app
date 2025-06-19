from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from urllib.parse import urlparse, quote_plus
import time
import urllib.parse
from GoogleNews import GoogleNews
class GoogleSearchNews:
    """
    A class to perform Google News searches using Selenium and filter results by a whitelist of domains.
    """
    # Default whitelist domains


    def __init__(self, whitelist=None, driver_path=None, headless=True):
        """
        :param whitelist: Optional list of domain substrings (e.g. ['nytimes.com', 'bbc.com']) to allow.
                          If None, uses the class default whitelist.
        :param driver_path: Optional path to the Chrome WebDriver executable. If None, assumes it's in PATH.
        :param headless: Whether to run Chrome in headless mode.
        """
        options = Options()

        service = Service(driver_path) if driver_path else Service()
        self.driver = webdriver.Chrome(service=service, options=options)
        self.wait = WebDriverWait(self.driver, 10)

        #self.whitelist = whitelist if whitelist is not None else type(self).whitelist

    def search_news(self, query: str) -> list[str]:

        whitelist = [
            'tagesschau.de',
            'sueddeutsche.de',
            'augsburger-allgemeine.de',
            'bbc.com',
            'nytimes.com',
            "The New York Times",
            "BBC News"
        ]

        timeout: int = 10

        encoded = quote_plus(query)
        url = f"https://www.google.com/search?q={encoded}&tbm=nws"
        print(url)

        self.driver.get(url)

        cookies = self.driver.find_elements(By.XPATH, '//button[normalize-space()="Alle akzeptieren"]')
        cookies[0].click()
        print("done")

        # --- Wait until results are present ---
        wait = WebDriverWait(self.driver, timeout)
        articles = wait.until(EC.presence_of_all_elements_located(
            (By.CSS_SELECTOR, "div.dbsr")
        ))

        results: list[str] = []
        for art in articles:
            try:
                # Extract the publisher/source name
                source = art.find_element(
                    By.CLASS_NAME, "SoaBEf"
                ).text.strip()

                # If it matches our whitelist, grab the link
                if source in whitelist:
                    href = art.find_element(By.TAG_NAME, "a").get_attribute("href")
                    results.append(href)
            except Exception:
                # skip if any element not found or parsing error
                continue

        return results


    def close(self):
        """Closes the WebDriver session."""
        self.driver.quit()
