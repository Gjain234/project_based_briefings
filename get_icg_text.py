import json
import os
import re
import time
from datetime import date, datetime
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse, urlunparse

import pandas as pd
import requests
from bs4 import BeautifulSoup
from dateutil.relativedelta import relativedelta


BASE_DIR = Path(__file__).resolve().parent
with open(BASE_DIR / "country_ids.json", "r", encoding="utf-8") as f:
    COUNTRY_IDS = json.load(f)


ICG_BASE_URL = "https://www.crisisgroup.org"
LATEST_UPDATES_URL = f"{ICG_BASE_URL}/latest-updates"
CRISISWATCH_URL = f"{ICG_BASE_URL}/crisiswatch/database"
CF_CLEARANCE_CACHE_FILE = BASE_DIR / "cf_clearance_cache.json"
DEFAULT_RETRY_DELAY_SECONDS = 2
MAX_CF_CLEARANCE_CACHE_AGE_HOURS = 23

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/147.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

LATEST_UPDATES_PUBLICATION_TYPE_IDS = [100, 1218, 104, 3329, 3898, 105]

KNOWN_NON_LANG_PREFIXES = {
    "rpt",
    "news",
    "latest-updates",
    "node",
    "about",
    "taxonomy",
    "contact-us",
    "privacy-policy",
    "support-us",
    "global-search",
    "rss-feed",
    "subscribe",
}


def _parse_html(text):
    return BeautifulSoup(text, "html.parser")


