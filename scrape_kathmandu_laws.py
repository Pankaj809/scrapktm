import argparse
import csv
import hashlib
import json
import logging
import os
import random
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple
from urllib.parse import unquote, urljoin, urlparse, urlsplit, urlunsplit

import certifi
import requests
from requests import exceptions as req_exc
from bs4 import BeautifulSoup
from tqdm import tqdm


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/123.0.0.0 Safari/537.36"
)


TARGETS = [
    (
        "national_laws",
        "https://law.kathmandu.gov.np/law_types/%e0%a4%b0%e0%a4%be%e0%a4%b7%e0%a5%8d%e0%a4%9f%e0%a5%8d%e0%a4%b0%e0%a4%bf%e0%a4%af-%e0%a4%95%e0%a4%be%e0%a4%a8%e0%a5%81%e0%a4%a8/",
    ),
    (
        "provincial_laws",
        "https://law.kathmandu.gov.np/law_types/%e0%a4%aa%e0%a5%8d%e0%a4%b0%e0%a4%be%e0%a4%a6%e0%a5%87%e0%a4%b6%e0%a4%bf%e0%a4%95-%e0%a4%95%e0%a4%be%e0%a4%a8%e0%a5%81%e0%a4%a8/",
    ),
    (
        "historical_laws",
        "https://law.kathmandu.gov.np/law_types/%e0%a4%aa%e0%a5%81%e0%a4%b0%e0%a4%be%e0%a4%a8%e0%a4%be-%e0%a4%95%e0%a4%be%e0%a4%a8%e0%a5%82%e0%a4%a8/",
    ),
]

LALITPUR_TARGET = (
    "lalitpur_act_laws",
    "https://lalitpurmun.gov.np/act-law-directives",
)

BHAKTAPUR_TARGET = (
    "bhaktapur_act_laws",
    "https://bhaktapurmun.gov.np/ne/act-law-directives",
)


def now_ts() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def safe_filename(name: str, max_len: int = 180) -> str:
    name = name.strip().replace("\u200d", "").replace("\u200c", "")
    name = re.sub(r"\s+", " ", name)
    name = name.replace("/", "／")
    name = re.sub(r'[<>:"\\\\|?*]+', "_", name)
    name = name.strip(" .")
    if not name:
        return "untitled"
    if len(name) > max_len:
        h = hashlib.sha1(name.encode("utf-8")).hexdigest()[:10]
        name = name[: max_len - 11].rstrip() + "_" + h
    return name


def normalize_url(url: str) -> str:
    # Drop fragments; keep query (pagination sometimes uses it).
    parts = urlsplit(url)
    parts = parts._replace(fragment="")
    return urlunsplit(parts)


def sha1_bytes(b: bytes) -> str:
    return hashlib.sha1(b).hexdigest()


@dataclass
class FetchResult:
    url: str
    status_code: int
    content: bytes
    final_url: str


class Scraper:
    def __init__(
        self,
        base_out: Path,
        delay_s: float = 1.0,
        jitter_s: float = 0.75,
        timeout_s: float = 30.0,
        max_retries: int = 5,
        backoff_base_s: float = 1.5,
        allow_insecure_ssl: bool = True,
    ):
        self.base_out = base_out
        self.delay_s = delay_s
        self.jitter_s = jitter_s
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        self.backoff_base_s = backoff_base_s
        self.allow_insecure_ssl = allow_insecure_ssl
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"})
        # Ignore proxy-related env vars (HTTPS_PROXY, etc.) for reliability in locked-down environments.
        self.session.trust_env = False
        # Some environments lack a usable system CA bundle; force certifi's CA bundle.
        self.session.verify = certifi.where()

    def polite_sleep(self):
        time.sleep(self.delay_s + random.random() * self.jitter_s)

    def fetch(self, url: str) -> FetchResult:
        url = normalize_url(url)
        last_exc: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                self.polite_sleep()
                resp = self.session.get(
                    url,
                    timeout=self.timeout_s,
                    allow_redirects=True,
                    verify=self.session.verify,
                )
                status = resp.status_code
                if status in (429, 500, 502, 503, 504):
                    raise requests.HTTPError(f"HTTP {status} (retryable)", response=resp)
                return FetchResult(url=url, status_code=status, content=resp.content, final_url=str(resp.url))
            except req_exc.SSLError as e:
                if self.allow_insecure_ssl:
                    logging.warning("SSL verification failed for %s; retrying without verification", url)
                    try:
                        resp = self.session.get(
                            url,
                            timeout=self.timeout_s,
                            allow_redirects=True,
                            verify=False,
                        )
                        status = resp.status_code
                        if status in (429, 500, 502, 503, 504):
                            raise requests.HTTPError(f"HTTP {status} (retryable)", response=resp)
                        return FetchResult(url=url, status_code=status, content=resp.content, final_url=str(resp.url))
                    except Exception as retry_exc:
                        last_exc = retry_exc
                else:
                    last_exc = e
            except Exception as e:
                last_exc = e
            wait = (self.backoff_base_s ** (attempt - 1)) + random.random()
            logging.warning(
                "Fetch failed (%s) attempt %d/%d: %s | waiting %.2fs",
                url,
                attempt,
                self.max_retries,
                last_exc,
                wait,
            )
            time.sleep(wait)
        raise RuntimeError(f"Failed to fetch {url} after {self.max_retries} attempts: {last_exc}")

    def soup(self, url: str) -> Tuple[BeautifulSoup, str, int]:
        fr = self.fetch(url)
        try:
            html = fr.content.decode("utf-8", errors="replace")
        except Exception:
            html = fr.content.decode(errors="replace")
        return BeautifulSoup(html, "lxml"), fr.final_url, fr.status_code


