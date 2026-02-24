import streamlit as st
import pandas as pd
import os
import glob
from main_briefing_generator import get_fcv_content_from_docs
from generate_briefing import generate_briefing
from config import DOCUMENT_DF_PATH
from setup import setup
from get_briefing_risks import extract_country_risk_items
from country_name_mapping import is_individual_country

st.set_page_config(page_title="FCV Portfolio Briefing Generator", layout="wide")

st.title("🌍 FCV Portfolio Briefing Generator")

# Load available countries from document dataframe
@st.cache_data
def load_available_countries():
    document_df = pd.read_csv(DOCUMENT_DF_PATH)
    # Get unique countries and filter out regional groupings
    all_countries = document_df['CNTRY_SHORT_NAME'].unique()
    individual_countries = [c for c in all_countries if is_individual_country(c)]
    return sorted(individual_countries)

available_countries = load_available_countries()

# Sidebar for main controls
st.sidebar.header("Configuration")

# Country selection
default_index = available_countries.index("Djibouti") if "Djibouti" in available_countries else 0
country = st.sidebar.selectbox(
    "Select Country",
    options=available_countries,
    index=default_index
)

# Briefing type
briefing_mode = st.sidebar.selectbox(
    "Briefing Type",
    options=["risk", "sector", "custom"],
    format_func=lambda x: {
        "risk": "Risk-Aligned Briefing",
        "sector": "Sector-Aligned Briefing",
        "custom": "Custom Categories Briefing"
    }[x]
)

# Number of paragraphs
n_paragraphs = st.sidebar.slider(
    "Number of Paragraphs",
    min_value=3,
    max_value=10,
    value=5,
    step=1
)

# Custom categories input (only for custom mode)
custom_categories = None
if briefing_mode == "custom":
    custom_categories_text = st.sidebar.text_area(
        "Custom Categories (one per line)",
        value="Governance and Institutional Capacity\nService Delivery and Access\nEconomic Vulnerability\nSocial Cohesion and Protection",
        height=150
    )
    custom_categories = [cat.strip() for cat in custom_categories_text.split('\n') if cat.strip()]
    n_paragraphs = len(custom_categories)
    st.sidebar.info(f"Number of paragraphs set to {n_paragraphs} (one per category)")

# Generate button
if st.sidebar.button("🚀 Generate Briefing", type="primary", use_container_width=True):
    st.session_state.generate = True
else:
    if 'generate' not in st.session_state:
        st.session_state.generate = False

# Show force regenerate option
force_regenerate = st.sidebar.checkbox("Force regenerate all steps", value=False)

st.sidebar.markdown("---")
st.sidebar.markdown("### About")
st.sidebar.markdown("Generate comprehensive FCV portfolio briefings using country risk analysis, PAD assessments, and implementation status.")