def _normalize_whitespace(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _dedupe_preserve_order(values):
    seen = set()
    ordered = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _coerce_to_date(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raise TypeError("override_date must be a date or datetime instance")


def _load_cached_cf_clearance():
    env_value = _normalize_whitespace(os.getenv("ICG_CF_CLEARANCE", ""))
    if env_value:
        return env_value

    if not CF_CLEARANCE_CACHE_FILE.exists():
        return None

    try:
        payload = json.loads(CF_CLEARANCE_CACHE_FILE.read_text(encoding="utf-8"))
        saved_at = datetime.fromisoformat(payload["saved_at"])
        age_hours = (datetime.now() - saved_at).total_seconds() / 3600
        if age_hours < MAX_CF_CLEARANCE_CACHE_AGE_HOURS:
            return _normalize_whitespace(payload.get("value", "")) or None
    except Exception:
        return None

    return None


def _cache_cf_clearance(cf_clearance):
    cookie_value = _normalize_whitespace(cf_clearance)
    if not cookie_value:
        return
    payload = {
        "value": cookie_value,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
    }
    CF_CLEARANCE_CACHE_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _build_session(cf_clearance=None):
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)

    cookie_value = _normalize_whitespace(cf_clearance) or _load_cached_cf_clearance()
    if cookie_value:
        session.cookies.set("cf_clearance", cookie_value, domain="www.crisisgroup.org")
        if cf_clearance:
            _cache_cf_clearance(cookie_value)

    return session, bool(cookie_value)


def normalize_icg_link_to_english(url):
    parsed = urlparse(url)
    parts = parsed.path.lstrip("/").split("/", 1)

    if len(parts) > 1:
        prefix = parts[0]
        if prefix.isalpha() and 2 <= len(prefix) <= 3 and prefix not in KNOWN_NON_LANG_PREFIXES:
            new_path = "/" + parts[1]
        else:
            new_path = parsed.path
    else:
        new_path = parsed.path

    return urlunparse(parsed._replace(path=new_path))


def _get_page(url, session=None, max_retries=3, require_cf_clearance=False, debug_file=None):
    active_session = session or requests.Session()

    for attempt in range(1, max_retries + 1):
        try:
            response = active_session.get(url, timeout=60)
            if response.status_code == 200:
                return _parse_html(response.text)

            print(f"Attempt {attempt}: status {response.status_code} for {url}")
            if response.status_code == 403 and require_cf_clearance:
                break
        except requests.RequestException as exc:
            print(f"Attempt {attempt} failed (network): {exc}")

        if attempt < max_retries:
            time.sleep(DEFAULT_RETRY_DELAY_SECONDS * attempt)

    if debug_file and 'response' in locals() and getattr(response, "text", None):
        Path(debug_file).write_text(response.text, encoding="utf-8")

    if require_cf_clearance:
        raise RuntimeError(
            "Failed to fetch CrisisWatch. A valid cf_clearance cookie is likely required. "
            "Set ICG_CF_CLEARANCE in the environment or pass cf_clearance=... when calling get_crisiswatch_lastnmonths()."
        )
    raise RuntimeError(f"Failed to fetch {url}")


def _extract_total_pages(soup):
    page_numbers = set()

    for link in soup.select("a[href*='page=']"):
        href = link.get("href") or ""
        page_value = parse_qs(urlparse(href).query).get("page")
        if not page_value:
            continue
        try:
            page_numbers.add(int(page_value[0]))
        except ValueError:
            continue

    text = " ".join(soup.stripped_strings)
    for match in re.finditer(r"\b\d+\s*-\s*\d+\s+of\s+(\d+)\b", text, flags=re.IGNORECASE):
        try:
            total_items = int(match.group(1))
            if total_items > 0:
                page_numbers.add((total_items - 1) // 10)
        except ValueError:
            continue

    for match in re.finditer(r"\b\d+\s+of\s+(\d+)\b", text, flags=re.IGNORECASE):
        try:
            max_page = int(match.group(1)) - 1
            if max_page >= 0:
                page_numbers.add(max_page)
        except ValueError:
            continue

    return (max(page_numbers) + 1) if page_numbers else 1


def _is_probable_article_link(url):
    parsed = urlparse(url)
    if parsed.netloc and parsed.netloc != "www.crisisgroup.org":
        return False
    path = parsed.path or ""
    if not path or path in {"/", "/latest-updates", "/crisiswatch/database"}:
        return False
    if any(path.endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".webp", ".svg", ".pdf")):
        return False

    segments = [segment for segment in path.split("/") if segment]
    if len(segments) < 2:
        return False
    if segments[0] in KNOWN_NON_LANG_PREFIXES:
        return False
    return True


def _extract_latest_update_links(listing_soup):
    candidate_links = []
    selectors = [
        ".c-news-listing__title a[href]",
        ".views-row h2 a[href]",
        ".views-row h3 a[href]",
        ".views-row h4 a[href]",
        "h2 a[href]",
        "h3 a[href]",
        "h4 a[href]",
    ]

    for selector in selectors:
        for anchor in listing_soup.select(selector):
            href = anchor.get("href")
            if not href:
                continue
            full_url = normalize_icg_link_to_english(urljoin(ICG_BASE_URL, href.strip()))
            if _is_probable_article_link(full_url):
                candidate_links.append(full_url)

    if not candidate_links:
        for anchor in listing_soup.select("a[href]"):
            href = anchor.get("href")
            if not href:
                continue
            full_url = normalize_icg_link_to_english(urljoin(ICG_BASE_URL, href.strip()))
            if _is_probable_article_link(full_url):
                candidate_links.append(full_url)

    return _dedupe_preserve_order(candidate_links)


def _extract_article_text(article_soup):
    selectors = [
        "main .field--name-body p",
        "main article p",
        "main .node__content p",
        "main .c-content p",
        "article p",
        "main p",
    ]

    paragraphs = []
    for selector in selectors:
        paragraphs = [_normalize_whitespace(node.get_text(" ", strip=True)) for node in article_soup.select(selector)]
        paragraphs = [paragraph for paragraph in paragraphs if paragraph]
        if paragraphs:
            break

    paragraphs = [
        paragraph for paragraph in paragraphs
        if paragraph.lower() not in {"share", "email", "print"}
    ]
    return "\n".join(_dedupe_preserve_order(paragraphs))


def _extract_article_metadata(article_soup, url, country_name):
    title_node = article_soup.select_one("h1")
    date_node = article_soup.select_one("time")
    return {
        "country": country_name,
        "title": _normalize_whitespace(title_node.get_text(" ", strip=True)) if title_node else url,
        "date": _normalize_whitespace(date_node.get_text(" ", strip=True)) if date_node else None,
        "link": url,
        "text": _extract_article_text(article_soup),
    }


def get_icg_reports(country_name, write=False, override_date=None):
    if country_name not in COUNTRY_IDS:
        raise ValueError(f"Country '{country_name}' not found")

    country_id = COUNTRY_IDS[country_name]
    today = _coerce_to_date(override_date) or datetime.today().date()
    three_months_ago = today - relativedelta(months=3)

    params = [
        ("location[]", country_id),
        ("created", "custom"),
        ("from_month", three_months_ago.month),
        ("from_year", three_months_ago.year),
        ("to_month", today.month),
        ("to_year", today.year),
    ]
    params.extend(("publication_type[]", publication_type_id) for publication_type_id in LATEST_UPDATES_PUBLICATION_TYPE_IDS)

    session, _ = _build_session()
    prepared_url = requests.Request("GET", LATEST_UPDATES_URL, params=params).prepare().url
    print(f"Fetching ICG reports for {country_name}")

    first_page = _get_page(prepared_url, session=session)
    total_pages = _extract_total_pages(first_page)
    print(f"Detected {total_pages} latest-updates page(s)")

    article_links = []
    for page_index in range(total_pages):
        page_url = requests.Request("GET", LATEST_UPDATES_URL, params=params + [("page", page_index)]).prepare().url
        listing_soup = first_page if page_index == 0 else _get_page(page_url, session=session)
        page_links = _extract_latest_update_links(listing_soup)
        print(f"Latest-updates page {page_index + 1}/{total_pages}: found {len(page_links)} candidate link(s)")
        article_links.extend(page_links)
        if page_index < total_pages - 1:
            time.sleep(0.5)

    rows = []
    for link in _dedupe_preserve_order(article_links):
        try:
            page = _get_page(link, session=session)
        except Exception as exc:
            print(f"Skipping {link}: {exc}")
            continue

        rows.append(_extract_article_metadata(page, link, country_name))
        time.sleep(0.5)

    if not rows:
        print("No reports found.")
        return None

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"], errors="coerce", dayfirst=True)
    df = df.sort_values("date", ascending=False, na_position="last")
    df = df.drop_duplicates(subset=["country", "title", "link"])

    if write:
        fname = f"icg_country_reports_{country_name.replace(' ', '_')}.csv"
        df.to_csv(fname, index=False)
        print(f"Saved {len(df)} reports -> {fname}")

    print(df.head())
    return df


def _parse_crisiswatch_entry(entry_node):
    name_node = entry_node.select_one("h3")
    time_node = entry_node.select_one("time")
    detail_nodes = entry_node.select(".o-crisis-states__detail p")
    if not detail_nodes:
        detail_nodes = entry_node.select("p")

    return {
        "country": _normalize_whitespace(name_node.get_text(" ", strip=True)) if name_node else None,
        "entry_month": _normalize_whitespace(time_node.get_text(" ", strip=True)) if time_node else None,
        "text": "\n".join(
            paragraph
            for paragraph in (_normalize_whitespace(node.get_text(" ", strip=True)) for node in detail_nodes)
            if paragraph
        ),
    }


def _fetch_crisiswatch_entries(country_name, from_date, to_date, cf_clearance=None):
    country_id = COUNTRY_IDS[country_name]
    params = [
        ("location[]", country_id),
        ("crisis_state", ""),
        ("created", "custom"),
        ("from_month", from_date.month),
        ("from_year", from_date.year),
        ("to_month", to_date.month),
        ("to_year", to_date.year),
    ]

    session, has_cf_clearance = _build_session(cf_clearance=cf_clearance)
    prepared_url = requests.Request("GET", CRISISWATCH_URL, params=params).prepare().url
    debug_file = BASE_DIR / "crisiswatch_debug.html"
    first_page = _get_page(
        prepared_url,
        session=session,
        require_cf_clearance=not has_cf_clearance,
        debug_file=debug_file,
    )

    first_entries = first_page.select("div.c-crisiswatch-entry")
    if not first_entries:
        debug_file.write_text(str(first_page), encoding="utf-8")
        raise RuntimeError(
            "No CrisisWatch entries found. The site structure may have changed or cf_clearance expired. "
            f"Debug HTML saved to {debug_file.name}."
        )

    total_pages = _extract_total_pages(first_page)
    print(f"Detected {total_pages} CrisisWatch page(s)")

    rows = []
    for page_index in range(total_pages):
        page_url = requests.Request("GET", CRISISWATCH_URL, params=params + [("page", page_index)]).prepare().url
        page_soup = first_page if page_index == 0 else _get_page(
            page_url,
            session=session,
            require_cf_clearance=True,
            debug_file=debug_file,
        )
        page_entries = page_soup.select("div.c-crisiswatch-entry")
        print(f"CrisisWatch page {page_index + 1}/{total_pages}: found {len(page_entries)} entry node(s)")

        for entry in page_entries:
            parsed_entry = _parse_crisiswatch_entry(entry)
            if parsed_entry["country"] == country_name and parsed_entry["entry_month"]:
                rows.append(parsed_entry)

        if page_index < total_pages - 1:
            time.sleep(0.5)

    return rows


def get_crisiswatch_lastnmonths(country_name, override_date=None, n=3, cf_clearance=None):
    if country_name not in COUNTRY_IDS:
        raise ValueError(f"Country '{country_name}' not found")

    if isinstance(override_date, int) and cf_clearance is None and n == 3:
        n = override_date
        override_date = None

    today = _coerce_to_date(override_date) or datetime.today().date()
    n_months_ago = today - relativedelta(months=n)

    print(f"Fetching CrisisWatch entries for {country_name}")
    rows = _fetch_crisiswatch_entries(
        country_name=country_name,
        from_date=n_months_ago,
        to_date=today,
        cf_clearance=cf_clearance,
    )

    if not rows:
        print("No CrisisWatch entries found.")
        return None

    df = pd.DataFrame(rows)
    raw_entry_month = df["entry_month"].copy()
    df["entry_month"] = pd.to_datetime(df["entry_month"], format="%B %Y", errors="coerce")
    fallback_mask = df["entry_month"].isna()
    if fallback_mask.any():
        df.loc[fallback_mask, "entry_month"] = pd.to_datetime(
            raw_entry_month[fallback_mask],
            errors="coerce",
        )

    df = df.dropna(subset=["entry_month"]).copy()
    df["year_month"] = df["entry_month"].dt.to_period("M")
    last_periods = sorted(df["year_month"].unique(), reverse=True)[:n]
    df = df[df["year_month"].isin(last_periods)]
    df = df.drop(columns=["year_month"])
    df = df.sort_values("entry_month", ascending=False)
    df = df.drop_duplicates(subset=["country", "entry_month", "text"])

    print(df.head())
    return df
