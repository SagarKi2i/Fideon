"""
Build instruction/output dataset from PDFs in the Sample Data folder.

Reads all PDFs from `fine_tuning/Sample Data`, extracts text, chunks it,
and generates QA-style entries for fine-tuning. Writes `dataset.json`
(next to config or in a path you specify).

Usage:
  python -m fine_tuning.pdf_to_dataset
  python -m fine_tuning.pdf_to_dataset --input-dir "fine_tuning/Sample Data" --output dataset.json
"""

from pathlib import Path
import argparse
import json
import re
from typing import Any, Dict, List, Optional

# Default folder name (relative to this file's parent)
DEFAULT_SAMPLE_DIR = "Sample Data"
DEFAULT_OUTPUT_JSON = "dataset.json"


def extract_text_from_pdf(pdf_path: Path) -> List[Dict[str, Any]]:
    """Extract text per page. Returns list of {page: int, text: str}."""
    try:
        import PyPDF2
    except ImportError:
        raise ImportError("PyPDF2 is required. Install with: pip install PyPDF2")

    pages: List[Dict[str, Any]] = []
    with open(pdf_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            text = text.strip()
            if text:
                pages.append({"page": i + 1, "text": text, "source": pdf_path.name})
    return pages


def chunk_text(
    text: str,
    max_chars: int = 1200,
    overlap_chars: int = 100,
) -> List[str]:
    """Split text into overlapping chunks by character count."""
    if not text or len(text) <= max_chars:
        return [text] if text else []
    chunks = []
    start = 0
    while start < len(text):
        end = start + max_chars
        chunk = text[start:end]
        # Try to break at sentence or line end
        if end < len(text):
            for sep in (". ", "\n\n", "\n"):
                last = chunk.rfind(sep)
                if last > max_chars // 2:
                    chunk = chunk[: last + len(sep)]
                    end = start + len(chunk)
                    break
        chunks.append(chunk.strip())
        start = end - overlap_chars
        if start >= len(text):
            break
    return chunks


def build_qa_from_chunk(
    chunk: str,
    source_name: str = "",
    page: Optional[int] = None,
    variant: str = "content",
) -> Dict[str, Any]:
    """
    Create one training example from a text chunk.
    variant: "content" | "summarize" | "what_says"
    """
    if variant == "content":
        instruction = "What information does this document section contain?"
        input_text = chunk
        output = chunk
    elif variant == "summarize":
        instruction = "Summarize the following section from the document."
        input_text = chunk
        # Use first 2-3 sentences as a simple "summary" for training
        sentences = re.split(r"(?<=[.!?])\s+", chunk)
        output = " ".join(sentences[:3]).strip() if sentences else chunk[:500]
    else:  # what_says
        instruction = "According to the document, what does this section say?"
        input_text = chunk
        output = chunk

    return {
        "instruction": instruction,
        "input": input_text,
        "output": output,
        "source": source_name,
        "page": page,
    }


def build_dataset_from_pdfs(
    input_dir: Path,
    output_path: Path,
    *,
    max_chars_per_chunk: int = 1200,
    overlap_chars: int = 100,
    variants: Optional[List[str]] = None,
    min_chunk_chars: int = 80,
) -> int:
    """
    Scan input_dir for *.pdf, extract text, chunk, build QA list, write JSON.
    Returns number of examples written.
    """
    if variants is None:
        variants = ["content"]

    input_dir = Path(input_dir)
    output_path = Path(output_path)
    if not input_dir.is_dir():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    pdf_files = sorted(input_dir.glob("*.pdf"))
    if not pdf_files:
        raise FileNotFoundError(
            f"No PDF files found in {input_dir}. Add .pdf files to the folder."
        )

    examples: List[Dict[str, Any]] = []
    for pdf_path in pdf_files:
        pages = extract_text_from_pdf(pdf_path)
        for item in pages:
            text = item["text"]
            source = item.get("source", pdf_path.name)
            page = item.get("page")
            if len(text) < min_chunk_chars:
                # Still add as one example if it has some content
                if len(text) >= 20:
                    for v in variants:
                        ex = build_qa_from_chunk(text, source_name=source, page=page, variant=v)
                        examples.append(ex)
                continue
            chunks = chunk_text(text, max_chars=max_chars_per_chunk, overlap_chars=overlap_chars)
            for chunk in chunks:
                if len(chunk) < min_chunk_chars:
                    continue
                for v in variants:
                    ex = build_qa_from_chunk(chunk, source_name=source, page=page, variant=v)
                    examples.append(ex)

    # Dedupe by (instruction, output) to avoid exact duplicates
    seen = set()
    unique = []
    for ex in examples:
        key = (ex["instruction"], ex["output"][:200])
        if key not in seen:
            seen.add(key)
            unique.append({k: v for k, v in ex.items() if k in ("instruction", "input", "output")})

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(unique, f, indent=2, ensure_ascii=False)

    return len(unique)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build dataset.json from PDFs in Sample Data folder"
    )
    parser.add_argument(
        "--input-dir",
        "-i",
        default=None,
        help=f"Folder containing PDFs (default: fine_tuning/{DEFAULT_SAMPLE_DIR})",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Output JSON path (default: fine_tuning/dataset.json)",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=1200,
        help="Max characters per chunk (default: 1200)",
    )
    parser.add_argument(
        "--overlap",
        type=int,
        default=100,
        help="Overlap between chunks in characters (default: 100)",
    )
    parser.add_argument(
        "--variants",
        nargs="+",
        default=["content"],
        choices=["content", "summarize", "what_says"],
        help="QA variants per chunk (default: content)",
    )
    args = parser.parse_args()

    base = Path(__file__).resolve().parent
    input_dir = Path(args.input_dir) if args.input_dir else base / DEFAULT_SAMPLE_DIR
    output_path = Path(args.output) if args.output else base / DEFAULT_OUTPUT_JSON

    count = build_dataset_from_pdfs(
        input_dir,
        output_path,
        max_chars_per_chunk=args.max_chars,
        overlap_chars=args.overlap,
        variants=args.variants,
    )
    print(f"Wrote {count} examples to {output_path}")


if __name__ == "__main__":
    main()
