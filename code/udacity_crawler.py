import argparse
import json
import logging
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("udacity_crawler")

BASE_URL = "https://www.udacity.com"

COURSE_PATH_RE = re.compile(
    r"^/(?:course|nanodegree-program)/[a-z0-9\-]+--[a-z]{2}[0-9]+"
    r"|^/course/[a-z0-9\-]+--[a-z]{2}[0-9]+"
    r"|^/course/[a-z0-9\-]+"
    r"|/(?:catalog|courses)/.*--[a-z]{2}[0-9]+"
)

SEED_LISTING_PAGES = [
    "/courses/all",
    "/catalog",
    "/school/programming-software-engineering",
    "/school/data-science",
    "/school/artificial-intelligence",
    "/school/cloud-computing",
    "/school/cybersecurity",
    "/school/business",
    "/school/autonomous-systems",
    "/school/product-management",
    "/degrees",
    "/nanodegree-programs",
]

CATALOG_API_URLS = [
    "https://www.udacity.com/api/unified_catalog/search?PageSize=500&p=1",
    "https://catalog.udacity.com/api/v1/catalog?Nanodegree=true&Course=true&FreeProgram=true&page=1&pageSize=1000",
]

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

SITEMAP_URL = "https://www.udacity.com/sitemap.xml"

def make_session(delay: float) -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": USER_AGENT,
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })
    return s


def safe_get(session: requests.Session, url: str, timeout: int = 20,
             retries: int = 3, delay: float = 2.0, as_json: bool = False):

    for attempt in range(1, retries + 1):
        try:
            resp = session.get(url, timeout=timeout, allow_redirects=True)
            if resp.status_code == 404:
                log.debug("404  %s", url)
                return None
            resp.raise_for_status()
            return resp.json() if as_json else resp.text
        except requests.exceptions.JSONDecodeError:
            log.warning("JSON decode error  %s", url)
            return None
        except requests.exceptions.HTTPError as e:
            log.warning("HTTP %s  %s  (attempt %d/%d)", e.response.status_code, url, attempt, retries)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            log.warning("%s  %s  (attempt %d/%d)", type(e).__name__, url, attempt, retries)
        if attempt < retries:
            time.sleep(2 ** attempt)
    return None


def is_course_url(url: str) -> bool:
   
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    if parsed.netloc and "udacity.com" not in parsed.netloc:
        return False
    if "/course/" not in path and "/nanodegree-program/" not in path:
        return False
    for excl in ["/enroll", "/checkout", "/login", "/signup", "/dashboard"]:
        if excl in path:
            return False
    return True


def normalise(url: str) -> str:
    
    p = urlparse(url)
    return f"https://www.udacity.com{p.path.rstrip('/')}" if not p.scheme else \
        f"{p.scheme}://{p.netloc}{p.path.rstrip('/')}"


def links_from_html(html: str, base: str = BASE_URL) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    found = []
    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        if not href or href.startswith("#") or href.startswith("mailto:"):
            continue
        full = urljoin(base, href)
        found.append(full)
    return found



def crawl_sitemap(session: requests.Session, delay: float) -> set[str]:
    found: set[str] = set()
    to_visit = [SITEMAP_URL]
    visited_sitemaps: set[str] = set()

    while to_visit:
        sm_url = to_visit.pop(0)
        if sm_url in visited_sitemaps:
            continue
        visited_sitemaps.add(sm_url)

        log.info("[sitemap] fetching %s", sm_url)
        text = safe_get(session, sm_url, delay=delay)
        if not text:
            continue

        try:
            root = ET.fromstring(text)
        except ET.ParseError:
            log.warning("[sitemap] parse error: %s", sm_url)
            continue

        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

        for sitemap_el in root.findall(".//sm:sitemap/sm:loc", ns):
            loc = sitemap_el.text.strip()
            if loc not in visited_sitemaps:
                to_visit.append(loc)

        for url_el in root.findall(".//sm:url/sm:loc", ns):
            loc = url_el.text.strip()
            if is_course_url(loc):
                found.add(normalise(loc))

        time.sleep(delay)

    log.info("[sitemap] discovered %d course URLs", len(found))
    return found


