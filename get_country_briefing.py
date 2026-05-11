import os
import datetime
import anthropic
from docx import Document
from get_icg_text import (
    get_icg_reports,
    get_crisiswatch_lastnmonths,
)
from briefing_config import ANTHROPIC_API_KEY, ANTHROPIC_COUNTRY_RISK_MODEL, ANTHROPIC_RISK_BRIEFING_MODEL
from briefing_prompts import get_country_risk_extraction_prompt, COUNTRY_THEMES
from local_media_sources import build_country_media_source_prompt, log_country_media_source_injection
import pandas as pd
import json
import uuid

client = anthropic.Anthropic(
    api_key=ANTHROPIC_API_KEY,
)

def extract_country_risks_with_websearch(country_name):
    """
    Extract structured country risks directly from ICG/CrisisWatch data with web search.
    Single LLM call that combines data gathering and risk extraction.
    
    Returns: DataFrame with risk items (risk_id, title, summary, themes, keywords, severity, time_horizon)
    """
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    print(f"\n=== Extracting country risks for {country_name} with web search ===")
    
    try:
        cw = get_crisiswatch_lastnmonths(country_name, 3)
        reports = get_icg_reports(country_name)
    except:
        cw = None
        reports = None        

    icg_texts = ""

    if cw is not None:
        for _, row in cw.iterrows():
            icg_texts += (
                f"--- CrisisWatch Entry: {row['entry_month'].strftime('%B %Y')} ---\n"
                f"{row['text']}\n\n"
            )
    if icg_texts == "":
        icg_texts = "No ICG text available for country"

    if reports is not None:
        for _, row in reports.iterrows():
            icg_texts += (
                f"--- ICG Report: {row['title']} ({row['date'].strftime('%Y-%m-%d')}) ---\n"
                f"{row['text']}\n\n"
            )

    # Log the exact local sources/notes that will be injected into the extraction prompt.
    log_country_media_source_injection(country_name)

    prompt = get_country_risk_extraction_prompt(country_name, today, icg_texts)

    response = client.messages.create(
        model=ANTHROPIC_COUNTRY_RISK_MODEL,
        max_tokens=10000,
        messages=[
            {"role": "user", "content": prompt}
        ],
        tools=[{
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": 10,
            "blocked_domains": ["wikipedia.org", "en.wikipedia.org/*"],
        }]
    )

    # Extract JSON from response and collect all citations
    raw_output = ""
    all_citations = []
    
    for block in response.content:
        if block.type == "text":
            raw_output += block.text
            # Collect citations from this text block
            if hasattr(block, 'citations') and block.citations:
                for citation in block.citations:
                    # Avoid duplicates
                    if citation not in all_citations:
                        all_citations.append(citation)

    raw_output = raw_output.strip()
    
    # Debug: print if we found citations
    if all_citations:
        print(f"   Found {len(all_citations)} citations from web search")

    # Parse JSON safely
    try:
        parsed = json.loads(raw_output)
    except json.JSONDecodeError as e:
        # Try to extract JSON from markdown code block
        if "```json" in raw_output:
            json_start = raw_output.find("```json") + 7
            json_end = raw_output.find("```", json_start)
            if json_end > json_start:
                raw_output = raw_output[json_start:json_end].strip()
        else:
            # Attempt to extract JSON block if model wrapped it
            json_start = raw_output.find("{")
            json_end = raw_output.rfind("}")
            if json_start >= 0 and json_end > json_start:
                raw_output = raw_output[json_start:json_end+1]
        
        try:
            parsed = json.loads(raw_output)
        except json.JSONDecodeError as e2:
            print(f"   ⚠️  JSON parsing failed for country risks")
            print(f"   Error: {str(e2)}")
            print(f"   Raw output (first 500 chars): {raw_output[:500]}")
            raise ValueError(f"Failed to parse JSON from LLM response: {raw_output[:200]}")

    risks = parsed.get("risks", [])

    # Light cleanup / validation
    cleaned = []
    for r in risks:
        if not r.get("risk_id"):
            r["risk_id"] = "cr_" + uuid.uuid4().hex[:8]

        r["themes"] = [t for t in r.get("themes", []) if t in COUNTRY_THEMES]

        if not isinstance(r.get("keywords"), list):
            r["keywords"] = []
        
        if not isinstance(r.get("locations"), list):
            r["locations"] = []

        cleaned.append(r)

    country_risks_df = pd.DataFrame(cleaned)
    return country_risks_df