def extract_listing_links(soup: BeautifulSoup, base_url: str) -> Set[str]:
    """
    Extract candidate law detail links from a category listing page.
    We do this heuristically to be robust across theme changes:
    - Prefer links that look like post/permalink pages on the same host.
    - Exclude obvious pagination, category, tag, and file links.
    """
    out: Set[str] = set()
    base_host = urlparse(base_url).netloc

    for a in soup.select("a[href]"):
        href = a.get("href") or ""
        href = href.strip()
        if not href:
            continue
        abs_url = normalize_url(urljoin(base_url, href))
        p = urlparse(abs_url)
        if p.scheme not in ("http", "https"):
            continue
        if p.netloc != base_host:
            continue
        if any(abs_url.lower().endswith(ext) for ext in (".pdf", ".doc", ".docx", ".jpg", ".png", ".zip")):
            continue
        path = p.path.rstrip("/")
        if not path:
            continue
        # Ignore category listings and navigation helpers.
        if "/law_types/" in path:
            continue
        if "/page/" in path and "/law_types/" in urlparse(base_url).path:
            # Still could be listing pagination; exclude.
            continue
        if any(seg in path for seg in ("/tag/", "/category/", "/author/", "/wp-admin", "/wp-content", "/feed")):
            continue

        # Heuristic: WordPress-like slugs tend to be longer and not root pages.
        if len(path.split("/")) >= 2:
            out.add(abs_url)

    return out


def extract_pagination_urls(soup: BeautifulSoup, base_url: str) -> Set[str]:
    urls: Set[str] = set()
    for a in soup.select("a[href]"):
        rel = " ".join(a.get("rel", []) or [])
        href = (a.get("href") or "").strip()
        if not href:
            continue
        text = (a.get_text(" ", strip=True) or "").lower()
        if "next" in rel.lower() or "prev" in rel.lower() or text in {"next", "previous", "older posts", "newer posts"}:
            urls.add(normalize_url(urljoin(base_url, href)))
        # common WP nav classes
        classes = " ".join(a.get("class", []) or [])
        if any(k in classes.lower() for k in ("page-numbers", "pagination", "nav-links", "next", "prev")):
            # keep only likely listing pages on same host
            abs_u = normalize_url(urljoin(base_url, href))
            if urlparse(abs_u).netloc == urlparse(base_url).netloc:
                if "/law_types/" in urlparse(base_url).path:
                    if "/law_types/" in urlparse(abs_u).path or "/page/" in urlparse(abs_u).path or "paged=" in abs_u:
                        urls.add(abs_u)
    return urls


def extract_pdf_links(soup: BeautifulSoup, base_url: str) -> Set[str]:
    pdfs: Set[str] = set()
    for a in soup.select("a[href]"):
        href = (a.get("href") or "").strip()
        if not href:
            continue
        abs_url = normalize_url(urljoin(base_url, href))
        if abs_url.lower().endswith(".pdf"):
            pdfs.add(abs_url)
    # Also check embedded iframes/object sources.
    for tag in soup.select("iframe[src], embed[src], object[data]"):
        attr = "src" if tag.has_attr("src") else "data"
        v = (tag.get(attr) or "").strip()
        if not v:
            continue
        abs_url = normalize_url(urljoin(base_url, v))
        if abs_url.lower().endswith(".pdf"):
            pdfs.add(abs_url)
    return pdfs


