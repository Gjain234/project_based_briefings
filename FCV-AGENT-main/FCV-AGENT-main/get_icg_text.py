import json
import time
from datetime import datetime
from dateutil.relativedelta import relativedelta

import requests
import pandas as pd
from bs4 import BeautifulSoup

with open("country_ids.json", "r") as f:
    COUNTRY_IDS = json.load(f)
def _parse_html(text):
    return BeautifulSoup(text, "html.parser")
from urllib.parse import urlparse, urlunparse

KNOWN_NON_LANG_PREFIXES = {
    "rpt", "news", "latest-updates", "node", "about"
}

def normalize_icg_link_to_english(url):
    parsed = urlparse(url)
    parts = parsed.path.lstrip("/").split("/", 1)

    if len(parts) > 1:
        prefix = parts[0]

        # Likely language code:
        if (
            prefix.isalpha()
            and 2 <= len(prefix) <= 3
            and prefix not in KNOWN_NON_LANG_PREFIXES
        ):
            new_path = "/" + parts[1]
        else:
            new_path = parsed.path
    else:
        new_path = parsed.path

    return urlunparse(parsed._replace(path=new_path))

def _get_page(url, max_retries=3):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/119.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    for attempt in range(1, max_retries + 1):
        try:
            r = requests.get(url, headers=headers, timeout=60)
            if r.status_code == 200:
                return _parse_html(r.text)

            print(f"Attempt {attempt}: status {r.status_code}")

        except requests.RequestException as e:
            # ONLY retry network errors
            print(f"Attempt {attempt} failed (network): {e}")
            time.sleep(2 ** attempt)

    raise RuntimeError(f"Failed to fetch {url}")

def get_icg_reports(country_name, write=False, override_date=None):
    if country_name not in COUNTRY_IDS:
        raise ValueError(f"Country '{country_name}' not found")

    country_id = COUNTRY_IDS[country_name]

    if override_date:
        today = override_date
    else:
        today = datetime.today().date()
    three_months_ago = today - relativedelta(months=3)

    # MEDIA TYPES YOU WANT
    publication_type_ids = [
        100,   # Briefings
        1218,
        104,   # Reports
        3329,
        3898,
        105
    ]

    # build publication type parameters
    pub_type_params = "".join(
        f"&publication_type%5B%5D={pt}"
        for pt in publication_type_ids
    )

    created_param = "custom" if override_date is not None else "-3+months"
    url = (
        "https://www.crisisgroup.org/latest-updates"
        f"?location%5B%5D={country_id}"
        f"{pub_type_params}"
        f"&created={created_param}"
        f"&from_month={three_months_ago.month}&from_year={three_months_ago.year}"
        f"&to_month={today.month}&to_year={today.year}"
    )

    print(f"Fetching ICG reports for {country_name}")
    soup = _get_page(url)

    links = {
        a.get("href").strip()
        for a in soup.select(
            ".views-row .c-news-listing__title a, "
            ".views-row .c-news-listing__img a"
        )
        if a.get("href")
    }

    rows = []
    for link in links:
        full = link if link.startswith("http") else f"https://www.crisisgroup.org{link}"
        full = normalize_icg_link_to_english(full)
        time.sleep(1)

        try:
            page = _get_page(full)
        except Exception:
            continue

        rows.append({
            "country": country_name,
            "title": page.select_one("h1").get_text(strip=True),
            "date": page.select_one("time").get_text(strip=True),
            "link": full,
            "text": "\n".join(p.get_text(strip=True) for p in page.select("p")),
        })

    if not rows:
        print("No reports found.")
        return None

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"], errors="coerce", dayfirst=True)
    df = df.sort_values("date", ascending=False)
    df = df.drop_duplicates(subset=["country", "title"])

    if write:
        fname = f"icg_country_reports_{country_name.replace(' ', '_')}.csv"
        df.to_csv(fname, index=False)
        print(f"Saved {len(df)} reports → {fname}")

    print(df.head())
    return df