def get_country_recent_risks_briefing(country_name):
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    print(f"\n=== Running briefing for {country_name} ===")
    local_media_guidance = log_country_media_source_injection(country_name)
    try:
        cw = get_crisiswatch_lastnmonths(country_name, 3)
        reports = get_icg_reports(country_name)
    except:
        cw=None
        reports=None        

    icg_texts = ""

    if cw is not None:
        for _, row in cw.iterrows():
            icg_texts += (
                f"--- CrisisWatch Entry: {row['entry_month'].strftime('%B %Y')} ---\n"
                f"{row['text']}\n\n"
            )
    if icg_texts == "":
        icg_texts = "No ICG text available for country"

    if reports is not None:
        for _, row in reports.iterrows():
            icg_texts += (
                f"--- ICG Report: {row['title']} ({row['date'].strftime('%Y-%m-%d')}) ---\n"
                f"{row['text']}\n\n"
            )

    # ---- Build prompt (unchanged logic) ----
    prompt = f"""You are a Fragility, Conflict & Violence (FCV) analyst preparing a briefing for senior development leadership (e.g., World Bank Country Director).

    Your audience already has baseline knowledge of {country_name} and economics. They do not need primers or definitions. They need a concise but detailed overview that catches them up on the latest FCV dynamics and operational implications.

    **Country:** {country_name}

    **Timeframe:** Cover the last 3 months ending {today}. If essential for continuity, you may include clearly labeled **Context** items up to 6 months back.

    ---

    ### Task

    * You will be provided a concise summary of recent International Crisis Group/CrisisWatch reporting if available.
    * Treat that summary as the **backbone** of the briefing: emphasize and synthesize it.
    * Use a small number of outside sources only to corroborate, fill gaps, or capture very recent developments not in the ICG summary.
    * In the case that the summary is not available, use ICG reporting as a style guide and use your own websearch and research to write the briefing.
    * Write a **{country_name} FCV briefing**.
    * Return **only markdown** — no methodology or internal notes.
    * The entire briefing should be roughly **500 words**.
    * **STRICTLY FOLLOW:** Always start the response with **“Risk Assessment summary as follows:”**

    ---

    ### Briefing Sections

    * **Risk Overview:** Summarize the most important details in the briefing and the key FCV dynamics the reader should know.

    Then fill in the following 4 sections:

    * **Institutional fragility, political tensions, and social unrest** (governance, elections, corruption or impunity, protests, political subjugation and contestation).
    * **Conflict and violence dynamics** (jihadist or insurgent activity; intercommunal violence; organized crime, banditry, or kidnapping; security-force conduct; cross-border spillovers; climate or market shocks).
    * **Displacement and refugee dynamics** if relevant (UNHCR, IOM DTM, IDMC). If citing stock figures, note the latest update month.
    * **Sensitivities between government and development actors**: Conclude with recent frictions or alignment between development and humanitarian actors (e.g., World Bank, United Nations) and the Government of {country_name} (federal and/or state).

    ---

    ### Formatting Rules (Strict)

    * Bold **only** the section titles.
    * Do not add any title beyond the section headings.
    * Write section titles inline with their paragraphs.
    * After the first paragraph (**Risk Overview:**), use the four following subheadings tied to salient risks.
    * Subheadings must be **bold** and end with a colon (no trailing space).
    * Immediately start each paragraph after the heading do not add a new line e.g. **Risk Overview:** This is the risk overview paragraph...
    * Do not exceed 500 words.
    * Do not include a separate sources section.
    * DO NOT RETURN ANY TEXT OR COMMENTARY OUTSIDE THE BRIEFING ITSELF.

    ---

    ### Sources and Citations

    * Base the narrative primarily on the provided ICG/CrisisWatch summary.
    * Supplement with other trusted sources only if necessary.
    * Use websearch to ensure every factual claim has an inline hyperlink.
    * Aim for **8–10 inline hyperlinks** total.
    * Avoid more than two links from the same publisher.
    * Clearly label **Context** for any item older than one year.
    * Use inline hyperlinks only (no endnotes).

    **Source preference order:**

    1. ICG / CrisisWatch (from the provided summary) and Reputable national or regional outlets from {country_name}
    2. Multilateral or UN sources (OCHA, UNHCR, WFP, UNICEF, OHCHR, World Bank, UNDP, IOM DTM, IDMC)
    3. Reputable international wires or broadcasters (Reuters, AP, BBC, Al Jazeera, VOA)

    {local_media_guidance}

    ---

    **Input: ICG/CrisisWatch Summary**
    {icg_texts}
    """

    response = client.messages.create(
        model=ANTHROPIC_RISK_BRIEFING_MODEL,
        max_tokens=10000,
        messages=[
            {"role": "user", "content" : prompt}
        ],
        tools=[{
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": 5,
            "blocked_domains": ["wikipedia.org","en.wikipedia.org/*"],
        }]
    )

    full_text = ""
    started = False

    for block in response.content:
        if block.type != "text":
            continue

        text = block.text
        if not started:
            if "**Risk Overview:**" in text:
                started = True
                text = text[text.index("**Risk Overview:**"):]
            else:
                continue

        if block.citations:
            for c in block.citations:
                text += f" ([{c.title}]({c.url}))"

        full_text += text
    prompt = f"""
    You are editing a markdown document.

    TASK:
    - Shorten ONLY the visible hyperlink anchor text.
    - Replace long article titles with a short news-source name (e.g., "Reuters", "UN News", "BusinessDay Nigeria", "BBC", "Al Jazeera", "Semafor").
    - Do NOT change:
    - the surrounding text
    - the URLs
    - sentence structure
    - wording
    - punctuation
    - formatting
    - Do NOT add or remove any links.
    - Do NOT summarize or rewrite content.

    RULES:
    - Every markdown link must remain a valid markdown link.
    - Only the text inside the square brackets [] may change.
    - If the source name is unclear, infer it from the URL domain.
    - Output the full revised markdown document and nothing else.

    Here is the markdown document to edit:
    {full_text}
    """

    response = client.messages.create(
        model=ANTHROPIC_RISK_BRIEFING_MODEL,
        max_tokens=10000,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    # Extract text safely
    revised_text = "".join(
        block.text for block in response.content if block.type == "text"
    )
    return revised_text