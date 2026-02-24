from get_country_briefing import get_country_recent_risks_briefing
import pandas as pd
from config import *
from setup import setup
from get_briefing_risks import extract_country_risk_items
from get_pad_risks import run_stress_tests_for_all_pads
from get_implementation_docs_risks import extract_all_realized_fcv_risks, map_all_realized_risks_to_country
from generate_briefing import generate_briefing
from country_name_mapping import get_possible_wb_country_names, get_country_id_key
import os
from datetime import datetime

def get_fcv_content_from_docs(country, mode='risk', n_paragraphs=5, custom_categories=None, save_outputs=False,internal=False):
    save_folder = "intermediary_outputs"
    
    # Define file paths
    briefing_risks_path = f"{save_folder}/{country}_briefing_risks.csv"
    pad_risks_path = f"{save_folder}/{country}_pad_risks.csv"
    implementation_risks_path = f"{save_folder}/{country}_implementation_realized_risks.csv"
    implementation_mapped_path = f"{save_folder}/{country}_implementation_realized_risks_mapped.csv"
    
    # Add timestamp to briefing output to avoid overwriting
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    briefing_output_path = f"{save_folder}/final_{country}_{mode}_briefing_{timestamp}.md"
    
    # Create folder if saving
    if save_outputs and not os.path.exists(save_folder):
        os.makedirs(save_folder)
    
    # Check if we need to generate anything
    need_generation = (
        not os.path.exists(briefing_risks_path) or
        not os.path.exists(pad_risks_path) or
        not os.path.exists(implementation_risks_path) or
        not os.path.exists(implementation_mapped_path) or
        not os.path.exists(briefing_output_path)
    )
    
    # Initialize client and data only if needed
    client = None
    document_df = None
    country_document_df = None
    
    if need_generation:
        client = setup(internal=internal)
        document_df = pd.read_csv(DOCUMENT_DF_PATH)
        
        # Get all possible World Bank country name variants for this country
        possible_country_names = get_possible_wb_country_names(country)
        country_document_df = document_df[
            document_df["CNTRY_SHORT_NAME"].isin(possible_country_names)
        ].copy()
        
        if country_document_df.empty:
            print(f"⚠️  Warning: No documents found for country '{country}'")
            print(f"    Searched for variants: {possible_country_names}")
            print(f"    Available countries in data: {sorted(document_df['CNTRY_SHORT_NAME'].unique())[:10]}...")
    
    # Load or generate briefing risks
    if os.path.exists(briefing_risks_path):
        print(f"✓ Loading existing briefing risks from {briefing_risks_path}")
        briefing_risks_df = pd.read_csv(briefing_risks_path)
    else:
        print("→ Generating briefing risks...")
        
        # Try to map to country_ids format for ICG lookup
        icg_country_name = get_country_id_key(country)
        
        if icg_country_name:
            print(f"   Using '{icg_country_name}' for ICG lookup")
            risk_briefing = get_country_recent_risks_briefing(icg_country_name)
        else:
            print(f"   ⚠️  No ICG mapping found for '{country}' - generating briefing without ICG data")
            risk_briefing = get_country_recent_risks_briefing(country)
        
        briefing_risks_df = extract_country_risk_items(risk_briefing, client)
        if save_outputs:
            with open(f"{save_folder}/{country}_risk_scan.txt", "w", encoding="utf-8") as f:
                f.write(risk_briefing)
            briefing_risks_df.to_csv(briefing_risks_path, index=False)
            print(f"  ✓ Saved to {briefing_risks_path}")
    
    # Load or generate PAD risks
    if os.path.exists(pad_risks_path):
        print(f"✓ Loading existing PAD risks from {pad_risks_path}")
        pad_risks = pd.read_csv(pad_risks_path)
    else:
        print("→ Generating PAD risks...")
        pad_risks_list = run_stress_tests_for_all_pads(country_document_df, briefing_risks_df, client)
        pad_risks = pd.DataFrame(pad_risks_list)
        if save_outputs:
            pad_risks.to_csv(pad_risks_path, index=False)
            print(f"  ✓ Saved to {pad_risks_path}")
    
    # Load or generate implementation realized risks
    if os.path.exists(implementation_risks_path):
        print(f"✓ Loading existing implementation risks from {implementation_risks_path}")
        implementation_realized_risks = pd.read_csv(implementation_risks_path)
    else:
        print("→ Generating implementation realized risks...")
        implementation_realized_risks = extract_all_realized_fcv_risks(country_document_df, client)
        if save_outputs:
            implementation_realized_risks.to_csv(implementation_risks_path, index=False)
            print(f"  ✓ Saved to {implementation_risks_path}")
    
    # Load or generate implementation risks mapped to country risks
    if os.path.exists(implementation_mapped_path):
        print(f"✓ Loading existing implementation-to-country risk mappings from {implementation_mapped_path}")
        implementation_realized_risks_mapped = pd.read_csv(implementation_mapped_path)
    else:
        print("→ Generating implementation-to-country risk mappings...")
        implementation_realized_risks_mapped = map_all_realized_risks_to_country(
            implementation_realized_risks, briefing_risks_df, client
        )
        if save_outputs:
            implementation_realized_risks_mapped.to_csv(implementation_mapped_path, index=False)
            print(f"  ✓ Saved to {implementation_mapped_path}")
    
    # Load or generate final briefing
    if os.path.exists(briefing_output_path):
        print(f"✓ Loading existing briefing from {briefing_output_path}")
        with open(briefing_output_path, "r", encoding="utf-8") as f:
            briefing = f.read()
    else:
        print("→ Generating final briefing...")
        briefing = generate_briefing(
            mode=mode,
            n_paragraphs=n_paragraphs,
            country_risks_df=briefing_risks_df,
            pad_risks=pad_risks,
            implementation_realized_risks=implementation_realized_risks,
            implementation_realized_risks_mapped=implementation_realized_risks_mapped,
            client=client,
            country_document_df=country_document_df,
            custom_categories=custom_categories
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