# Main content area
if st.session_state.generate or 'briefing' in st.session_state:
    
    # Create tabs for different views
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📄 Final Briefing",
        "🌐 Country Risks",
        "📋 PAD Risks",
        "⚠️ Implementation Risks",
        "🔗 Risk Mappings",
        "✏️ Edit Prompt"
    ])
    
    save_folder = "intermediary_outputs"
    
    # Define file paths
    briefing_risks_path = f"{save_folder}/{country}_briefing_risks.csv"
    pad_risks_path = f"{save_folder}/{country}_pad_risks.csv"
    implementation_risks_path = f"{save_folder}/{country}_implementation_realized_risks.csv"
    implementation_mapped_path = f"{save_folder}/{country}_implementation_realized_risks_mapped.csv"
    briefing_output_path = f"{save_folder}/final_{country}_{briefing_mode}_briefing.md"
    
    # Check if parameters changed (requires briefing regeneration)
    params_changed = False
    if os.path.exists(briefing_output_path):
        prev_params = st.session_state.get('prev_params', {})
        current_params = {
            'country': country,
            'mode': briefing_mode,
            'n_paragraphs': n_paragraphs,
            'custom_categories': custom_categories
        }
        if prev_params != current_params:
            params_changed = True
            st.info("⚠️ Parameters changed - briefing will be regenerated")
    
    # Only generate if button was clicked
    if st.session_state.generate:
        with st.spinner("🔄 Generating briefing... This may take a few minutes."):
            try:
                # Clear cache if force regenerate or params changed
                if force_regenerate:
                    # Delete intermediary outputs only, keep timestamped briefings
                    for path in [briefing_risks_path, pad_risks_path, 
                                implementation_risks_path, implementation_mapped_path]:
                        if os.path.exists(path):
                            os.remove(path)
                
                # Generate briefing
                briefing = get_fcv_content_from_docs(
                    country=country,
                    mode=briefing_mode,
                    n_paragraphs=n_paragraphs,
                    custom_categories=custom_categories,
                    save_outputs=True,
                    internal=False
                )
                
                st.session_state.briefing = briefing
                st.session_state.country = country
                st.session_state.mode = briefing_mode
                st.session_state.prev_params = {
                    'country': country,
                    'mode': briefing_mode,
                    'n_paragraphs': n_paragraphs,
                    'custom_categories': custom_categories
                }
                st.success("✅ Briefing generated successfully!")
                
            except Exception as e:
                st.error(f"❌ Error generating briefing: {str(e)}")
                st.exception(e)
        
        st.session_state.generate = False
    
    # Tab 1: Final Briefing
    with tab1:
        st.header("Final Briefing")
        
        if 'briefing' in st.session_state:
            st.markdown(st.session_state.briefing)
            
            # Download button
            st.download_button(
                label="📥 Download Briefing (Markdown)",
                data=st.session_state.briefing,
                file_name=f"{country}_{briefing_mode}_briefing.md",
                mime="text/markdown"
            )
        else:
            st.info("Click 'Generate Briefing' to create the final briefing.")
    
    # Tab 2: Country Risks
    with tab2:
        st.header("Country-Level FCV Risks")
        
        if os.path.exists(briefing_risks_path):
            df = pd.read_csv(briefing_risks_path)
            
            st.metric("Total Risks Identified", len(df))
            
            for idx, row in df.iterrows():
                with st.expander(f"**{row['title']}**", expanded=idx < 3):
                    col1, col2, col3 = st.columns([2, 1, 1])
                    with col1:
                        st.markdown(f"**Themes:** {', '.join(eval(row['themes']) if isinstance(row['themes'], str) else row['themes'])}")
                    with col2:
                        st.markdown(f"**Severity:** {row['severity']}")
                    with col3:
                        st.markdown(f"**Time Horizon:** {row['time_horizon']}")
                    
                    st.markdown(f"**Summary:**\n\n{row['summary']}")
                    
                    if 'keywords' in row and pd.notna(row['keywords']):
                        keywords = eval(row['keywords']) if isinstance(row['keywords'], str) else row['keywords']
                        st.markdown(f"**Keywords:** {', '.join(keywords)}")
        else:
            st.info("Generate a briefing to view country risks.")
    
    # Tab 3: PAD Risks
    with tab3:
        st.header("PAD Risk Assessment")
        
        if os.path.exists(pad_risks_path):
            df = pd.read_csv(pad_risks_path)
            
            st.metric("Total PAD Susceptibilities", len(df))
            
            # Group by project
            projects = df['PROJ_ID_IB'].unique()
            
            for proj in projects:
                proj_df = df[df['PROJ_ID_IB'] == proj]
                with st.expander(f"**Project: {proj}** ({len(proj_df)} susceptibilities)", expanded=False):
                    for idx, row in proj_df.iterrows():
                        st.markdown(f"**Related Risk:** {row['related_country_risk_title']}")
                        st.markdown(f"**Susceptibility:** {row['susceptibility_summary']}")
                        st.markdown(f"**Evidence:** _{row['evidence_quote']}_")
                        st.markdown(f"**Confidence:** {row['confidence']}")
                        st.markdown("---")
        else:
            st.info("Generate a briefing to view PAD risks.")
    
    # Tab 4: Implementation Risks
    with tab4:
        st.header("Realized Implementation Risks")
        
        if os.path.exists(implementation_risks_path):
            df = pd.read_csv(implementation_risks_path)
            
            st.metric("Total Implementation Risks", len(df))
            
            # Group by project
            projects = df['PROJ_ID_IB'].unique()
            
            for proj in projects:
                proj_df = df[df['PROJ_ID_IB'] == proj]
                with st.expander(f"**Project: {proj}** ({len(proj_df)} risks)", expanded=False):
                    for idx, row in proj_df.iterrows():
                        col1, col2, col3 = st.columns([2, 1, 1])
                        with col1:
                            st.markdown(f"**{row['risk_title']}**")
                        with col2:
                            st.markdown(f"**Severity:** {row['severity']}")
                        with col3:
                            st.markdown(f"**Direction:** {row['direction']}")
                        
                        st.markdown(f"{row['risk_summary']}")
                        st.markdown(f"**Evidence:** _{row['evidence_quote']}_")
                        st.markdown(f"**Document:** {row['doc_type']}")
                        st.markdown("---")
        else:
            st.info("Generate a briefing to view implementation risks.")
    
    # Tab 5: Risk Mappings
    with tab5:
        st.header("Implementation-to-Country Risk Mappings")
        
        if os.path.exists(implementation_mapped_path):
            df = pd.read_csv(implementation_mapped_path)
            
            st.metric("Total Risk Connections", len(df))
            
            # Group by project
            if 'PROJ_ID_IB' in df.columns:
                projects = df['PROJ_ID_IB'].unique()
                projects = sorted([p for p in projects if pd.notna(p)])
                
                for proj in projects:
                    proj_df = df[df['PROJ_ID_IB'] == proj]
                    with st.expander(f"**Project: {proj}** ({len(proj_df)} connections)", expanded=False):
                        for idx, row in proj_df.iterrows():
                            st.markdown(f"**Country Risk:** {row['country_risk_title']}")
                            st.markdown(f"**Connection:** {row['connection_summary']}")
                            st.markdown(f"**Confidence:** {row['confidence']}")
                            if 'doc_type' in row and pd.notna(row['doc_type']):
                                st.markdown(f"**Document Type:** {row['doc_type']}")
                            st.markdown("---")
            else:
                # Fallback if no project ID
                for idx, row in df.iterrows():
                    with st.expander(f"**Connection {idx + 1}**", expanded=idx < 3):
                        st.markdown(f"**Country Risk:** {row['country_risk_title']}")
                        st.markdown(f"**Connection:** {row['connection_summary']}")
                        st.markdown(f"**Confidence:** {row['confidence']}")
        else:
            st.info("Generate a briefing to view risk mappings.")
    
    # Tab 6: Edit Prompt
    with tab6:
        st.header("Edit Final Briefing Prompt")
        st.markdown("Customize the prompt used to generate the final briefing. Changes will be applied on next generation.")
        
        # Default prompts based on mode
        default_prompts = {
            "risk": """You are writing a structured FCV portfolio briefing.

Write exactly {n_paragraphs} paragraphs.
Each paragraph must correspond to a distinct country-level FCV risk.

For each paragraph:
- Describe the country-level risk clearly without using technical risk IDs.
- Explain how projects are susceptible (PAD evidence).
- Explain whether risks are materializing (ISR/Aide evidence).
- Integrate both forward-looking and realized risks.

Important rules:
- Do NOT mention risk_id or any technical identifiers (e.g., DJI_R1, NIG_R9).
- Describe risks in natural language for senior leadership.
- Focus on substance, not reference codes.

Citation rules:
- When referencing PAD evidence use marker: [PROJ_ID | PAD]
- When referencing ISR/Aide evidence use marker: [PROJ_ID | document_type]
- Do NOT create hyperlinks.
- Do NOT invent citations.
- Use citation markers only when grounded in evidence.
- Write analytically and concisely.""",
            "sector": """You are writing a sector-aligned FCV portfolio briefing.

Write exactly {n_paragraphs} paragraphs.
Each paragraph should correspond to a major sectoral cluster that you infer from the evidence (e.g., health, infrastructure, governance, social protection).

For each paragraph:
- Identify the sector cluster clearly in the first sentence.
- Integrate country risk context.
- Integrate PAD risks.
- Integrate realized implementation risks.

Citation rules:
- Use [PROJ_ID | PAD] for PAD evidence.
- Use [PROJ_ID | document_type] for ISR/Aide evidence.
- Do NOT create hyperlinks.
- Do NOT invent citations.""",
            "custom": """You are writing a structured FCV portfolio briefing.

Write exactly {n_paragraphs} paragraphs.
Each paragraph must correspond exactly to one of the provided categories.

For each paragraph:
- Use the category name clearly in the first sentence.
- Integrate relevant country risks.
- Integrate PAD risks.
- Integrate realized implementation risks.

Citation rules:
- Use marker: [PROJ_ID | PAD]
- Use marker: [PROJ_ID | document_type]
- Do NOT create hyperlinks.
- Do NOT invent citations.
- Only use citation markers when supported by evidence."""
        }
        
        current_mode = st.session_state.get('mode', briefing_mode)
        
        custom_prompt = st.text_area(
            "System Prompt",
            value=default_prompts[current_mode].format(n_paragraphs=n_paragraphs),
            height=400,
            help="This prompt will be used to generate the final briefing"
        )
        
        st.session_state.custom_prompt = custom_prompt
        
        if st.button("💾 Save Custom Prompt"):
            st.success("Prompt saved! It will be used on next generation.")
        
        if st.button("🔄 Reset to Default"):
            st.session_state.custom_prompt = default_prompts[current_mode]
            st.rerun()

else:
    # Welcome screen
    st.markdown("""
    ## Welcome to the FCV Portfolio Briefing Generator
    
    This tool generates comprehensive Fragility, Conflict & Violence (FCV) portfolio briefings by:
    
    1. **Analyzing country-level risks** from ICG reports and CrisisWatch
    2. **Assessing PAD vulnerabilities** against current FCV dynamics
    3. **Extracting implementation risks** from ISRs and Aide Memoires
    4. **Generating structured briefings** tailored to your needs
    
    ### Getting Started
    
    1. **Select a country** from the sidebar
    2. **Choose a briefing type:**
       - **Risk-Aligned**: Organized by country-level FCV risks
       - **Sector-Aligned**: Organized by sectoral clusters
       - **Custom**: Define your own categories
    3. **Adjust parameters** (number of paragraphs, custom categories)
    4. **Click "Generate Briefing"** to start
    
    ### Features
    
    - 📊 View intermediary outputs (country risks, PAD assessments, implementation status)
    - ✏️ Customize the final briefing prompt
    - 💾 Automatically saves and caches results
    - 📥 Download briefings in Markdown format
    
    **Ready to begin?** Configure your settings in the sidebar and click "Generate Briefing"!
    """)
