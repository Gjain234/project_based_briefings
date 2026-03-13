from langchain_core.prompts import ChatPromptTemplate
from prompts import IMPLEMENTATION_RISK_EXTRACTION_SYSTEM_PROMPT, RISK_MAPPING_SYSTEM_PROMPT
import uuid
import json
import os
import hashlib
import re
from document_utils import *
import pandas as pd

def fix_json_string(raw_text):
    """
    Attempt to fix common JSON formatting issues from LLM output.
    
    Fixes:
    - Extracts JSON from markdown code blocks
    - Handles unescaped quotes in string values
    - Replaces literal newlines with spaces in quoted strings
    """
    # Try to extract from markdown code block first
    if "```json" in raw_text:
        json_start = raw_text.find("```json") + 7
        json_end = raw_text.find("```", json_start)
        if json_end > json_start:
            raw_text = raw_text[json_start:json_end].strip()
    
    # Find JSON object boundaries
    json_start = raw_text.find("{")
    json_end = raw_text.rfind("}")
    if json_start >= 0 and json_end > json_start:
        raw_text = raw_text[json_start:json_end+1]
    
    # Replace literal newlines with spaces within quoted strings
    # This regex finds quoted strings and replaces internal newlines
    def replace_newlines_in_strings(text):
        def replacer(match):
            # Get the quoted string content
            content = match.group(1)
            # Replace newlines and multiple spaces with single space
            content = content.replace('\n', ' ').replace('\r', ' ')
            content = re.sub(r' +', ' ', content).strip()
            return f'"{content}"'
        # Match quoted strings (handles escaped quotes)
        return re.sub(r'"((?:[^"\\]|\\.)*)"', replacer, text)
    
    raw_text = replace_newlines_in_strings(raw_text)
    
    return raw_text

def get_document_cache_key(row):
    """Generate a unique cache key for a document based on project ID, document type, and node ID."""
    proj_id = str(row['PROJ_ID_IB'])
    doc_type = str(row['document_type']).replace(' ', '_').replace('/', '_')
    node_id = str(row.get('node_id', row.get('guid', '')))
    # Use hash of node_id to keep filename reasonable length
    node_hash = hashlib.md5(node_id.encode()).hexdigest()[:8]
    return f"{proj_id}_{doc_type}_{node_hash}"

def extract_all_realized_fcv_risks(country_document_df, client, country=None):
    """Extract FCV risks from documents, using individual document-level caching.
    
    Args:
        country_document_df: DataFrame with documents for the country
        client: LLM client
        country: Country name for organizing cache (optional but recommended)
    """
    project_docs_df = select_recent_project_docs(country_document_df)
    all_risks = []
    
    # Organize cache by country if provided
    if country:
        cache_dir = f"intermediary_outputs/implementation_risks_cache/{country}"
    else:
        cache_dir = "intermediary_outputs/implementation_risks_cache"
    
    # Create cache directory if it doesn't exist
    os.makedirs(cache_dir, exist_ok=True)
    
    # Check if all expected documents are already cached
    missing_docs = []
    for _, row in project_docs_df.iterrows():
        cache_key = get_document_cache_key(row)
        cache_path = os.path.join(cache_dir, f"{cache_key}.csv")
        if not os.path.exists(cache_path):
            missing_docs.append((row['PROJ_ID_IB'], row['document_type']))
    
    if missing_docs:
        print(f"   ⚠️ {len(missing_docs)} implementation doc(s) not yet cached: ")
        for proj_id, doc_type in missing_docs[:5]:
            print(f"      - {proj_id} ({doc_type})")
        if len(missing_docs) > 5:
            print(f"      ... and {len(missing_docs) - 5} more")
        print(f"   Will process all documents to ensure completeness")

    for _, row in project_docs_df.iterrows():
        print(f"📄 Processing {row['PROJ_ID_IB']} - {row['document_type']}")
        
        # Check if this specific document is already cached
        cache_key = get_document_cache_key(row)
        cache_path = os.path.join(cache_dir, f"{cache_key}.csv")
        
        if os.path.exists(cache_path):
            try:
                print(f"   ✓ Loading from cache: {cache_key}")
                cached_df = pd.read_csv(cache_path)
                if not cached_df.empty:
                    cached_risks = cached_df.to_dict('records')
                    all_risks.extend(cached_risks)
                else:
                    print(f"   - No risks in cache (previously processed with no results)")
            except Exception as e:
                print(f"   ⚠️ Error reading cache for {cache_key}: {e}")
                print(f"   → Will reprocess this document")
                # Reprocess if cache is corrupted
                risks = extract_realized_fcv_risks_from_doc(row, client)
                if risks:
                    print(f"   ✓ Found {len(risks)} FCV risks")
                    pd.DataFrame(risks).to_csv(cache_path, index=False)
                    print(f"   ✓ Cached to: {cache_key}")
                    all_risks.extend(risks)
                else:
                    print("   - No FCV risks found")
                    # Save empty cache with proper columns
                    empty_cache = pd.DataFrame(columns=[
                        'realized_risk_id', 'PROJ_ID_IB', 'doc_type', 'doc_date',
                        'risk_title', 'risk_summary', 'severity', 'direction', 'evidence_quote'
                    ])
                    empty_cache.to_csv(cache_path, index=False)
        else:
            # Extract risks from document
            risks = extract_realized_fcv_risks_from_doc(row, client)

            if risks:
                print(f"   ✓ Found {len(risks)} FCV risks")
                # Save to individual cache
                pd.DataFrame(risks).to_csv(cache_path, index=False)
                print(f"   ✓ Cached to: {cache_key}")
                all_risks.extend(risks)
            else:
                print("   - No FCV risks found")
                # Save empty cache with proper columns to avoid reprocessing
                # Use the expected column structure
                empty_cache = pd.DataFrame(columns=[
                    'realized_risk_id', 'PROJ_ID_IB', 'doc_type', 'doc_date',
                    'risk_title', 'risk_summary', 'severity', 'direction', 'evidence_quote'
                ])
                empty_cache.to_csv(cache_path, index=False)

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
            IMPLEMENTATION_RISK_EXTRACTION_SYSTEM_PROMPT
        ),
        (
            "human",
            "Document text:\n\n{document_text}"
        )
    ])

    chain = prompt | client

    message = chain.invoke({"document_text": text})
    raw = (message.content or "").strip()

    # Try multiple approaches to parse JSON
    parsed = None
    last_error = None
    
    # Approach 1: Direct parse
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        last_error = e
        # Approach 2: Clean and retry
        try:
            cleaned = fix_json_string(raw)
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as e2:
            last_error = e2
            # Approach 3: Try extracting just the fcv_risks array
            try:
                fcv_start = raw.lower().find('"fcv_risks"')
                if fcv_start >= 0:
                    array_start = raw.find("[", fcv_start)
                    array_end = raw.rfind("]")
                    if array_start >= 0 and array_end > array_start:
                        array_str = raw[array_start:array_end+1]
                        # Try to parse as array directly
                        fcv_array = json.loads(array_str)
                        parsed = {"fcv_risks": fcv_array}
            except json.JSONDecodeError as e3:
                last_error = e3
    
    if parsed is None:
        print(f"   ⚠️  JSON parsing failed after all cleanup attempts")
        print(f"   Error: {str(last_error)}")
        print(f"   Raw output (first 800 chars): {raw[:800]}")
        print(f"   → Skipping document due to malformed LLM response")
        # Return empty list if JSON is completely malformed
        return []

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
            RISK_MAPPING_SYSTEM_PROMPT
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
