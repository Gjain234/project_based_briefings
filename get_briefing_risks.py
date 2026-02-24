from langchain_core.prompts import ChatPromptTemplate
import pandas as pd
import json
import uuid

COUNTRY_THEMES = [
    "governance",
    "political",
    "security",
    "economy",
    "health",
    "environment",
    "social",
    "humanitarian",
    "displacement",
    "crime"
]

def extract_country_risk_items(risk_briefing: str, client):

    if not isinstance(risk_briefing, str) or not risk_briefing.strip():
        raise ValueError("risk_briefing must be a non-empty string.")

    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "You are a World Bank FCV analyst extracting structured country-level risk items "
            "from a risk briefing.\n\n"
            "Rules:\n"
            "- Use ONLY information explicitly stated in the briefing.\n"
            "- Do NOT introduce new facts.\n"
            "- Create 6–12 distinct risk items.\n"
            "- Each item must represent one clear risk.\n"
            "- Avoid duplication.\n"
            "- Summaries should be concise (2–4 sentences).\n"
            f"- Assign 1–3 theme tags from this allowed list only: {COUNTRY_THEMES}\n"
            "- Provide 3–8 keywords per risk.\n\n"
            "Return valid JSON in this exact format:\n"
            "{{\n"
            '  "risks": [\n'
            "    {{\n"
            '      "risk_id": "string",\n'
            '      "title": "string",\n'
            '      "summary": "string",\n'
            '      "themes": ["string"],\n'
            '      "keywords": ["string"],\n'
            '      "severity": "low|medium|high|unknown",\n'
            '      "time_horizon": "current|0-3m|3-12m|unknown"\n'
            "    }}\n"
            "  ]\n"
            "}}"
        ),
        (
            "human",
            "Here is the country FCV risk briefing:\n\n{risk_briefing}"
        )
    ])

    chain = prompt | client

    message = chain.invoke({"risk_briefing": risk_briefing})

    raw_output = (message.content or "").strip()

    # -----------------------------
    # Parse JSON safely
    # -----------------------------
    try:
        parsed = json.loads(raw_output)
    except json.JSONDecodeError:
        # Attempt to extract JSON block if model wrapped it in markdown
        json_start = raw_output.find("{")
        json_end = raw_output.rfind("}")
        parsed = json.loads(raw_output[json_start:json_end+1])

    risks = parsed.get("risks", [])

    # -----------------------------
    # Light cleanup / validation
    # -----------------------------
    cleaned = []
    for r in risks:
        if not r.get("risk_id"):
            r["risk_id"] = "cr_" + uuid.uuid4().hex[:8]

        r["themes"] = [t for t in r.get("themes", []) if t in COUNTRY_THEMES]

        if not isinstance(r.get("keywords"), list):
            r["keywords"] = []

        cleaned.append(r)

    country_risks_df = pd.DataFrame(cleaned)

    return country_risks_df
