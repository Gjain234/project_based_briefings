from langchain_core.prompts import ChatPromptTemplate
import json
import re

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
        
        return f"[{proj_id} – {display_name}]({pdf_url})"

    return re.sub(pattern, replacer, text)

def generate_custom_aligned_briefing(
    custom_categories,
    country_risks_df,
    pad_risks,
    implementation_realized_risks,
    implementation_realized_risks_mapped,
    client
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

    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            f"You are writing a structured FCV portfolio briefing.\n\n"
            f"Write exactly {n_paragraphs} paragraphs.\n"
            "Each paragraph must correspond exactly to one of the provided categories.\n\n"
            "For each paragraph:\n"
            "- Use the category name clearly in the first sentence.\n"
            "- Integrate relevant country risks.\n"
            "- Integrate PAD risks.\n"
            "- Integrate realized implementation risks.\n\n"
            "Citation rules:\n"
            "- Use marker format: [PROJ_ID | PAD] or [PROJ_ID | ISR] or [PROJ_ID | Aide Memoire]\n"
            "- Each citation must be in its own bracket pair: [P123456 | PAD] [P123456 | ISR]\n"
            "- NEVER combine multiple citations with semicolons inside one bracket\n"
            "- NEVER write: [P123 | PAD; P456 | ISR] - this is WRONG\n"
            "- ALWAYS write: [P123 | PAD] [P456 | ISR] - this is CORRECT\n"
            "- Do NOT create hyperlinks.\n"
            "- Do NOT invent citations.\n"
            "- Only use citation markers when supported by evidence."
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
    client
):
    evidence = {
        "country_risks": country_risks_df.to_dict(orient="records"),
        "pad_risks": pad_risks.to_dict(orient="records"),
        "implementation_realized_risks_mapped": implementation_realized_risks_mapped.to_dict(orient="records")
    }

    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
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
            "Citation rules:\n"
            "- When referencing PAD evidence use marker: [PROJ_ID | PAD]\n"
            "- When referencing ISR evidence use marker: [PROJ_ID | ISR]\n"
            "- When referencing Aide Memoire use marker: [PROJ_ID | Aide Memoire]\n"
            "- Each citation must be in its own bracket pair: [P123456 | PAD] [P123456 | ISR]\n"
            "- NEVER combine multiple citations with semicolons inside one bracket\n"
            "- NEVER write: [P123 | PAD; P456 | ISR] - this is WRONG\n"
            "- ALWAYS write: [P123 | PAD] [P456 | ISR] - this is CORRECT\n"
            "- Do NOT create hyperlinks.\n"
            "- Do NOT invent citations.\n"
            "- Use citation markers only when grounded in evidence.\n"
            "- Write analytically and concisely."
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
    client
):

    evidence = {
        "country_risks": country_risks_df.to_dict(orient="records"),
        "pad_risks": pad_risks.to_dict(orient="records"),
        "implementation_realized_risks": implementation_realized_risks.to_dict(orient="records"),
    }

    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
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
            "- Use [PROJ_ID | ISR] for ISR evidence.\n"
            "- Use [PROJ_ID | Aide Memoire] for Aide Memoire evidence.\n"
            "- Each citation must be in its own bracket pair: [P123456 | PAD] [P123456 | ISR]\n"
            "- NEVER combine multiple citations with semicolons inside one bracket\n"
            "- NEVER write: [P123 | PAD; P456 | ISR] - this is WRONG\n"
            "- ALWAYS write: [P123 | PAD] [P456 | ISR] - this is CORRECT\n"
            "- Do NOT create hyperlinks.\n"
            "- Do NOT invent citations."
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
    custom_categories=None
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
    """
    
    # Generate briefing based on mode
    if mode == "risk":
        briefing = generate_risk_aligned_briefing(
            country_risks_df=country_risks_df,
            pad_risks=pad_risks,
            implementation_realized_risks_mapped=implementation_realized_risks_mapped,
            n_paragraphs=n_paragraphs,
            client=client
        )

    elif mode == "sector":
        briefing = generate_sector_aligned_briefing(
            country_risks_df=country_risks_df,
            pad_risks=pad_risks,
            implementation_realized_risks=implementation_realized_risks,
            n_paragraphs=n_paragraphs,
            client=client
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
            client=client
        )

    else:
        raise ValueError("mode must be 'risk', 'sector', or 'custom'")
    
    # Inject links for citation markers
    briefing = inject_links(briefing, country_document_df)
    
    return briefing