from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from urllib.parse import urlparse, quote_plus
from GoogleNews import GoogleNews
class GoogleSearchNews:
    """
    A class to perform Google News searches using Selenium and filter results by a whitelist of domains.
    """
    # Default whitelist domains
    whitelist = [
        'tagesschau.de',
        'sueddeutsche.de',
        'augsburger-allgemeine.de',
        'bbc.com',
        'nytimes.com'
    ]

    def __init__(self, whitelist=None, driver_path=None, headless=True):
        """
        :param whitelist: Optional list of domain substrings (e.g. ['nytimes.com', 'bbc.com']) to allow.
                          If None, uses the class default whitelist.
        :param driver_path: Optional path to the Chrome WebDriver executable. If None, assumes it's in PATH.
        :param headless: Whether to run Chrome in headless mode.
        """
        options = Options()
        if headless:
            options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")

        service = Service(driver_path) if driver_path else Service()
        self.driver = webdriver.Chrome(service=service, options=options)
        self.wait = WebDriverWait(self.driver, 10)

        self.whitelist = whitelist if whitelist is not None else type(self).whitelist

    def search_news(self, query: str):
        """
        Perform the Google News search, filter results, and return the first 5 formatted articles.

        :param query: The search query string.
        :return: List of strings, each containing the headline and snippet of an article.
        """
        encoded = quote_plus(query)
        url = f"https://www.google.com/search?q={encoded}&tbm=nws"
        print(url)

        self.driver.get(url)


        # wait for and click the consent button
        WebDriverWait(self.driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, "/html/body/div[2]/div[3]/span/div/div/div/div[3]/div[1]/button[2]"))
        ).click()

        print("done")

        app = WebDriverWait(self.driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "news-app"))
        )

        shadow = self.driver.execute_script("return arguments[0].shadowRoot", app)
        clusters = self.driver.execute_script("""
          return Array.from(
            arguments[0].querySelectorAll('div[data-news-cluster-id]')
          );
        """, shadow)

        print(f"Found {len(clusters)} news clusters")
        print("1")

        items = self.driver.find_elements(By.XPATH, "//div[@data-news-cluster-id]")

        print("2")
        print(items)
        results = []
        for item in items:
            try:
                link_el = item.find_element(By.TAG_NAME, 'a')
                print(link_el)
                href = link_el.get_attribute('href')
                print(href)
                domain = urlparse(href).netloc

                if any(allowed in domain for allowed in self.whitelist):
                    headline = item.find_element(By.TAG_NAME, 'h3').text
                    snippet_el = item.find_element(By.CSS_SELECTOR, 'div.Y3v8qd')
                    snippet = snippet_el.text if snippet_el else ''
                    results.append(f"{headline}\n{snippet}")

                if len(results) >= 5:
                    break
            except Exception:
                continue

        return results

    def close(self):
        """Closes the WebDriver session."""
        self.driver.quit()
