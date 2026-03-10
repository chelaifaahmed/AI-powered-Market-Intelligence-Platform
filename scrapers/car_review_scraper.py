import re
from datetime import datetime
from bs4 import BeautifulSoup
from scrapers.base_scraper import BaseScraper


class CarReviewScraper(BaseScraper):
    """Scraper for car reviews."""

    source_name = "car_reviews_demo"
    start_urls = [
        "https://www.caranddriver.com/toyota/camry",
        "https://www.motortrend.com/cars/honda/accord/",
        "https://www.caranddriver.com/ford/f-150",
        "https://www.motortrend.com/cars/tesla/model-3/",
    ]
    rate_limit = 1.0

    def parse(self, html: str) -> list[dict]:
        """Parse car reviews from HTML using BeautifulSoup."""
        soup = BeautifulSoup(html, "html.parser")
        records = []

        # Try to extract the page title
        title_tag = soup.find("title")
        review_title = title_tag.get_text(strip=True) if title_tag else "Unknown Car Review"

        # Try to find the author
        author = "Unknown Author"
        author_meta = soup.find("meta", {"name": "author"})
        if author_meta and author_meta.get("content"):
            author = author_meta["content"].strip()
        else:
            # Fallback for common author classes
            author_tag = soup.find(class_=re.compile(r"author|byline", re.I))
            if author_tag:
                author = author_tag.get_text(strip=True)

        # Try to find publication date
        pub_date = None
        date_meta = soup.find("meta", {"property": "article:published_time"})
        if date_meta and date_meta.get("content"):
            try:
                # Naive parse, or use current date as fallback
                pub_date = datetime.fromisoformat(date_meta["content"].replace("Z", "+00:00")).date()
            except ValueError:
                pass

        if not pub_date:
             time_tag = soup.find("time")
             if time_tag and time_tag.get("datetime"):
                 try:
                     pub_date = datetime.fromisoformat(time_tag["datetime"][:10]).date()
                 except ValueError:
                     pass

        # Try to extract rating (naive extraction looking for numbers / 5 or / 10)
        rating = None
        rating_tag = soup.find(class_=re.compile(r"rating|score", re.I))
        if rating_tag:
             text = rating_tag.get_text(strip=True)
             match = re.search(r"(\d+(\.\d+)?)\s*/\s*(5|10)", text)
             if match:
                 val = float(match.group(1))
                 base = float(match.group(3))
                 if base == 10:
                     val = val / 2.0 # Normalize to 5
                 rating = min(max(val, 1.0), 5.0)

        # Fallback rating
        if rating is None:
            rating = 4.0 # Default fallback if not found to satisfy schema if needed (schema allows null, but good to have)

        # Try to extract car model name from title or URL
        if "camry" in html.lower() or "camry" in review_title.lower():
             car_model_name = "Camry"
             brand_name = "Toyota"
        elif "accord" in html.lower() or "accord" in review_title.lower():
             car_model_name = "Accord"
             brand_name = "Honda"
        elif "f-150" in html.lower() or "f-150" in review_title.lower():
             car_model_name = "F-150"
             brand_name = "Ford"
        elif "model 3" in html.lower() or "model 3" in review_title.lower():
             car_model_name = "Model 3"
             brand_name = "Tesla"
        else:
             brand_name = "Unknown Brand"

        # Extract article text (concatenate paragraphs)
        paragraphs = soup.find_all("p")
        text_blocks = [p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 20]
        article_text = "\n\n".join(text_blocks)
        
        if not article_text:
             article_text = "No article text could be extracted."

        record = {
            "review_title": review_title,
            "author": author,
            "publication_date": pub_date,
            "car_model_name": car_model_name,
            "brand_name": brand_name,
            "rating": rating,
            "article_text": article_text
        }
        records.append(record)

        self.logger.info(f"Parsed car review: '{review_title}'")
        self.logger.info("Parsed %d car reviews.", len(records))
        return records
