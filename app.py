import streamlit as st
import pandas as pd
import os
from main_briefing_generator import get_fcv_content_from_docs
from generate_briefing import generate_briefing
from config import (
    get_document_df_path, 
    ANTHROPIC_COUNTRY_RISK_MODEL, 
    ANTHROPIC_PAD_PREPROCESSING_MODEL,
    ANTHROPIC_PAD_STRESS_TEST_MODEL,
    ANTHROPIC_IMPLEMENTATION_RISK_MODEL,
    ANTHROPIC_RISK_MAPPING_MODEL
)
from prompts import (
    get_country_risk_extraction_prompt,
    PAD_STRESS_TEST_SYSTEM_PROMPT,
    IMPLEMENTATION_RISK_EXTRACTION_SYSTEM_PROMPT,
    RISK_MAPPING_SYSTEM_PROMPT
)
from setup import setup
from get_briefing_risks import extract_country_risk_items
from country_name_mapping import is_individual_country

st.set_page_config(page_title="FCV Portfolio Briefing Generator", layout="wide")

st.title("🌍 FCV Portfolio Briefing Generator")

# Load available countries from document dataframe
@st.cache_data
def load_available_countries(internal=False):
    document_df_path = get_document_df_path(internal=internal)
    document_df = pd.read_csv(document_df_path)
    # Get unique countries and filter out regional groupings
    all_countries = document_df['CNTRY_SHORT_NAME'].unique()
    individual_countries = [c for c in all_countries if is_individual_country(c)]
    return sorted(individual_countries)

# Sidebar for main controls
st.sidebar.header("Configuration")

# Internal/External toggle
internal = st.sidebar.checkbox(
    "Internal (World Bank)",
    value=False,
    help="Do not select internal unless you are running locally."
)

available_countries = load_available_countries(internal=internal)

# Country selection
if 'selected_country' not in st.session_state:
    st.session_state.selected_country = "Djibouti" if "Djibouti" in available_countries else available_countries[0]

default_index = available_countries.index(st.session_state.selected_country) if st.session_state.selected_country in available_countries else 0

country = st.sidebar.selectbox(
    "Select Country",
    options=available_countries,
    index=default_index,
    key="country_selector"
)

st.session_state.selected_country = country

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

