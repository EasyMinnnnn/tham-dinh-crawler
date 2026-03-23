from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


COMMON_REPLACEMENTS = {
    "GÐ": "GĐ",
    "TÐV": "TDV",
    "nghè": "nghề",
    "nghê": "nghề",
    "Só:": "Số:",
    "CHU NGHĨA": "CHỦ NGHĨA",
}


def collapse_spaces(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def fix_common_ocr_errors(text: str) -> str:
    text = text or ""
    for bad, good in COMMON_REPLACEMENTS.items():
        text = text.replace(bad, good)
    text = re.sub(r"\bTÐV\b", "TDV", text, flags=re.IGNORECASE)
    text = re.sub(r"\bGÐ\b", "GĐ", text, flags=re.IGNORECASE)
    return collapse_spaces(text)


def normalize_name(text: str) -> Optional[str]:
    text = fix_common_ocr_errors(text)
    text = re.sub(r"^\d+\s+", "", text)
    text = re.sub(r"\b(TDV|GĐ|GD)\b$", "", text, flags=re.IGNORECASE).strip()
    return text or None


def normalize_card_no(text: str) -> Optional[str]:
    text = fix_common_ocr_errors(text).upper()
    text = text.replace(" ", "")
    m = re.search(r"\b([A-ZIVX]+\d+[A-Z]*\.\d+)\b", text)
    if m:
        return m.group(1)
    return text or None


def normalize_notice_content(text: str) -> Optional[str]:
    text = fix_common_ocr_errors(text)

    if "người đại diện theo pháp luật" in text.lower():
        return "Đủ điều kiện hành nghề, người đại diện theo pháp luật"

    if "kinh doanh dịch vụ" in text.lower() and "thẩm định giá" in text.lower():
        return "Đủ điều kiện kinh doanh dịch vụ thẩm định giá"

    if "đủ điều kiện hành nghề" in text.lower():
        return "Đủ điều kiện hành nghề"

    return text or None


def normalize_effective_date(text: str) -> Optional[str]:
    text = fix_common_ocr_errors(text)
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", text)
    if not m:
        return None
    dd = int(m.group(1))
    mm = int(m.group(2))
    yyyy = int(m.group(3))
    return f"{yyyy:04d}-{mm:02d}-{dd:02d}"


def normalize_position(text: str) -> Optional[str]:
    text = fix_common_ocr_errors(text).upper()

    if re.search(r"\bGĐ\b", text):
        return "GĐ"
    if re.search(r"\bGD\b", text):
        return "GĐ"
    if re.search(r"\bTDV\b", text):
        return "TDV"

    return text or None


def normalize_scope(text: str) -> Optional[str]:
    text = fix_common_ocr_errors(text)
    lowered = text.lower()

    if "tài sản" in lowered and "doanh nghiệp" in lowered:
        return "Tài sản và doanh nghiệp"

    return text or None


def normalize_tt(text: str) -> Optional[int]:
    text = fix_common_ocr_errors(text)
    m = re.search(r"\d{1,2}", text)
    return int(m.group(0)) if m else None


def confidence_score(record: Dict[str, Any]) -> float:
    score = 0.0
    if record.get("tt") is not None:
        score += 0.10
    if record.get("full_name"):
        score += 0.25
    if record.get("card_no"):
        score += 0.25
    if record.get("notice_content"):
        score += 0.15
    if record.get("effective_date"):
        score += 0.10
    if record.get("position"):
        score += 0.075
    if record.get("valuation_scope"):
        score += 0.075
    return round(min(score, 1.0), 3)


def normalize_record(
    row: Dict[str, Any],
    doc_meta: Dict[str, Any],
) -> Dict[str, Any]:
    raw_name = row.get("full_name", "")
    raw_card_no = row.get("card_no", "")
    raw_notice = row.get("notice_content", "")
    raw_effective = row.get("effective_date", "")
    raw_position = row.get("position", "")
    raw_scope = row.get("valuation_scope", "")
    raw_tt = row.get("tt", "")

    normalized = {
        "doc_no": doc_meta.get("doc_no"),
        "signed_date": doc_meta.get("signed_date"),
        "title": doc_meta.get("title"),
        "company_name": doc_meta.get("company_name"),
        "company_code": doc_meta.get("company_code"),
        "source_url": doc_meta.get("source_url"),
        "tt": normalize_tt(str(raw_tt)),
        "full_name": normalize_name(raw_name),
        "card_no": normalize_card_no(raw_card_no),
        "notice_content": normalize_notice_content(raw_notice),
        "effective_date": normalize_effective_date(raw_effective),
        "position": normalize_position(raw_position),
        "valuation_scope": normalize_scope(raw_scope),
        "repair_flag": bool(row.get("repair_flag", False)),
        "raw_layout_row": row.get("_raw_layout_row"),
        "raw_ocr_row": [
            {
                "text": fix_common_ocr_errors(x.get("text", "")),
                "x_min": x.get("x_min"),
                "x_max": x.get("x_max"),
                "y_min": x.get("y_min"),
                "y_max": x.get("y_max"),
            }
            for x in row.get("_raw_ocr_lines", [])
        ],
        "_debug_columns": row.get("_debug_columns", {}),
    }

    normalized["confidence_score"] = confidence_score(normalized)
    return normalized


def normalize_records(
    repaired_rows: List[Dict[str, Any]],
    doc_meta: Dict[str, Any],
) -> List[Dict[str, Any]]:
    out = [normalize_record(row, doc_meta) for row in repaired_rows]

    # bỏ các dòng rỗng hoàn toàn
    out = [
        r for r in out
        if r.get("full_name") or r.get("card_no") or r.get("notice_content")
    ]

    return out
