from selenium.webdriver.chrome.options import Options
import time
from selenium import webdriver
from selenium.webdriver.common.by import By

class NewsOutlet:
    def __init__(self):
        """Initializes the Selenium WebDriver with necessary options."""
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        self.driver = webdriver.Chrome(options=options)

    def search_articles(self, search_query):
        """Searches for articles on Tagesschau based on the search query."""
        search_url = f"https://www.tagesschau.de/suche#/article/1/?searchText='{search_query}'"
        print(f"Searching: {search_url}")

        self.driver.get(search_url)
        time.sleep(2)

        articles = self.driver.find_elements(By.CLASS_NAME, "teaser-right__link")
        return [article.get_attribute("href") for article in articles if article.get_attribute("href")]

    def load_articles(self, article_links):
        """Loads the full text of articles from the extracted links."""
        extracted_content = {}
        links_count = len(article_links)
        for id, link in enumerate(article_links):
            try:
                print(f"[{id+1}/{links_count}] Downloading {link}")
                self.driver.get(link)
                time.sleep(1)

                elements = self.driver.find_elements(By.CLASS_NAME, "textabsatz")
                elements += self.driver.find_elements(By.CLASS_NAME, "meldung__subhead")
                article_text = [element.text.strip() for element in elements if element.text.strip()]

                if article_text:
                    extracted_content[link] = article_text
            except Exception as e:
                print(f"Error processing {link}: {e}")

        return extracted_content

    def close(self):
        """Closes the WebDriver session."""
        self.driver.quit()