def extract_lalitpur_detail_links(soup: BeautifulSoup, base_url: str) -> Set[str]:
    base_host = urlparse(base_url).netloc
    out: Set[str] = set()
    selectors = (
        "main a[href]",
        "#content a[href]",
        ".view-content a[href]",
        ".views-row a[href]",
    )
    anchors: List = []
    for sel in selectors:
        anchors.extend(soup.select(sel))
    if not anchors:
        anchors = soup.select("a[href]")
    for a in anchors:
        href = (a.get("href") or "").strip()
        if not href:
            continue
        abs_url = normalize_url(urljoin(base_url, href))
        parsed = urlparse(abs_url)
        if parsed.scheme not in ("http", "https"):
            continue
        if parsed.netloc != base_host:
            continue
        if parsed.path.startswith("/content/") or parsed.path.startswith("/node/"):
            out.add(abs_url)
    return out


def extract_lalitpur_pagination_urls(soup: BeautifulSoup, base_url: str) -> Set[str]:
    base_host = urlparse(base_url).netloc
    urls: Set[str] = set()
    base_path = urlparse(base_url).path.rstrip("/")
    for a in soup.select("a[href]"):
        href = (a.get("href") or "").strip()
        if not href:
            continue
        abs_url = normalize_url(urljoin(base_url, href))
        parsed = urlparse(abs_url)
        if parsed.netloc != base_host:
            continue
        if "act-law-directives" not in parsed.path:
            continue
        if "page=" in abs_url or parsed.path.rstrip("/") == base_path:
            urls.add(abs_url)
    return urls


def extract_title(soup: BeautifulSoup) -> str:
    # Try common WordPress title selectors; fallback to <title>.
    for sel in ("h1.entry-title", "h1", ".entry-title", ".page-title", ".post-title"):
        el = soup.select_one(sel)
        if el:
            t = el.get_text(" ", strip=True)
            if t:
                return t
    t = (soup.title.get_text(" ", strip=True) if soup.title else "") or "untitled"
    return t


def extract_description(soup: BeautifulSoup) -> str:
    selectors = (
        ".entry-content p",
        ".post-content p",
        ".entry-summary p",
        ".entry-content",
        ".post-content",
        ".summary",
    )
    for sel in selectors:
        for el in soup.select(sel):
            text = el.get_text(" ", strip=True)
            if text:
                return text
    return ""


def extract_dates(soup: BeautifulSoup) -> List[str]:
    dates: List[str] = []
    for el in soup.select("time[datetime]"):
        dt = (el.get("datetime") or "").strip()
        if dt:
            dates.append(dt)
    for el in soup.select(".entry-date, .posted-on, .published, .updated"):
        text = el.get_text(" ", strip=True)
        if text:
            dates.append(text)
    # De-duplicate while preserving order
    seen: Set[str] = set()
    out: List[str] = []
    for d in dates:
        if d not in seen:
            seen.add(d)
            out.append(d)
    return out


