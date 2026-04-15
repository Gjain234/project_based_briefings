from langchain_core.prompts import ChatPromptTemplate
import json
import re
import pandas as pd


def estimate_tokens_from_text(text):
    """Approximate token count using a conservative chars-per-token heuristic."""
    if not text:
        return 0
    return max(1, int(len(text) / 4))


def _is_token_limit_error(error):
    message = str(error).lower()
    return (
        'token limit will exceed' in message
        or ('statuscode' in message and '429' in message and 'token' in message)
    )


def _normalize_record_value(value, max_field_chars):
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        if len(text) > max_field_chars:
            return text[:max_field_chars].rstrip() + '...'
        return text
    return value


def _truncate_project_records(records, level_cfg):
    max_records_per_project = level_cfg['max_records_per_project']
    max_field_chars = level_cfg['max_field_chars']
    max_fields_per_record = level_cfg['max_fields_per_record']

    truncated = []
    for row in records[:max_records_per_project]:
        if not isinstance(row, dict):
            truncated.append(row)
            continue

        keys = list(row.keys())
        if len(keys) > max_fields_per_record:
            keys = keys[:max_fields_per_record]

        row_out = {}
        for key in keys:
            row_out[key] = _normalize_record_value(row.get(key), max_field_chars)

        truncated.append(row_out)

    return truncated


def _truncate_evidence_payload(evidence, level):
    """Progressively reduce payload size while preserving project-by-project structure."""
    if level <= 0:
        return evidence

    level_configs = {
        1: {'max_projects_per_doc': 30, 'max_records_per_project': 10, 'max_field_chars': 450, 'max_fields_per_record': 16},
        2: {'max_projects_per_doc': 24, 'max_records_per_project': 7, 'max_field_chars': 320, 'max_fields_per_record': 14},
        3: {'max_projects_per_doc': 18, 'max_records_per_project': 5, 'max_field_chars': 220, 'max_fields_per_record': 12},
        4: {'max_projects_per_doc': 12, 'max_records_per_project': 3, 'max_field_chars': 160, 'max_fields_per_record': 10},
    }
    level_cfg = level_configs.get(level, level_configs[4])

    # Deep copy via JSON to avoid mutating the original structure
    payload = json.loads(json.dumps(evidence))

    by_doc = payload.get('evidence_by_document_type')
    if not isinstance(by_doc, dict):
        return payload

    for doc_type, projects in list(by_doc.items()):
        if not isinstance(projects, dict):
            continue

        # Keep projects with most evidence first
        ranked_projects = sorted(
            projects.items(),
            key=lambda item: len(item[1]) if isinstance(item[1], list) else 0,
            reverse=True
        )

        keep_count = level_cfg['max_projects_per_doc']
        selected_projects = ranked_projects[:keep_count]

        truncated_projects = {}
        for project_id, records in selected_projects:
            if isinstance(records, list):
                truncated_projects[project_id] = _truncate_project_records(records, level_cfg)
            else:
                truncated_projects[project_id] = records

        by_doc[doc_type] = truncated_projects

    return payload


def _run_chain_with_token_fallback(chain, system_prompt, evidence, stream_callback=None, max_attempts=5):
    """Retry generation with progressively truncated per-project evidence on token-limit 429 errors."""
    last_error = None

    for attempt in range(max_attempts):
        truncation_level = attempt
        attempt_evidence = _truncate_evidence_payload(evidence, truncation_level)
        evidence_text = json.dumps(attempt_evidence, indent=2)

        estimated_tokens = (
            estimate_tokens_from_text(system_prompt)
            + estimate_tokens_from_text(evidence_text)
            + 500
        )

        print(
            f"   ℹ️ Briefing generation attempt {attempt + 1}/{max_attempts} "
            f"(estimated request tokens: ~{estimated_tokens:,}, truncation level: {truncation_level})"
        )

        try:
            if stream_callback:
                full_content = ""
                for chunk in chain.stream({"evidence": evidence_text}):
                    if hasattr(chunk, 'content'):
                        content = chunk.content
                    else:
                        content = str(chunk)

                    if content:
                        full_content += content
                        stream_callback(content)

                return full_content.strip()

            message = chain.invoke({"evidence": evidence_text})
            return (message.content or "").strip()

        except Exception as error:
            last_error = error
            if not _is_token_limit_error(error):
                raise

            if attempt >= max_attempts - 1:
                break

            print(
                "   ⚠️ Token-limit 429 encountered. "
                "Retrying with stronger per-project metadata truncation..."
            )

    raise last_error

