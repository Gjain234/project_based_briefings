import os
from datetime import datetime
from pathlib import Path

import pandas as pd
from dateutil.relativedelta import relativedelta


BASE_DIR = Path(__file__).resolve().parent

_DATABRICKS_HOST = "https://adb-8552758251265347.7.azuredatabricks.net"
_DATABRICKS_PATH = "/Volumes/prd_datascience_compoundriskmonitor/volumes/compoundriskmonitor/fcvriskdashboard/crisiswatch-text.xlsx"
_LOCAL_CW_XLSX = BASE_DIR / "crisiswatch-text.xlsx"

_CW_DB_DF = None     # module-level cache: downloaded once per Python session
_CW_LOC_ISO3 = None  # Location (casefold) -> iso3 mapping built from the xlsx


def _download_cw_db():
    from databricks.sdk import WorkspaceClient
    token = os.getenv("DATABRICKS_API_KEY")
    if not token:
        raise RuntimeError(
            "DATABRICKS_API_KEY not found in process environment. "
            "Make sure it is exported in your shell profile (use 'export DATABRICKS_API_KEY=...' "
            "not just 'DATABRICKS_API_KEY=...') and restart the server."
        )
    print("Downloading crisiswatch-text.xlsx from Databricks...")
    w = WorkspaceClient(host=_DATABRICKS_HOST, token=token)
    content = w.files.download(_DATABRICKS_PATH)
    with open(_LOCAL_CW_XLSX, "wb") as f:
        f.write(content.contents.read())
    print(f"Saved -> {_LOCAL_CW_XLSX}")


def _load_cw_db():
    global _CW_DB_DF, _CW_LOC_ISO3
    if _CW_DB_DF is not None:
        return _CW_DB_DF
    if not _LOCAL_CW_XLSX.exists():
        _download_cw_db()
    _CW_DB_DF = pd.read_excel(_LOCAL_CW_XLSX)
    _CW_DB_DF["month"] = pd.to_datetime(_CW_DB_DF["month"])
    _CW_LOC_ISO3 = (
        _CW_DB_DF[["Location", "iso3"]]
        .drop_duplicates("Location")
        .set_index(_CW_DB_DF["Location"].str.strip().str.casefold().drop_duplicates())["iso3"]
        .to_dict()
    )
    return _CW_DB_DF


def get_icg_text_db(iso3, override_date=None):
    """
    Return a DataFrame of CrisisWatch text for the given iso3 code covering
    the last 3 months, sourced from Databricks (crisiswatch-text.xlsx).

    The file is downloaded on the first call and cached in memory for the
    rest of the session — subsequent calls for other countries are instant.

    Returns None if iso3 is None or no entries found.
    Columns returned: entry_month (datetime), text (str)
    """
    if iso3 is None:
        return None

    df = _load_cw_db()

    today = override_date or datetime.today().date()
    three_months_ago = today - relativedelta(months=3)

    mask = (
        (df["iso3"] == iso3) &
        (df["month"] >= pd.Timestamp(three_months_ago))
    )
    filtered = df[mask].copy()

    if filtered.empty:
        print(f"No CrisisWatch DB entries found for iso3={iso3}.")
        return None

    filtered = filtered.drop_duplicates(subset=["month", "text"])
    filtered = filtered.rename(columns={"month": "entry_month"})
    filtered = filtered.sort_values("entry_month", ascending=False).reset_index(drop=True)
    print(f"Found {len(filtered)} CrisisWatch DB entries for iso3={iso3}.")
    return filtered[["entry_month", "text"]]


def get_crisiswatch_lastnmonths(country_name, override_date=None, n=3, cf_clearance=None):
    """Thin wrapper around get_icg_text_db that resolves country_name to iso3."""
    if isinstance(override_date, int) and n == 3:
        n = override_date
        override_date = None

    try:
        df = _load_cw_db()
        iso3 = _CW_LOC_ISO3.get(country_name.strip().casefold())
        if iso3 is None:
            print(f"No iso3 found for {country_name} in CrisisWatch DB.")
            return None

        today = override_date or datetime.today().date()
        n_months_ago = today - relativedelta(months=n)

        mask = (df["iso3"] == iso3) & (df["month"] >= pd.Timestamp(n_months_ago))
        filtered = df[mask].copy()
        if filtered.empty:
            print(f"No CrisisWatch DB entries found for {country_name} (iso3={iso3}).")
            return None

        filtered = filtered.drop_duplicates(subset=["month", "text"])
        filtered = filtered.rename(columns={"month": "entry_month", "Location": "country"})
        filtered = filtered.sort_values("entry_month", ascending=False).reset_index(drop=True)
        print(f"Found {len(filtered)} CrisisWatch DB entries for {country_name} (iso3={iso3}).")
        return filtered[["country", "entry_month", "text"]]
    except Exception as e:
        print(f"CrisisWatch DB lookup failed for {country_name}: {e}")
        return None
