from langchain_core.prompts import ChatPromptTemplate
import json
import re
import pandas as pd

def prioritize_projects_by_risk_count(pad_risks, implementation_realized_risks, implementation_realized_risks_mapped, max_projects=15):
    """
    Select top N projects by total risk count (PAD susceptibilities + implementation risks).
    
    Returns filtered versions of the three dataframes containing only the highest-risk projects.
    """
    # Count risks per project
    project_risk_counts = {}
    
    # Count PAD susceptibilities
    if len(pad_risks) > 0 and 'PROJ_ID_IB' in pad_risks.columns:
        pad_counts = pad_risks.groupby('PROJ_ID_IB').size().to_dict()
        for proj, count in pad_counts.items():
            project_risk_counts[proj] = project_risk_counts.get(proj, 0) + count
    
    # Count implementation risks
    if len(implementation_realized_risks) > 0 and 'PROJ_ID_IB' in implementation_realized_risks.columns:
        impl_counts = implementation_realized_risks.groupby('PROJ_ID_IB').size().to_dict()
        for proj, count in impl_counts.items():
            project_risk_counts[proj] = project_risk_counts.get(proj, 0) + count
    
    # Count mapped risks
    if len(implementation_realized_risks_mapped) > 0 and 'PROJ_ID_IB' in implementation_realized_risks_mapped.columns:
        mapped_counts = implementation_realized_risks_mapped.groupby('PROJ_ID_IB').size().to_dict()
        for proj, count in mapped_counts.items():
            project_risk_counts[proj] = project_risk_counts.get(proj, 0) + count
    
    # Get top N projects
    top_projects = sorted(project_risk_counts.items(), key=lambda x: x[1], reverse=True)[:max_projects]
    top_project_ids = [proj for proj, _ in top_projects]
    
    if len(top_projects) < len(project_risk_counts):
        total_risks_kept = sum(count for _, count in top_projects)
        total_risks_all = sum(project_risk_counts.values())
        print(f"   ℹ️ Prioritized top {len(top_projects)} projects (keeping {total_risks_kept}/{total_risks_all} risk items)")
        print(f"   Top projects: {', '.join(top_project_ids[:5])}{'...' if len(top_project_ids) > 5 else ''}")
    
    # Filter dataframes
    pad_risks_filtered = pad_risks[pad_risks['PROJ_ID_IB'].isin(top_project_ids)] if len(pad_risks) > 0 and 'PROJ_ID_IB' in pad_risks.columns else pad_risks
    impl_risks_filtered = implementation_realized_risks[implementation_realized_risks['PROJ_ID_IB'].isin(top_project_ids)] if len(implementation_realized_risks) > 0 and 'PROJ_ID_IB' in implementation_realized_risks.columns else implementation_realized_risks
    mapped_risks_filtered = implementation_realized_risks_mapped[implementation_realized_risks_mapped['PROJ_ID_IB'].isin(top_project_ids)] if len(implementation_realized_risks_mapped) > 0 and 'PROJ_ID_IB' in implementation_realized_risks_mapped.columns else implementation_realized_risks_mapped
    
    return pad_risks_filtered, impl_risks_filtered, mapped_risks_filtered

def inject_links(text, country_document_df):
    """
    Replace [PROJ_ID_IB | document_type] markers with actual PDF links.
    Looks up the PDF URL from country_document_df based on PROJ_ID_IB and document_type.
    """
    import re

    # Match pattern like [P123456 | PAD] where P is followed by digits
    # Use a more restrictive pattern: stop at semicolons, closing brackets, or opening brackets
    pattern = r"\[(P\d+)\s*\|\s*([^\];\[]+?)\]"
    
    # Map short doc type names to full names in the dataframe
    doc_type_mapping = {
        "PAD": "Project Appraisal Document",
        "ISR": "Implementation Status and Results Report",
        "Aide Memoire": "Aide Memoire",
        "Aide": "Aide Memoire"
    }
    
    # Reverse mapping to display short names in citations
    display_name_mapping = {
        "Project Appraisal Document": "PAD",
        "Implementation Status and Results Report": "ISR",
        "Aide Memoire": "Aide Memoire"
    }

    def replacer(match):
        proj_id = match.group(1).strip()
        doc_type = match.group(2).strip()
        
        # Map the doc_type if it's a shorthand
        lookup_doc_type = doc_type_mapping.get(doc_type, doc_type)
        
        # Look up the document in the dataframe
        matches = country_document_df[
            (country_document_df['PROJ_ID_IB'] == proj_id) & 
            (country_document_df['document_type'] == lookup_doc_type)
        ]
        
        if matches.empty:
            # Keep the original marker if no match found
            print(f"⚠️ No match found for PROJ_ID={proj_id}, doc_type={doc_type} (lookup as {lookup_doc_type})")
            return match.group(0)
        
        # Get the first match's PDF URL
        pdf_url = matches.iloc[0]['pdf_url']
        
        # Use short display name if available, otherwise use original
        display_name = display_name_mapping.get(lookup_doc_type, doc_type_mapping.get(doc_type, doc_type))
        
        # Use HTML anchor tag for better compatibility with Streamlit
        return f'<a href="{pdf_url}" target="_blank">{proj_id} – {display_name}</a>'

    return re.sub(pattern, replacer, text)

