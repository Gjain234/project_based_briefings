from get_country_briefing import get_country_recent_risks_briefing, extract_country_risks_with_websearch
import pandas as pd
from briefing_config import (
    get_document_df_path, 
    ANTHROPIC_FINAL_BRIEFING_MODEL,
    ANTHROPIC_PAD_PREPROCESSING_MODEL,
    ANTHROPIC_PAD_STRESS_TEST_MODEL,
    ANTHROPIC_IMPLEMENTATION_RISK_MODEL,
    ANTHROPIC_RISK_MAPPING_MODEL,
    MAX_BRIEFING_INPUT_LENGTH,
    MAX_PROJECTS_FOR_BRIEFING
)
from briefing_setup import setup, get_client_for_model
from get_briefing_risks import extract_country_risk_items
from get_pad_risks import run_stress_tests_for_all_pads
from get_implementation_docs_risks import extract_all_realized_fcv_risks, map_all_realized_risks_to_country
from generate_briefing import generate_briefing
from country_name_mapping import get_possible_wb_country_names, get_country_id_key
from local_media_sources import log_country_media_source_injection
import os
from datetime import datetime

def get_fcv_content_from_docs(country, mode='risk', n_paragraphs=5, custom_categories=None, save_outputs=False,internal=False, force_regenerate=False, status_callback=None, custom_prompt=None, stream_callback=None):
    """Generate FCV briefing with optional status updates.
    
    Args:
        status_callback: Optional function to call with status updates (str)
        custom_prompt: Optional custom system prompt to override defaults
        stream_callback: Optional function to call with streamed briefing chunks
    """
    def update_status(msg):
        if status_callback:
            status_callback(msg)
        print(msg)
    save_folder = "intermediary_outputs"
    
    # Define file paths
    briefing_risks_path = f"{save_folder}/{country}_briefing_risks.csv"
    briefing_risks_metadata_path = f"{save_folder}/{country}_briefing_risks_metadata.json"
    pad_risks_path = f"{save_folder}/{country}_pad_risks.csv"
    implementation_risks_path = f"{save_folder}/{country}_implementation_realized_risks.csv"
    implementation_mapped_path = f"{save_folder}/{country}_implementation_realized_risks_mapped.csv"
    
    # Add timestamp to briefing output to avoid overwriting
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    briefing_output_path = f"{save_folder}/final_{country}_{mode}_briefing_{timestamp}.md"
    
    # Create folder if saving
    if save_outputs and not os.path.exists(save_folder):
        os.makedirs(save_folder)
    
    # ALWAYS load document_df and country_document_df since we need it for link injection
    # Use appropriate CSV based on internal/external usage
    document_df_path = get_document_df_path(internal=internal)
    document_df = pd.read_csv(document_df_path)

    # Always log local media source injection intent so users can verify behavior,
    # even when country risks are loaded from cache.
    log_country_media_source_injection(country)
    
    # Get all possible World Bank country name variants for this country
    possible_country_names = get_possible_wb_country_names(country)
    country_document_df = document_df[
        document_df["CNTRY_SHORT_NAME"].isin(possible_country_names)
    ].copy()
    
    if country_document_df.empty:
        print(f"⚠️  Warning: No documents found for country '{country}'")
        print(f"    Searched for variants: {possible_country_names}")
        print(f"    Available countries in data: {sorted(document_df['CNTRY_SHORT_NAME'].unique())[:10]}...")
    
    # Initialize clients lazily when first needed
    client = None
    reasoning_client = None
    
    # Load or generate briefing risks
    should_regenerate_risks = force_regenerate
    
    if os.path.exists(briefing_risks_path) and not force_regenerate:
        # Load metadata to show when it was last generated
        if os.path.exists(briefing_risks_metadata_path):
            import json
            with open(briefing_risks_metadata_path, 'r') as f:
                metadata = json.load(f)
                last_generated = metadata.get('generated_at', 'Unknown')
                # Parse and format to show only date
                try:
                    dt = datetime.strptime(last_generated, "%Y-%m-%d %H:%M:%S")
                    date_only = dt.strftime("%Y-%m-%d")
                except:
                    date_only = last_generated.split()[0] if ' ' in last_generated else last_generated
                update_status(f"📂 Loading existing country risks (from {date_only})")
                print("   Note: country risk extraction was not re-run; loaded cached risks and skipped fresh websearch extraction.")
        else:
            update_status("📂 Loading existing country risks")
            print("   Note: country risk extraction was not re-run; loaded cached risks and skipped fresh websearch extraction.")
        
        briefing_risks_df = pd.read_csv(briefing_risks_path)
    else:
        # Initialize clients if not already done
        if client is None:
            client, reasoning_client = setup(internal=internal)
        
        if force_regenerate:
            update_status("🌐 Fetching latest country risks from ICG/CrisisWatch...")
        else:
            update_status("🌐 Generating country risk briefing...")
        
        # Try to map to country_ids format for ICG lookup
        icg_country_name = get_country_id_key(country)
        
        if icg_country_name:
            print(f"   Using '{icg_country_name}' for ICG lookup")
            # Use new combined function that extracts risks directly with web search
            briefing_risks_df = extract_country_risks_with_websearch(icg_country_name)
        else:
            print(f"   ⚠️  No ICG mapping found for '{country}' - generating briefing without ICG data")
            briefing_risks_df = extract_country_risks_with_websearch(country)
        
        if save_outputs:
            # Save the extracted risks
            briefing_risks_df.to_csv(briefing_risks_path, index=False)
            
            # Save metadata with timestamp
            import json
            metadata = {
                'generated_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'country': country,
                'icg_country_name': icg_country_name
            }
            with open(briefing_risks_metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            print(f"  ✓ Saved to {briefing_risks_path}")
            print(f"  ✓ Saved metadata to {briefing_risks_metadata_path}")
    
    # Load or generate PAD risks
    should_regenerate_pad_risks = False
    if os.path.exists(pad_risks_path):
        try:
            update_status("📂 Loading existing PAD susceptibilities")
            pad_risks = pd.read_csv(pad_risks_path)
            # Check if the file is empty
            if pad_risks.empty or len(pad_risks.columns) == 0:
                update_status("   ⚠️ Previous PAD analysis is incomplete, will regenerate")
                should_regenerate_pad_risks = True
        except Exception as e:
            update_status(f"   ⚠️ Error reading previous PAD analysis, will regenerate")
            should_regenerate_pad_risks = True
    else:
        should_regenerate_pad_risks = True
    
    if should_regenerate_pad_risks:
        update_status("📋 Analyzing PAD susceptibilities...")
        # Create specific clients for PAD tasks based on config
        if not internal:
            pad_preprocessing_client = get_client_for_model(ANTHROPIC_PAD_PREPROCESSING_MODEL, internal=False)
            pad_stress_test_client = get_client_for_model(ANTHROPIC_PAD_STRESS_TEST_MODEL, internal=False)
        else:
            # Internal mode uses the same client for both (GPT-5.2)
            pad_preprocessing_client = reasoning_client
            pad_stress_test_client = client
        
        pad_risks_list = run_stress_tests_for_all_pads(
            country_document_df, 
            briefing_risks_df, 
            pad_stress_test_client, 
            country,
            pad_preprocessing_client
        )
        pad_risks = pd.DataFrame(pad_risks_list)
        if save_outputs:
            pad_risks.to_csv(pad_risks_path, index=False)
            print(f"  ✓ Saved to {pad_risks_path}")
    
    # Load or generate implementation realized risks
    # Uses document-level caching - only processes new documents
    update_status("⚠️ Extracting implementation risks from ISRs/Aide Memoires...")
    
    # Create specific client for implementation risk extraction based on config
    if not internal:
        implementation_risk_client = get_client_for_model(ANTHROPIC_IMPLEMENTATION_RISK_MODEL, internal=False)
    else:
        implementation_risk_client = client
    
    # extract_all_realized_fcv_risks now handles caching internally at document level
    implementation_realized_risks = extract_all_realized_fcv_risks(
        country_document_df, 
        implementation_risk_client, 
        country=country
    )
    
    # Always save the combined results for this country
    if save_outputs and len(implementation_realized_risks) > 0:
        implementation_realized_risks.to_csv(implementation_risks_path, index=False)
        print(f"  ✓ Saved combined results to {implementation_risks_path}")
    
    # Load or generate implementation risks mapped to country risks
    if os.path.exists(implementation_mapped_path):
        update_status("📂 Loading existing risk mappings")
        implementation_realized_risks_mapped = pd.read_csv(implementation_mapped_path)
    else:
        update_status("🔗 Mapping implementation risks to country risks...")
        # Create specific client for risk mapping based on config
        if not internal:
            risk_mapping_client = get_client_for_model(ANTHROPIC_RISK_MAPPING_MODEL, internal=False)
        else:
            risk_mapping_client = client
        
        implementation_realized_risks_mapped = map_all_realized_risks_to_country(
            implementation_realized_risks, briefing_risks_df, risk_mapping_client
        )
        if save_outputs:
            implementation_realized_risks_mapped.to_csv(implementation_mapped_path, index=False)
            print(f"  ✓ Saved to {implementation_mapped_path}")
    
    # Load or generate final briefing
    if os.path.exists(briefing_output_path):
        update_status(f"📂 Loading existing briefing")
        with open(briefing_output_path, "r", encoding="utf-8") as f:
            briefing = f.read()
    else:
        update_status(f"📝 Generating final {mode} briefing document...")
        # Use specific model for final briefing synthesis based on config
        if not internal:
            final_briefing_client = get_client_for_model(ANTHROPIC_FINAL_BRIEFING_MODEL, internal=False)
        else:
            final_briefing_client = reasoning_client
        
        # Check if we need to filter projects due to context size
        total_input_length = (
            len(briefing_risks_df.to_json()) +
            len(pad_risks.to_json()) +
            len(implementation_realized_risks.to_json()) +
            len(implementation_realized_risks_mapped.to_json())
        )
        
        max_projects_limit = None
        if total_input_length > MAX_BRIEFING_INPUT_LENGTH:
            max_projects_limit = MAX_PROJECTS_FOR_BRIEFING
            update_status(f"   📊 Portfolio is too large - prioritizing top {MAX_PROJECTS_FOR_BRIEFING} highest-risk projects. To see all project risks, check the PAD Risks, Implementation Risks, and Risk Mappings tabs.")
        
        # Verify custom_categories are provided for custom mode
        if mode == "custom" and not custom_categories:
            raise ValueError("custom_categories must be provided when mode='custom'")
        
        briefing = generate_briefing(
            mode=mode,
            n_paragraphs=n_paragraphs,
            country_risks_df=briefing_risks_df,
            pad_risks=pad_risks,
            implementation_realized_risks=implementation_realized_risks,
            implementation_realized_risks_mapped=implementation_realized_risks_mapped,
            client=final_briefing_client,
            country_document_df=country_document_df,
            custom_categories=custom_categories,
            custom_prompt=custom_prompt,
            max_projects=max_projects_limit
        )
        if save_outputs:
            print(f"DEBUG: About to save briefing")
            print(f"    mode parameter: {mode}")
            print(f"    briefing_output_path: {briefing_output_path}")
            with open(briefing_output_path, "w", encoding="utf-8") as f:
                f.write(briefing)
            print(f"  ✓ Saved to {briefing_output_path}")
    
    return briefing


if __name__ == "__main__":
    country = "Djibouti"
    briefing = get_fcv_content_from_docs(country, save_outputs=True)
    print("\n\n=== GENERATED BRIEFING ===\n")
    print(briefing)