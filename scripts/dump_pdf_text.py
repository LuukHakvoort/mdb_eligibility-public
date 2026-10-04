"""Dump each page's text layer of a PDF to data/raw/text/<stem>/pNNN.txt (a search
cache; pages without a text layer are written empty). Usage: dump_pdf_text.py FILE.pdf"""

import logging
import sys
from pathlib import Path

logging.disable(logging.CRITICAL)
import pdfplumber  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pdf_lines import page_lines  # noqa: E402

REPO = Path(__file__).resolve().parents[1]


def main(path: str) -> None:
    pdf_path = Path(path)
    out = REPO / "data" / "raw" / "text" / pdf_path.stem
    if (out / "DONE").exists():
        return
    out.mkdir(parents=True, exist_ok=True)
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            target = out / f"p{i:03d}.txt"
            if target.exists():
                continue
            try:
                text = "\n".join(page_lines(page))
            except Exception:
                text = ""
            target.write_text(text, encoding="utf-8")
            page.flush_cache()
    (out / "DONE").write_text("")


if __name__ == "__main__":
    main(sys.argv[1])
