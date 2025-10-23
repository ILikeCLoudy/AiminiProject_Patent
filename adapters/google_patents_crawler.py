"""Google Patents crawler for extracting patent metrics."""
from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional
from datetime import datetime

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    requests = None
    BeautifulSoup = None


class GooglePatentsCrawler:
    """Crawler for Google Patents to extract structured metrics."""

    BASE_URL = "https://patents.google.com/patent/{doc_id}"
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

    def __init__(self, timeout: int = 10, rate_limit: float = 1.5, retry_attempts: int = 3):
        """
        Initialize the crawler.

        Args:
            timeout: Request timeout in seconds
            rate_limit: Delay between requests in seconds
            retry_attempts: Number of retry attempts on failure
        """
        if requests is None or BeautifulSoup is None:
            raise ImportError("requests and beautifulsoup4 are required for crawling")

        self.timeout = timeout
        self.rate_limit = rate_limit
        self.retry_attempts = retry_attempts
        self._last_request_time = 0.0

    def _rate_limit_wait(self) -> None:
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        self._last_request_time = time.time()

    def _fetch_html(self, doc_id: str) -> Optional[str]:
        """
        Fetch HTML content from Google Patents.

        Args:
            doc_id: Patent document ID (e.g., "WO2018097365A1")

        Returns:
            HTML content or None if failed
        """
        url = self.BASE_URL.format(doc_id=doc_id)
        headers = {"User-Agent": self.USER_AGENT}

        for attempt in range(self.retry_attempts):
            try:
                self._rate_limit_wait()
                response = requests.get(url, headers=headers, timeout=self.timeout)
                response.raise_for_status()
                return response.text
            except requests.RequestException as e:
                if attempt == self.retry_attempts - 1:
                    return None
                time.sleep(2 ** attempt)  # Exponential backoff

        return None

    def _extract_citations(self, soup: BeautifulSoup) -> int:
        """Extract forward citations count."""
        # Look for "Cited by" section
        cited_by_section = soup.find("section", {"id": "cited-by"})
        if not cited_by_section:
            return 0

        # Find the count in the heading
        heading = cited_by_section.find("h2")
        if heading:
            match = re.search(r"Cited by (\d+)", heading.get_text())
            if match:
                return int(match.group(1))

        # Fallback: count citation items
        citation_items = cited_by_section.find_all("article")
        return len(citation_items)

    def _extract_family_size(self, soup: BeautifulSoup) -> int:
        """Extract patent family size."""
        # Look for "Patent family" or "Similar documents" section
        family_section = soup.find("section", {"id": "family"})
        if not family_section:
            # Try alternative selectors
            family_section = soup.find("div", {"class": "family"})

        if family_section:
            family_items = family_section.find_all("article")
            return len(family_items) if family_items else 1

        return 1  # At least the patent itself

    def _extract_countries(self, soup: BeautifulSoup) -> List[str]:
        """Extract countries from patent family."""
        countries = set()

        # Look for patent family members
        family_section = soup.find("section", {"id": "family"})
        if family_section:
            # Extract country codes from patent numbers
            family_items = family_section.find_all("article")
            for item in family_items:
                patent_num = item.get_text()
                # Extract country code (first 2 letters before numbers)
                match = re.match(r"([A-Z]{2})", patent_num)
                if match:
                    countries.add(match.group(1))

        # Fallback: extract from main patent number
        if not countries:
            title = soup.find("meta", {"name": "citation_patent_number"})
            if title:
                patent_num = title.get("content", "")
                match = re.match(r"([A-Z]{2})", patent_num)
                if match:
                    countries.add(match.group(1))

        return sorted(list(countries))

    def _extract_legal_status(self, soup: BeautifulSoup) -> str:
        """Extract legal status."""
        # Look for legal events section
        legal_section = soup.find("section", {"id": "legal-events"})
        if not legal_section:
            return "unknown"

        # Check for "active", "granted", "pending", "expired" keywords
        text = legal_section.get_text().lower()
        if "granted" in text or "active" in text:
            return "active"
        elif "expired" in text or "lapsed" in text:
            return "expired"
        elif "pending" in text:
            return "pending"
        elif "abandoned" in text or "withdrawn" in text:
            return "abandoned"

        return "unknown"

    def _extract_publication_date(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract publication date."""
        # Try meta tag first
        date_meta = soup.find("meta", {"name": "citation_publication_date"})
        if date_meta:
            date_str = date_meta.get("content", "")
            # Parse date (format: YYYY/MM/DD or YYYY-MM-DD)
            try:
                if "/" in date_str:
                    dt = datetime.strptime(date_str, "%Y/%m/%d")
                else:
                    dt = datetime.strptime(date_str, "%Y-%m-%d")
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                pass

        # Fallback: look in document details
        details = soup.find("dd", {"itemprop": "publicationDate"})
        if details:
            return details.get_text().strip()

        return None

    def crawl(self, doc_id: str, exec_meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Crawl Google Patents and extract metrics.

        Args:
            doc_id: Patent document ID
            exec_meta: Execution metadata for logging

        Returns:
            Dictionary with extracted metrics
        """
        html = self._fetch_html(doc_id)
        if not html:
            return {
                "success": False,
                "doc_id": doc_id,
                "error": "Failed to fetch patent page",
                "metrics": {},
            }

        soup = BeautifulSoup(html, "html.parser")

        # Extract metrics
        metrics = {
            "CITATIONS_TOTAL": self._extract_citations(soup),
            "FAMILY_SIZE": self._extract_family_size(soup),
            "COUNTRIES": self._extract_countries(soup),
            "LEGAL_STATUS": self._extract_legal_status(soup),
            "PUBLICATION_DATE": self._extract_publication_date(soup),
        }

        # Calculate derived metrics
        publication_date = metrics.get("PUBLICATION_DATE")
        if publication_date:
            try:
                pub_dt = datetime.strptime(publication_date, "%Y-%m-%d")
                now = datetime.now()
                age_years = max((now - pub_dt).days / 365.25, 0.0)
                metrics["AGE_YEARS"] = round(age_years, 2)
            except ValueError:
                metrics["AGE_YEARS"] = None
        else:
            metrics["AGE_YEARS"] = None

        # Calculate HHI (simple approximation based on country diversity)
        countries = metrics.get("COUNTRIES", [])
        market_span = max(len(countries), 1)
        metrics["HHI"] = round(10000.0 / market_span, 2)

        # Log to exec_meta if provided
        if exec_meta:
            api_meta = exec_meta.setdefault("api", {})
            api_meta.setdefault("crawled_patents", []).append(
                {
                    "doc_id": doc_id,
                    "timestamp": datetime.now().isoformat(),
                    "source": "google_patents",
                }
            )

        return {
            "success": True,
            "doc_id": doc_id,
            "source": "google_patents",
            "timestamp": datetime.now().isoformat(),
            "metrics": metrics,
        }


def crawl_google_patents(
    doc_id: str,
    config: Optional[Dict[str, Any]] = None,
    exec_meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Convenience function to crawl Google Patents.

    Args:
        doc_id: Patent document ID
        config: Crawler configuration
        exec_meta: Execution metadata

    Returns:
        Crawl result with metrics
    """
    config = config or {}
    crawler_cfg = config.get("crawler", {})

    timeout = crawler_cfg.get("timeout_seconds", 10)
    rate_limit = crawler_cfg.get("rate_limit_seconds", 1.5)
    retry_attempts = crawler_cfg.get("retry_attempts", 3)

    crawler = GooglePatentsCrawler(
        timeout=timeout,
        rate_limit=rate_limit,
        retry_attempts=retry_attempts,
    )

    return crawler.crawl(doc_id, exec_meta)


__all__ = ["GooglePatentsCrawler", "crawl_google_patents"]
