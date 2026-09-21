"""
Mechanical extraction of text, tables, and page/section metadata from approved
source documents. No interpretation, no diagnostic knowledge inference —
that belongs to later stages (UDS knowledge extraction / RAG).
"""
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

SUPPORTED_EXTENSIONS = {".pdf", ".txt"}

# Heuristic heading pattern for approved spec documents, e.g. "3.2 Diagnostic Session Control"
_SECTION_HEADING_RE = re.compile(r"^\s*(\d+(?:\.\d+)*)\s+([A-Z][A-Za-z0-9 ,/&()\-]{2,120})\s*$")


@dataclass
class ExtractedUnit:
    page_number: Optional[int]
    section_title: Optional[str]
    segment_type: str  # "text" | "table"
    content: str
    metadata: dict = field(default_factory=dict)


def _detect_section(line: str) -> Optional[str]:
    match = _SECTION_HEADING_RE.match(line.strip())
    if match:
        return f"{match.group(1)} {match.group(2).strip()}"
    return None


def _split_text_by_section(page_text: str) -> list[tuple[Optional[str], str]]:
    """Split a page's text into (section_title, body) chunks using heading heuristics."""
    lines = page_text.splitlines()
    chunks: list[tuple[Optional[str], list[str]]] = []
    current_section: Optional[str] = None
    current_lines: list[str] = []

    for line in lines:
        heading = _detect_section(line)
        if heading:
            if current_lines:
                chunks.append((current_section, current_lines))
            current_section = heading
            current_lines = []
        else:
            current_lines.append(line)

    if current_lines:
        chunks.append((current_section, current_lines))

    return [(section, "\n".join(body).strip()) for section, body in chunks if "\n".join(body).strip()]


def extract_txt(file_path: str) -> list[ExtractedUnit]:
    """Plain-text documents have no page boundaries; treated as a single page (page 1)."""
    text = Path(file_path).read_text(encoding="utf-8", errors="replace")
    units: list[ExtractedUnit] = []
    for section_title, body in _split_text_by_section(text):
        units.append(
            ExtractedUnit(
                page_number=1,
                section_title=section_title,
                segment_type="text",
                content=body,
                metadata={"source_format": "txt"},
            )
        )
    if not units and text.strip():
        units.append(
            ExtractedUnit(
                page_number=1,
                section_title=None,
                segment_type="text",
                content=text.strip(),
                metadata={"source_format": "txt"},
            )
        )
    return units


def extract_pdf(file_path: str) -> list[ExtractedUnit]:
    import pdfplumber

    units: list[ExtractedUnit] = []

    with pdfplumber.open(file_path) as pdf:
        for page_index, page in enumerate(pdf.pages, start=1):
            page_text = page.extract_text() or ""
            for section_title, body in _split_text_by_section(page_text):
                units.append(
                    ExtractedUnit(
                        page_number=page_index,
                        section_title=section_title,
                        segment_type="text",
                        content=body,
                        metadata={"source_format": "pdf"},
                    )
                )
            if not any(u.page_number == page_index for u in units) and page_text.strip():
                units.append(
                    ExtractedUnit(
                        page_number=page_index,
                        section_title=None,
                        segment_type="text",
                        content=page_text.strip(),
                        metadata={"source_format": "pdf"},
                    )
                )

            for table in page.extract_tables() or []:
                if not table:
                    continue
                units.append(
                    ExtractedUnit(
                        page_number=page_index,
                        section_title=None,
                        segment_type="table",
                        content=json.dumps(table),
                        metadata={
                            "source_format": "pdf",
                            "table_shape": [len(table), len(table[0]) if table[0] else 0],
                        },
                    )
                )

    return units


def extract(file_path: str) -> list[ExtractedUnit]:
    """Dispatch to the correct extractor based on file extension."""
    suffix = Path(file_path).suffix.lower()
    if suffix == ".pdf":
        return extract_pdf(file_path)
    if suffix == ".txt":
        return extract_txt(file_path)
    raise ValueError(f"Unsupported document format: {suffix}. Supported: {sorted(SUPPORTED_EXTENSIONS)}")