def extract_categories(soup: BeautifulSoup, base_url: str) -> List[str]:
    cats: List[str] = []
    for el in soup.select("a[rel~='category'], .cat-links a, .post-categories a"):
        text = el.get_text(" ", strip=True)
        if text:
            cats.append(text)
    for el in soup.select("a[href*='/law_types/']"):
        text = el.get_text(" ", strip=True)
        if text:
            cats.append(text)
    # De-duplicate while preserving order
    seen: Set[str] = set()
    out: List[str] = []
    for c in cats:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def write_csv(path: Path, items: List[Dict]):
    if not items:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = [
        "category",
        "detail_url",
        "final_url",
        "status",
        "title",
        "description",
        "dates",
        "categories",
        "pdf_links",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for item in items:
            row = dict(item)
            row["dates"] = "|".join(item.get("dates") or [])
            row["categories"] = "|".join(item.get("categories") or [])
            row["pdf_links"] = "|".join(item.get("pdf_links") or [])
            writer.writerow(row)


def download_pdf(scraper: Scraper, pdf_url: str, out_path: Path) -> Tuple[bool, Optional[str]]:
    try:
        fr = scraper.fetch(pdf_url)
        if fr.status_code != 200:
            return False, f"HTTP {fr.status_code}"
        ensure_dir(out_path.parent)
        out_path.write_bytes(fr.content)
        return True, sha1_bytes(fr.content)
    except Exception as e:
        return False, str(e)


def pdf_filename_from_url(pdf_url: str, fallback: str) -> str:
    parsed = urlparse(pdf_url)
    raw_name = Path(parsed.path).name
    if raw_name:
        return safe_filename(unquote(raw_name))
    return safe_filename(fallback)


def crawl_category(
    scraper: Scraper,
    category_key: str,
    start_url: str,
    category_out: Path,
) -> Dict:
    ensure_dir(category_out)
    ensure_dir(category_out / "pdfs")
    ensure_dir(category_out / "pages")

    seen_listing_pages: Set[str] = set()
    listing_queue: List[str] = [normalize_url(start_url)]

    detail_urls: Set[str] = set()
    listing_pages_scraped = 0
    errors: List[Dict] = []

    # 1) Traverse listing pagination and collect detail links.
    while listing_queue:
        url = listing_queue.pop(0)
        if url in seen_listing_pages:
            continue
        seen_listing_pages.add(url)
        try:
            soup, final_url, status = scraper.soup(url)
            listing_pages_scraped += 1
            html_path = category_out / "pages" / f"listing_{listing_pages_scraped:04d}.html"
            html_path.write_text(str(soup), encoding="utf-8")
            logging.info("[%s] Listing page %d: %s (final=%s, status=%d)", category_key, listing_pages_scraped, url, final_url, status)

            new_detail = extract_listing_links(soup, final_url)
            detail_urls.update(new_detail)

            for nxt in sorted(extract_pagination_urls(soup, final_url)):
                if nxt not in seen_listing_pages:
                    listing_queue.append(nxt)
        except Exception as e:
            logging.exception("[%s] Failed listing page: %s", category_key, url)
            errors.append({"stage": "listing", "url": url, "error": str(e)})

    # 2) Visit each detail page and extract + download PDFs.
    pdf_seen: Set[str] = set()
    pdf_hash_seen: Set[str] = set()
    items: List[Dict] = []
    detail_pages_scraped = 0
    pdf_downloaded = 0
    pdf_failed = 0

    for detail_url in tqdm(sorted(detail_urls), desc=f"{category_key} details", unit="page"):
        try:
            soup, final_url, status = scraper.soup(detail_url)
            detail_pages_scraped += 1
            title = extract_title(soup)
            description = extract_description(soup)
            dates = extract_dates(soup)
            categories = extract_categories(soup, final_url)
            pdf_links = sorted(extract_pdf_links(soup, final_url))
            item = {
                "category": category_key,
                "detail_url": detail_url,
                "final_url": final_url,
                "status": status,
                "title": title,
                "description": description,
                "dates": dates,
                "categories": categories,
                "pdf_links": pdf_links,
            }
            items.append(item)
            logging.info("[%s] Detail page %d: %s | pdfs=%d | title=%s", category_key, detail_pages_scraped, final_url, len(pdf_links), title)

            safe_title = safe_filename(title)
            for idx, pdf_url in enumerate(pdf_links, start=1):
                if pdf_url in pdf_seen:
                    continue
                pdf_seen.add(pdf_url)
                pdf_name = pdf_filename_from_url(pdf_url, f"document_{idx}.pdf")
                out_pdf = category_out / "pdfs" / safe_title / f"{idx:02d}_{pdf_name}"
                ok, info = download_pdf(scraper, pdf_url, out_pdf)
                if ok:
                    if info and info in pdf_hash_seen:
                        # duplicate content; remove the just-downloaded file
                        try:
                            out_pdf.unlink(missing_ok=True)  # py3.8+? (mac likely 3.11+)
                        except TypeError:
                            if out_pdf.exists():
                                out_pdf.unlink()
                        logging.info("[%s] Duplicate PDF content removed: %s", category_key, pdf_url)
                    else:
                        if info:
                            pdf_hash_seen.add(info)
                        pdf_downloaded += 1
                        logging.info("[%s] PDF saved: %s -> %s", category_key, pdf_url, out_pdf)
                else:
                    pdf_failed += 1
                    logging.warning("[%s] PDF failed: %s | %s", category_key, pdf_url, info)
                    errors.append({"stage": "pdf", "url": pdf_url, "from_detail": final_url, "error": info})
        except Exception as e:
            logging.exception("[%s] Failed detail page: %s", category_key, detail_url)
            errors.append({"stage": "detail", "url": detail_url, "error": str(e)})

    # Write per-category manifest
    manifest = {
        "category": category_key,
        "start_url": start_url,
        "listing_pages_scraped": listing_pages_scraped,
        "detail_pages_scraped": detail_pages_scraped,
        "unique_detail_urls": len(detail_urls),
        "unique_pdf_urls": len(pdf_seen),
        "pdf_downloaded": pdf_downloaded,
        "pdf_failed": pdf_failed,
        "errors": errors,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    write_json(category_out / "manifest.json", manifest)
    (category_out / "items.jsonl").write_text(
        "\n".join(json.dumps(it, ensure_ascii=False) for it in items) + ("\n" if items else ""),
        encoding="utf-8",
    )
    write_csv(category_out / "items.csv", items)
    return manifest


def crawl_lalitpur_pdfs(scraper: Scraper, start_url: str, out_dir: Path) -> Dict:
    ensure_dir(out_dir)
    ensure_dir(out_dir / "pdfs")
    ensure_dir(out_dir / "pages")

    seen_pages: Set[str] = set()
    queue: List[str] = [normalize_url(start_url)]
    pdf_seen: Set[str] = set()
    pdf_hash_seen: Set[str] = set()
    detail_seen: Set[str] = set()
    items: List[Dict] = []
    errors: List[Dict] = []
    listing_pages_scraped = 0
    detail_pages_scraped = 0
    pdf_downloaded = 0
    pdf_failed = 0

    while queue:
        url = queue.pop(0)
        if url in seen_pages:
            continue
        seen_pages.add(url)
        try:
            soup, final_url, status = scraper.soup(url)
            listing_pages_scraped += 1
            html_path = out_dir / "pages" / f"listing_{listing_pages_scraped:04d}.html"
            html_path.write_text(str(soup), encoding="utf-8")
            logging.info("[lalitpur] Listing page %d: %s (final=%s, status=%d)", listing_pages_scraped, url, final_url, status)

            for pdf_url in sorted(extract_pdf_links(soup, final_url)):
                if pdf_url in pdf_seen:
                    continue
                pdf_seen.add(pdf_url)
                items.append({"source_page": final_url, "detail_url": None, "pdf_url": pdf_url})
                pdf_name = pdf_filename_from_url(pdf_url, "document.pdf")
                out_pdf = out_dir / "pdfs" / pdf_name
                ok, info = download_pdf(scraper, pdf_url, out_pdf)
                if ok:
                    if info and info in pdf_hash_seen:
                        try:
                            out_pdf.unlink(missing_ok=True)
                        except TypeError:
                            if out_pdf.exists():
                                out_pdf.unlink()
                        logging.info("[lalitpur] Duplicate PDF content removed: %s", pdf_url)
                    else:
                        if info:
                            pdf_hash_seen.add(info)
                        pdf_downloaded += 1
                        logging.info("[lalitpur] PDF saved: %s -> %s", pdf_url, out_pdf)
                else:
                    pdf_failed += 1
                    logging.warning("[lalitpur] PDF failed: %s | %s", pdf_url, info)
                    errors.append({"stage": "pdf", "url": pdf_url, "from_page": final_url, "error": info})

            for detail_url in sorted(extract_lalitpur_detail_links(soup, final_url)):
                if detail_url not in detail_seen:
                    detail_seen.add(detail_url)
            for nxt in sorted(extract_lalitpur_pagination_urls(soup, final_url)):
                if nxt not in seen_pages:
                    queue.append(nxt)
        except Exception as e:
            logging.exception("[lalitpur] Failed listing page: %s", url)
            errors.append({"stage": "listing", "url": url, "error": str(e)})

    for detail_url in tqdm(sorted(detail_seen), desc="lalitpur details", unit="page"):
        try:
            soup, final_url, status = scraper.soup(detail_url)
            detail_pages_scraped += 1
            for pdf_url in sorted(extract_pdf_links(soup, final_url)):
                if pdf_url in pdf_seen:
                    continue
                pdf_seen.add(pdf_url)
                items.append({"source_page": None, "detail_url": final_url, "pdf_url": pdf_url})
                pdf_name = pdf_filename_from_url(pdf_url, "document.pdf")
                out_pdf = out_dir / "pdfs" / pdf_name
                ok, info = download_pdf(scraper, pdf_url, out_pdf)
                if ok:
                    if info and info in pdf_hash_seen:
                        try:
                            out_pdf.unlink(missing_ok=True)
                        except TypeError:
                            if out_pdf.exists():
                                out_pdf.unlink()
                        logging.info("[lalitpur] Duplicate PDF content removed: %s", pdf_url)
                    else:
                        if info:
                            pdf_hash_seen.add(info)
                        pdf_downloaded += 1
                        logging.info("[lalitpur] PDF saved: %s -> %s", pdf_url, out_pdf)
                else:
                    pdf_failed += 1
                    logging.warning("[lalitpur] PDF failed: %s | %s", pdf_url, info)
                    errors.append({"stage": "pdf", "url": pdf_url, "from_detail": final_url, "error": info})
        except Exception as e:
            logging.exception("[lalitpur] Failed detail page: %s", detail_url)
            errors.append({"stage": "detail", "url": detail_url, "error": str(e)})

    manifest = {
        "category": out_dir.name,
        "start_url": start_url,
        "listing_pages_scraped": listing_pages_scraped,
        "detail_pages_scraped": detail_pages_scraped,
        "unique_pdf_urls": len(pdf_seen),
        "pdf_downloaded": pdf_downloaded,
        "pdf_failed": pdf_failed,
        "errors": errors,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    write_json(out_dir / "manifest.json", manifest)
    (out_dir / "items.jsonl").write_text(
        "\n".join(json.dumps(it, ensure_ascii=False) for it in items) + ("\n" if items else ""),
        encoding="utf-8",
    )
    return manifest


def configure_logging(out_dir: Path):
    ensure_dir(out_dir)
    log_path = out_dir / "scrape.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    logging.info("Logging to %s", log_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=f"kathmandu_laws_scrape_{now_ts()}", help="Output folder name")
    ap.add_argument("--delay", type=float, default=1.2, help="Base delay between requests (seconds)")
    ap.add_argument("--jitter", type=float, default=0.8, help="Random extra delay (seconds)")
    ap.add_argument("--timeout", type=float, default=30.0, help="HTTP timeout (seconds)")
    ap.add_argument(
        "--only-lalitpur",
        action="store_true",
        help="Scrape only Lalitpur act-law-directives PDFs",
    )
    ap.add_argument(
        "--only-bhaktapur",
        action="store_true",
        help="Scrape only Bhaktapur act-law-directives PDFs",
    )
    args = ap.parse_args()

    out_dir = Path(args.out).resolve()
    configure_logging(out_dir)

    scraper = Scraper(
        base_out=out_dir,
        delay_s=args.delay,
        jitter_s=args.jitter,
        timeout_s=args.timeout,
    )

    run_summary = {
        "output_dir": str(out_dir),
        "targets": [{"category": k, "url": u} for k, u in TARGETS]
        + [{"category": LALITPUR_TARGET[0], "url": LALITPUR_TARGET[1]}],
        "categories": {},
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }

    if not args.only_lalitpur and not args.only_bhaktapur:
        for category_key, url in TARGETS:
            cat_out = out_dir / category_key
            logging.info("=== START CATEGORY %s ===", category_key)
            manifest = crawl_category(scraper, category_key, url, cat_out)
            run_summary["categories"][category_key] = manifest
            logging.info("=== END CATEGORY %s ===", category_key)

    if not args.only_bhaktapur:
        lalitpur_key, lalitpur_url = LALITPUR_TARGET
        logging.info("=== START CATEGORY %s ===", lalitpur_key)
        lalitpur_out = out_dir / lalitpur_key
        manifest = crawl_lalitpur_pdfs(scraper, lalitpur_url, lalitpur_out)
        run_summary["categories"][lalitpur_key] = manifest
        logging.info("=== END CATEGORY %s ===", lalitpur_key)

    if not args.only_lalitpur:
        bhaktapur_key, bhaktapur_url = BHAKTAPUR_TARGET
        logging.info("=== START CATEGORY %s ===", bhaktapur_key)
        bhaktapur_out = out_dir / bhaktapur_key
        manifest = crawl_lalitpur_pdfs(scraper, bhaktapur_url, bhaktapur_out)
        run_summary["categories"][bhaktapur_key] = manifest
        logging.info("=== END CATEGORY %s ===", bhaktapur_key)

    write_json(out_dir / "run_summary.json", run_summary)
    logging.info("Done. Summary at %s", out_dir / "run_summary.json")


if __name__ == "__main__":
    main()

