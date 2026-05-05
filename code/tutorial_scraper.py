import xml.etree.ElementTree as ET
import requests
from bs4 import BeautifulSoup
import json, csv, time, re, argparse, logging
from datetime import datetime, timezone
from pathlib import Path

XML_CONFIG_PATH = r"D:\Microsoft VS Code\udacity_sources.xml"

OUTPUT_DIR = r"C:\Users\ERRoR404\Downloads\output"  

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("scraper")

def _udacity_get_json(soup):
    
    course_ld   = None
    page_props  = None

    for script in soup.find_all("script"):
        txt = (script.string or "").strip()
        if not txt:
            continue

        if script.get("type") == "application/ld+json" and '"@type":"Course"' in txt:
            try:
                data = json.loads(txt)
                graph = data.get("@graph", [])
                course_ld = next((x for x in graph if x.get("@type") == "Course"), None)
            except Exception:
                pass

        if script.get("id") == "__NEXT_DATA__" or (
            txt.startswith("{") and '"pageProps"' in txt and '"staticProgramDetailsSectionProps"' in txt
        ):
            try:
                data = json.loads(txt)
                page_props = data["props"]["pageProps"]
            except Exception:
                pass

    return course_ld, page_props


def build_udacity_record(soup, url):
    course, pp = _udacity_get_json(soup)

    if course is None and pp is None:
        return build_generic_record(soup, url)

    details  = (pp or {}).get("staticProgramDetailsSectionProps")  or {}
    outline  = (pp or {}).get("staticProgramOutlineSectionProps")  or {}
    inst_sec = (pp or {}).get("staticProgramInstructorsSectionProps") or {}
    reviews  = (pp or {}).get("staticReviewsSectionProps")         or {}
    about    = (pp or {}).get("staticProgramAboutSectionProps")    or {}

    title = (
        details.get("title")
        or (course or {}).get("name")
        or _generic_title(soup)
    )

    description = (
        about.get("aboutText")
        or details.get("summary")
        or (course or {}).get("description")
    )

    short_desc = details.get("summary") or _generic_short_desc(soup)

    is_free_flag = (pp or {}).get("isProgramFree")
    if is_free_flag is None and course:
        is_free_flag = course.get("isAccessibleForFree")
    price = "Free" if is_free_flag else "Subscription (see site for price)"

    instructors_raw = inst_sec.get("instructors", [])
    instructor_names = [i.get("name", "") for i in instructors_raw if i.get("name")]
    instructor_bios  = [
        f"{i.get('name','')} — {i.get('jobTitle','')}"
        for i in instructors_raw if i.get("name")
    ]
    if not instructor_names and course:
        for inst in (course.get("hasCourseInstance") or [{}])[0].get("instructor", []):
            instructor_names.append(inst.get("name", ""))

    agg = (course or {}).get("aggregateRating", {})
    rating        = agg.get("ratingValue") or details.get("reviewStarsAverage")
    reviews_count = agg.get("ratingCount")  or details.get("reviewCount")

    raw_reviews = reviews.get("initReviews", []) or (course or {}).get("review", [])
    comments = []
    for r in raw_reviews[:5]:
        body = r.get("reviewBody") or r.get("content", "")
        author = (r.get("author") or {}).get("name") or (r.get("consumer") or {}).get("name", "")
        if body:
            comments.append(f"{author}: {body}" if author else body)

    duration = details.get("duration") or _parse_iso_duration(
        (course or {}).get("hasCourseInstance", [{}])[0].get("courseWorkload", "")
    )

    level = (
        details.get("difficulty")
        or (pp or {}).get("difficultyLevel")
        or (course or {}).get("educationalLevel")
    )

    language = (course or {}).get("inLanguage") or _generic_language(soup)

    breadcrumbs = (pp or {}).get("staticBreadcrumbsProps", {})
    category = breadcrumbs.get("schoolName") or _generic_category(soup)

    tags = details.get("allSkills") or (course or {}).get("about") or []

    prereqs_raw = details.get("prerequisites") or (course or {}).get("coursePrerequisites") or []
    if prereqs_raw and isinstance(prereqs_raw[0], dict):
        prerequisites = [p.get("label", "") for p in prereqs_raw]
    else:
        prerequisites = prereqs_raw

    learning_outcomes = tags[:] if tags else None

    parts = outline.get("parts", [])
    content_outline = [p.get("title", "").strip() for p in parts if p.get("title")]

    summary       = outline.get("summary", {})
    modules_count = summary.get("courses") or len(parts) or None
    lessons_count = summary.get("lessons") or None

    cred = (course or {}).get("educationalCredentialAwarded", {})
    certificate = bool(cred.get("credentialCategory"))  if cred else None

    enrolments = details.get("enrolledCount")

    last_updated   = details.get("updatedAt")
    published_date = None

    thumbnail = (
        (pp or {}).get("imageUrl")
        or (course or {}).get("image")
        or _generic_thumbnail(soup)
    )

    return {
        "Title"             : title,
        "Course Name"       : title,
        "Description"       : description,
        "Short Description" : short_desc,
        "Price"             : price,
        "Is Free"           : is_free_flag,
        "Instructor"        : instructor_names,
        "Instructor Bio"    : instructor_bios,
        "Rating"            : rating,
        "Reviews Count"     : reviews_count,
        "Comments"          : comments,
        "Duration"          : duration,
        "Level"             : level,
        "Language"          : language,
        "Category"          : category,
        "Tags"              : tags,
        "Prerequisites"     : prerequisites,
        "Learning Outcomes" : learning_outcomes,
        "Content Outline"   : content_outline,
        "Modules Count"     : modules_count,
        "Lessons Count"     : lessons_count,
        "Certificate"       : certificate,
        "Enrolments"        : enrolments,
        "Last Updated"      : last_updated,
        "Published Date"    : published_date,
        "Thumbnail URL"     : thumbnail,
        "URL"               : url,
        "Status"            : "ok",
        "Scraped At"        : datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00","Z"),
    }


