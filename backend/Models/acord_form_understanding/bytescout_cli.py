from __future__ import annotations

import logging
import os
import shlex
import subprocess
import tempfile
from pathlib import Path
import csv
from typing import Optional

from .uir import Table, TextBlock, UnifiedIntermediateRepresentation


logger = logging.getLogger("fideon.bytescout")

_COMMON_EXE_NAMES = [
    # Common naming patterns for PDF->Text tools in CLI suites
    "pdf2text.exe",
    "pdftotext.exe",
    "pdf-to-text.exe",
    "pdftext.exe",
    # Generic fallbacks
    "bytescout.exe",
]


def _enabled() -> bool:
    return (os.getenv("BYTESCOUT_ENABLED") or "").strip().lower() in {"1", "true", "yes", "on"}


def _timeout_secs() -> int:
    try:
        return int((os.getenv("BYTESCOUT_TIMEOUT_SECS") or "30").strip())
    except Exception:
        return 30


def _tmp_dir() -> Optional[str]:
    v = (os.getenv("BYTESCOUT_TMP_DIR") or "").strip()
    return v or None


def _cmd_template() -> str:
    """
    A fully configurable command template so we don't depend on a specific ByteScout CLI product.

    It MUST write extracted text to {output_txt}.

    Supported placeholders:
    - {cli}: BYTESCOUT_CLI_PATH
    - {input_pdf}: temp PDF path
    - {output_txt}: temp output text path
    - {output_dir}: temp output directory
    """
    return (os.getenv("BYTESCOUT_CMD_TEMPLATE") or "").strip()


def _default_templates_for_exe(exe_path: str) -> list[str]:
    """
    Provide sane defaults for common CLI styles.
    We keep these generic (no product-specific flags) and rely on multiple attempts.
    """
    exe = Path(exe_path).name.lower()

    # Many cli tools accept: <input> <output>
    t_basic = "\"{cli}\" \"{input_pdf}\" \"{output_txt}\""

    # Some accept explicit flags for input/output
    t_in_out = "\"{cli}\" -i \"{input_pdf}\" -o \"{output_txt}\""
    t_in_out_long = "\"{cli}\" --input \"{input_pdf}\" --output \"{output_txt}\""

    # Some accept output dir + auto naming (we still need output_txt, so include it)
    t_out_first = "\"{cli}\" \"{output_txt}\" \"{input_pdf}\""

    # A few accept page range; we expose {max_pages} so user can override if supported.
    t_pages = "\"{cli}\" -i \"{input_pdf}\" -o \"{output_txt}\" -pages 1-{max_pages}"

    # Choose ordering based on exe hints, but always return a list to try.
    if "pdftotext" in exe or "pdf2text" in exe or "pdftext" in exe:
        return [t_basic, t_in_out, t_in_out_long, t_pages, t_out_first]

    return [t_in_out, t_in_out_long, t_basic, t_pages, t_out_first]


def _discover_cli_path() -> str:
    """
    If BYTESCOUT_CLI_PATH is not set, try common install locations (Windows).
    Returns empty string if not found.
    """
    configured = (os.getenv("BYTESCOUT_CLI_PATH") or "").strip()
    if configured:
        # Allow pointing to a directory: pick first matching exe.
        p = Path(configured)
        if p.exists() and p.is_dir():
            for name in _COMMON_EXE_NAMES:
                cand = p / name
                if cand.exists():
                    return str(cand)
        return configured

    roots: list[Path] = []
    for env_name in ("ProgramFiles", "ProgramFiles(x86)"):
        v = os.getenv(env_name)
        if v:
            roots.append(Path(v))

    # Search a couple typical vendor folders without deep recursion (keeps it fast).
    vendor_dirs: list[Path] = []
    for r in roots:
        vendor_dirs.extend(
            [
                r / "ByteScout",
                r / "Bytescout",
                r / "ByteScout PDF Tools",
                r / "ByteScout Command Line Tools",
            ]
        )

    for vd in vendor_dirs:
        if not vd.exists():
            continue
        # Check immediate children and one level deep.
        candidates: list[Path] = []
        candidates.extend([vd / name for name in _COMMON_EXE_NAMES])
        for child in vd.iterdir():
            if child.is_dir():
                candidates.extend([child / name for name in _COMMON_EXE_NAMES])
        for c in candidates:
            if c.exists():
                return str(c)
    return ""


