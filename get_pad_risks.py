import pandas as pd
from document_utils import *
def select_latest_pad_per_project(country_document_df):
    
    # Filter to country
    country_df = country_document_df.copy()

    # Ensure datetime
    country_df["lupdate_dt"] = pd.to_datetime(
        country_df["lupdate"],
        errors="coerce"
    )

    # Filter to PADs only
    pad_df = country_df[
        country_df["document_type"] == "Project Appraisal Document"
    ].copy()

    if pad_df.empty:
        print("⚠️ No PAD documents found for this country.")
        return pad_df

    # Sort newest first
    pad_df = pad_df.sort_values(
        "lupdate_dt",
        ascending=False
    )

    # Keep most recent PAD per PROJ_ID_IB
    pad_df = pad_df.drop_duplicates(
        subset=["PROJ_ID_IB"],
        keep="first"
    )

    print(f"Selected {len(pad_df)} latest PADs across projects.")

    return pad_df

from langchain_core.prompts import ChatPromptTemplate
import json


def chunk_text(text, max_chars=50000, overlap=1000):
    """
    Split text into overlapping chunks to fit context window.
    
    Args:
        text: Text to chunk
        max_chars: Maximum characters per chunk
        overlap: Number of characters to overlap between chunks
    
    Returns:
        List of text chunks
    """
    if len(text) <= max_chars:
        return [text]
    
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + max_chars
        chunk = text[start:end]
        chunks.append(chunk)
        start = end - overlap
    
    return chunks


def stress_test_pad_against_country_risks(pad_row,
                                          country_risks_df,
                                          client):

    pad_text = fetch_pdf_text(str(pad_row["guid"]), str(pad_row["node_id"]))

    if not pad_text:
        return []

    pad_text = clean_text(pad_text)
    
    # Check if text needs chunking
    if len(pad_text) > 200000:
        print(f"   ⚠️ PAD text is {len(pad_text)} chars, chunking into smaller pieces...")
        chunks = chunk_text(pad_text, max_chars=200000, overlap=1000)
        print(f"   → Split into {len(chunks)} chunks")
        
        all_exposures = []
        for i, chunk in enumerate(chunks, 1):
            print(f"   → Processing chunk {i}/{len(chunks)}...")
            exposures = _analyze_pad_chunk(chunk, country_risks_df, client, pad_row)
            all_exposures.extend(exposures)
        
        # Deduplicate based on similar content
        return _deduplicate_exposures(all_exposures)
    
    else:
        return _analyze_pad_chunk(pad_text, country_risks_df, client, pad_row)


def _analyze_pad_chunk(pad_text, country_risks_df, client, pad_row):
    """Analyze a single chunk of PAD text."""

def _analyze_pad_chunk(pad_text, country_risks_df, client, pad_row):
    """Analyze a single chunk of PAD text."""

    # Use structured risks only (compact form)
    country_risks = country_risks_df[[
        "risk_id",
        "title",
        "summary",
        "themes",
        "severity"
    ]].to_dict(orient="records")

    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "You are a World Bank FCV analyst reviewing a project.\n\n"
            "You are given:\n"
            "- A list of current country-level FCV risk drivers.\n"
            "- The Project Appraisal Document (PAD) text.\n\n"
            "Your task:\n"
            "Assess where this project may be susceptible to implementation "
            "or outcome disruption given the current FCV dynamics.\n\n"
            "Think operationally:\n"
            "- Could political instability disrupt governance arrangements?\n"
            "- Could conflict affect access, logistics, or staffing?\n"
            "- Could displacement undermine targeting or beneficiary reach?\n"
            "- Could tensions between government and development actors create interference?\n\n"
            "Rules:\n"
            "- Identify only vulnerabilities supported by the PAD text.\n"
            "- Each item MUST include a verbatim evidence quote from the PAD.\n"
            "- Do NOT speculate beyond the PAD.\n"
            "- If the PAD shows no meaningful susceptibility to current FCV risks, return an empty list.\n\n"
            "Return valid JSON:\n"
            "{{\n"
            '  "project_susceptibilities": [\n'
            "    {{\n"
            '      "related_country_risk_id": "string",\n'
            '      "related_country_risk_title": "string",\n'
            '      "susceptibility_summary": "string",\n'
            '      "evidence_quote": "verbatim from PAD",\n'
            '      "confidence": 0.0\n'
            "    }}\n"
            "  ]\n"
            "}}"
        ),
        (
            "human",
            "Current Country FCV Risks:\n\n{country_risks}\n\n"
            "Project Appraisal Document (PAD):\n\n{pad_text}"
        )
    ])

    chain = prompt | client

    message = chain.invoke({
        "country_risks": json.dumps(country_risks, indent=2),
        "pad_text": pad_text
    })

    raw = (message.content or "").strip()

    try:
        parsed = json.loads(raw)
    except:
        json_start = raw.find("{")
        json_end = raw.rfind("}")
        parsed = json.loads(raw[json_start:json_end+1])

    exposures = []

    for e in parsed.get("project_susceptibilities", []):
        e["PROJ_ID_IB"] = pad_row["PROJ_ID_IB"]
        exposures.append(e)

    return exposures


def _deduplicate_exposures(exposures):
    """
    Remove duplicate exposures based on similar risk IDs and summaries.
    Keeps the one with highest confidence.
    """
    if not exposures:
        return []
    
    # Group by related_country_risk_id
    grouped = {}
    for exp in exposures:
        risk_id = exp.get("related_country_risk_id", "unknown")
        if risk_id not in grouped:
            grouped[risk_id] = []
        grouped[risk_id].append(exp)
    
    # Keep highest confidence per risk_id
    deduplicated = []
    for risk_id, group in grouped.items():
        best = max(group, key=lambda x: x.get("confidence", 0.0))
        deduplicated.append(best)
    
    return deduplicated


def run_stress_tests_for_all_pads(country_document_df, country_risks_df, client):
    """
    Run stress test for every PAD returned from select_latest_pad_per_project.
    
    Args:
        country_document_df: DataFrame with all documents for the country
        country: Country name to filter
        country_risks_df: DataFrame with country-level risks
        client: LLM client for analysis
    
    Returns:
        List of all susceptibilities found across all PADs
    """
    # Get latest PADs per project
    pads_df = select_latest_pad_per_project(country_document_df)
    
    if pads_df.empty:
        print("No PADs to test.")
        return []
    
    all_susceptibilities = []
    
    # Iterate through each PAD and run stress test
    for idx, pad_row in pads_df.iterrows():
        project_id = pad_row.get("PROJ_ID_IB", "Unknown")
        print(f"\n🔍 Testing PAD for project: {project_id}")
        
        try:
            susceptibilities = stress_test_pad_against_country_risks(
                pad_row,
                country_risks_df,
                client
            )
            
            if susceptibilities:
                print(f"   ✓ Found {len(susceptibilities)} susceptibility(ies)")
                all_susceptibilities.extend(susceptibilities)
            else:
                print(f"   - No susceptibilities detected")
                
        except Exception as e:
            print(f"   ✗ Error processing {project_id}: {e}")
            continue
    
    print(f"\n📊 Total susceptibilities found: {len(all_susceptibilities)}")
    
    return all_susceptibilities
