"""
Preprocessing module for Project Appraisal Documents (PADs).

Extracts and structures PAD content into high-density JSON format for faster reuse.
Uses a higher reasoning model to handle large PAD documents.
"""

import os
import json
import hashlib
from pathlib import Path
from langchain_core.prompts import ChatPromptTemplate
from document_utils import fetch_pdf_text


def _parse_json_response(raw_response):
    """Parse JSON response, including fallback extraction from code fences/text."""
    raw = (raw_response or "").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        json_start = raw.find("{")
        json_end = raw.rfind("}")
        if json_start != -1 and json_end != -1 and json_end > json_start:
            return json.loads(raw[json_start:json_end + 1])
        raise ValueError("Could not extract valid JSON from response")


def _is_context_or_token_limit_error(error):
    error_str = str(error).lower()
    return any(marker in error_str for marker in [
        "context",
        "tokens",
        "overflow",
        "token limit will exceed",
        "estimated request tokens",
        "rate limit",
        "statuscode",
        "429"
    ])


def get_pad_cache_path(proj_id, country):
    """
    Get the cache file path for a preprocessed PAD.
    
    Args:
        proj_id: Project ID (PROJ_ID_IB)
        country: Country name for folder organization
        
    Returns:
        Path to the cached JSON file
    """
    cache_dir = Path("preprocessed_pads") / country
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / f"{proj_id}_preprocessed.json"


def is_pad_preprocessed(proj_id, country, pad_row):
    """
    Check if a PAD has already been preprocessed.
    
    Args:
        proj_id: Project ID
        country: Country name
        pad_row: DataFrame row containing PAD metadata
        
    Returns:
        tuple: (bool, dict or None) - (is_cached, cached_data)
    """
    cache_path = get_pad_cache_path(proj_id, country)
    
    if not cache_path.exists():
        return False, None
    
    try:
        with open(cache_path, 'r', encoding='utf-8') as f:
            cached_data = json.load(f)
        
        # Verify the cached data matches current document
        # Check if guid/node_id match to ensure it's the same document version
        if (cached_data.get('metadata', {}).get('guid') == pad_row.get('guid') and
            cached_data.get('metadata', {}).get('node_id') == pad_row.get('node_id')):
            return True, cached_data
        else:
            print(f"   ⚠️  Cached version outdated for {proj_id}, will reprocess")
            return False, None
            
    except Exception as e:
        print(f"   ⚠️  Error reading cache for {proj_id}: {e}")
        return False, None


def preprocess_pad(pad_row, client):
    """
    Extract structured information from a PAD document.
    
    Args:
        pad_row: DataFrame row containing PAD metadata
        client: LLM client (should support large context)
        
    Returns:
        dict: Structured PAD information
    """
    proj_id = pad_row.get("PROJ_ID_IB", "Unknown")
    
    print(f"   📄 Preprocessing PAD for {proj_id}...")
    
    # Use pre-fetched text if available, otherwise fetch from URL
    try:
        pad_text = str(pad_row.get("document_text") or "").strip()
        if not pad_text:
            pad_text = fetch_pdf_text(str(pad_row["guid"]), str(pad_row["node_id"]))
    except Exception as e:
        print(f"   ❌ Error fetching PAD text: {e}")
        return None
    
    original_pad_text = pad_text
    
    # Extract structured information using LLM
    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "You are analyzing a World Bank Project Appraisal Document (PAD).\n\n"
            "Extract and structure key information into a high-density JSON format.\n"
            "Focus on information relevant for FCV risk assessment.\n\n"
            "Return ONLY valid JSON with the following structure:\n"
            "{{\n"
            '  "project_overview": {{\n'
            '    "project_name": "string",\n'
            '    "project_development_objective": "string",\n'
            '    "total_financing": "string (with currency)",\n'
            '    "implementation_period": "string",\n'
            '    "beneficiaries": "string"\n'
            "  }},\n"
            '  "geographic_scope": {{\n'
            '    "primary_locations": ["list of regions/provinces/cities"],\n'
            '    "coverage_type": "national/regional/local",\n'
            '    "fragile_or_conflict_affected_areas": "yes/no/partial with details"\n'
            "  }},\n"
            '  "key_components": [\n'
            "    {{\n"
            '      "component_name": "string",\n'
            '      "description": "concise summary",\n'
            '      "financing": "string (amount)"\n'
            "    }}\n"
            "  ],\n"
            '  "implementation_arrangements": {{\n'
            '    "implementing_agency": "string",\n'
            '    "coordination_mechanisms": "string",\n'
            '    "procurement_approach": "string",\n'
            '    "monitoring_and_evaluation": "string"\n'
            "  }},\n"
            '  "identified_risks": [\n'
            "    {{\n"
            '      "risk_category": "string (e.g., political, security, institutional, fiduciary)",\n'
            '      "risk_description": "string",\n'
            '      "risk_rating": "high/substantial/moderate/low",\n'
            '      "mitigation_measures": "string"\n'
            "    }}\n"
            "  ],\n"
            '  "safeguards_and_social": {{\n'
            '    "environmental_category": "string",\n'
            '    "triggered_safeguard_policies": ["list"],\n'
            '    "grievance_redress_mechanism": "yes/no with details",\n'
            '    "gender_considerations": "string",\n'
            '    "vulnerable_groups": ["list"]\n'
            "  }},\n"
            '  "fcv_relevant_details": {{\n'
            '    "conflict_sensitivity": "string (how project addresses conflict risks)",\n'
            '    "fragility_context": "string (key fragility factors mentioned)",\n'
            '    "security_considerations": "string",\n'
            '    "displacement_or_refugees": "yes/no with details"\n'
            "  }}\n"
            "}}\n\n"
            "Be thorough. Extract actual content from the PAD.\n"
            "If a field is not applicable or not found, use empty string or empty array."
        ),
        (
            "human",
            "Project Appraisal Document:\n\n{pad_text}"
        )
    ])
    
    chain = prompt | client
    
    # Keep retrying with progressively smaller tails until success or minimum floor.
    truncation_plan = [760000, 600000, 500000, 400000, 300000, 220000, 160000, 120000, 90000, 70000, 50000, 35000, 25000]
    last_error = None

    for attempt, max_chars in enumerate(truncation_plan, start=1):
        truncated = len(original_pad_text) > max_chars
        candidate_text = original_pad_text[-max_chars:] if truncated else original_pad_text

        if truncated:
            approx_tokens = max_chars // 4
            candidate_text = (
                f"[NOTE: This PAD exceeds context limits. Displaying approximately the LAST ~{approx_tokens} tokens of the document.]\n\n"
                f"{candidate_text}"
            )

        try:
            if attempt == 1 and truncated:
                print(
                    f"   ⚠️  PAD is {len(original_pad_text)} chars (~{len(original_pad_text)//4} tokens), "
                    f"starting with last {max_chars} chars"
                )
            elif attempt > 1:
                print(f"   ↻ Retry {attempt}/{len(truncation_plan)} with last {max_chars} chars")

            message = chain.invoke({"pad_text": candidate_text})
            structured_data = _parse_json_response(message.content)

            result = {
                "metadata": {
                    "PROJ_ID_IB": proj_id,
                    "guid": pad_row.get("guid"),
                    "node_id": pad_row.get("node_id"),
                    "pdf_url": pad_row.get("pdf_url"),
                    "document_type": "Project Appraisal Document",
                    "preprocessing_version": "1.0",
                    "truncated": truncated,
                    "truncation_chars": max_chars if truncated else len(original_pad_text)
                },
                "structured_content": structured_data
            }

            if attempt > 1:
                print(f"   ✓ Successfully preprocessed after iterative truncation (attempt {attempt})")
            return result

        except Exception as e:
            last_error = e
            if _is_context_or_token_limit_error(e):
                if attempt < len(truncation_plan):
                    print("   ⚠️  Context/token limit issue detected, truncating further...")
                    continue
                print("   ❌ Reached minimum truncation threshold and still hit token/context limits")
                break

            print(f"   ❌ Error preprocessing PAD: {repr(e)}")
            import traceback
            traceback.print_exc()
            return None

    if last_error is not None:
        print(f"   ❌ Failed to preprocess PAD after all truncation attempts: {repr(last_error)}")
    return None