# Number of paragraphs (disabled for custom mode)
n_paragraphs = st.sidebar.slider(
    "Number of Paragraphs",
    min_value=3,
    max_value=10,
    value=5,
    step=1,
    disabled=(briefing_mode == "custom"),
    help="Number of paragraphs in the briefing. Disabled when using custom categories."
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

# Check if country risk briefing exists and show timestamp
save_folder = "intermediary_outputs"
briefing_risks_metadata_path = f"{save_folder}/{country}_briefing_risks_metadata.json"
briefing_risks_csv_path = f"{save_folder}/{country}_briefing_risks.csv"

last_scan_date = None
never_scanned = True

# Check metadata file first (preferred)
if os.path.exists(briefing_risks_metadata_path):
    import json
    from datetime import datetime
    try:
        with open(briefing_risks_metadata_path, 'r') as f:
            metadata = json.load(f)
            last_scan_date = metadata.get('generated_at', None)
            if last_scan_date:
                never_scanned = False
                # Parse and format to show only date
                try:
                    dt = datetime.strptime(last_scan_date, "%Y-%m-%d %H:%M:%S")
                    date_only = dt.strftime("%Y-%m-%d")
                except:
                    date_only = last_scan_date.split()[0] if ' ' in last_scan_date else last_scan_date
                st.sidebar.info(f"📅 Generating briefing using news from **{date_only}**. If you would like to use fresh news, tick the regenerate checkbox (will take around 10 minutes).")
    except:
        pass

# Fallback: check CSV file's modification time if metadata doesn't exist
if never_scanned and os.path.exists(briefing_risks_csv_path):
    import json
    from datetime import datetime
    try:
        file_mtime = os.path.getmtime(briefing_risks_csv_path)
        file_date = datetime.fromtimestamp(file_mtime)
        date_only = file_date.strftime("%Y-%m-%d")
        never_scanned = False
        st.sidebar.info(f"📅 Generating briefing using news from **{date_only}**. If you would like to use fresh news, tick the regenerate checkbox (will take around 10 minutes).")
    except:
        pass

if never_scanned:
    st.sidebar.warning("⚠️ No previous scan found so will need to generate from scratch with fresh news (10 minutes)")

# Regeneration options
st.sidebar.markdown("---")
st.sidebar.markdown("### Regeneration")
force_regenerate = st.sidebar.checkbox(
    "Regenerate with fresh news", 
    value=never_scanned,  # Auto-select if never scanned
    help="Pull latest country risks from ICG/CrisisWatch (~10 minutes)"
)

# Generate button
if st.sidebar.button(
    "🚀 Generate Briefing", 
    type="primary", 
    use_container_width=True,
    disabled=st.session_state.get('generate', False),
    key="generate_button"
):
    st.session_state.generate = True
    st.session_state.stop_generation = False  # Clear stop flag on new generation
    st.rerun()  # Force immediate rerun to show loading state

# Initialize generate flag if not present
if 'generate' not in st.session_state:
    st.session_state.generate = False

# Show loading indicator when generating
if st.session_state.get('generate', False):
    st.sidebar.info("⏳ Generating briefing... Please wait.")
    
    # Stop button (only shown when generating)
    if st.sidebar.button("🛑 Stop Generation", type="secondary", use_container_width=True):
        st.session_state.generate = False
        st.session_state.stop_generation = True
        st.warning("⚠️ Generation cancelled by user")
        st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("### About")
st.sidebar.markdown("Generate comprehensive FCV portfolio briefings using country risk analysis, PAD assessments, and implementation status.")

# Main content area
if st.session_state.generate or 'briefing' in st.session_state:
    
    # Create tabs for different views
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "📄 Final Briefing",
        "✏️ Edit Final Briefing Prompt",
        "🌐 Country Risks",
        "📋 PAD Risks",
        "⚠️ Implementation Risks",
        "🔗 Risk Mappings",
        "📖 How It Works"
    ])
    
    save_folder = "intermediary_outputs"
    
    # Define file paths
    briefing_risks_path = f"{save_folder}/{country}_briefing_risks.csv"
    pad_risks_path = f"{save_folder}/{country}_pad_risks.csv"
    implementation_risks_path = f"{save_folder}/{country}_implementation_realized_risks.csv"
    implementation_mapped_path = f"{save_folder}/{country}_implementation_realized_risks_mapped.csv"
    
    # Only generate if button was clicked
    if st.session_state.generate:
        # Create a placeholder for status updates
        status_placeholder = st.empty()
        
        def update_status(msg):
            # Check if user clicked stop
            if st.session_state.get('stop_generation', False):
                st.session_state.stop_generation = False
                raise InterruptedError("Generation stopped by user")
            status_placeholder.info(msg)
        
        with st.spinner("🔄 Generating briefing..."):
            try:
                if force_regenerate:
                    from datetime import datetime
                    archive_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    update_status("🗂️ Archiving previous outputs...")
                    # Archive country risks, PAD susceptibilities, and implementation mappings
                    # Keep preprocessed PADs and implementation risk caches (document-level)
                    for path in [briefing_risks_path, briefing_risks_metadata_path,
                                pad_risks_path, implementation_mapped_path]:
                        if os.path.exists(path):
                            base_name = os.path.splitext(os.path.basename(path))[0]
                            extension = os.path.splitext(path)[1]
                            archive_path = f"{save_folder}/{base_name}_archived_{archive_timestamp}{extension}"
                            os.rename(path, archive_path)
                
                # Generate briefing
                # Only use custom prompt if regenerating from Edit Prompt tab
                custom_prompt = st.session_state.get('custom_prompt') if st.session_state.get('regenerate_with_custom_prompt', False) else None
                if st.session_state.get('regenerate_with_custom_prompt', False):
                    st.session_state.regenerate_with_custom_prompt = False
                
                briefing = get_fcv_content_from_docs(
                    country=country,
                    mode=briefing_mode,
                    n_paragraphs=n_paragraphs,
                    custom_categories=custom_categories,
                    save_outputs=True,
                    internal=internal,
                    force_regenerate=force_regenerate,
                    status_callback=update_status,
                    custom_prompt=custom_prompt
                )
                
                status_placeholder.empty()  # Clear the status message
                st.session_state.briefing = briefing
                st.session_state.country = country
                st.session_state.mode = briefing_mode
                st.session_state.prev_params = {
                    'country': country,
                    'mode': briefing_mode,
                    'n_paragraphs': n_paragraphs,
                    'custom_categories': custom_categories
                }
                st.session_state.generate = False  # Clear generation flag
                st.success("✅ Briefing generated successfully!")
                st.rerun()  # Force UI update to re-enable button
                
            except InterruptedError:
                status_placeholder.empty()
                st.session_state.generate = False  # Clear generation flag
                st.warning("⚠️ Briefing generation was cancelled")
                st.rerun()  # Force UI update
            except Exception as e:
                status_placeholder.empty()
                st.session_state.generate = False  # Clear generation flag
                st.error(f"❌ Error generating briefing: {str(e)}")
                st.exception(e)
                st.rerun()  # Force UI update
        
        st.session_state.generate = False
    
    # Tab 1: Final Briefing
    with tab1:
        st.header("Final Briefing")
        
        with st.expander("ℹ️ About This Briefing", expanded=False):
            st.markdown(f"""
            **Briefing Mode:** {briefing_mode.title()}
            
            This final briefing is generated using an LLM that synthesizes all the extracted data:
            - Country-level FCV risks (from ICG/CrisisWatch + web search)
            - PAD susceptibility assessments
            - Implementation risks from ISRs and Aide Memoires
            - Risk mappings connecting implementation to country-level risks
            
            **Prompt Used:**
            The LLM receives a structured prompt instructing it to write {n_paragraphs} paragraph(s) organized by {briefing_mode}.
            Each paragraph integrates evidence from all sources with proper citations.
            
            Citation markers like `[P123456 | PAD]` are automatically converted to clickable PDF links.
            
            You can customize the generation prompt in the "Edit Prompt" tab.
            """)
        
        if 'briefing' in st.session_state:
            st.markdown(st.session_state.briefing, unsafe_allow_html=True)
            
            # Download button
            st.download_button(
                label="📥 Download Briefing (Markdown)",
                data=st.session_state.briefing,
                file_name=f"{country}_{briefing_mode}_briefing.md",
                mime="text/markdown"
            )
        else:
            st.info("Click 'Generate Briefing' to create the final briefing.")
    
    # Tab 3: Country Risks
    with tab3:
        st.header("Country-Level FCV Risks")
        
        with st.expander("ℹ️ How Country Risks Are Extracted", expanded=False):
            st.markdown(f"""
**Inputs:**
- ICG reports and CrisisWatch entries (last 3 months)
- Web search results (up to 10 searches)

**Model:** `{ANTHROPIC_COUNTRY_RISK_MODEL}`

**System Prompt:**
```
{get_country_risk_extraction_prompt("{country}", "YYYY-MM-DD", "[ICG/CrisisWatch texts...]")}
```

**Caching:** Results cached with timestamps. Use "Regenerate with fresh news" to pull latest data.
""")
        
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
                    
                    if 'locations' in row and pd.notna(row['locations']):
                        locations = eval(row['locations']) if isinstance(row['locations'], str) else row['locations']
                        if locations:
                            st.markdown(f"**Locations:** {', '.join(locations)}")
        else:
            st.info("Generate a briefing to view country risks.")
    
    # Tab 4: PAD Risks
    with tab4:
        st.header("PAD Risk Assessment")
        
        with st.expander("ℹ️ How PAD Susceptibilities Are Analyzed", expanded=False):
            st.markdown(f"""
**Inputs:**
- Current country-level FCV risks
- Preprocessed PAD data (sectors, components, beneficiaries, locations, risk matrices)

**Models:**
- PAD Preprocessing: `{ANTHROPIC_PAD_PREPROCESSING_MODEL}` (complex extraction)
- Stress Testing: `{ANTHROPIC_PAD_STRESS_TEST_MODEL}` (matching risks to PADs)

**System Prompt:**
```
{PAD_STRESS_TEST_SYSTEM_PROMPT}
```

**Caching:** PAD preprocessing cached permanently. Stress tests regenerate when country risks change.
""")
        
        if os.path.exists(pad_risks_path):
            try:
                df = pd.read_csv(pad_risks_path)
                
                if df.empty or len(df.columns) == 0:
                    st.warning("⚠️ PAD risks file is empty. Try regenerating the briefing.")
                else:
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
            except Exception as e:
                st.error(f"❌ Error loading PAD risks: {str(e)}")
                st.info("Try regenerating the briefing.")
        else:
            st.info("Generate a briefing to view PAD risks.")
    
    # Tab 5: Implementation Risks
    with tab5:
        st.header("Realized Implementation Risks")
        
        with st.expander("ℹ️ How Implementation Risks Are Extracted", expanded=False):
            st.markdown(f"""
**Inputs:**
- Document text from ISRs and Aide Memoires
- Most recent 2 ISRs and 2 Aide Memoires per project

**Model:** `{ANTHROPIC_IMPLEMENTATION_RISK_MODEL}`

**System Prompt:**
```
{IMPLEMENTATION_RISK_EXTRACTION_SYSTEM_PROMPT}
```

**Caching:** Results cached at document level by country. Cache persists across briefing regenerations.
""")
        
        if os.path.exists(implementation_risks_path):
            try:
                df = pd.read_csv(implementation_risks_path)
                
                if df.empty or len(df.columns) == 0:
                    st.warning("⚠️ Implementation risks file is empty. Try regenerating the briefing.")
                else:
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
            except Exception as e:
                st.error(f"❌ Error loading implementation risks: {str(e)}")
                st.info("Try regenerating the briefing.")
        else:
            st.info("Generate a briefing to view implementation risks.")
    
    # Tab 6: Risk Mappings
    with tab6:
        st.header("Implementation-to-Country Risk Mappings")
        
        with st.expander("ℹ️ How Risk Mappings Are Created", expanded=False):
            st.markdown(f"""
**Inputs:**
- Realized project implementation risks
- Current country-level FCV risks

**Model:** `{ANTHROPIC_RISK_MAPPING_MODEL}`

**System Prompt:**
```
{RISK_MAPPING_SYSTEM_PROMPT}
```

**Purpose:** These mappings enable the risk-aligned briefing mode, which organizes the final briefing by country-level risks and shows how they're affecting projects.
""")
        
        if os.path.exists(implementation_mapped_path):
            try:
                df = pd.read_csv(implementation_mapped_path)
                
                if df.empty or len(df.columns) == 0:
                    st.warning("⚠️ Risk mappings file is empty. Try regenerating the briefing.")
                else:
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
            except Exception as e:
                st.error(f"❌ Error loading risk mappings: {str(e)}")
                st.info("Try regenerating the briefing.")
        else:
            st.info("Generate a briefing to view risk mappings.")
    
    # Tab 2: Edit Final Briefing Prompt
    with tab2:
        st.header("Edit Final Briefing Prompt")
        st.markdown("Customize the prompt used to generate the final briefing.")
        
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
        
        st.info("ℹ️ Your custom prompt will automatically receive all the data sources as JSON evidence:\n"
                "- `country_risks`: Country-level FCV risks\n"
                "- `pad_risks`: PAD susceptibility analysis\n"
                "- `implementation_realized_risks`: Extracted ISR/Aide Memoire risks\n"
                "- `implementation_realized_risks_mapped`: Implementation risks mapped to country risks\n\n"
                "Citation markers like [PROJ_ID | PAD] will be automatically converted to document links.")
        
        custom_prompt = st.text_area(
            "System Prompt",
            value=default_prompts[briefing_mode].format(n_paragraphs=n_paragraphs),
            height=400,
            help="This prompt will be used to generate the final briefing. All data sources are automatically provided as evidence."
        )
        
        st.session_state.custom_prompt = custom_prompt
        
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("🔄 Reset to Default", use_container_width=True):
                st.session_state.custom_prompt = default_prompts[briefing_mode]
                st.rerun()
        with col2:
            if st.button("🚀 Regenerate Briefing", type="primary", use_container_width=True):
                st.session_state.regenerate_with_custom_prompt = True  # Set flag to use custom prompt
                st.session_state.generate = True
                st.session_state.stop_generation = False
                st.rerun()
    
    # Tab 7: How It Works
    with tab7:
        st.header("📖 How the Briefing Pipeline Works")
        
        st.markdown("""
        This tool generates comprehensive FCV portfolio briefings through a multi-stage pipeline that combines external intelligence, 
        project documents, and AI analysis. Here's how it works:
        """)
        
        st.markdown("---")
        
        st.subheader("🔄 Stage 1: Country-Level Risk Intelligence")
        st.markdown("""
        **Objective:** Understand current FCV dynamics in the country
        
        **Process:**
        1. Fetch latest ICG (International Crisis Group) reports for the country
        2. Fetch CrisisWatch entries from the last 3 months
        3. Use Claude Sonnet 4 with web search to:
           - Corroborate ICG reporting
           - Fill gaps in coverage
           - Capture very recent developments not yet in ICG reports
        4. Extract 6-12 structured risk items in a **single LLM call**
        
        **Each risk includes:**
        - Title and detailed summary with inline citations
        - Themes (governance, political, security, humanitarian, etc.)
        - Keywords for semantic matching
        - Affected locations (regions, cities, districts)
        - Severity (low/medium/high) and time horizon (current/0-3m/3-12m)
        
        **Caching:** Results stored with timestamps. Only regenerates when you click "Regenerate with fresh news" (~10 minutes).
        
        **Why web search?** Ensures the most current information, as ICG reports may lag behind fast-moving events.
        """)
        
        st.markdown("---")
        
        st.subheader("📋 Stage 2: PAD Preprocessing & Risk Assessment")
        st.markdown("""
        **Objective:** Identify how projects are susceptible to country-level risks
        
        **Process:**
        1. **Preprocessing** (one-time per PAD):
           - Extract full PAD text from World Bank API
           - Restructure into high-density JSON (sectors, components, beneficiaries, locations, risk matrices)
           - Cache preprocessed structure permanently
        
        2. **Stress Testing** (regenerates with country risks):
           - For each PAD × country risk combination:
             - LLM determines if project is susceptible
             - Extracts verbatim evidence quote
             - Explains susceptibility mechanism
             - Assigns confidence level
        
        **Why preprocess?** PADs are long (100-300 pages). Preprocessing creates a condensed, structured version 
        that fits in LLM context windows and speeds up analysis by ~10x.
        
        **Output:** Susceptibility matrix showing which projects are exposed to which country risks.
        """)
        
        st.markdown("---")
        
        st.subheader("⚠️ Stage 3: Implementation Risk Extraction")
        st.markdown("""
        **Objective:** Identify FCV risks that have already materialized during implementation
        
        **Process:**
        1. **Document Selection:**
           - Select most recent 2 ISRs per project
           - Select most recent 2 Aide Memoires per project
        
        2. **Extraction** (per document):
           - Fetch full document text
           - LLM extracts FCV-related risks affecting implementation
           - Each risk must have verbatim evidence quote
           - Classify severity and direction (new/worsening/persistent/improving)
        
        3. **Caching:**
           - Results cached at document level (by country)
           - Hash-based cache keys prevent reprocessing same documents
           - Cached indefinitely unless document changes
        
        **What qualifies as FCV risk?**
        - Political instability, governance fragility, protests
        - Conflict and violence dynamics
        - Displacement or refugee pressures
        - Government-development actor tensions
        
        **NOT included:** Generic fiduciary or procurement issues (unless clearly FCV-linked)
        """)
        
        st.markdown("---")
        
        st.subheader("🔗 Stage 4: Risk Mapping")
        st.markdown("""
        **Objective:** Connect implementation risks to country-level risks
        
        **Process:**
        1. For each implementation risk:
           - LLM matches it to 1-3 most relevant country risks
           - Explains the connection mechanism
           - Assigns confidence level
        
        **Purpose:** Enables "risk-aligned" briefing mode where each paragraph:
        - Describes a country-level FCV risk
        - Shows which projects are susceptible (PAD evidence)
        - Shows how it's manifesting in implementation (ISR/Aide evidence)
        
        **Example Mapping:**
        - Country Risk: "Insecurity in northern regions disrupting aid access"
        - Implementation Risk: "Education project suspended in 3 districts due to insurgent activity"
        - Connection: "Country-level insurgency directly causing project suspension"
        """)
        
        st.markdown("---")
        
        st.subheader("📝 Stage 5: Final Briefing Generation")
        st.markdown("""
        **Objective:** Synthesize all evidence into a coherent briefing
        
        **Process:**
        1. LLM receives all extracted data as JSON:
           - Country risks with citations
           - PAD susceptibilities
           - Implementation risks
           - Risk mappings
        
        2. Generates structured briefing based on mode:
           - **Risk-Aligned:** One paragraph per country risk (shows susceptibility + realization)
           - **Sector-Aligned:** One paragraph per sector cluster (inferred from evidence)
           - **Custom:** One paragraph per user-defined category
        
        3. **Citation System:**
           - LLM writes markers: `[P123456 | PAD]`, `[P123456 | ISR]`, `[P123456 | Aide Memoire]`
           - System automatically converts to clickable PDF links
           - Each citation links directly to the source document
        
        **Customization:** You can edit the system prompt in the "Edit Prompt" tab to change:
        - Writing style and tone
        - Focus areas and priorities
        - Level of detail
        - Analytical framing
        
        All data is automatically injected - your prompt just needs to specify how to present it.
        """)
        
        st.markdown("---")
        
        st.subheader("💾 Caching Strategy")
        st.markdown("""
        The pipeline uses intelligent caching to optimize performance:
        
        | Data Type | Cache Level | Regenerates When |
        |-----------|-------------|------------------|
        | **Preprocessed PADs** | Document | Never (unless doc changes) |
        | **Implementation Risks** | Document (by country) | Never (unless doc changes) |
        | **Country Risks** | Country | User clicks "Regenerate with fresh news" |
        | **PAD Stress Tests** | Country | Country risks regenerate |
        | **Risk Mappings** | Country | Implementation risks or country risks change |
        | **Final Briefing** | Country + params | Any input changes or settings change |
        
        **First generation:** ~10-15 minutes (fetches ICG, preprocesses PADs, extracts from ISRs)
        
        **Subsequent generations:** ~2-3 minutes (uses cached preprocessed data)
        
        **Fresh news update:** ~10 minutes (only regenerates country risks, reuses all document caches)
        """)
        
        st.markdown("---")
        
        st.subheader("🤖 AI Models Used")
        st.markdown("""
        | Task | Model | Why This Model |
        |------|-------|----------------|
        | **Country Risk Extraction** | Claude Sonnet 4 + Web Search | Complex extraction with real-time data |
        | **PAD Preprocessing** | GPT-5.2 or Claude Haiku 4.5 | Fast, cost-effective for structured extraction |
        | **PAD Stress Testing** | GPT-5.2 or Claude Haiku 4.5 | Analytical reasoning for susceptibility assessment |
        | **Implementation Risk Extraction** | GPT-5.2 or Claude Haiku 4.5 | Consistent extraction from similar documents |
        | **Risk Mapping** | GPT-5.2 or Claude Haiku 4.5 | Pattern matching and semantic similarity |
        | **Final Briefing** | GPT-5.2 or Claude Haiku 4.5 | Coherent synthesis and narrative generation |
        
        **Note:** System uses dual-client setup:
        - **Internal (World Bank):** Azure OpenAI GPT-5.2
        - **External:** Anthropic Claude (Haiku 4.5 for speed, Sonnet 4 for complex tasks)
        """)
        
        st.markdown("---")
        
        st.subheader("📊 Data Flow Diagram")
        st.markdown("""
        ```
        ICG Reports + CrisisWatch → [Web Search + LLM] → Country Risks (cached)
                                                               ↓
        PADs → [Preprocess + Cache] → Preprocessed PADs ──────┤
                                                               ↓
                                                    [Stress Test + LLM]
                                                               ↓
                                                        PAD Susceptibilities
                                                               ↓
        ISRs/Aides → [Extract + Cache] → Implementation Risks ┤
                                                               ↓
                                                       [Map Risks + LLM]
                                                               ↓
                                                         Risk Mappings
                                                               ↓
        [All Evidence] → [Synthesis LLM + Custom Prompt] → Final Briefing
                                                               ↓
                                                    [Inject PDF Links]
                                                               ↓
                                                      📄 Output (Markdown)
        ```
        """)
        
        st.markdown("---")
        
        st.subheader("🎯 Best Practices")
        st.markdown("""
        **For accurate briefings:**
        - Regenerate country risks monthly (or after major events)
        - Review intermediary outputs in other tabs to verify quality
        - Use custom prompts to tailor briefing style to your audience
        - Check citations link to correct documents
        
        **For faster performance:**
        - Don't regenerate unless needed (caches are your friend)
        - Preprocessed PADs and implementation caches are permanent - no need to regenerate
        - Only click "Regenerate with fresh news" when you need latest country intelligence
        
        **For customization:**
        - Edit the prompt in "Edit Prompt" tab to change briefing style
        - Use "Custom Categories" mode to define your own organizational structure
        - Adjust number of paragraphs to control briefing length
        
        **For troubleshooting:**
        - Check each tab to see which stage may have issues
        - Empty or missing data usually means that stage needs regeneration
        - Error messages will indicate which extraction step failed
        """)

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