def _parse_iso_duration(iso):
    if not iso:
        return None
    iso = iso.upper()
    parts = []
    for unit, label in [("Y","year"), ("M","month"), ("W","week"), ("D","day"),
                         ("H","hour"), ("M","minute")]:
        m = re.search(rf"(\d+){unit}", iso)
        if m:
            n = int(m.group(1))
            parts.append(f"{n} {label}{'s' if n != 1 else ''}")
    return ", ".join(parts) if parts else iso


def _generic_title(soup):
    for sel in ["h1.course-title","h1.title","h1","title"]:
        el = soup.select_one(sel)
        if el:
            return el.get_text(strip=True)
    return None

def _generic_short_desc(soup):
    for sel in ["[class*='headline']","[class*='subtitle']","meta[name='description']","p.lead"]:
        el = soup.select_one(sel)
        if el:
            val = el.get("content") or el.get_text(strip=True)
            if val and len(val) < 300:
                return val
    return None

def _generic_description(soup):
    for sel in ["[class*='course-description']","[class*='description']",
                "meta[property='og:description']","meta[name='description']"]:
        el = soup.select_one(sel)
        if el:
            val = el.get("content") or el.get_text(separator=" ", strip=True)[:2000]
            if val:
                return val
    return None

def _generic_price(soup):
    for sel in ["[class*='price']","[data-purpose='course-price-text']",
                "meta[property='product:price:amount']"]:
        el = soup.select_one(sel)
        if el:
            val = el.get("content") or el.get_text(strip=True)
            if val:
                return val
    return None

def _generic_instructor(soup):
    names = []
    for sel in ["[class*='instructor-name']","[data-purpose='instructor-name']",
                "a[href*='/instructor/']"]:
        for el in soup.select(sel)[:5]:
            t = el.get_text(strip=True)
            if t and t not in names:
                names.append(t)
    return names or None

def _generic_rating(soup):
    for sel in ["[class*='rating-number']","meta[itemprop='ratingValue']",
                "span.rating"]:
        el = soup.select_one(sel)
        if el:
            raw = el.get("content") or el.get_text(strip=True)
            m = re.search(r"[\d]+\.?[\d]*", raw)
            if m:
                return float(m.group())
    return None

def _generic_reviews_count(soup):
    for sel in ["[class*='reviews-count']","[class*='rating-count']",
                "meta[itemprop='reviewCount']"]:
        el = soup.select_one(sel)
        if el:
            raw = el.get("content") or el.get_text(strip=True)
            m = re.search(r"[\d,]+", raw)
            if m:
                return int(m.group().replace(",",""))
    return None

def _generic_duration(soup):
    for sel in ["[class*='duration']","[data-purpose='video-content-length']",
                "meta[itemprop='duration']"]:
        el = soup.select_one(sel)
        if el:
            return (el.get("content") or el.get_text(strip=True)).strip()
    return None

def _generic_level(soup):
    for sel in ["[class*='course-level']","[class*='level']","[data-purpose='skill-level']"]:
        el = soup.select_one(sel)
        if el:
            t = el.get_text(strip=True)
            if t:
                return t
    for kw in ["Beginner","Intermediate","Advanced","All Levels","Expert"]:
        if kw.lower() in soup.get_text(" ").lower():
            return kw
    return None

