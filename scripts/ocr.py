"""OCR fallback for image-only PDFs (no text layer at all) -- needed for AIIB's
2016-2018 financial statements, which are scanned pages. Renders each page
with pdfplumber's own rasteriser (no extra dependency) and reads it with the
`tesseract` command-line tool (`brew install tesseract`).

Cached like every other fetch in this repo: one text file per page under
data/raw/ocr/<pdf stem>/, so re-runs never re-OCR. OCR is slower (~3 s per
page) and can misread digits, so every caller must reconcile what it reads
against a printed total, exactly as with a normal text layer.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _panel import REPO  # noqa: E402

OCR_DIR = REPO / "data" / "raw" / "ocr"
DPI = 200


def has_text_layer(path: Path, sample_pages: int = 8) -> bool:
    """True if the PDF has a *usable* text layer. Two ways it can be unusable:
    no text at all (scanned images -- AIIB 2016-2018), or text that is font-
    encoding garbage, which pdfplumber renders as "(cid:12)(cid:7)..." runs
    (IDA's 2006-2007 special-purpose statements)."""

    import pdfplumber

    with pdfplumber.open(path) as pdf:
        texts = [page.extract_text() or "" for page in pdf.pages[:sample_pages]]
    if sum(len(t) for t in texts) / max(1, len(texts)) <= 50:
        return False
    return sum(t.count("(cid:") for t in texts) < 20


def page_text_upright(path: Path, index: int, must_contain: str) -> str:
    """OCR of a page image that may be rotated (a landscape table scanned onto a
    portrait page): tries 0, 90 and 270 degrees and returns the first reading that
    contains `must_contain` (case-insensitive), else the longest. Cached per
    rotation under data/raw/ocr/<stem>/pNNN_rRRR.txt."""

    import pdfplumber

    if shutil.which("tesseract") is None:
        raise SystemExit("error: OCR needs the `tesseract` command (brew install tesseract).")
    cache = OCR_DIR / path.stem
    cache.mkdir(parents=True, exist_ok=True)
    best = ""
    image = None
    for rotation in (0, 90, 270):
        cached = cache / f"p{index:03d}_r{rotation:03d}.txt"
        if not cached.is_file():
            if image is None:
                with pdfplumber.open(path) as pdf:
                    image = pdf.pages[index].to_image(resolution=DPI).original
            rotated = image.rotate(rotation, expand=True) if rotation else image
            with tempfile.TemporaryDirectory() as tmp:
                png = Path(tmp) / "page.png"
                rotated.save(png)
                result = subprocess.run(["tesseract", str(png), "stdout", "--psm", "6"], capture_output=True, text=True, check=True)
            cached.write_text(result.stdout, encoding="utf-8")
        text = cached.read_text(encoding="utf-8")
        if must_contain.lower() in text.lower():
            return text
        if len(text) > len(best):
            best = text
    return best


def page_text(path: Path, index: int) -> str:
    """One page's text, OCR'd (and cached) -- for a document whose text layer is
    fine except on a page or two (ADB's 2009 report: the OCR-8 statement page
    alone is font-encoding garbage)."""

    import pdfplumber

    if shutil.which("tesseract") is None:
        raise SystemExit("error: OCR needs the `tesseract` command (brew install tesseract).")
    cache = OCR_DIR / path.stem
    cache.mkdir(parents=True, exist_ok=True)
    cached = cache / f"p{index:03d}.txt"
    if not cached.is_file():
        with pdfplumber.open(path) as pdf:
            image = pdf.pages[index].to_image(resolution=DPI).original
        with tempfile.TemporaryDirectory() as tmp:
            png = Path(tmp) / "page.png"
            image.save(png)
            result = subprocess.run(["tesseract", str(png), "stdout", "--psm", "6"], capture_output=True, text=True, check=True)
        cached.write_text(result.stdout, encoding="utf-8")
    return cached.read_text(encoding="utf-8")


def page_texts(path: Path) -> list[str]:
    """Text of every page, OCR'd (and cached) page by page."""

    import pdfplumber

    if shutil.which("tesseract") is None:
        raise SystemExit("error: OCR needs the `tesseract` command (brew install tesseract).")
    cache = OCR_DIR / path.stem
    cache.mkdir(parents=True, exist_ok=True)
    texts: list[str] = []
    with pdfplumber.open(path) as pdf:
        for index, page in enumerate(pdf.pages):
            cached = cache / f"p{index:03d}.txt"
            if not cached.is_file():
                image = page.to_image(resolution=DPI).original
                with tempfile.TemporaryDirectory() as tmp:
                    png = Path(tmp) / "page.png"
                    image.save(png)
                    result = subprocess.run(
                        ["tesseract", str(png), "stdout", "--psm", "6"],
                        capture_output=True, text=True, check=True,
                    )
                cached.write_text(result.stdout, encoding="utf-8")
            texts.append(cached.read_text(encoding="utf-8"))
    return texts
