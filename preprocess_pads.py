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
    
    # Fetch full PAD text
    try:
        pad_text = fetch_pdf_text(str(pad_row["guid"]), str(pad_row["node_id"]))
    except Exception as e:
        print(f"   ❌ Error fetching PAD text: {e}")
        return None
    # switch to a model that can handle large context like sonnet 4.6
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
    
    try:
        message = chain.invoke({"pad_text": pad_text})
        raw = (message.content or "").strip()
        
        # Parse JSON
        try:
            structured_data = json.loads(raw)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code blocks
            json_start = raw.find("{")
            json_end = raw.rfind("}")
            if json_start != -1 and json_end != -1:
                structured_data = json.loads(raw[json_start:json_end+1])
            else:
                raise ValueError("Could not extract valid JSON from response")
        
        # Add metadata
        result = {
            "metadata": {
                "PROJ_ID_IB": proj_id,
                "guid": pad_row.get("guid"),
                "node_id": pad_row.get("node_id"),
                "pdf_url": pad_row.get("pdf_url"),
                "document_type": "Project Appraisal Document",
                "preprocessing_version": "1.0"
            },
            "structured_content": structured_data
        }
        
        return result
        
    except Exception as e:
        print(f"   ❌ Error preprocessing PAD: {repr(e)}")
        import traceback
        traceback.print_exc()
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
