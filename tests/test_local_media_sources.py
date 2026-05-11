import sys
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from local_media_sources import build_country_media_source_prompt, get_country_media_source_guidance


def write_media_sources_workbook(path):
    rows = [
        {
            "Country": "Somalia",
            "POC(s) who added Source(s)": "Tester",
            "Trusted/Untrusted Regional News Sources": "Hiiraan Online",
            "Source specific points": "Useful for local political reporting; verify casualty figures.",
            "Any general notes/clarifications": "Triangulate major national political developments with Reuters or AP.",
        },
        {
            "Country": "",
            "POC(s) who added Source(s)": "Tester",
            "Trusted/Untrusted Regional News Sources": "Shabelle Media Network",
            "Source specific points": "Can surface early security reporting but requires corroboration.",
            "Any general notes/clarifications": "",
        },
        {
            "Country": "Bangladesh",
            "POC(s) who added Source(s)": "Tester",
            "Trusted/Untrusted Regional News Sources": "The Daily Star",
            "Source specific points": "Large English daily with broad coverage.",
            "Any general notes/clarifications": "",
        },
    ]
    df = pd.DataFrame(rows)
    with pd.ExcelWriter(path) as writer:
        pd.DataFrame({"example": [1]}).to_excel(writer, sheet_name="(DO NOT EDIT) AI Examples", index=False)
        df.to_excel(writer, sheet_name="(EDIT HERE) Media Sources", index=False)


def test_country_media_source_guidance_handles_country_aliases_and_forward_fill(tmp_path):
    workbook_path = tmp_path / "media_sources.xlsx"
    write_media_sources_workbook(workbook_path)

    guidance = get_country_media_source_guidance(
        "Somalia, Federal Republic of",
        workbook_path=str(workbook_path),
    )

    assert [source["name"] for source in guidance["sources"]] == [
        "Hiiraan Online",
        "Shabelle Media Network",
    ]
    assert guidance["general_notes"] == [
        "Triangulate major national political developments with Reuters or AP.",
    ]


def test_country_media_source_prompt_includes_source_and_general_notes(tmp_path):
    workbook_path = tmp_path / "media_sources.xlsx"
    write_media_sources_workbook(workbook_path)

    prompt_block = build_country_media_source_prompt(
        "Somalia, Federal Republic of",
        workbook_path=str(workbook_path),
    )

    assert "### Country-Specific Local Media Guidance" in prompt_block
    assert "Hiiraan Online - Useful for local political reporting; verify casualty figures." in prompt_block
    assert "Shabelle Media Network - Can surface early security reporting but requires corroboration." in prompt_block
    assert "Triangulate major national political developments with Reuters or AP." in prompt_block


def test_country_media_source_prompt_is_empty_when_country_has_no_rows(tmp_path):
    workbook_path = tmp_path / "media_sources.xlsx"
    write_media_sources_workbook(workbook_path)

    assert build_country_media_source_prompt("Nepal", workbook_path=str(workbook_path)) == ""