def save_preprocessed_pad(preprocessed_data, proj_id, country):
    """
    Save preprocessed PAD data to cache.
    
    Args:
        preprocessed_data: Structured PAD data
        proj_id: Project ID
        country: Country name
    """
    cache_path = get_pad_cache_path(proj_id, country)
    
    try:
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(preprocessed_data, f, indent=2, ensure_ascii=False)
        print(f"   ✅ Saved preprocessed PAD to {cache_path}")
    except Exception as e:
        print(f"   ❌ Error saving preprocessed PAD: {e}")


def get_or_preprocess_pad(pad_row, country, client):
    """
    Get preprocessed PAD data from cache or preprocess if needed.
    
    Args:
        pad_row: DataFrame row containing PAD metadata
        country: Country name
        client: LLM client for preprocessing
        
    Returns:
        dict: Preprocessed PAD data or None if failed
    """
    proj_id = pad_row.get("PROJ_ID_IB", "Unknown")
    
    # Check cache first
    is_cached, cached_data = is_pad_preprocessed(proj_id, country, pad_row)
    
    if is_cached:
        print(f"   ✓ Using cached preprocessed PAD for {proj_id}")
        return cached_data
    
    # Preprocess if not cached
    print(f"   → Preprocessing PAD for {proj_id} (not in cache)")
    preprocessed_data = preprocess_pad(pad_row, client)
    
    if preprocessed_data:
        save_preprocessed_pad(preprocessed_data, proj_id, country)
        return preprocessed_data
    else:
        print(f"   ⚠️ Failed to preprocess PAD for {proj_id}, will skip this PAD")
        return None


def preprocess_all_pads_for_country(country_document_df, country, client):
    """
    Preprocess all PADs for a country (useful for batch processing).
    
    Args:
        country_document_df: DataFrame with all documents for the country
        country: Country name
        client: LLM client
        
    Returns:
        dict: {proj_id: preprocessed_data}
    """
    from get_pad_risks import select_latest_pad_per_project
    
    # Get latest PADs
    pads_df = select_latest_pad_per_project(country_document_df)
    
    if pads_df.empty:
        print(f"No PADs found for {country}")
        return {}
    
    print(f"\n📦 Preprocessing {len(pads_df)} PAD(s) for {country}")
    
    results = {}
    for idx, pad_row in pads_df.iterrows():
        proj_id = pad_row.get("PROJ_ID_IB", "Unknown")
        preprocessed_data = get_or_preprocess_pad(pad_row, country, client)
        if preprocessed_data:
            results[proj_id] = preprocessed_data
    
    print(f"\n✅ Preprocessed {len(results)} PAD(s)")
    return results
