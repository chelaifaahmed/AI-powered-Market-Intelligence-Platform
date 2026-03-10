import re
from datetime import datetime
from bs4 import BeautifulSoup
from scrapers.base_scraper import BaseScraper


class InsuranceReviewScraper(BaseScraper):
    """Scraper for insurance company reviews."""

    source_name = "insurance_reviews_demo"
    start_urls = [
        "https://www.nerdwallet.com/reviews/insurance/geico",
        "https://www.forbes.com/advisor/car-insurance/reviews/state-farm/",
        "https://www.nerdwallet.com/reviews/insurance/progressive",
        "https://www.forbes.com/advisor/car-insurance/reviews/allstate/",
    ]
    rate_limit = 1.0

    def parse(self, html: str) -> list[dict]:
        """Parse insurance reviews from HTML using BeautifulSoup."""
        soup = BeautifulSoup(html, "html.parser")
        records = []

        # Extract title
        title_tag = soup.find("title")
        review_title = title_tag.get_text(strip=True) if title_tag else "Unknown Insurance Review"

        # Determine Company Name from URL or title
        insurance_company_name = "Unknown Company"
        if "geico" in html.lower() or "geico" in review_title.lower():
             insurance_company_name = "GEICO"
        elif "state-farm" in html.lower() or "state farm" in review_title.lower():
             insurance_company_name = "State Farm"
        elif "progressive" in html.lower() or "progressive" in review_title.lower():
             insurance_company_name = "Progressive"
        elif "allstate" in html.lower() or "allstate" in review_title.lower():
             insurance_company_name = "Allstate"

        # Try to find Reviewer Name
        reviewer_name = "Anonymous Reviewer"
        author_meta = soup.find("meta", {"name": "author"})
        if author_meta and author_meta.get("content"):
            reviewer_name = author_meta["content"].strip()
        else:
            author_tag = soup.find(class_=re.compile(r"author|reviewer", re.I))
            if author_tag:
                 reviewer_name = author_tag.get_text(strip=True)

        # Review date
        review_date = None
        date_meta = soup.find("meta", {"property": "article:published_time"})
        if date_meta and date_meta.get("content"):
            try:
                review_date = datetime.fromisoformat(date_meta["content"].replace("Z", "+00:00")).date()
            except ValueError:
                pass
        
        if not review_date:
            review_date = datetime.utcnow().date() # Fallback to today

        # Extract rating
        rating = 4.5 # Fallback
        rating_tag = soup.find(class_=re.compile(r"rating|score", re.I))
        if rating_tag:
             text = rating_tag.get_text(strip=True)
             match = re.search(r"(\d+(\.\d+)?)\s*/\s*5", text)
             if match:
                 rating = float(match.group(1))

        # Extract review text
        paragraphs = soup.find_all("p")
        text_blocks = [p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 20]
        review_text = "\n\n".join(text_blocks)
        
        if not review_text:
             review_text = "No review text could be extracted."

        record = {
            "insurance_company_name": insurance_company_name,
            "review_title": review_title,
            "rating": rating,
            "reviewer_name": reviewer_name,
            "review_text": review_text,
            "review_date": review_date
        }
        records.append(record)

        self.logger.info(f"Parsed insurance review: '{review_title}'")
        self.logger.info("Parsed %d insurance reviews.", len(records))
        return records
