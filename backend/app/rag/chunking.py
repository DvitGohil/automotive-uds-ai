"""
Pure chunking logic — no DB access, no embeddings. Splits extracted-segment
text into overlapping, size-bounded chunks; tables are kept whole (never
split) since splitting a table row-wise would break its meaning.
"""
import hashlib
from dataclasses import dataclass
from typing import Optional


@dataclass
class ChunkInput:
    segment_id: Optional[str]
    document_id: str
    document_version_id: str
    page_number: Optional[int]
    section_title: Optional[str]
    segment_type: str  # "text" | "table"
    content: str


@dataclass
class ChunkOutput:
    chunk_index: int
    segment_id: Optional[str]
    page_number: Optional[int]
    section_title: Optional[str]
    chunk_type: str
    content: str
    content_hash: str
    char_count: int


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    """Split text into overlapping windows of at most chunk_size characters."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if chunk_overlap < 0:
        raise ValueError("chunk_overlap must not be negative")
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")

    stripped = text.strip()
    if not stripped:
        return []

    if len(stripped) <= chunk_size:
        return [stripped]

    pieces: list[str] = []
    start = 0
    length = len(stripped)
    step = chunk_size - chunk_overlap

    while start < length:
        end = min(start + chunk_size, length)
        piece = stripped[start:end].strip()
        if piece:
            pieces.append(piece)
        if end == length:
            break
        start += step

    return pieces


def build_chunks(
    segments: list[ChunkInput],
    chunk_size: int,
    chunk_overlap: int,
) -> list[ChunkOutput]:
    """
    Build the full ordered chunk list for a document version's segments.
    Section-aware: chunking never crosses a segment boundary, so a chunk
    never mixes two different sections. Table-aware: table segments are
    always kept as a single whole chunk.
    """
    chunks: list[ChunkOutput] = []
    index = 0

    for segment in segments:
        if segment.segment_type == "table":
            content = segment.content.strip()
            if content:
                chunks.append(
                    ChunkOutput(
                        chunk_index=index,
                        segment_id=segment.segment_id,
                        page_number=segment.page_number,
                        section_title=segment.section_title,
                        chunk_type="table",
                        content=content,
                        content_hash=_hash(content),
                        char_count=len(content),
                    )
                )
                index += 1
            continue

        for piece in chunk_text(segment.content, chunk_size, chunk_overlap):
            chunks.append(
                ChunkOutput(
                    chunk_index=index,
                    segment_id=segment.segment_id,
                    page_number=segment.page_number,
                    section_title=segment.section_title,
                    chunk_type="text",
                    content=piece,
                    content_hash=_hash(piece),
                    char_count=len(piece),
                )
            )
            index += 1

    return chunks
