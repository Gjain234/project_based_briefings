import pandas as pd
from document_utils import *
from preprocess_pads import get_or_preprocess_pad
from prompts import PAD_STRESS_TEST_SYSTEM_PROMPT
import json
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
                                          client,
                                          country,
                                          reasoning_client=None,
                                          preprocessed_pad=None):
    """
    Test a PAD against country risks using preprocessed PAD data.
    
    Args:
        pad_row: DataFrame row with PAD metadata
        country_risks_df: DataFrame with country risks
        client: LLM client for risk analysis
        country: Country name (for caching preprocessed PADs)
        reasoning_client: Optional higher-reasoning client for PAD preprocessing
        preprocessed_pad: Optional preprocessed PAD data (if already loaded)
    """
    
    # Use reasoning_client for preprocessing if provided, otherwise use standard client
    preprocess_client = reasoning_client if reasoning_client else client
    
    # Get or create preprocessed PAD
    if preprocessed_pad is None:
        preprocessed_pad = get_or_preprocess_pad(pad_row, country, preprocess_client)
    
    if not preprocessed_pad:
        print(f"   ❌ Could not get preprocessed PAD data")
        return []
    
    # Convert preprocessed data to compact text format for analysis
    pad_content = _format_preprocessed_pad_for_analysis(preprocessed_pad)
    
    # Use standard client for risk analysis (faster)
    return _analyze_pad_content(pad_content, country_risks_df, client, pad_row)


def _format_preprocessed_pad_for_analysis(preprocessed_pad):
    """
    Convert preprocessed PAD JSON into a compact text format for risk analysis.
    
    Args:
        preprocessed_pad: Preprocessed PAD dictionary
        
    Returns:
        str: Formatted text representation
    """
    content = preprocessed_pad.get("structured_content", {})
    
    sections = []
    
    # Project overview
    overview = content.get("project_overview", {})
    sections.append(f"PROJECT: {overview.get('project_name', 'N/A')}")
    sections.append(f"OBJECTIVE: {overview.get('project_development_objective', 'N/A')}")
    sections.append(f"FINANCING: {overview.get('total_financing', 'N/A')}")
    sections.append(f"BENEFICIARIES: {overview.get('beneficiaries', 'N/A')}")
    
    # Geographic scope
    geo = content.get("geographic_scope", {})
    sections.append(f"\nLOCATIONS: {', '.join(geo.get('primary_locations', []))}")
    sections.append(f"COVERAGE: {geo.get('coverage_type', 'N/A')}")
    sections.append(f"CONFLICT-AFFECTED AREAS: {geo.get('fragile_or_conflict_affected_areas', 'N/A')}")
    
    # Components
    components = content.get("key_components", [])
    if components:
        sections.append("\nCOMPONENTS:")
        for comp in components:
            sections.append(f"  - {comp.get('component_name')}: {comp.get('description')} ({comp.get('financing', 'N/A')})")
    
    # Implementation
    impl = content.get("implementation_arrangements", {})
    sections.append(f"\nIMPLEMENTING AGENCY: {impl.get('implementing_agency', 'N/A')}")
    sections.append(f"COORDINATION: {impl.get('coordination_mechanisms', 'N/A')}")
    sections.append(f"M&E: {impl.get('monitoring_and_evaluation', 'N/A')}")
    
    # Identified risks from PAD
    risks = content.get("identified_risks", [])
    if risks:
        sections.append("\nIDENTIFIED RISKS IN PAD:")
        for risk in risks:
            sections.append(f"  - {risk.get('risk_category')} ({risk.get('risk_rating')}): {risk.get('risk_description')}")
            sections.append(f"    Mitigation: {risk.get('mitigation_measures')}")
    
    # Safeguards and social
    safeguards = content.get("safeguards_and_social", {})
    sections.append(f"\nSAFEGUARDS: {safeguards.get('environmental_category', 'N/A')}")
    if safeguards.get('triggered_safeguard_policies'):
        sections.append(f"TRIGGERED POLICIES: {', '.join(safeguards.get('triggered_safeguard_policies', []))}")
    sections.append(f"GRM: {safeguards.get('grievance_redress_mechanism', 'N/A')}")
    sections.append(f"VULNERABLE GROUPS: {', '.join(safeguards.get('vulnerable_groups', []))}")
    
    # FCV relevant
    fcv = content.get("fcv_relevant_details", {})
    sections.append(f"\nCONFLICT SENSITIVITY: {fcv.get('conflict_sensitivity', 'N/A')}")
    sections.append(f"FRAGILITY CONTEXT: {fcv.get('fragility_context', 'N/A')}")
    sections.append(f"SECURITY: {fcv.get('security_considerations', 'N/A')}")
    sections.append(f"DISPLACEMENT/REFUGEES: {fcv.get('displacement_or_refugees', 'N/A')}")
    
    return "\n".join(sections)


def _analyze_pad_content(pad_content, country_risks_df, client, pad_row):
    """Analyze preprocessed PAD content against country risks."""

def _analyze_pad_content(pad_content, country_risks_df, client, pad_row):
    """Analyze preprocessed PAD content against country risks."""

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
            PAD_STRESS_TEST_SYSTEM_PROMPT
        ),
        (
            "human",
            "Current Country FCV Risks:\n\n{country_risks}\n\n"
            "Project Information from PAD:\n\n{pad_content}"
        )
    ])

    chain = prompt | client

    message = chain.invoke({
        "country_risks": json.dumps(country_risks, indent=2),
        "pad_content": pad_content
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
        # Rename field for consistency
        if "evidence_from_pad" in e:
            e["evidence_quote"] = e.pop("evidence_from_pad")
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


def run_stress_tests_for_all_pads(country_document_df, country_risks_df, client, country, reasoning_client=None):
    """
    Run stress test for every PAD returned from select_latest_pad_per_project.
    Uses preprocessed PADs for efficiency.
    
    Args:
        country_document_df: DataFrame with all documents for the country
        country_risks_df: DataFrame with country-level risks
        client: LLM client for analysis (standard/fast model)
        country: Country name (for preprocessing cache)
        reasoning_client: Optional higher-reasoning client for PAD preprocessing
    
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
                client,
                country,
                reasoning_client
            )
            
            if susceptibilities:
                print(f"   ✓ Found {len(susceptibilities)} susceptibility(ies)")
                all_susceptibilities.extend(susceptibilities)
            else:
                print(f"   - No susceptibilities detected")
                
        except Exception as e:
            print(f"   ✗ Error processing {project_id}: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    print(f"\n📊 Total susceptibilities found: {len(all_susceptibilities)}")
    
    return all_susceptibilities