def _generic_language(soup):
    el = soup.select_one("html")
    if el and el.get("lang"):
        return el["lang"]
    el = soup.select_one("meta[http-equiv='content-language']")
    if el:
        return el.get("content","").strip()
    return None

def _generic_category(soup):
    for sel in ["a[href*='/category/']","a[href*='/topic/']",
                "nav[aria-label*='breadcrumb'] a",".breadcrumb a"]:
        for el in soup.select(sel)[:3]:
            t = el.get_text(strip=True)
            if t and len(t) < 60:
                return t
    return None

def _generic_tags(soup):
    meta = soup.select_one("meta[name='keywords']")
    if meta and meta.get("content"):
        return [t.strip() for t in meta["content"].split(",") if t.strip()]
    tags = []
    for sel in ["[class*='tag']","[class*='skill']"]:
        for el in soup.select(sel)[:10]:
            t = el.get_text(strip=True)
            if t and len(t) < 50 and t not in tags:
                tags.append(t)
    return tags or None

def _generic_prerequisites(soup):
    items = []
    for sel in ["[class*='prerequisite']","[class*='requirement']","#requirements li"]:
        for el in soup.select(sel)[:10]:
            t = el.get_text(strip=True)
            if t and t not in items:
                items.append(t)
    return items or None

def _generic_outcomes(soup):
    items = []
    for sel in ["[class*='learning-outcome']","[class*='what-you-will-learn']",
                ".objectives li",".outcomes li"]:
        for el in soup.select(sel)[:20]:
            t = el.get_text(strip=True)
            if t and t not in items:
                items.append(t)
    return items or None

def _generic_outline(soup):
    items = []
    for sel in ["[class*='section-title']","[class*='chapter-title']",
                "[class*='curriculum'] h3","[class*='module-title']"]:
        for el in soup.select(sel)[:30]:
            t = el.get_text(strip=True)
            if t and t not in items:
                items.append(t)
    return items or None

def _generic_certificate(soup):
    text = soup.get_text(" ").lower()
    for phrase in ["certificate of completion","earn a certificate","get certified"]:
        if phrase in text:
            return True
    return None

def _generic_enrolments(soup):
    for sel in ["[class*='enrollment']","[class*='students-count']"]:
        el = soup.select_one(sel)
        if el:
            m = re.search(r"[\d,]+", el.get_text())
            if m:
                return int(m.group().replace(",",""))
    return None

def _generic_last_updated(soup):
    for sel in ["[class*='last-updated']","time[datetime]",
                "meta[property='article:modified_time']"]:
        el = soup.select_one(sel)
        if el:
            return el.get("datetime") or el.get("content") or el.get_text(strip=True)
    return None

def _generic_published_date(soup):
    for sel in ["time[datetime]","meta[property='article:published_time']",
                "meta[name='date']"]:
        el = soup.select_one(sel)
        if el:
            return el.get("datetime") or el.get("content") or el.get_text(strip=True)
    return None

def _generic_thumbnail(soup):
    for sel in ["meta[property='og:image']","meta[name='twitter:image']",
                "[class*='course-image'] img","[class*='thumbnail'] img"]:
        el = soup.select_one(sel)
        if el:
            return el.get("content") or el.get("src")
    return None


def build_generic_record(soup, url):
    title = _generic_title(soup)
    return {
        "Title"             : title,
        "Course Name"       : title,
        "Description"       : _generic_description(soup),
        "Short Description" : _generic_short_desc(soup),
        "Price"             : _generic_price(soup),
        "Is Free"           : None,
        "Instructor"        : _generic_instructor(soup),
        "Instructor Bio"    : None,
        "Rating"            : _generic_rating(soup),
        "Reviews Count"     : _generic_reviews_count(soup),
        "Comments"          : None,
        "Duration"          : _generic_duration(soup),
        "Level"             : _generic_level(soup),
        "Language"          : _generic_language(soup),
        "Category"          : _generic_category(soup),
        "Tags"              : _generic_tags(soup),
        "Prerequisites"     : _generic_prerequisites(soup),
        "Learning Outcomes" : _generic_outcomes(soup),
        "Content Outline"   : _generic_outline(soup),
        "Modules Count"     : None,
        "Lessons Count"     : None,
        "Certificate"       : _generic_certificate(soup),
        "Enrolments"        : _generic_enrolments(soup),
        "Last Updated"      : _generic_last_updated(soup),
        "Published Date"    : _generic_published_date(soup),
        "Thumbnail URL"     : _generic_thumbnail(soup),
        "URL"               : url,
        "Status"            : "ok",
        "Scraped At"        : datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00","Z"),
    }

SITE_BUILDERS = {
    "udacity": build_udacity_record,
}

def build_record(soup, url, site_id):
    builder = SITE_BUILDERS.get(site_id, build_generic_record)
    return builder(soup, url)