def crawl_listing_pages(session: requests.Session, delay: float,
                         extra_seeds: list[str] | None = None) -> set[str]:
    found: set[str] = set()
    queue = [urljoin(BASE_URL, p) for p in SEED_LISTING_PAGES]
    if extra_seeds:
        queue.extend(extra_seeds)

    visited: set[str] = set()
    listing_visited: set[str] = set()

    while queue:
        url = queue.pop(0)
        if url in listing_visited:
            continue
        listing_visited.add(url)

        log.info("[listing] fetching %s", url)
        html = safe_get(session, url, delay=delay)
        if not html:
            continue

        for link in links_from_html(html, base=url):
            norm = normalise(link)
            if is_course_url(norm):
                found.add(norm)
            elif any(seg in norm for seg in ["/school/", "/catalog", "/courses/all",
                                              "/degrees", "/nanodegree-programs"]):
                if norm not in listing_visited:
                    queue.append(norm)

        found.update(_extract_from_next_data(html))

        time.sleep(delay)

    log.info("[listing] discovered %d course URLs", len(found))
    return found


def _extract_from_next_data(html: str) -> set[str]:
    
    found: set[str] = set()
    soup = BeautifulSoup(html, "lxml")
    script = soup.find("script", id="__NEXT_DATA__")
    if not script or not script.string:
        return found

    try:
        data = json.loads(script.string)
    except json.JSONDecodeError:
        return found

    text = json.dumps(data)
    for match in re.finditer(
        r'(?:\"|\')(/(?:course|nanodegree-program)/[a-zA-Z0-9\-]+(?:--[a-zA-Z0-9]+)?)(?:\"|\')' ,
        text
    ):
        path = match.group(1)
        if is_course_url(path):
            found.add(normalise(urljoin(BASE_URL, path)))

    return found


def crawl_api(session: requests.Session, delay: float) -> set[str]:
   
    found: set[str] = set()

    page = 1
    while True:
        api_url = (
            f"https://www.udacity.com/api/unified_catalog/search"
            f"?PageSize=200&p={page}&Locale=en-us"
        )
        log.info("[api] page %d  %s", page, api_url)
        data = safe_get(session, api_url, as_json=True, delay=delay)
        if not data or not isinstance(data, dict):
            break

        items = (
            data.get("programs")
            or data.get("results")
            or data.get("hits")
            or data.get("data")
            or []
        )

        if not items:
            for key, val in data.items():
                if isinstance(val, list) and val:
                    items = val
                    break

        if not items:
            break

        for item in items:
            slug = item.get("slug") or item.get("key") or item.get("nd_key")
            if slug:
                url = f"{BASE_URL}/course/{slug}"
                if is_course_url(url):
                    found.add(normalise(url))

        total = data.get("total") or data.get("totalResults") or 0
        if page * 200 >= total or len(items) < 200:
            break
        page += 1
        time.sleep(delay)

    catalog_url = (
        "https://catalog.udacity.com/api/v1/catalog"
        "?Nanodegree=true&Course=true&FreeProgram=true&page=1&pageSize=1000"
    )
    log.info("[api] catalog.udacity.com  %s", catalog_url)
    data = safe_get(session, catalog_url, as_json=True, delay=delay)
    if data and isinstance(data, dict):
        for item in data.get("programs", []) + data.get("courses", []):
            slug = item.get("key") or item.get("slug")
            if slug:
                url = f"{BASE_URL}/course/{slug}"
                found.add(normalise(url))

    log.info("[api] legacy API")
    legacy_url = "https://www.udacity.com/api/degrees"
    data = safe_get(session, legacy_url, as_json=True, delay=delay)
    if data and isinstance(data, (list, dict)):
        items = data if isinstance(data, list) else data.get("degrees", [])
        for item in items:
            slug = item.get("slug") or item.get("key")
            if slug:
                url = f"{BASE_URL}/course/{slug}"
                found.add(normalise(url))

    log.info("[api] discovered %d course URLs", len(found))
    return found

def crawl_deep(session: requests.Session, delay: float,
               known_urls: set[str]) -> set[str]:

    found: set[str] = set()
    visited: set[str] = set()

    for url in list(known_urls)[:200]:
        if url in visited:
            continue
        visited.add(url)

        html = safe_get(session, url, delay=delay)
        if not html:
            continue

        for link in links_from_html(html, base=url):
            norm = normalise(link)
            if is_course_url(norm) and norm not in known_urls:
                found.add(norm)

        found.update(_extract_from_next_data(html))
        time.sleep(delay)

    log.info("[deep] discovered %d additional course URLs", len(found))
    return found