def _cmd_templates() -> list[str]:
    """
    Support multiple templates, tried in order.
    Use '||' to separate alternatives in BYTESCOUT_CMD_TEMPLATE.
    """
    raw = _cmd_template()
    if not raw:
        return []
    parts = [p.strip() for p in raw.split("||")]
    return [p for p in parts if p]


def _max_pages() -> int:
    try:
        return int((os.getenv("BYTESCOUT_MAX_PAGES") or "20").strip())
    except Exception:
        return 20


def _read_tables_from_output_dir(output_dir: Path) -> list[Table]:
    """
    Best-effort: if the CLI drops any CSVs in output_dir, treat each CSV as a table.
    This is generic and works across many PDF tool CLIs.
    """
    tables: list[Table] = []
    for csv_path in sorted(output_dir.glob("*.csv")):
        try:
            with csv_path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
                reader = csv.reader(f)
                rows = [[(c or "").strip() for c in row] for row in reader]
            if any(any(cell for cell in r) for r in rows):
                tables.append(Table(page=1, bbox=None, rows=rows))
        except Exception:
            continue
    return tables


def try_extract_pdf_to_uir(pdf_bytes: bytes, *, filename: str | None = None) -> UnifiedIntermediateRepresentation | None:
    """
    Best-effort PDF extraction via ByteScout CLI (Windows-only).
    Returns a UIR on success, or None to indicate fallback should be used.
    """
    if not _enabled():
        return None

    cli = _discover_cli_path()
    templates = _cmd_templates()
    if not cli and not templates:
        logger.info("ByteScout enabled but CLI not configured/found; falling back.")
        return None
    if cli and not templates:
        templates = _default_templates_for_exe(cli)
    if not cli:
        # If user provided templates that already reference an absolute exe path, allow it.
        # In this case {cli} will be empty; templates should not use it.
        logger.info("ByteScout using templates without cli path.")

    timeout = _timeout_secs()
    max_pages = _max_pages()
    base_tmp = _tmp_dir()

    with tempfile.TemporaryDirectory(prefix="bytescout_", dir=base_tmp) as td:
        tdir = Path(td)
        in_pdf = tdir / ("input.pdf" if not filename else Path(filename).name.replace(" ", "_"))
        out_txt = tdir / "output.txt"
        in_pdf.write_bytes(pdf_bytes)

        last_err: str | None = None
        for template in templates:
            cmd_str = template.format(
                cli=cli,
                input_pdf=str(in_pdf),
                output_txt=str(out_txt),
                output_dir=str(tdir),
                max_pages=str(max_pages),
            )
            # Windows-safe split
            cmd = shlex.split(cmd_str, posix=False)

            try:
                logger.info(
                    "ByteScout cmd=%s timeout=%ss",
                    " ".join(cmd[:2]) if cmd else "<empty>",
                    timeout,
                )
                completed = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    check=False,
                    shell=False,
                )
            except subprocess.TimeoutExpired:
                last_err = f"timeout after {timeout}s"
                continue
            except FileNotFoundError:
                last_err = f"executable not found: {cmd[0] if cmd else '<empty>'}"
                continue
            except Exception as exc:
                last_err = str(exc)
                continue

            if completed.returncode != 0:
                stderr_head = (completed.stderr or "").strip().replace("\r", "")[:400]
                last_err = f"exit_code={completed.returncode} stderr={stderr_head}"
                continue

            if not out_txt.exists():
                last_err = f"no output_txt at {out_txt}"
                continue

            text = out_txt.read_text(encoding="utf-8", errors="ignore").strip()
            if len(text) < 300:
                last_err = f"output too small ({len(text)} chars)"
                continue

            tables = _read_tables_from_output_dir(tdir)
            uir = UnifiedIntermediateRepresentation(
                text_blocks=[TextBlock(text=text, page=1, bbox=None, source="pdf_text")],
                tables=tables,
                key_values=[],
                layout={"provider": "bytescout-cli", "tables_detected": len(tables)},
            )
            return uir

        logger.warning("ByteScout failed all templates; falling back. last_err=%s", last_err)
        return None