def load_config(xml_path):
    tree = ET.parse(xml_path)
    root = tree.getroot()
    s = root.find("settings")
    settings = {
        "delay":       float(s.findtext("delay_between_requests", "2")),
        "timeout":     int(s.findtext("timeout", "15")),
        "max_retries": int(s.findtext("max_retries", "3")),
        "output_fmt":  s.findtext("output_format", "json"),
        "output_file": s.findtext("output_file", "scraped_tutorials.json"),
        "user_agent":  s.findtext("user_agent", "TutorialScraper/1.0"),
    }
    sites = {}
    for site in root.findall(".//site"):
        sid = site.get("id")
        sites[sid] = {
            "id":       sid,
            "type":     site.get("type", "free"),
            "name":     site.findtext("name", sid),
            "base_url": site.findtext("base_url", ""),
            "urls":     [u.text.strip() for u in site.findall(".//url") if u.text],
        }
    return {"settings": settings, "sites": sites}

def fetch_page(url, session, timeout, retries):
    for attempt in range(1, retries + 1):
        try:
            resp = session.get(url, timeout=timeout)
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "lxml")
        except requests.exceptions.HTTPError as e:
            log.warning("HTTP %s  %s  (attempt %d/%d)", e.response.status_code, url, attempt, retries)
        except requests.exceptions.ConnectionError:
            log.warning("Connection error  %s  (attempt %d/%d)", url, attempt, retries)
        except requests.exceptions.Timeout:
            log.warning("Timeout  %s  (attempt %d/%d)", url, attempt, retries)
        if attempt < retries:
            time.sleep(2 ** attempt)
    log.error("Gave up on %s", url)
    return None

def scrape_site(site_cfg, settings):
    session = requests.Session()
    session.headers.update({
        "User-Agent": settings["user_agent"],
        "Accept-Language": "en-US,en;q=0.9",
    })

    results = []
    log.info("==> %s  (%d URLs)", site_cfg["name"], len(site_cfg["urls"]))

    for url in site_cfg["urls"]:
        log.info("    GET %s", url)
        soup = fetch_page(url, session, settings["timeout"], settings["max_retries"])

        if soup:
            record = build_record(soup, url, site_cfg["id"])
            record["Site"]      = site_cfg["name"]
            record["Site ID"]   = site_cfg["id"]
            record["Site Type"] = site_cfg["type"]
            results.append(record)
            log.info("    OK  title=%r  rating=%s  instructors=%s  duration=%s",
                     record.get("Title"), record.get("Rating"),
                     record.get("Instructor"), record.get("Duration"))
        else:
            results.append({
                "URL": url, "Site": site_cfg["name"],
                "Site ID": site_cfg["id"], "Status": "error",
                "Scraped At": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00","Z"),
            })

        time.sleep(settings["delay"])

    return results

def save_json(records, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    log.info("Saved %d records  -->  %s", len(records), path)


def save_csv(records, path):
    if not records:
        return
    flat = []
    for r in records:
        row = {}
        for k, v in r.items():
            row[k] = " | ".join(str(x) for x in v) if isinstance(v, list) else v
        flat.append(row)
    all_keys = list(dict.fromkeys(k for row in flat for k in row))
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=all_keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(flat)
    log.info("Saved %d rows  -->  %s", len(flat), path)


def main():
    parser = argparse.ArgumentParser(description="Academic tutorial scraper")
    parser.add_argument("--config", default=XML_CONFIG_PATH, help="Path to XML config file")
    parser.add_argument("--site",   default=None, help="Scrape only this site ID (e.g. udacity)")
    parser.add_argument("--output", default=None, help="Override output format: json | csv")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        log.error("XML config not found: %s", config_path)
        log.error("Set XML_CONFIG_PATH at the top of the script.")
        return

    cfg      = load_config(str(config_path))
    settings = cfg["settings"]
    sites    = cfg["sites"]

    if args.output:
        settings["output_fmt"] = args.output

    if args.site:
        if args.site not in sites:
            log.error("Unknown site '%s'. Available: %s", args.site, list(sites.keys()))
            return
        sites = {args.site: sites[args.site]}

    all_results = []
    for site_cfg in sites.values():
        all_results.extend(scrape_site(site_cfg, settings))

    out_dir = Path(OUTPUT_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)

    filename = settings["output_file"]
    if settings["output_fmt"] == "csv":
        filename = filename.replace(".json", ".csv")
        save_csv(all_results, str(out_dir / filename))
    else:
        save_json(all_results, str(out_dir / filename))

    log.info("Done -- %d records -- folder: %s", len(all_results), out_dir.resolve())


if __name__ == "__main__":
    main()
