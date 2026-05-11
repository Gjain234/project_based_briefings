from langchain_core.prompts import ChatPromptTemplate
import json
import re
import pandas as pd


PROJECT_ID_PATTERN = re.compile(r"\bP\d{5,}\b", re.IGNORECASE)
TECHNICAL_ID_FIELDS = {
    "risk_id",
    "country_risk_id",
    "realized_risk_id",
}
DOC_TYPE_SHORT_NAMES = {
    "Project Appraisal Document": "PAD",
    "Implementation Status and Results Report": "ISR",
    "Aide Memoire": "Aide Memoire",
}


def normalize_project_id(project_id):
    if project_id is None:
        return None
    normalized = str(project_id).strip().upper()
    return normalized or None


def extract_project_ids_from_prompt(custom_prompt):
    if not isinstance(custom_prompt, str):
        return []

    seen = set()
    project_ids = []
    for match in PROJECT_ID_PATTERN.findall(custom_prompt.upper()):
        project_id = normalize_project_id(match)
        if project_id and project_id not in seen:
            seen.add(project_id)
            project_ids.append(project_id)
    return project_ids


def _collect_project_risk_counts(pad_risks, implementation_realized_risks, implementation_realized_risks_mapped):
    project_risk_counts = {}

    if len(pad_risks) > 0 and 'PROJ_ID_IB' in pad_risks.columns:
        pad_counts = pad_risks.groupby('PROJ_ID_IB').size().to_dict()
        for proj, count in pad_counts.items():
            normalized = normalize_project_id(proj)
            if normalized:
                project_risk_counts[normalized] = project_risk_counts.get(normalized, 0) + count

    if len(implementation_realized_risks) > 0 and 'PROJ_ID_IB' in implementation_realized_risks.columns:
        impl_counts = implementation_realized_risks.groupby('PROJ_ID_IB').size().to_dict()
        for proj, count in impl_counts.items():
            normalized = normalize_project_id(proj)
            if normalized:
                project_risk_counts[normalized] = project_risk_counts.get(normalized, 0) + count

    if len(implementation_realized_risks_mapped) > 0 and 'PROJ_ID_IB' in implementation_realized_risks_mapped.columns:
        mapped_counts = implementation_realized_risks_mapped.groupby('PROJ_ID_IB').size().to_dict()
        for proj, count in mapped_counts.items():
            normalized = normalize_project_id(proj)
            if normalized:
                project_risk_counts[normalized] = project_risk_counts.get(normalized, 0) + count

    return project_risk_counts


def _dedupe_project_ids(project_ids):
    seen = set()
    deduped = []
    for project_id in project_ids or []:
        normalized = normalize_project_id(project_id)
        if normalized and normalized not in seen:
            seen.add(normalized)
            deduped.append(normalized)
    return deduped


def sanitize_evidence_records(df):
    if len(df) == 0:
        return []

    records = df.where(pd.notnull(df), None).to_dict(orient="records")
    sanitized_records = []
    for record in records:
        sanitized_records.append({
            key: value
            for key, value in record.items()
            if key not in TECHNICAL_ID_FIELDS
        })
    return sanitized_records


def build_project_name_map(project_names_by_id=None, *dataframes, selected_project_ids=None):
    project_names = {}

    for project_id, project_name in (project_names_by_id or {}).items():
        normalized = normalize_project_id(project_id)
        cleaned_name = str(project_name).strip() if project_name is not None else ""
        if normalized and cleaned_name:
            project_names[normalized] = cleaned_name

    for df in dataframes:
        if len(df) == 0 or 'PROJ_ID_IB' not in df.columns or 'project_name' not in df.columns:
            continue

        name_rows = df[['PROJ_ID_IB', 'project_name']].dropna(subset=['PROJ_ID_IB', 'project_name'])
        for _, row in name_rows.iterrows():
            normalized = normalize_project_id(row['PROJ_ID_IB'])
            cleaned_name = str(row['project_name']).strip()
            if normalized and cleaned_name and normalized not in project_names:
                project_names[normalized] = cleaned_name

    selected_ids = _dedupe_project_ids(selected_project_ids)
    if selected_ids:
        selected_set = set(selected_ids)
        project_names = {
            project_id: project_name
            for project_id, project_name in project_names.items()
            if project_id in selected_set
        }

    return project_names