# def get_icg_reports(country_name, write=False):
#     if country_name not in COUNTRY_IDS:
#         raise ValueError(f"Country '{country_name}' not found")

#     country_id = COUNTRY_IDS[country_name]

#     today = datetime.today().date()
#     three_months_ago = today - relativedelta(months=3)

#     url = (
#         "https://www.crisisgroup.org/latest-updates"
#         f"?location%5B%5D={country_id}"
#         "&created=-3+months"
#         f"&from_month={three_months_ago.month}&from_year={three_months_ago.year}"
#         f"&to_month={today.month}&to_year={today.year}"
#     )


#     print(f"Fetching ICG reports for {country_name}")
#     soup = _get_page(url)

#     links = {
#         a.get("href").strip()
#         for a in soup.select(
#             ".views-row .c-news-listing__title a, "
#             ".views-row .c-news-listing__img a"
#         )
#         if a.get("href")
#     }

#     rows = []
#     for link in links:
#         full = link if link.startswith("http") else f"https://www.crisisgroup.org{link}"
#         full = normalize_icg_link_to_english(full)
#         time.sleep(1)

#         try:
#             page = _get_page(full)
#         except Exception:
#             continue

#         rows.append({
#             "country": country_name,
#             "title": page.select_one("h1").get_text(strip=True),
#             "date": page.select_one("time").get_text(strip=True),
#             "link": full,
#             "text": "\n".join(p.get_text(strip=True) for p in page.select("p")),
#         })

#     if not rows:
#         print("No reports found.")
#         return None

#     df = pd.DataFrame(rows)
#     df["date"] = pd.to_datetime(df["date"], errors="coerce", dayfirst=True)
#     df = df.sort_values("date", ascending=False)
#     df = df.drop_duplicates(subset=["country", "title"])

#     if write:
#         fname = f"icg_country_reports_{country_name.replace(' ', '_')}.csv"
#         df.to_csv(fname, index=False)
#         print(f"Saved {len(df)} reports → {fname}")
#     print(df.head())
#     return df

def get_crisiswatch_lastnmonths(country_name, override_date=None, n=3):
    if country_name not in COUNTRY_IDS:
        raise ValueError(f"Country '{country_name}' not found")

    country_id = COUNTRY_IDS[country_name]
    if override_date:
        today = override_date
    else:
        today = datetime.today().date()
    n_months_ago = today - relativedelta(months=n)
    created_param = "custom" if override_date is not None else f"-{n}+months"

    url = (
        "https://www.crisisgroup.org/crisiswatch/database"
        f"?location%5B%5D={country_id}"
        f"&crisis_state=&created={created_param}"
        f"&from_month={n_months_ago.month}&from_year={n_months_ago.year}"
        f"&to_month={today.month}&to_year={today.year}"
    )

    print(f"Fetching CrisisWatch entries for {country_name}")
    soup = _get_page(url)

    rows = []
    for entry in soup.select("div.c-crisiswatch-entry"):
        name = entry.select_one("h3").get_text(strip=True)
        if name != country_name:
            continue

        entry_month = entry.select_one("time").get_text(strip=True)
        text = "\n".join(
            p.get_text(strip=True)
            for p in entry.select(".o-crisis-states__detail p")
        )

        rows.append({
            "country": name,
            "entry_month": entry_month,
            "text": text,
        })

    if not rows:
        print("No CrisisWatch entries found.")
        return None

    df = pd.DataFrame(rows)
    df["entry_month"] = pd.to_datetime(
        df["entry_month"],
        format="%B %Y",   # e.g. "January 2026"
        errors="coerce"
    )
    # convert to year–month only
    df["year_month"] = df["entry_month"].dt.to_period("M")

    # compute last n months based on site logic
    last_periods = sorted(df["year_month"].unique(), reverse=True)[:n]

    df = df[df["year_month"].isin(last_periods)]
    df = df.drop(columns=["year_month"])
    print(df.head())
    return df
