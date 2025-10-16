from typing import List, Optional

from pdfminer.high_level import extract_text


def extract_text_from_pdf(pdf_path: str, pages: Optional[List[int]] = None) -> str:
    """Return full text from the specified PDF.

    pages: optional 1-based page numbers to include. If None, include all pages.
    """
    page_numbers_zero_based = (
        [page - 1 for page in pages] if pages is not None and len(pages) > 0 else None
    )
    return extract_text(pdf_path, page_numbers=page_numbers_zero_based)


def extract_text_by_page(pdf_path: str, pages: Optional[List[int]] = None) -> List[str]:
    """Return a list of page texts from the specified PDF.

    pages: optional 1-based page numbers to include. If None, include all pages.
    """
    if pages is None or len(pages) == 0:
        # pdfminer extract_text with page_numbers=None returns full text; we split pages by form feed
        full_text = extract_text(pdf_path)
        return [p for p in full_text.split("\f") if p]

    texts: List[str] = []
    for page in pages:
        zero_based = page - 1
        text = extract_text(pdf_path, page_numbers=[zero_based])
        texts.append(text)
    return texts