def _format_doc_date(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None

    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.strftime("%Y-%m-%d")


def prepare_implementation_evidence(implementation_realized_risks, implementation_realized_risks_mapped):
    implementation_realized_risks = implementation_realized_risks.copy()
    implementation_realized_risks_mapped = implementation_realized_risks_mapped.copy()

    if len(implementation_realized_risks) > 0:
        implementation_realized_risks["citation_date"] = implementation_realized_risks.get("doc_date").apply(_format_doc_date)
        implementation_realized_risks["citation_doc_type"] = implementation_realized_risks.get("doc_type").map(
            lambda value: DOC_TYPE_SHORT_NAMES.get(value, value)
        )
        implementation_realized_risks["citation_marker"] = implementation_realized_risks.apply(
            lambda row: (
                f"[{row['PROJ_ID_IB']} | {row['citation_doc_type']} | {row['citation_date']}]"
                if row.get("PROJ_ID_IB") and row.get("citation_doc_type") and row.get("citation_date")
                else None
            ),
            axis=1,
        )

    if len(implementation_realized_risks_mapped) > 0:
        if "doc_date" not in implementation_realized_risks_mapped.columns and len(implementation_realized_risks) > 0:
            join_columns = [column for column in ["realized_risk_id", "PROJ_ID_IB", "doc_type", "doc_date"] if column in implementation_realized_risks.columns]
            if {"realized_risk_id", "PROJ_ID_IB", "doc_type"}.issubset(join_columns):
                implementation_realized_risks_mapped = implementation_realized_risks_mapped.merge(
                    implementation_realized_risks[join_columns].drop_duplicates(
                        subset=["realized_risk_id", "PROJ_ID_IB", "doc_type"]
                    ),
                    on=["realized_risk_id", "PROJ_ID_IB", "doc_type"],
                    how="left",
                )

        if "doc_date" in implementation_realized_risks_mapped.columns:
            implementation_realized_risks_mapped["citation_date"] = implementation_realized_risks_mapped["doc_date"].apply(_format_doc_date)
        else:
            implementation_realized_risks_mapped["citation_date"] = None

        implementation_realized_risks_mapped["citation_doc_type"] = implementation_realized_risks_mapped.get("doc_type").map(
            lambda value: DOC_TYPE_SHORT_NAMES.get(value, value)
        )
        implementation_realized_risks_mapped["citation_marker"] = implementation_realized_risks_mapped.apply(
            lambda row: (
                f"[{row['PROJ_ID_IB']} | {row['citation_doc_type']} | {row['citation_date']}]"
                if row.get("PROJ_ID_IB") and row.get("citation_doc_type") and row.get("citation_date")
                else None
            ),
            axis=1,
        )

    return implementation_realized_risks, implementation_realized_risks_mapped


STYLE_GUARDRAILS = (
    "\n\nSTYLE GUARDRAILS:\n"
    "- Avoid repetitive paragraph openings across the briefing.\n"
    "- Do NOT begin every paragraph with formulaic lead-ins like 'Country-level monitoring shows', "
    "'Country-level evidence documents', 'Country-level monitoring does not document', or close variants.\n"
    "- After the heading or topic label, vary the first sentence structure and move directly into the substantive point.\n"
    "- When referring to a project in prose, use the project's name from the PAD-derived evidence if available; do not refer to projects only by project ID or p-code. You may include the project ID alongside the name when useful.\n"
    "- Write like a senior analyst, not a template.\n"
)


def apply_style_guardrails(system_prompt):
    return f"{system_prompt.rstrip()}{STYLE_GUARDRAILS}"


def get_default_briefing_prompt(mode, n_paragraphs=None, include_guardrails=False):
    if mode == "custom":
        if n_paragraphs is None:
            raise ValueError("n_paragraphs is required for custom mode")
        prompt = (
            f"You are writing a structured FCV portfolio briefing.\n\n"
            f"Write exactly {n_paragraphs} paragraphs.\n"
            "Each paragraph MUST correspond to exactly one of the custom categories provided in the evidence.\n"
            "Process the categories in the exact order given.\n\n"
            "For each paragraph:\n"
            "- Start with the category name (e.g., 'Governance and Institutional Capacity:', 'Service Delivery and Access:', etc.)\n"
            "- Analyze how this category relates to the country's FCV risks.\n"
            "- Show how projects are exposed to relevant risks (PAD evidence). Provide 1-3 sentences per project cited, elaborating on specific vulnerabilities.\n"
            "- Show whether these risks are materializing (ISR/Aide Memoire evidence). Provide 1-3 sentences per issue cited, describing observed impacts.\n"
            "- Focus on risks and project evidence that align with this specific category.\n\n"
            "CRITICAL CITATION RULES:\n"
            "- PAD citations: Look at 'pad_risks' data. Each entry has 'PROJ_ID_IB'. ONLY cite [PROJ_ID | PAD] if that project appears in pad_risks.\n"
            "- Implementation citations: Look at 'implementation_realized_risks_mapped' data. Each entry includes a 'citation_marker'. Use that exact marker for implementation citations, for example [P123456 | ISR | 2025-09-26].\n"
            "- NEVER cite a document type that doesn't appear in the evidence for that project.\n"
            "- If a project only has 'Aide Memoire' in the data, cite its exact Aide Memoire citation_marker, NOT an ISR marker.\n"
            "- If a project only appears in implementation_realized_risks_mapped but NOT in pad_risks, do NOT cite [PROJ_ID | PAD].\n"
            "- Each citation must be in its own bracket pair: [P123456 | PAD] [P123456 | ISR | 2025-09-26]\n"
            "- NEVER combine multiple citations with semicolons inside one bracket\n"
            "- Do NOT create hyperlinks.\n"
            "- Do NOT invent citations."
        )
    elif mode == "risk":
        if n_paragraphs is None:
            raise ValueError("n_paragraphs is required for risk mode")
        prompt = (
            "You are writing a structured FCV portfolio briefing.\n\n"
            f"Write exactly {n_paragraphs} paragraphs.\n"
            "Each paragraph must correspond to a distinct country-level FCV risk.\n\n"
            "For each paragraph:\n"
            "- Describe the country-level risk clearly without using technical risk IDs.\n"
            "- Explain how projects are susceptible (PAD evidence). For each project cited, provide 1-3 sentences elaborating on the specific exposure mechanism.\n"
            "- Explain whether risks are materializing (ISR/Aide evidence). For each implementation issue cited, provide 1-3 sentences on the specific impacts observed.\n"
            "- Integrate both forward-looking and realized risks.\n\n"
            "Important rules:\n"
            "- Do NOT mention risk_id or any technical identifiers (e.g., DJI_R1, NIG_R9).\n"
            "- Describe risks in natural language for senior leadership.\n"
            "- Focus on substance, not reference codes.\n\n"
            "CRITICAL CITATION RULES:\n"
            "- PAD citations: Look at 'pad_risks' data. Each entry has 'PROJ_ID_IB'. ONLY cite [PROJ_ID | PAD] if that project appears in pad_risks.\n"
            "- Implementation citations: Look at 'implementation_realized_risks_mapped' data. Each entry includes a 'citation_marker'. Use that exact marker for implementation citations.\n"
            "- NEVER cite a document type that doesn't appear in the evidence for that project.\n"
            "- If a project only has 'Aide Memoire' in the data, cite its exact Aide Memoire citation_marker, NOT an ISR marker.\n"
            "- If a project only appears in implementation_realized_risks_mapped but NOT in pad_risks, do NOT cite [PROJ_ID | PAD].\n"
            "- Each citation must be in its own bracket pair: [P123456 | PAD] [P123456 | ISR | 2025-09-26]\n"
            "- NEVER combine multiple citations with semicolons inside one bracket\n"
            "- Do NOT create hyperlinks.\n"
            "- Do NOT invent citations.\n"
            "- Write analytically and concisely."
        )
    elif mode == "sector":
        if n_paragraphs is None:
            raise ValueError("n_paragraphs is required for sector mode")
        prompt = (
            "You are writing a sector-aligned FCV portfolio briefing.\n\n"
            f"Write exactly {n_paragraphs} paragraphs.\n"
            "Each paragraph should correspond to a major sectoral cluster "
            "that you infer from the evidence (e.g., health, infrastructure, governance, social protection).\n\n"
            "For each paragraph:\n"
            "- Identify the sector cluster clearly in the first sentence.\n"
            "- Integrate country risk context.\n"
            "- Integrate PAD risks. Provide 1-3 sentences per project cited, describing specific exposure pathways.\n"
            "- Integrate realized implementation risks. Provide 1-3 sentences per issue cited, detailing observed effects.\n\n"
            "Citation rules:\n"
            "- Use [PROJ_ID | PAD] for PAD evidence.\n"
            "- Use the exact implementation 'citation_marker' shown in the evidence, for example [P123456 | ISR | 2025-09-26].\n"
            "- Each citation must be in its own bracket pair\n"
            "- NEVER combine citations with semicolons\n"
            "- Do NOT create hyperlinks.\n"
            "- Do NOT invent citations."
        )
    elif mode == "project-based":
        paragraph_instruction = (
            f"Write exactly {n_paragraphs} paragraphs, one for each project listed in the evidence.\n"
            if n_paragraphs is not None
            else "Write exactly one paragraph for each project listed in the evidence.\n"
        )
        prompt = (
            "You are writing a project-based FCV portfolio briefing.\n\n"
            f"{paragraph_instruction}"
            "Process the projects in the exact order provided.\n\n"
            "For each paragraph:\n"
            "- Start with the project ID (e.g., 'P123456'). You may look up project names from the evidence if available.\n"
            "- Analyze the project's FCV exposure and risks.\n"
            "- Describe how country-level FCV risks affect this specific project.\n"
            "- Include PAD-stage susceptibilities. Provide 1-3 sentences elaborating on the specific exposure mechanisms.\n"
            "- Include any realized implementation risks or issues. Provide 1-3 sentences detailing observed impacts.\n"
            "- Focus on the unique context and risks for this specific project.\n\n"
            "Citation rules:\n"
            "- Use [PROJ_ID | PAD] only if that project appears in pad_risks.\n"
            "- Use the exact implementation 'citation_marker' shown in implementation_realized_risks_mapped.\n"
            "- Each citation must be in its own bracket pair: [P123456 | PAD] [P123456 | ISR | 2025-09-26]\n"
            "- NEVER combine multiple citations with semicolons inside one bracket\n"
            "- Do NOT cite a document type that doesn't appear in the evidence for that project.\n"
            "- Do NOT create hyperlinks.\n"
            "- Do NOT invent citations.\n"
            "- Do NOT cite any risk mapping IDs as they have no meaning in the final briefing"
        )
    elif mode == "rra":
        prompt = (
            f"You are writing a structured FCV portfolio briefing organised around the five standard "
            f"short-term RRA (Risk and Resilience Assessment) risk headings.\n\n"
            f"Write exactly {len(RRA_HEADINGS)} paragraphs, one for each heading in the order given.\n\n"
            "For each paragraph:\n"
            "- Begin the paragraph with the exact RRA heading in bold followed by a colon "
            "(e.g. **Social unrest, protests, and oppression:**).\n"
            "- Summarise the relevant country-level FCV dynamics under that heading. "
            "Ground this entirely in the `country_risks` entries in the evidence — these are extracted from "
            "live web search and recent ICG/CrisisWatch monitoring covering the last 3 months. "
            "Treat them as the authoritative source of current conditions. "
            "Do NOT substitute or supplement with your background training knowledge about the country.\n"
            "- Show how World Bank projects in the portfolio are susceptible to that risk "
            "(PAD evidence). Provide 1-3 sentences per project cited.\n"
            "- Show whether those risks are materialising in implementation "
            "(ISR/Aide Memoire evidence). Provide 1-3 sentences per issue cited.\n\n"
            "CRITICAL CITATION RULES:\n"
            "- PAD citations: ONLY cite [PROJ_ID | PAD] if that project appears in pad_risks.\n"
            "- Implementation citations: use the exact 'citation_marker' from implementation_realized_risks_mapped, "
            "for example [P123456 | ISR | 2025-09-26].\n"
            "- NEVER cite a document type absent from the evidence for that project.\n"
            "- Each citation must be in its own bracket pair: [P123456 | PAD] [P123456 | ISR | 2025-09-26]\n"
            "- NEVER combine multiple citations with semicolons inside one bracket.\n"
            "- Do NOT create hyperlinks.\n"
            "- Do NOT invent citations.\n"
            "- Write analytically and concisely for senior leadership."
        )
    else:
        raise ValueError("mode must be 'rra', 'risk', 'sector', 'project-based', or 'custom'")

    if include_guardrails:
        return apply_style_guardrails(prompt)
    return prompt


def build_project_selection(
    pad_risks,
    implementation_realized_risks,
    implementation_realized_risks_mapped,
    max_projects=None,
    preferred_project_ids=None,
    selected_project_ids=None
):
    project_risk_counts = _collect_project_risk_counts(
        pad_risks,
        implementation_realized_risks,
        implementation_realized_risks_mapped
    )
    ranked_projects = sorted(project_risk_counts.items(), key=lambda item: (-item[1], item[0]))
    all_project_ids = [project_id for project_id, _ in ranked_projects]
    available_project_ids = set(all_project_ids)

    preferred_ids = _dedupe_project_ids(preferred_project_ids)
    selected_override_ids = _dedupe_project_ids(selected_project_ids)

    unavailable_preferred_ids = [project_id for project_id in preferred_ids if project_id not in available_project_ids]
    unavailable_selected_ids = [project_id for project_id in selected_override_ids if project_id not in available_project_ids]

    preferred_present_ids = [project_id for project_id in preferred_ids if project_id in available_project_ids]

    if selected_override_ids:
        selected_ids = [project_id for project_id in selected_override_ids if project_id in available_project_ids]
        selection_source = 'manual'
    elif preferred_present_ids:
        selected_ids = list(preferred_present_ids)
        selection_source = 'prompt-requested'
    elif max_projects is not None and len(all_project_ids) > max_projects:
        selected_ids = all_project_ids[:max_projects]
        selection_source = 'auto-prioritized'
    else:
        selected_ids = list(all_project_ids)
        selection_source = 'all-projects'

    selected_ids = _dedupe_project_ids(selected_ids)
    discarded_ids = [project_id for project_id in all_project_ids if project_id not in selected_ids]
    total_risks_selected = sum(project_risk_counts[project_id] for project_id in selected_ids)
    total_risks_available = sum(project_risk_counts.values())

    rank_lookup = {project_id: index + 1 for index, project_id in enumerate(all_project_ids)}

    return {
        'selection_source': selection_source,
        'portfolio_too_large': bool(max_projects is not None and len(all_project_ids) > max_projects),
        'max_projects': max_projects,
        'total_projects': len(all_project_ids),
        'selected_project_ids': selected_ids,
        'discarded_project_ids': discarded_ids,
        'prompt_requested_project_ids': preferred_ids,
        'prompt_requested_project_ids_available': preferred_present_ids,
        'prompt_requested_project_ids_missing': unavailable_preferred_ids,
        'selected_project_ids_missing': unavailable_selected_ids,
        'selected_projects': [
            {'project_id': project_id, 'risk_count': project_risk_counts[project_id], 'rank': rank_lookup[project_id]}
            for project_id in selected_ids
        ],
        'discarded_projects': [
            {'project_id': project_id, 'risk_count': project_risk_counts[project_id], 'rank': rank_lookup[project_id]}
            for project_id in discarded_ids
        ],
        'total_risks_selected': total_risks_selected,
        'total_risks_available': total_risks_available,
    }


def filter_project_evidence(
    pad_risks,
    implementation_realized_risks,
    implementation_realized_risks_mapped,
    selected_project_ids
):
    selected_set = set(_dedupe_project_ids(selected_project_ids))

    def filter_df(df):
        if len(df) == 0 or 'PROJ_ID_IB' not in df.columns:
            return df
        normalized_ids = df['PROJ_ID_IB'].astype(str).str.strip().str.upper()
        return df[normalized_ids.isin(selected_set)].copy()

    return (
        filter_df(pad_risks),
        filter_df(implementation_realized_risks),
        filter_df(implementation_realized_risks_mapped)
    )

def prioritize_projects_by_risk_count(pad_risks, implementation_realized_risks, implementation_realized_risks_mapped, max_projects=15):
    """
    Select top N projects by total risk count (PAD susceptibilities + implementation risks).
    
    Returns filtered versions of the three dataframes containing only the highest-risk projects.
    """
    selection = build_project_selection(
        pad_risks,
        implementation_realized_risks,
        implementation_realized_risks_mapped,
        max_projects=max_projects
    )

    if selection['portfolio_too_large']:
        print(
            f"   ℹ️ Prioritized top {len(selection['selected_project_ids'])} projects "
            f"(keeping {selection['total_risks_selected']}/{selection['total_risks_available']} risk items)"
        )
        print(
            f"   Top projects: {', '.join(selection['selected_project_ids'][:5])}"
            f"{'...' if len(selection['selected_project_ids']) > 5 else ''}"
        )

    return filter_project_evidence(
        pad_risks,
        implementation_realized_risks,
        implementation_realized_risks_mapped,
        selection['selected_project_ids']
    )

def inject_links(text, country_document_df):
    """
    Replace [PROJ_ID_IB | document_type] markers with actual PDF links.
    If multiple documents match the same project/document-type citation, render
    links to all matching documents instead of arbitrarily choosing one.
    """
    import re

    # Match pattern like [P123456 | PAD] where P is followed by digits
    # Use a more restrictive pattern: stop at semicolons, closing brackets, or opening brackets
    pattern = r"\[(P\d+)\s*\|\s*([^\]|;\[]+?)(?:\s*\|\s*(\d{4}-\d{2}-\d{2}))?\]"
    
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
        citation_date = match.group(3).strip() if match.group(3) else None
        
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

        if 'lupdate' in matches.columns:
            matches = matches.sort_values('lupdate', ascending=False, na_position='last')

        if citation_date and 'lupdate' in matches.columns:
            matched_dates = pd.to_datetime(matches['lupdate'], errors='coerce').dt.strftime('%Y-%m-%d')
            matches = matches[matched_dates == citation_date]

        matches = matches.dropna(subset=['pdf_url'])
        matches = matches.drop_duplicates(subset=['pdf_url'])

        if matches.empty:
            return match.group(0)
        
        # Use short display name if available, otherwise use original
        display_name = display_name_mapping.get(lookup_doc_type, doc_type_mapping.get(doc_type, doc_type))
        link_label = f"{display_name} {citation_date}" if citation_date else display_name

        if len(matches) == 1:
            pdf_url = matches.iloc[0]['pdf_url']
            return f'<a href="{pdf_url}" target="_blank">{proj_id} – {link_label}</a>'

        doc_links = []
        for index, (_, row) in enumerate(matches.iterrows(), start=1):
            pdf_url = row['pdf_url']
            item_label = f'{link_label} {index}' if citation_date else f'{display_name} {index}'
            doc_links.append(f'<a href="{pdf_url}" target="_blank">{item_label}</a>')

        return f'{proj_id} – ' + ' / '.join(doc_links)

    return re.sub(pattern, replacer, text)

def generate_custom_aligned_briefing(
    custom_categories,
    country_risks_df,
    pad_risks,
    implementation_realized_risks,
    implementation_realized_risks_mapped,
    client,
    project_names_by_id=None,
    custom_prompt=None
):
    """
    Each custom category becomes exactly one paragraph.
    """

    n_paragraphs = len(custom_categories)
    implementation_realized_risks, implementation_realized_risks_mapped = prepare_implementation_evidence(
        implementation_realized_risks,
        implementation_realized_risks_mapped,
    )

    evidence = {
        "categories": custom_categories,
        "project_names": build_project_name_map(
            project_names_by_id,
            pad_risks,
            implementation_realized_risks,
            implementation_realized_risks_mapped,
        ),
        "country_risks": sanitize_evidence_records(country_risks_df),
        "pad_risks": sanitize_evidence_records(pad_risks),
        "implementation_realized_risks": sanitize_evidence_records(implementation_realized_risks),
        "implementation_realized_risks_mapped": sanitize_evidence_records(implementation_realized_risks_mapped)
    }

    # Validate and clean custom_prompt
    if custom_prompt:
        if not isinstance(custom_prompt, str):
            custom_prompt = None
        else:
            custom_prompt = custom_prompt.strip() if custom_prompt else None

    # Use custom prompt if provided, otherwise use default
    system_prompt = custom_prompt if custom_prompt else get_default_briefing_prompt("custom", n_paragraphs=n_paragraphs)

    system_prompt = apply_style_guardrails(system_prompt)

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
    project_names_by_id=None,
    custom_prompt=None
):
    _, implementation_realized_risks_mapped = prepare_implementation_evidence(
        pd.DataFrame(),
        implementation_realized_risks_mapped,
    )

    evidence = {
        "project_names": build_project_name_map(
            project_names_by_id,
            pad_risks,
            implementation_realized_risks_mapped,
        ),
        "country_risks": sanitize_evidence_records(country_risks_df),
        "pad_risks": sanitize_evidence_records(pad_risks),
        "implementation_realized_risks_mapped": sanitize_evidence_records(implementation_realized_risks_mapped)
    }

    # Validate and clean custom_prompt
    if custom_prompt:
        if not isinstance(custom_prompt, str):
            custom_prompt = None
        else:
            custom_prompt = custom_prompt.strip() if custom_prompt else None

    # Use custom prompt if provided, otherwise use default
    system_prompt = custom_prompt if custom_prompt else get_default_briefing_prompt("risk", n_paragraphs=n_paragraphs)

    system_prompt = apply_style_guardrails(system_prompt)

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
    project_names_by_id=None,
    custom_prompt=None
):

    implementation_realized_risks, _ = prepare_implementation_evidence(
        implementation_realized_risks,
        pd.DataFrame(),
    )

    evidence = {
        "project_names": build_project_name_map(
            project_names_by_id,
            pad_risks,
            implementation_realized_risks,
        ),
        "country_risks": sanitize_evidence_records(country_risks_df),
        "pad_risks": sanitize_evidence_records(pad_risks),
        "implementation_realized_risks": sanitize_evidence_records(implementation_realized_risks),
    }

    # Validate and clean custom_prompt
    if custom_prompt:
        if not isinstance(custom_prompt, str):
            custom_prompt = None
        else:
            custom_prompt = custom_prompt.strip() if custom_prompt else None

    # Use custom prompt if provided, otherwise use default
    system_prompt = custom_prompt if custom_prompt else get_default_briefing_prompt("sector", n_paragraphs=n_paragraphs)

    system_prompt = apply_style_guardrails(system_prompt)

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

