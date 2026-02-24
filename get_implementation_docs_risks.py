from langchain_core.prompts import ChatPromptTemplate
import uuid
import json
from document_utils import *
import pandas as pd

def extract_all_realized_fcv_risks(country_document_df, client):
    project_docs_df = select_recent_project_docs(country_document_df)
    all_risks = []

    for _, row in project_docs_df.iterrows():
        print(f"📄 Processing {row['PROJ_ID_IB']} - {row['document_type']}")

        risks = extract_realized_fcv_risks_from_doc(row, client)

        if risks:
            print(f"   ✓ Found {len(risks)} FCV risks")
            all_risks.extend(risks)
        else:
            print("   - No FCV risks found")

    return pd.DataFrame(all_risks)


def extract_realized_fcv_risks_from_doc(row, client):

    text = fetch_pdf_text(str(row["guid"]), str(row["node_id"]))
    print(f"Text url: {row['text_url']}")
    print(f"PDF url: {row['pdf_url']}")
    if not text:
        return []

    text = clean_text(text)

    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "You are a World Bank FCV analyst reviewing a project implementation document.\n\n"
            "Extract realized or emerging FCV-related risks affecting project implementation.\n\n"
            "FCV includes:\n"
            "- Political instability, governance fragility, protests\n"
            "- Conflict and violence dynamics\n"
            "- Displacement or refugee pressures\n"
            "- Tensions between government and development actors\n\n"
            "Rules:\n"
            "- Extract only risks already affecting implementation.\n"
            "- Do NOT extract generic fiduciary or procurement issues unless clearly FCV-linked.\n"
            "- Each risk must include a verbatim evidence quote.\n"
            "- Keep risks atomic.\n\n"
            "Return valid JSON:\n"
            "{{\n"
            '  "fcv_risks": [\n'
            "    {{\n"
            '      "risk_title": "string",\n'
            '      "risk_summary": "string",\n'
            '      "severity": "low|medium|high|unclear",\n'
            '      "direction": "new|worsening|persistent|improving|unclear",\n'
            '      "evidence_quote": "verbatim"\n'
            "    }}\n"
            "  ]\n"
            "}}"
        ),
        (
            "human",
            "Document text:\n\n{document_text}"
        )
    ])

    chain = prompt | client

    message = chain.invoke({"document_text": text})
    raw = (message.content or "").strip()

    try:
        parsed = json.loads(raw)
    except:
        json_start = raw.find("{")
        json_end = raw.rfind("}")
        parsed = json.loads(raw[json_start:json_end+1])

    extracted = []

    for r in parsed.get("fcv_risks", []):
        r["realized_risk_id"] = uuid.uuid4().hex[:8]
        r["PROJ_ID_IB"] = row["PROJ_ID_IB"]
        r["doc_type"] = row["document_type"]
        r["doc_date"] = row["lupdate"]
        extracted.append(r)

    return extracted


def select_recent_project_docs(country_document_df):
    """
    Select most recent 2 ISR and 2 Aide Memoire per project.
    Returns DataFrame of selected documents.
    """
    country_df = country_document_df.copy()
    country_df["lupdate_dt"] = pd.to_datetime(
        country_df["lupdate"],
        errors="coerce"
    )

    # Only ISR + Aide
    project_docs = country_df[
        country_df["document_type"].isin([
            "Implementation Status and Results Report",
            "Aide Memoire"
        ])
    ].copy()

    project_docs = project_docs.sort_values(
        "lupdate_dt",
        ascending=False
    )

    # Keep top 2 per project per document type
    project_docs = project_docs.groupby(
        ["PROJ_ID_IB", "document_type"]
    ).head(2)

    return project_docs


def map_realized_risk_to_country_risks(realized_risk_row,
                                       country_risks_df,
                                       client):

    # Keep only compact fields for token efficiency
    country_risks = country_risks_df[[
        "risk_id",
        "title",
        "summary",
        "themes"
    ]].to_dict(orient="records")

    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "You are a World Bank FCV analyst.\n\n"
            "Assess whether the realized project implementation risk "
            "is plausibly connected to any of the current country-level FCV risks.\n\n"
            "Guidelines:\n"
            "- Identify only meaningful substantive connections.\n"
            "- Do NOT force connections.\n"
            "- A connection should reflect shared political, conflict, displacement, "
            "or institutional fragility dynamics.\n\n"
            "Return valid JSON:\n"
            "{{\n"
            '  "connections": [\n'
            "    {{\n"
            '      "country_risk_id": "string",\n'
            '      "country_risk_title": "string",\n'
            '      "connection_summary": "string",\n'
            '      "confidence": 0.0\n'
            "    }}\n"
            "  ]\n"
            "}}"
        ),
        (
            "human",
            "Current Country FCV Risks:\n\n{country_risks}\n\n"
            "Realized Project Risk:\n\n{realized_risk}"
        )
    ])

    chain = prompt | client

    message = chain.invoke({
        "country_risks": json.dumps(country_risks, indent=2),
        "realized_risk": json.dumps(realized_risk_row.to_dict(), indent=2)
    })

    raw = (message.content or "").strip()

    try:
        parsed = json.loads(raw)
    except:
        json_start = raw.find("{")
        json_end = raw.rfind("}")
        parsed = json.loads(raw[json_start:json_end+1])

    connections = []

    for c in parsed.get("connections", []):
        c["PROJ_ID_IB"] = realized_risk_row["PROJ_ID_IB"]
        c["realized_risk_id"] = realized_risk_row["realized_risk_id"]
        c["doc_type"] = realized_risk_row["doc_type"]  # Include document type for citations
        connections.append(c)

    return connections


def map_all_realized_risks_to_country(realized_fcv_risks_df,
                                      country_risks_df,
                                      client):

    all_links = []

    for _, row in realized_fcv_risks_df.iterrows():

        links = map_realized_risk_to_country_risks(
            row,
            country_risks_df,
            client
        )

        if links:
            all_links.extend(links)

    return pd.DataFrame(all_links)
