import re
from datetime import datetime
from bs4 import BeautifulSoup
from scrapers.base_scraper import BaseScraper


class MarketNewsScraper(BaseScraper):
    """Scraper for automotive market news."""

    source_name = "market_news_demo"
    start_urls = [
        "https://www.reuters.com/business/autos-transportation/",
        "https://www.bloomberg.com/markets/sectors/consumer-discretionary/automobiles-components",
        "https://www.cnn.com/business/autos",
        "https://www.autonews.com/",
    ]
    rate_limit = 1.0

    def parse(self, html: str) -> list[dict]:
        """Parse market news articles from HTML using BeautifulSoup."""
        soup = BeautifulSoup(html, "html.parser")
        records = []

        # Extract title
        title_tag = soup.find("title")
        article_title = title_tag.get_text(strip=True) if title_tag else "Unknown Market News"

        # Try to find author
        author = "News Desk"
        author_meta = soup.find("meta", {"name": "author"})
        if author_meta and author_meta.get("content"):
            author = author_meta["content"].strip()
        else:
            author_tag = soup.find(class_=re.compile(r"author|byline", re.I))
            if author_tag:
                 author = author_tag.get_text(strip=True)

        # Try to find source
        source = "Automotive News"
        if "reuters" in html.lower() or "reuters" in article_title.lower():
             source = "Reuters"
        elif "bloomberg" in html.lower() or "bloomberg" in article_title.lower():
             source = "Bloomberg"
        elif "cnn" in html.lower() or "cnn" in article_title.lower():
             source = "CNN Business"
        elif "autonews" in html.lower() or "automotive news" in article_title.lower():
             source = "Automotive News"

        # Review date
        pub_date = None
        date_meta = soup.find("meta", {"property": "article:published_time"})
        if date_meta and date_meta.get("content"):
            try:
                pub_date = datetime.fromisoformat(date_meta["content"].replace("Z", "+00:00")).date()
            except ValueError:
                pass
        
        if not pub_date:
            pub_date = datetime.utcnow().date() # Fallback to today

        # Extract text
        paragraphs = soup.find_all("p")
        text_blocks = [p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 20]
        article_body = "\n\n".join(text_blocks)
        
        if not article_body:
             article_body = "No article text could be extracted."

        # Extract topic keywords naively
        topic_keywords = ["Automotive", "Market Trend"]
        if "ev" in html.lower() or "electric" in html.lower():
             topic_keywords.append("EV")
        if "sales" in html.lower():
             topic_keywords.append("Sales")
        if "manufacturer" in html.lower():
             topic_keywords.append("Manufacturer Announcement")

        record = {
            "article_title": article_title,
            "source": source,
            "publication_date": pub_date,
            "author": author,
            "article_body": article_body,
            "topic_keywords": topic_keywords
        }
        records.append(record)

        self.logger.info(f"Parsed market news article: '{article_title}'")
        self.logger.info("Parsed %d market news articles.", len(records))
        return records
