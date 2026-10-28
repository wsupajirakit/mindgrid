"""PDF text per page (pypdf, BSD). Encrypted PDFs are refused; the page count is capped.
Layout-aware parsing (tables, figures) can plug in later behind the same registry."""

import io

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from mindgrid.core.errors import ApiError

from .. import config as intake_config
from ..sanitize import clean
from ..sections import Section


def parse(data: bytes) -> list[Section]:
    try:
        reader = PdfReader(io.BytesIO(data))
    except PdfReadError:
        raise ApiError(400, "document.unreadable", "the PDF cannot be read") from None
    if reader.is_encrypted:
        raise ApiError(400, "document.encrypted", "encrypted PDFs are not accepted")
    limit = intake_config.get_settings().pdf_max_pages
    sections: list[Section] = []
    for number, page in enumerate(reader.pages[:limit], start=1):
        text = clean(page.extract_text() or "")
        if text:
            sections.append(Section(text=text, location={"page": number}))
    return sections
