import os
import re
from functools import lru_cache

import pandas as pd

from country_name_mapping import COUNTRY_NAME_MAPPING, get_country_id_key, get_possible_wb_country_names


WORKBOOK_NAME = "FCV Country News Sources.xlsx"
WORKSHEET_NAME = "(EDIT HERE) Media Sources"
WORKBOOK_PATH = os.path.join(os.path.dirname(__file__), WORKBOOK_NAME)

COUNTRY_COLUMN = "Country"
SOURCE_COLUMN = "Trusted/Untrusted Regional News Sources"
SOURCE_NOTES_COLUMN = "Source specific points"
GENERAL_NOTES_COLUMN = "Any general notes/clarifications"


def _clean_text(value):
    if pd.isna(value):
        return ""

    text = str(value).strip()
    if text.lower() == "nan":
        return ""
    return re.sub(r"\s+", " ", text)


def _clean_source_name(value):
    return _clean_text(value).strip(" ;")


def _normalize_country_name(value):
    text = _clean_text(value).casefold().replace("&", "and")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _get_country_aliases(country_name):
    aliases = {country_name}

    mapped_name = get_country_id_key(country_name)
    if mapped_name:
        aliases.add(mapped_name)
        aliases.update(get_possible_wb_country_names(mapped_name))
    else:
        aliases.update(
            wb_name for wb_name, mapped_name in COUNTRY_NAME_MAPPING.items() if mapped_name == country_name
        )

    return {_normalize_country_name(name) for name in aliases if _clean_text(name)}


@lru_cache(maxsize=4)
def _load_media_source_rows(workbook_path=WORKBOOK_PATH):
    if not os.path.exists(workbook_path):
        return []

    df = pd.read_excel(workbook_path, sheet_name=WORKSHEET_NAME)
    kept_columns = [
        column for column in df.columns
        if isinstance(column, str) and not column.startswith("Unnamed:")
    ]
    df = df[kept_columns].copy()

    required_columns = [
        COUNTRY_COLUMN,
        SOURCE_COLUMN,
        SOURCE_NOTES_COLUMN,
        GENERAL_NOTES_COLUMN,
    ]
    if any(column not in df.columns for column in required_columns):
        return []

    df[COUNTRY_COLUMN] = (
        df[COUNTRY_COLUMN]
        .apply(_clean_text)
        .replace("", pd.NA)
        .ffill()
        .fillna("")
    )

    # Replace NaN with None for JSON compatibility
    df = df.where(pd.notnull(df), None)

    rows = []
    for record in df[required_columns].to_dict(orient="records"):
        country = _clean_text(record.get(COUNTRY_COLUMN, ""))
        source_name = _clean_source_name(record.get(SOURCE_COLUMN, ""))
        source_notes = _clean_text(record.get(SOURCE_NOTES_COLUMN, ""))
        general_notes = _clean_text(record.get(GENERAL_NOTES_COLUMN, ""))

        if not any([country, source_name, source_notes, general_notes]):
            continue

        rows.append({
            "country": country,
            "source_name": source_name,
            "source_notes": source_notes,
            "general_notes": general_notes,
        })

    return rows


def get_country_media_source_guidance(country_name, workbook_path=WORKBOOK_PATH):
    matching_countries = _get_country_aliases(country_name)
    if not matching_countries:
        return {"sources": [], "general_notes": []}

    sources = []
    general_notes = []
    seen_sources = set()
    seen_general_notes = set()

    for row in _load_media_source_rows(workbook_path):
        if _normalize_country_name(row["country"]) not in matching_countries:
            continue

        source_name = row["source_name"]
        source_notes = row["source_notes"]
        general_note = row["general_notes"]

        if source_name:
            source_key = (source_name.casefold(), source_notes.casefold())
            if source_key not in seen_sources:
                seen_sources.add(source_key)
                sources.append({"name": source_name, "note": source_notes})

        if general_note:
            general_key = general_note.casefold()
            if general_key not in seen_general_notes:
                seen_general_notes.add(general_key)
                general_notes.append(general_note)

    return {"sources": sources, "general_notes": general_notes}


def build_country_media_source_prompt(country_name, workbook_path=WORKBOOK_PATH):
    guidance = get_country_media_source_guidance(country_name, workbook_path=workbook_path)
    if not guidance["sources"] and not guidance["general_notes"]:
        return ""

    lines = [
        "### Country-Specific Local Media Guidance",
        f"The following manually curated local-media guidance is available for {country_name}.",
        "Treat listed outlets as preferred local references when they are relevant and available.",
        "Follow the caution notes exactly. If a note says to triangulate, constrain, or be careful, corroborate before relying on that source.",
    ]

    if guidance["sources"]:
        lines.append("")
        lines.append("Preferred sources and usage notes:")
        for index, source in enumerate(guidance["sources"], start=1):
            line = f"{index}. {source['name']}"
            if source["note"]:
                line += f" - {source['note']}"
            lines.append(line)

    if guidance["general_notes"]:
        lines.append("")
        lines.append("General local-media notes:")
        for index, note in enumerate(guidance["general_notes"], start=1):
            lines.append(f"{index}. {note}")

    return "\n".join(lines)


def log_country_media_source_injection(country_name, workbook_path=WORKBOOK_PATH):
    """Print the exact local-media guidance block used in prompt injection."""
    prompt_block = build_country_media_source_prompt(country_name, workbook_path=workbook_path)

    print(f"\n--- Local media guidance for {country_name} ---")
    if prompt_block:
        print(prompt_block)
    else:
        print("No local media guidance found in workbook for this country.")
    print("--- End local media guidance ---\n")

    return prompt_block