def generate_custom_aligned_briefing(
    custom_categories,
    country_risks_df,
    pad_risks,
    implementation_realized_risks,
    implementation_realized_risks_mapped,
    client,
    custom_prompt=None
):
    """
    Each custom category becomes exactly one paragraph.
    """

    n_paragraphs = len(custom_categories)

    evidence = {
        "categories": custom_categories,
        "country_risks": country_risks_df.to_dict(orient="records"),
        "pad_risks": pad_risks.to_dict(orient="records"),
        "implementation_realized_risks": implementation_realized_risks.to_dict(orient="records"),
        "implementation_realized_risks_mapped": implementation_realized_risks_mapped.to_dict(orient="records")
    }

    # Use custom prompt if provided, otherwise use default
    system_prompt = custom_prompt if custom_prompt else (
        f"You are writing a structured FCV portfolio briefing.\n\n"
        f"Write exactly {n_paragraphs} paragraphs.\n"
        "Each paragraph MUST correspond to exactly one of the custom categories provided in the evidence.\n"
        "Process the categories in the exact order given.\n\n"
        "For each paragraph:\n"
        "- Start with the category name (e.g., 'Governance and Institutional Capacity:', 'Service Delivery and Access:', etc.)\n"
        "- Analyze how this category relates to the country's FCV risks.\n"
        "- Show how projects are exposed to relevant risks (PAD evidence).\n"
        "- Show whether these risks are materializing (ISR/Aide Memoire evidence).\n"
        "- Focus on risks and project evidence that align with this specific category.\n\n"
        "CRITICAL CITATION RULES:\n"
        "- PAD citations: Look at 'pad_risks' data. Each entry has 'PROJ_ID_IB'. ONLY cite [PROJ_ID | PAD] if that project appears in pad_risks.\n"
        "- Implementation citations: Look at 'implementation_realized_risks_mapped' data. Each entry has 'PROJ_ID_IB' and 'doc_type'. ONLY cite the exact doc_type shown (ISR or Aide Memoire).\n"
        "- NEVER cite a document type that doesn't appear in the evidence for that project.\n"
        "- If a project only has 'Aide Memoire' in the data, cite [PROJ_ID | Aide Memoire], NOT [PROJ_ID | ISR].\n"
        "- If a project only appears in implementation_realized_risks_mapped but NOT in pad_risks, do NOT cite [PROJ_ID | PAD].\n"
        "- Each citation must be in its own bracket pair: [P123456 | PAD] [P123456 | ISR]\n"
        "- NEVER combine multiple citations with semicolons inside one bracket\n"
        "- Do NOT create hyperlinks.\n"
        "- Do NOT invent citations."
    )

    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            system_prompt
        ),
        (
            "human",
            "Evidence:\n\n{evidence}"
        )
    ])

    chain = prompt | client

    message = chain.invoke({
        "evidence": json.dumps(evidence, indent=2)
    })

    return (message.content or "").strip()


def generate_risk_aligned_briefing(
    country_risks_df,
    pad_risks,
    implementation_realized_risks_mapped,
    n_paragraphs,
    client,
    custom_prompt=None
):
    evidence = {
        "country_risks": country_risks_df.to_dict(orient="records"),
        "pad_risks": pad_risks.to_dict(orient="records"),
        "implementation_realized_risks_mapped": implementation_realized_risks_mapped.to_dict(orient="records")
    }

    # Use custom prompt if provided, otherwise use default
    system_prompt = custom_prompt if custom_prompt else (
        "You are writing a structured FCV portfolio briefing.\n\n"
        f"Write exactly {n_paragraphs} paragraphs.\n"
        "Each paragraph must correspond to a distinct country-level FCV risk.\n\n"
        "For each paragraph:\n"
        "- Describe the country-level risk clearly without using technical risk IDs.\n"
        "- Explain how projects are susceptible (PAD evidence).\n"
        "- Explain whether risks are materializing (ISR/Aide evidence).\n"
        "- Integrate both forward-looking and realized risks.\n\n"
        "Important rules:\n"
        "- Do NOT mention risk_id or any technical identifiers (e.g., DJI_R1, NIG_R9).\n"
        "- Describe risks in natural language for senior leadership.\n"
        "- Focus on substance, not reference codes.\n\n"
        "CRITICAL CITATION RULES:\n"
        "- PAD citations: Look at 'pad_risks' data. Each entry has 'PROJ_ID_IB'. ONLY cite [PROJ_ID | PAD] if that project appears in pad_risks.\n"
        "- Implementation citations: Look at 'implementation_realized_risks_mapped' data. Each entry has 'PROJ_ID_IB' and 'doc_type'. ONLY cite the exact doc_type shown (ISR or Aide Memoire).\n"
        "- NEVER cite a document type that doesn't appear in the evidence for that project.\n"
        "- If a project only has 'Aide Memoire' in the data, cite [PROJ_ID | Aide Memoire], NOT [PROJ_ID | ISR].\n"
        "- If a project only appears in implementation_realized_risks_mapped but NOT in pad_risks, do NOT cite [PROJ_ID | PAD].\n"
        "- Each citation must be in its own bracket pair: [P123456 | PAD] [P123456 | ISR]\n"
        "- NEVER combine multiple citations with semicolons inside one bracket\n"
        "- Do NOT create hyperlinks.\n"
        "- Do NOT invent citations.\n"
        "- Write analytically and concisely."
    )

    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            system_prompt
        ),
        (
            "human",
            "Evidence:\n\n{evidence}"
        )
    ])

    chain = prompt | client

    message = chain.invoke({
        "evidence": json.dumps(evidence, indent=2)
    })

    return (message.content or "").strip()

