
import requests
import fitz
from io import BytesIO

def fetch_pdf_text(guid, node_id, text_url = None, pdf_url = None) -> str:
    if guid and len(guid) < 18:
            guid = "0" + guid
    url = f"https://documents1.worldbank.org/curated/en/{guid}/pdf/{node_id}.pdf"
    try:
        response = requests.get(url, timeout=20)
        response.raise_for_status()
        if "application/pdf" not in response.headers.get("Content-Type", "").lower():
            print(f"⚠️ Not a PDF: {url}")
            return ""
        with fitz.open(stream=BytesIO(response.content), filetype="pdf") as pdf:
            text = " ".join(page.get_text("text") for page in pdf)
        return text.strip()
    except Exception as e:
        print(f"⚠️ Error fetching {url}: {e}")
        return ""

import re

def clean_text(text: str) -> str:
    """
    Light normalization of PDF text.
    Does NOT alter meaning.
    Only removes excessive whitespace and formatting artifacts.
    """
    if not text:
        return ""

    # Replace multiple whitespace with single space
    text = re.sub(r"\s+", " ", text)

    # Strip leading/trailing whitespace
    return text.strip()