def generate_project_based_briefing(
    country_risks_df,
    pad_risks,
    implementation_realized_risks,
    implementation_realized_risks_mapped,
    client,
    project_names_by_id=None,
    custom_prompt=None
):
    """
    Generate a project-based briefing with one paragraph per project.
    Each project gets its own dedicated analysis paragraph.
    """

    implementation_realized_risks, implementation_realized_risks_mapped = prepare_implementation_evidence(
        implementation_realized_risks,
        implementation_realized_risks_mapped,
    )
    
    # Get unique projects from all data sources
    projects = set()
    
    if len(pad_risks) > 0 and 'PROJ_ID_IB' in pad_risks.columns:
        projects.update(pad_risks['PROJ_ID_IB'].unique())
    
    if len(implementation_realized_risks_mapped) > 0 and 'PROJ_ID_IB' in implementation_realized_risks_mapped.columns:
        projects.update(implementation_realized_risks_mapped['PROJ_ID_IB'].unique())
    
    projects = sorted(list(projects))
    n_projects = len(projects)
    
    evidence = {
        "projects": projects,
        "project_names": build_project_name_map(
            project_names_by_id,
            pad_risks,
            implementation_realized_risks,
            implementation_realized_risks_mapped,
        ),
        "country_risks": sanitize_evidence_records(country_risks_df),
        "pad_risks": sanitize_evidence_records(pad_risks),
        "implementation_realized_risks": sanitize_evidence_records(implementation_realized_risks),
        "implementation_realized_risks_mapped": sanitize_evidence_records(implementation_realized_risks_mapped)
    }

    # Validate and clean custom_prompt
    if custom_prompt:
        if not isinstance(custom_prompt, str):
            custom_prompt = None
        else:
            custom_prompt = custom_prompt.strip() if custom_prompt else None

    # Use custom prompt if provided, otherwise use default
    system_prompt = custom_prompt if custom_prompt else get_default_briefing_prompt("project-based", n_paragraphs=n_projects)

    system_prompt = apply_style_guardrails(system_prompt)

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

