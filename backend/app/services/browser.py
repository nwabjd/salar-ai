"""Web browser service — fetch pages, extract content, analyze links."""

import re
from typing import Dict, List, Any, Optional
from urllib.parse import urljoin, urlparse
import httpx
from bs4 import BeautifulSoup


class WebBrowser:
    def __init__(self):
        self._client = httpx.Client(
            timeout=20,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            },
        )

    def fetch_page(self, url: str) -> Dict[str, Any]:
        """Fetch a URL and return structured page data."""
        try:
            resp = self._client.get(url)
            content_type = resp.headers.get("content-type", "")

            if "text/html" not in content_type and "text/" not in content_type:
                return {
                    "url": url,
                    "status": resp.status_code,
                    "content_type": content_type,
                    "size": len(resp.content),
                    "error": f"Non-HTML content: {content_type}",
                }

            soup = BeautifulSoup(resp.text, "lxml")

            # Remove scripts and styles
            for tag in soup(["script", "style", "noscript", "iframe"]):
                tag.decompose()

            title = soup.title.string.strip() if soup.title and soup.title.string else ""

            # Meta description
            meta_desc = ""
            meta_tag = soup.find("meta", attrs={"name": "description"})
            if meta_tag and meta_tag.get("content"):
                meta_desc = meta_tag["content"].strip()

            # Extract text content
            text = soup.get_text(separator="\n", strip=True)
            # Collapse whitespace
            text = re.sub(r"\n{3,}", "\n\n", text)
            text = re.sub(r" {2,}", " ", text)

            # Extract links
            links = []
            for a in soup.find_all("a", href=True):
                href = a["href"]
                link_text = a.get_text(strip=True)
                if href.startswith(("http://", "https://")):
                    links.append({"url": href, "text": link_text[:100]})
                elif href.startswith("/") or href.startswith("#"):
                    links.append({"url": urljoin(url, href), "text": link_text[:100]})

            # Extract images
            images = []
            for img in soup.find_all("img", src=True):
                src = img["src"]
                alt = img.get("alt", "")
                if src.startswith(("http://", "https://")):
                    images.append({"url": src, "alt": alt[:100]})
                elif src.startswith("/"):
                    images.append({"url": urljoin(url, src), "alt": alt[:100]})

            # Extract headings
            headings = []
            for tag in soup.find_all(["h1", "h2", "h3", "h4"]):
                heading_text = tag.get_text(strip=True)
                if heading_text:
                    headings.append({"level": tag.name, "text": heading_text[:200]})

            return {
                "url": url,
                "status": resp.status_code,
                "title": title,
                "description": meta_desc,
                "text": text[:15000],  # Limit text
                "links": links[:100],
                "images": images[:50],
                "headings": headings[:30],
                "size": len(resp.content),
            }
        except Exception as e:
            return {"url": url, "error": str(e)}

    def extract_text(self, url: str) -> str:
        """Fetch a URL and return just the text content."""
        result = self.fetch_page(url)
        if "error" in result:
            return f"Error: {result['error']}"
        text = result.get("text", "")
        title = result.get("title", "")
        return f"## {title}\n\n{text[:10000]}"

    def extract_links(self, url: str) -> List[Dict[str, str]]:
        """Fetch a URL and return all links."""
        result = self.fetch_page(url)
        if "error" in result:
            return []
        return result.get("links", [])

    def get_page_info(self, url: str) -> Dict[str, Any]:
        """Get metadata about a page (title, description, headings) without full text."""
        result = self.fetch_page(url)
        if "error" in result:
            return result
        return {
            "url": result.get("url"),
            "title": result.get("title"),
            "description": result.get("description"),
            "headings": result.get("headings", []),
            "link_count": len(result.get("links", [])),
            "image_count": len(result.get("images", [])),
            "size": result.get("size"),
        }

    def read_article(self, url: str, max_chars: int = 8000) -> str:
        """Read a web article and return a clean, readable version."""
        result = self.fetch_page(url)
        if "error" in result:
            return f"Error reading {url}: {result['error']}"

        title = result.get("title", "")
        text = result.get("text", "")

        # Try to extract the main article content
        # Heuristic: find the longest paragraph block
        paragraphs = text.split("\n\n")
        if len(paragraphs) > 3:
            # Filter out very short paragraphs (likely nav/headers)
            content_paras = [p for p in paragraphs if len(p) > 50]
            if content_paras:
                text = "\n\n".join(content_paras)

        return f"# {title}\n\nSource: {url}\n\n{text[:max_chars]}"

    def search_and_read(self, query: str) -> str:
        """Search using DDGS and return top results as readable text."""
        try:
            from .searcher import Searcher
            searcher = Searcher()
            results = searcher.search(query, max_results=5)
            if not results:
                return "No search results found."

            output_parts = [f"## Search results for: {query}\n"]
            for i, r in enumerate(results, 1):
                url = r.get("href", r.get("url", ""))
                title = r.get("title", "")
                snippet = r.get("body", r.get("snippet", ""))
                output_parts.append(f"### {i}. {title}\n{snippet}\nURL: {url}\n")

            return "\n".join(output_parts)
        except Exception as e:
            return f"Search failed: {e}"

    def close(self):
        self._client.close()
