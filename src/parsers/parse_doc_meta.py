from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Optional


DOC_NO_PATTERNS = [
    r"\b(\d{1,5}\s*/\s*TB-BTC)\b",
    r"\b(\d{1,5}\s*/\s*QĐ-BTC)\b",
    r"\b(\d{1,5}\s*/\s*[A-ZĐ\-]+)\b",
]

COMPANY_CODE_PATTERNS = [
    r"\((\d+\s*/\s*T[ĐD]G)\)",
    r"\((\d+\s*/\s*TDG)\)",
]


def load_json(path: str | Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def collapse_spaces(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_line(text: str) -> str:
    return collapse_spaces(text.replace("\n", " "))


def normalize_doc_no(text: str) -> str:
    return re.sub(r"\s+", "", text.upper())


def parse_date_to_iso(day: str, month: str, year: str) -> str:
    dd = int(day)
    mm = int(month)
    yyyy = int(year)
    return f"{yyyy:04d}-{mm:02d}-{dd:02d}"


def extract_doc_no(text: str) -> Optional[str]:
    for pattern in DOC_NO_PATTERNS:
        m = re.search(pattern, text, flags=re.IGNORECASE)
        if m:
            return normalize_doc_no(m.group(1))
    return None


def extract_signed_date(text: str) -> Optional[str]:
    # Ưu tiên dòng "Thời gian ký"
    m = re.search(
        r"Thời gian ký\s*:\s*(\d{1,2})/(\d{1,2})/(\d{4})",
        text,
        flags=re.IGNORECASE,
    )
    if m:
        return parse_date_to_iso(m.group(1), m.group(2), m.group(3))

    # Fallback: "Hà Nội, ngày 09 tháng 3 năm 2026"
    m = re.search(
        r"ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})",
        text,
        flags=re.IGNORECASE,
    )
    if m:
        return parse_date_to_iso(m.group(1), m.group(2), m.group(3))

    return None


def extract_title(lines: list[str]) -> Optional[str]:
    """
    Tìm title kiểu:
    THÔNG BÁO
    Về danh sách thẩm định viên về giá năm 2026
    tại Công ty Cổ phần Thẩm định giá Quang Minh
    """
    for i, line in enumerate(lines):
        line_clean = clean_line(line)
        if line_clean.lower().startswith("về danh sách thẩm định viên về giá"):
            parts = [line_clean]
            if i + 1 < len(lines):
                next_line = clean_line(lines[i + 1])
                if next_line.lower().startswith("tại "):
                    parts.append(next_line)
            return " ".join(parts)
    return None


def extract_company_name(text: str, title: Optional[str]) -> Optional[str]:
    # Ưu tiên lấy từ title
    if title:
        m = re.search(r"\btại\s+(Công ty.+)$", title, flags=re.IGNORECASE)
        if m:
            return clean_line(m.group(1))

    # Fallback: lấy từ body, ví dụ "Công ty ... (509/TĐG)"
    m = re.search(
        r"(Công ty[^\n]+?)\s*\((\d+\s*/\s*T[ĐD]G)\)",
        text,
        flags=re.IGNORECASE,
    )
    if m:
        return clean_line(m.group(1))

    # Fallback: dòng riêng "tại Công ty ..."
    m = re.search(r"\btại\s+(Công ty[^\n]+)", text, flags=re.IGNORECASE)
    if m:
        return clean_line(m.group(1))

    return None


def extract_company_code(text: str) -> Optional[str]:
    for pattern in COMPANY_CODE_PATTERNS:
        m = re.search(pattern, text, flags=re.IGNORECASE)
        if m:
            return normalize_doc_no(m.group(1)).replace("TDG", "TĐG")
    return None


def extract_year_from_title(title: Optional[str]) -> Optional[int]:
    if not title:
        return None
    m = re.search(r"năm\s+(\d{4})", title, flags=re.IGNORECASE)
    return int(m.group(1)) if m else None


def parse_document_meta(
    ocr_json_path: str | Path,
    source_url: Optional[str] = None,
    pdf_path: Optional[str] = None,
    layout_json_path: Optional[str] = None,
) -> Dict[str, Any]:
    data = load_json(ocr_json_path)
    raw_text = data.get("text", "") or ""
    text = collapse_spaces(raw_text)
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]

    title = extract_title(lines)
    company_name = extract_company_name(raw_text, title)
    company_code = extract_company_code(raw_text)

    doc_no = extract_doc_no(raw_text)
    signed_date = extract_signed_date(raw_text)

    doc_type = None
    if doc_no and "/" in doc_no:
        doc_type = doc_no.split("/", 1)[1]

    return {
        "doc_no": doc_no,
        "doc_type": doc_type,
        "signed_date": signed_date,
        "title": title,
        "company_name": company_name,
        "company_code": company_code,
        "year": extract_year_from_title(title),
        "source_url": source_url,
        "pdf_path": str(pdf_path) if pdf_path else None,
        "ocr_json_path": str(ocr_json_path),
        "layout_json_path": str(layout_json_path) if layout_json_path else None,
        "raw_text": raw_text,
    }


if __name__ == "__main__":
    import argparse
    from pprint import pprint

    parser = argparse.ArgumentParser()
    parser.add_argument("ocr_json_path")
    parser.add_argument("--source-url", default=None)
    parser.add_argument("--pdf-path", default=None)
    parser.add_argument("--layout-json-path", default=None)
    args = parser.parse_args()

    meta = parse_document_meta(
        ocr_json_path=args.ocr_json_path,
        source_url=args.source_url,
        pdf_path=args.pdf_path,
        layout_json_path=args.layout_json_path,
    )
    pprint(meta)