def write_xml(course_urls: set[str], output_path: str, delay: float) -> None:

    root = ET.Element("scraper_config")
    root.append(ET.Comment(" Generated by udacity_crawler.py  |  " +
                            datetime.now(timezone.utc).isoformat(timespec="seconds") + " UTC "))

    settings_el = ET.SubElement(root, "settings")
    ET.SubElement(settings_el, "delay_between_requests").text = str(delay)
    ET.SubElement(settings_el, "timeout").text = "15"
    ET.SubElement(settings_el, "max_retries").text = "3"
    ET.SubElement(settings_el, "output_format").text = "json"
    ET.SubElement(settings_el, "output_file").text = "scraped_tutorials.json"
    ET.SubElement(settings_el, "user_agent").text = USER_AGENT

    sites_el = ET.SubElement(root, "sites")

    site_el = ET.SubElement(sites_el, "site", id="udacity", type="paid")
    ET.SubElement(site_el, "name").text = "Udacity"
    ET.SubElement(site_el, "base_url").text = BASE_URL

    sections_el = ET.SubElement(site_el, "sections")
    sections_el.append(ET.Comment(f" {len(course_urls)} courses discovered by crawler "))

    for url in sorted(course_urls):
        ET.SubElement(sections_el, "url").text = url

    selectors_el = ET.SubElement(site_el, "selectors")
    ET.SubElement(selectors_el, "title").text = "h1"
    ET.SubElement(selectors_el, "content").text = ".course-card__body"
    ET.SubElement(selectors_el, "topics").text = ".course-card__title"

    _indent(root)
    tree = ET.ElementTree(root)
    ET.indent(tree, space="    ")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        tree.write(f, encoding="unicode", xml_declaration=False)

    log.info("Wrote %d URLs  -->  %s", len(course_urls), output_path)


def _indent(elem: ET.Element, level: int = 0) -> None:
    indent = "\n" + "    " * level
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = indent + "    "
        if not elem.tail or not elem.tail.strip():
            elem.tail = indent
        for child in elem:
            _indent(child, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = indent
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = indent

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Crawl Udacity and collect course links → XML config"
    )
    parser.add_argument(
        "--start-url",
        default=BASE_URL,
        help="Root URL to start from (default: https://www.udacity.com)",
    )
    parser.add_argument(
        "--output",
        default="udacity_sources.xml",
        help="Output XML file path (default: udacity_sources.xml)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.5,
        help="Seconds to wait between requests (default: 1.5)",
    )
    parser.add_argument(
        "--skip-sitemap",
        action="store_true",
        help="Skip sitemap crawling (faster but fewer results)",
    )
    parser.add_argument(
        "--skip-api",
        action="store_true",
        help="Skip API endpoint probing",
    )
    parser.add_argument(
        "--skip-deep",
        action="store_true",
        help="Skip deep crawl of already-found course pages",
    )
    args = parser.parse_args()

    session = make_session(args.delay)
    all_urls: set[str] = set()

    if not args.skip_sitemap:
        log.info("=== Strategy 1: Sitemap ===")
        all_urls.update(crawl_sitemap(session, args.delay))
        log.info("Running total: %d", len(all_urls))

    log.info("=== Strategy 2: Listing / catalog pages ===")
    extra_seeds = [args.start_url] if args.start_url != BASE_URL else None
    all_urls.update(crawl_listing_pages(session, args.delay, extra_seeds))
    log.info("Running total: %d", len(all_urls))

    if not args.skip_api:
        log.info("=== Strategy 3: Public API endpoints ===")
        all_urls.update(crawl_api(session, args.delay))
        log.info("Running total: %d", len(all_urls))

    if not args.skip_deep and all_urls:
        log.info("=== Strategy 4: Deep crawl of discovered pages ===")
        all_urls.update(crawl_deep(session, args.delay, set(all_urls)))
        log.info("Running total: %d", len(all_urls))

    if not all_urls:
        log.warning("No course URLs found — check your network or try --skip-sitemap.")
    else:
        log.info("=== Writing XML ===")
        write_xml(all_urls, args.output, args.delay)

    log.info("Done. Total unique course URLs: %d", len(all_urls))


if __name__ == "__main__":
    main()