def generate_sector_aligned_briefing(
    country_risks_df,
    pad_risks,
    implementation_realized_risks,
    n_paragraphs,
    client,
    custom_prompt=None
):

    evidence = {
        "country_risks": country_risks_df.to_dict(orient="records"),
        "pad_risks": pad_risks.to_dict(orient="records"),
        "implementation_realized_risks": implementation_realized_risks.to_dict(orient="records"),
    }

    # Use custom prompt if provided, otherwise use default
    system_prompt = custom_prompt if custom_prompt else (
        "You are writing a sector-aligned FCV portfolio briefing.\n\n"
        f"Write exactly {n_paragraphs} paragraphs.\n"
        "Each paragraph should correspond to a major sectoral cluster "
        "that you infer from the evidence (e.g., health, infrastructure, governance, social protection).\n\n"
        "For each paragraph:\n"
        "- Identify the sector cluster clearly in the first sentence.\n"
        "- Integrate country risk context.\n"
        "- Integrate PAD risks.\n"
        "- Integrate realized implementation risks.\n\n"
        "Citation rules:\n"
        "- Use [PROJ_ID | PAD] for PAD evidence.\n"
        "- Use [PROJ_ID | ISR] or [PROJ_ID | Aide Memoire] for implementation evidence.\n"
        "- Each citation must be in its own bracket pair\n"
        "- NEVER combine citations with semicolons\n"
        "- Do NOT create hyperlinks.\n"
        "- Do NOT invent citations."
    )

    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            system_prompt
        ),
        (
            "human",
            "Evidence:\n\n{evidence}"
        )
    ])

    chain = prompt | client

    message = chain.invoke({
        "evidence": json.dumps(evidence, indent=2)
    })

    return (message.content or "").strip()

def generate_briefing(
    mode,
    n_paragraphs,
    country_risks_df,
    pad_risks,
    implementation_realized_risks,
    implementation_realized_risks_mapped,
    client,
    country_document_df,
    custom_categories=None,
    custom_prompt=None,
    max_projects=None
):
    """
    Unified briefing generator.

    mode:
        - "risk"
        - "sector"
        - "custom"

    n_paragraphs:
        Exact number of paragraphs required.
    
    country_document_df:
        DataFrame containing document metadata including PROJ_ID_IB, document_type, and pdf_url

    custom_categories:
        Required if mode == "custom"
    
    max_projects:
        Optional limit on number of projects (prioritized by risk count). If None, includes all projects.
    """
    
    # Prioritize projects if max_projects is specified
    if max_projects is not None:
        pad_risks, implementation_realized_risks, implementation_realized_risks_mapped = prioritize_projects_by_risk_count(
            pad_risks, 
            implementation_realized_risks, 
            implementation_realized_risks_mapped, 
            max_projects=max_projects
        )
    
    # Generate briefing based on mode
    if mode == "risk":
        briefing = generate_risk_aligned_briefing(
            country_risks_df=country_risks_df,
            pad_risks=pad_risks,
            implementation_realized_risks_mapped=implementation_realized_risks_mapped,
            n_paragraphs=n_paragraphs,
            client=client,
            custom_prompt=custom_prompt
        )

    elif mode == "sector":
        briefing = generate_sector_aligned_briefing(
            country_risks_df=country_risks_df,
            pad_risks=pad_risks,
            implementation_realized_risks=implementation_realized_risks,
            n_paragraphs=n_paragraphs,
            client=client,
            custom_prompt=custom_prompt
        )

    elif mode == "custom":
        if not custom_categories:
            raise ValueError("custom_categories must be provided for custom mode")

        briefing = generate_custom_aligned_briefing(
            custom_categories=custom_categories,
            country_risks_df=country_risks_df,
            pad_risks=pad_risks,
            implementation_realized_risks=implementation_realized_risks,
            implementation_realized_risks_mapped=implementation_realized_risks_mapped,
            client=client,
            custom_prompt=custom_prompt
        )

    else:
        raise ValueError("mode must be 'risk', 'sector', or 'custom'")
    
    # Inject links for citation markers
    briefing = inject_links(briefing, country_document_df)
    
    return briefing