def restructure_evidence_by_source(pad_risks, implementation_realized_risks_mapped, implementation_realized_risks=None):
    """
    Restructure evidence data into a hierarchical format organized by document type, then by project.
    
    Returns:
    {
        "PAD": {
            "P123456": [risk1, risk2, ...],
            "P789012": [risk1, ...]
        },
        "ISR": {
            "P123456": [risk1, ...],
            "P345678": [risk1, ...]
        },
        "Aide Memoire": {
            "P789012": [risk1, ...]
        }
    }
    
    This format makes it impossible for the LLM to cite a project-document combination that doesn't exist.
    """
    evidence_by_source = {
        "PAD": {},
        "ISR": {},
        "Aide Memoire": {}
    }
    
    # Organize PAD risks by project
    if len(pad_risks) > 0 and 'PROJ_ID_IB' in pad_risks.columns:
        for proj_id in pad_risks['PROJ_ID_IB'].unique():
            project_risks = pad_risks[pad_risks['PROJ_ID_IB'] == proj_id].to_dict('records')
            evidence_by_source["PAD"][proj_id] = project_risks
    
    # Organize implementation risks by project and document type
    if len(implementation_realized_risks_mapped) > 0 and 'PROJ_ID_IB' in implementation_realized_risks_mapped.columns:
        for _, row in implementation_realized_risks_mapped.iterrows():
            proj_id = row['PROJ_ID_IB']
            doc_type = row.get('doc_type', 'ISR')
            
            if doc_type not in evidence_by_source:
                evidence_by_source[doc_type] = {}
            
            if proj_id not in evidence_by_source[doc_type]:
                evidence_by_source[doc_type][proj_id] = []
            
            evidence_by_source[doc_type][proj_id].append(row.to_dict())
    
    return evidence_by_source



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
    custom_prompt=None,
    stream_callback=None
):
    """
    Each custom category becomes exactly one paragraph.
    """

    n_paragraphs = len(custom_categories)

    # Restructure evidence by document type and project
    evidence_by_source = restructure_evidence_by_source(pad_risks, implementation_realized_risks_mapped, implementation_realized_risks)

    evidence = {
        "categories": custom_categories,
        "country_risks": country_risks_df.to_dict(orient="records"),
        "evidence_by_document_type": evidence_by_source
    }

    # Validate and clean custom_prompt
    if custom_prompt:
        if not isinstance(custom_prompt, str):
            custom_prompt = None
        else:
            custom_prompt = custom_prompt.strip() if custom_prompt else None

    # Use custom prompt if provided, otherwise use default
    system_prompt = custom_prompt if custom_prompt else (
        f"You are writing a structured FCV portfolio briefing.\n\n"
        f"Write exactly {n_paragraphs} paragraphs.\n"
        "Each paragraph MUST correspond to exactly one of the custom categories provided in the evidence.\n"
        "Process the categories in the exact order given.\n\n"
        "For each paragraph:\n"
        "- Start with the category name\n"
        "- Analyze how this category relates to the country's FCV risks\n"
        "- Show projects' exposure to relevant risks (from PAD evidence)\n"
        "- Show whether risks are materializing (from ISR/Aide Memoire evidence)\n\n"
        "Citation format: [PROJ_ID | DOC_TYPE]. Only cite projects that appear in the evidence_by_document_type structure."
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

    return _run_chain_with_token_fallback(
        chain=chain,
        system_prompt=system_prompt,
        evidence=evidence,
        stream_callback=stream_callback
    )


def generate_risk_aligned_briefing(
    country_risks_df,
    pad_risks,
    implementation_realized_risks_mapped,
    n_paragraphs,
    client,
    custom_prompt=None,
    stream_callback=None
):
    # Restructure evidence by document type and project
    evidence_by_source = restructure_evidence_by_source(pad_risks, implementation_realized_risks_mapped)

    evidence = {
        "country_risks": country_risks_df.to_dict(orient="records"),
        "evidence_by_document_type": evidence_by_source
    }
    # Validate and clean custom_prompt
    if custom_prompt:
        if not isinstance(custom_prompt, str):
            custom_prompt = None
        else:
            custom_prompt = custom_prompt.strip() if custom_prompt else None
    # Validate and clean custom_prompt
    if custom_prompt:
        if not isinstance(custom_prompt, str):
            custom_prompt = None
        else:
            custom_prompt = custom_prompt.strip() if custom_prompt else None

    # Use custom prompt if provided, otherwise use default
    system_prompt = custom_prompt if custom_prompt else (
        "You are writing a structured FCV portfolio briefing.\n\n"
        f"Write exactly {n_paragraphs} paragraphs.\n"
        "Each paragraph must correspond to a distinct country-level FCV risk.\n\n"
        "For each paragraph:\n"
        "- Describe the country-level risk clearly without technical risk IDs\n"
        "- Explain how projects are susceptible (from PAD evidence)\n"
        "- Explain whether risks are materializing (from ISR/Aide evidence)\n"
        "- Integrate both forward-looking and realized risks\n\n"
        "Citation format: [PROJ_ID | DOC_TYPE]. Only cite projects that appear in the evidence_by_document_type structure."
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

    return _run_chain_with_token_fallback(
        chain=chain,
        system_prompt=system_prompt,
        evidence=evidence,
        stream_callback=stream_callback
    )

def generate_sector_aligned_briefing(
    country_risks_df,
    pad_risks,
    implementation_realized_risks,
    n_paragraphs,
    client,
    custom_prompt=None,
    stream_callback=None
):
    # For sector mode, create mapped version from implementation_realized_risks
    implementation_realized_risks_mapped = implementation_realized_risks if len(implementation_realized_risks) > 0 else pd.DataFrame()

    # Restructure evidence by document type and project
    evidence_by_source = restructure_evidence_by_source(pad_risks, implementation_realized_risks_mapped)

    evidence = {
        "country_risks": country_risks_df.to_dict(orient="records"),
        "evidence_by_document_type": evidence_by_source
    }

    # Use custom prompt if provided, otherwise use default
    system_prompt = custom_prompt if custom_prompt else (
        "You are writing a sector-aligned FCV portfolio briefing.\n\n"
        f"Write exactly {n_paragraphs} paragraphs.\n"
        "Each paragraph should correspond to a major sectoral cluster (e.g., health, infrastructure, governance, social protection).\n\n"
        "For each paragraph:\n"
        "- Identify the sector cluster clearly\n"
        "- Integrate country risk context\n"
        "- Integrate PAD risks and realized implementation risks\n\n"
        "Citation format: [PROJ_ID | DOC_TYPE]. Only cite projects that appear in the evidence_by_document_type structure."
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

    return _run_chain_with_token_fallback(
        chain=chain,
        system_prompt=system_prompt,
        evidence=evidence,
        stream_callback=stream_callback
    )

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
    max_projects=None,
    stream_callback=None
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
    
    stream_callback:
        Optional callback function to receive streamed text chunks as they are generated.
        Called with each incoming text chunk (str).
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
            custom_prompt=custom_prompt,
            stream_callback=stream_callback
        )

    elif mode == "sector":
        briefing = generate_sector_aligned_briefing(
            country_risks_df=country_risks_df,
            pad_risks=pad_risks,
            implementation_realized_risks=implementation_realized_risks,
            n_paragraphs=n_paragraphs,
            client=client,
            custom_prompt=custom_prompt,
            stream_callback=stream_callback
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
            custom_prompt=custom_prompt,
            stream_callback=stream_callback
        )

    else:
        raise ValueError("mode must be 'risk', 'sector', or 'custom'")
    
    # Inject links for citation markers
    briefing = inject_links(briefing, country_document_df)
    
    return briefing