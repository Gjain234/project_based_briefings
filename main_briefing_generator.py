from get_country_briefing import get_country_recent_risks_briefing, extract_country_risks_with_websearch
import pandas as pd
from config import (
    get_document_df_path, 
    ANTHROPIC_FINAL_BRIEFING_MODEL,
    ANTHROPIC_PAD_PREPROCESSING_MODEL,
    ANTHROPIC_PAD_STRESS_TEST_MODEL,
    ANTHROPIC_IMPLEMENTATION_RISK_MODEL,
    ANTHROPIC_RISK_MAPPING_MODEL,
    MAX_BRIEFING_INPUT_LENGTH,
    MAX_PROJECTS_FOR_BRIEFING
)
from setup import setup, get_client_for_model
from get_briefing_risks import extract_country_risk_items
from get_pad_risks import run_stress_tests_for_all_pads
from get_implementation_docs_risks import extract_all_realized_fcv_risks, map_all_realized_risks_to_country
from generate_briefing import generate_briefing
from country_name_mapping import get_possible_wb_country_names, get_country_id_key
import os
from datetime import datetime

def get_fcv_content_from_docs(country, mode='risk', n_paragraphs=5, custom_categories=None, save_outputs=False,internal=False, force_regenerate=False, status_callback=None, custom_prompt=None, stream_callback=None):
    """Generate FCV briefing with optional status updates and streaming output.
    
    Args:
        status_callback: Optional function to call with status updates (str)
        custom_prompt: Optional custom system prompt to override defaults
        stream_callback: Optional function to call with streamed text chunks from briefing generation
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
    country_risks_are_fresh = False  # Track whether country risks are newly generated
    
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
        else:
            update_status("📂 Loading existing country risks")
        
        briefing_risks_df = pd.read_csv(briefing_risks_path)
        country_risks_are_fresh = False  # Country risks are cached, not fresh
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
        country_risks_are_fresh = True  # Country risks are newly generated
    
    # Load or generate PAD risks
    should_regenerate_pad_risks = False
    pads_needing_susceptibilities = []  # Track PADs that need susceptibility analysis
    existing_pad_risks = pd.DataFrame()  # Load existing ones to preserve
    
    # First check if all current PADs have been preprocessed
    from get_pad_risks import select_latest_pad_per_project
    from preprocess_pads import get_pad_cache_path
    pads_df = select_latest_pad_per_project(country_document_df)
    missing_preprocessed_pads = []
    
    if not pads_df.empty:
        for _, pad_row in pads_df.iterrows():
            proj_id = pad_row.get("PROJ_ID_IB", "Unknown")
            cache_path = get_pad_cache_path(proj_id, country)
            if not cache_path.exists():
                missing_preprocessed_pads.append(proj_id)
    
    # Check if we have existing susceptibilities
    if os.path.exists(pad_risks_path):
        try:
            existing_pad_risks = pd.read_csv(pad_risks_path)
            existing_proj_ids = set(existing_pad_risks['PROJ_ID_IB'].unique()) if 'PROJ_ID_IB' in existing_pad_risks.columns else set()
        except Exception:
            existing_pad_risks = pd.DataFrame()
            existing_proj_ids = set()
    else:
        existing_proj_ids = set()
    
    # Determine what needs to be done
    if missing_preprocessed_pads:
        update_status(f"   ⚠️ {len(missing_preprocessed_pads)} PAD(s) not yet preprocessed")
        # Only analyze susceptibilities for the newly-preprocessed PADs (or all if no existing results)
        if existing_proj_ids:
            pads_needing_susceptibilities = missing_preprocessed_pads
            print(f"   → Will preprocess missing PADs and generate susceptibilities only for those")
        else:
            pads_needing_susceptibilities = None  # None means analyze all
            print(f"   → Will preprocess missing PADs and generate susceptibilities for all PADs")
        should_regenerate_pad_risks = True
    elif country_risks_are_fresh:
        # If country risks are freshly generated, always regenerate PAD susceptibilities for all
        update_status("📋 Country risks are fresh, regenerating PAD susceptibilities for all PADs...")
        pads_needing_susceptibilities = None  # None means analyze all
        should_regenerate_pad_risks = True
    elif existing_pad_risks.empty:
        # No existing susceptibilities
        update_status("📋 Analyzing PAD susceptibilities (first time)...")
        pads_needing_susceptibilities = None  # None means analyze all
        should_regenerate_pad_risks = True
    else:
        # All PADs preprocessed, country risks cached, and susceptibilities exist
        update_status("📂 Loading existing PAD susceptibilities")
        pad_risks = existing_pad_risks
        should_regenerate_pad_risks = False
    
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
        
        # If pads_needing_susceptibilities is a list, only analyze those PADs
        if isinstance(pads_needing_susceptibilities, list) and pads_needing_susceptibilities:
            pads_df_to_analyze = pads_df[pads_df['PROJ_ID_IB'].isin(pads_needing_susceptibilities)]
        else:
            # None means analyze all PADs
            pads_df_to_analyze = pads_df
        
        pad_risks_list = run_stress_tests_for_all_pads(
            pads_df_to_analyze,  # Pass only the PADs that need analysis
            briefing_risks_df, 
            pad_stress_test_client, 
            country,
            pad_preprocessing_client
        )
        new_pad_risks = pd.DataFrame(pad_risks_list)
        
        # If we have existing results, combine with new ones
        if not existing_pad_risks.empty and isinstance(pads_needing_susceptibilities, list):
            # Remove entries for PADs we just re-analyzed from existing_pad_risks
            existing_filtered = existing_pad_risks[
                ~existing_pad_risks['PROJ_ID_IB'].isin(pads_needing_susceptibilities)
            ]
            # Combine existing (for untouched PADs) with new (for newly-analyzed PADs)
            pad_risks = pd.concat([existing_filtered, new_pad_risks], ignore_index=True)
            update_status(f"   ✓ Combined {len(existing_filtered)} existing + {len(new_pad_risks)} new PAD susceptibilities")
        else:
            # Either no existing results or we regenerated all
            pad_risks = new_pad_risks
        
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
    # First check if all implementation docs are cached
    from get_implementation_docs_risks import select_recent_project_docs, get_document_cache_key
    project_docs_df = select_recent_project_docs(country_document_df)
    
    impl_cache_dir = f"intermediary_outputs/implementation_risks_cache/{country}"
    missing_impl_docs = []
    if os.path.exists(impl_cache_dir):
        for _, row in project_docs_df.iterrows():
            cache_key = get_document_cache_key(row)
            cache_path = os.path.join(impl_cache_dir, f"{cache_key}.csv")
            if not os.path.exists(cache_path):
                missing_impl_docs.append((row['PROJ_ID_IB'], row['document_type']))
    else:
        missing_impl_docs = [(row['PROJ_ID_IB'], row['document_type']) for _, row in project_docs_df.iterrows()]
    
    should_regenerate_mapped = False
    if missing_impl_docs:
        update_status(f"   ⚠️ {len(missing_impl_docs)} implementation doc(s) incomplete, will regenerate mappings")
        should_regenerate_mapped = True
    elif os.path.exists(implementation_mapped_path):
        should_regenerate_mapped = False
    else:
        should_regenerate_mapped = True
    
    if not should_regenerate_mapped:
        update_status("📂 Loading existing risk mappings")
        try:
            implementation_realized_risks_mapped = pd.read_csv(implementation_mapped_path)
        except pd.errors.EmptyDataError:
            # File exists but is empty - create empty dataframe with correct schema
            implementation_realized_risks_mapped = pd.DataFrame(columns=[
                'PROJ_ID_IB', 'country_risk_id', 'country_risk_title', 
                'connection_summary', 'confidence'
            ])
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
        if save_outputs and len(implementation_realized_risks_mapped) > 0:
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
            max_projects=max_projects_limit,
            stream_callback=stream_callback
        )
        if save_outputs:
            with open(briefing_output_path, "w", encoding="utf-8") as f:
                f.write(briefing)
            print(f"  ✓ Saved to {briefing_output_path}")
    
    return briefing


if __name__ == "__main__":
    country = "Djibouti"
    briefing = get_fcv_content_from_docs(country, save_outputs=True)
    print("\n\n=== GENERATED BRIEFING ===\n")
    print(briefing)