RRA_HEADINGS = [
    "Social unrest, protests, and oppression",
    "Violence between refugees, host communities, and the state",
    "Organized violence between political and sectarian groups",
    "Political instability",
    "External risks and intra-state conflict",
]


def generate_rra_aligned_briefing(
    country_risks_df,
    pad_risks,
    implementation_realized_risks,
    implementation_realized_risks_mapped,
    client,
    project_names_by_id=None,
    custom_prompt=None
):
    """
    Generate a briefing structured around the five standard RRA short-term
    FCV risk headings.
    """
    n_paragraphs = len(RRA_HEADINGS)
    implementation_realized_risks, implementation_realized_risks_mapped = prepare_implementation_evidence(
        implementation_realized_risks,
        implementation_realized_risks_mapped,
    )

    evidence = {
        "categories": RRA_HEADINGS,
        "project_names": build_project_name_map(
            project_names_by_id,
            pad_risks,
            implementation_realized_risks,
            implementation_realized_risks_mapped,
        ),
        "country_risks": sanitize_evidence_records(country_risks_df),
        "pad_risks": sanitize_evidence_records(pad_risks),
        "implementation_realized_risks": sanitize_evidence_records(implementation_realized_risks),
        "implementation_realized_risks_mapped": sanitize_evidence_records(implementation_realized_risks_mapped),
    }

    if custom_prompt:
        if not isinstance(custom_prompt, str):
            custom_prompt = None
        else:
            custom_prompt = custom_prompt.strip() if custom_prompt else None

    system_prompt = custom_prompt if custom_prompt else get_default_briefing_prompt("rra", n_paragraphs=n_paragraphs)

    system_prompt = apply_style_guardrails(system_prompt)

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "Evidence:\n\n{evidence}"),
    ])

    chain = prompt | client
    message = chain.invoke({"evidence": json.dumps(evidence, indent=2)})
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
    project_names_by_id=None,
    custom_categories=None,
    custom_prompt=None,
    max_projects=None,
    selected_project_ids=None
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
    
    project_selection = build_project_selection(
        pad_risks,
        implementation_realized_risks,
        implementation_realized_risks_mapped,
        max_projects=max_projects,
        preferred_project_ids=extract_project_ids_from_prompt(custom_prompt),
        selected_project_ids=selected_project_ids
    )

    if project_selection['portfolio_too_large'] or project_selection['selection_source'] == 'manual':
        print(
            f"   ℹ️ Using {len(project_selection['selected_project_ids'])} projects "
            f"({project_selection['selection_source']}, keeping "
            f"{project_selection['total_risks_selected']}/{project_selection['total_risks_available']} risk items)"
        )

    pad_risks, implementation_realized_risks, implementation_realized_risks_mapped = filter_project_evidence(
        pad_risks,
        implementation_realized_risks,
        implementation_realized_risks_mapped,
        project_selection['selected_project_ids']
    )
    
    # Generate briefing based on mode
    if mode == "rra":
        briefing = generate_rra_aligned_briefing(
            country_risks_df=country_risks_df,
            pad_risks=pad_risks,
            implementation_realized_risks=implementation_realized_risks,
            implementation_realized_risks_mapped=implementation_realized_risks_mapped,
            client=client,
            project_names_by_id=build_project_name_map(
                project_names_by_id,
                pad_risks,
                implementation_realized_risks,
                implementation_realized_risks_mapped,
                selected_project_ids=project_selection['selected_project_ids'],
            ),
            custom_prompt=custom_prompt,
        )

    elif mode == "risk":
        briefing = generate_risk_aligned_briefing(
            country_risks_df=country_risks_df,
            pad_risks=pad_risks,
            implementation_realized_risks_mapped=implementation_realized_risks_mapped,
            n_paragraphs=n_paragraphs,
            client=client,
            project_names_by_id=build_project_name_map(
                project_names_by_id,
                pad_risks,
                implementation_realized_risks_mapped,
                selected_project_ids=project_selection['selected_project_ids'],
            ),
            custom_prompt=custom_prompt
        )

    elif mode == "sector":
        briefing = generate_sector_aligned_briefing(
            country_risks_df=country_risks_df,
            pad_risks=pad_risks,
            implementation_realized_risks=implementation_realized_risks,
            n_paragraphs=n_paragraphs,
            client=client,
            project_names_by_id=build_project_name_map(
                project_names_by_id,
                pad_risks,
                implementation_realized_risks,
                selected_project_ids=project_selection['selected_project_ids'],
            ),
            custom_prompt=custom_prompt
        )

    elif mode == "project-based":
        briefing = generate_project_based_briefing(
            country_risks_df=country_risks_df,
            pad_risks=pad_risks,
            implementation_realized_risks=implementation_realized_risks,
            implementation_realized_risks_mapped=implementation_realized_risks_mapped,
            client=client,
            project_names_by_id=build_project_name_map(
                project_names_by_id,
                pad_risks,
                implementation_realized_risks,
                implementation_realized_risks_mapped,
                selected_project_ids=project_selection['selected_project_ids'],
            ),
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
            project_names_by_id=build_project_name_map(
                project_names_by_id,
                pad_risks,
                implementation_realized_risks,
                implementation_realized_risks_mapped,
                selected_project_ids=project_selection['selected_project_ids'],
            ),
            custom_prompt=custom_prompt
        )

    else:
        raise ValueError("mode must be 'rra', 'risk', 'sector', 'project-based', or 'custom'")
    
    # Inject links for citation markers
    briefing = inject_links(briefing, country_document_df)
    
    return briefing