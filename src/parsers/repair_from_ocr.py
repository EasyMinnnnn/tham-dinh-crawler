from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


def load_json(path: str | Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def collapse_spaces(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def text_from_anchor(text_anchor: Dict[str, Any], full_text: str) -> str:
    segments = text_anchor.get("textSegments", []) or []
    parts: List[str] = []

    for seg in segments:
        start = int(seg.get("startIndex", 0) or 0)
        end = int(seg.get("endIndex", 0) or 0)
        if end > start:
            parts.append(full_text[start:end])

    return "".join(parts)


def bbox_from_layout(layout: Dict[str, Any]) -> Dict[str, float]:
    poly = layout.get("boundingPoly", {}) or {}
    vertices = poly.get("normalizedVertices", []) or []

    if not vertices:
        vertices = poly.get("vertices", []) or []
        # fallback nếu không có normalizedVertices thì scale về [0,1] không đảm bảo
        # nhưng với file của bạn normalizedVertices đang có đầy đủ.
        if not vertices:
            return {"x_min": 0.0, "x_max": 0.0, "y_min": 0.0, "y_max": 0.0}

        xs = [float(v.get("x", 0.0)) for v in vertices]
        ys = [float(v.get("y", 0.0)) for v in vertices]
        return {
            "x_min": min(xs),
            "x_max": max(xs),
            "y_min": min(ys),
            "y_max": max(ys),
        }

    xs = [float(v.get("x", 0.0)) for v in vertices]
    ys = [float(v.get("y", 0.0)) for v in vertices]
    return {
        "x_min": min(xs),
        "x_max": max(xs),
        "y_min": min(ys),
        "y_max": max(ys),
    }


def extract_ocr_lines(ocr_json_path: str | Path) -> List[Dict[str, Any]]:
    data = load_json(ocr_json_path)
    full_text = data.get("text", "") or ""
    pages = data.get("pages", []) or []

    lines_out: List[Dict[str, Any]] = []

    for page in pages:
        for line in page.get("lines", []) or []:
            layout = line.get("layout", {}) or {}
            text_anchor = layout.get("textAnchor", {}) or {}
            text = collapse_spaces(text_from_anchor(text_anchor, full_text))
            if not text:
                continue

            bbox = bbox_from_layout(layout)
            lines_out.append(
                {
                    "text": text,
                    "bbox": bbox,
                    "x_min": bbox["x_min"],
                    "x_max": bbox["x_max"],
                    "y_min": bbox["y_min"],
                    "y_max": bbox["y_max"],
                    "x_center": (bbox["x_min"] + bbox["x_max"]) / 2,
                    "y_center": (bbox["y_min"] + bbox["y_max"]) / 2,
                    "confidence": float(layout.get("confidence", 0.0) or 0.0),
                }
            )

    lines_out.sort(key=lambda x: (x["y_center"], x["x_min"]))
    return lines_out


def normalize_text_for_compare(text: str) -> str:
    return collapse_spaces(text).lower()


def overlap_x(a: Dict[str, float], b: Dict[str, float]) -> float:
    left = max(a["x_min"], b["x_min"])
    right = min(a["x_max"], b["x_max"])
    if right <= left:
        return 0.0
    overlap = right - left
    width = max(1e-9, min(a["x_max"] - a["x_min"], b["x_max"] - b["x_min"]))
    return overlap / width


def line_hits_column(line: Dict[str, Any], col: Dict[str, Any]) -> bool:
    line_box = {
        "x_min": line["x_min"],
        "x_max": line["x_max"],
        "y_min": line["y_min"],
        "y_max": line["y_max"],
    }
    col_box = {
        "x_min": col["x_min"],
        "x_max": col["x_max"],
        "y_min": col["y_min"],
        "y_max": col["y_max"],
    }

    if overlap_x(line_box, col_box) >= 0.20:
        return True

    return col["x_min"] <= line["x_center"] <= col["x_max"]


def get_tt_column(layout_table: Dict[str, Any]) -> Dict[str, Any]:
    for col in layout_table["column_regions"]:
        if col["field_key"] == "tt":
            return col
    raise ValueError("Không tìm thấy cột TT trong layout_table.")


def header_y_max(layout_table: Dict[str, Any]) -> float:
    return max(c["bbox"]["y_max"] for c in layout_table["header_row"])


def table_y_max(layout_table: Dict[str, Any]) -> float:
    return layout_table["table_bbox"]["y_max"]


def find_row_markers(ocr_lines: List[Dict[str, Any]], layout_table: Dict[str, Any]) -> List[Dict[str, Any]]:
    tt_col = get_tt_column(layout_table)
    y_top = header_y_max(layout_table)
    y_bottom = table_y_max(layout_table)

    markers = []
    for line in ocr_lines:
        if line["y_center"] <= y_top:
            continue
        if line["y_center"] >= y_bottom:
            continue
        if not line_hits_column(line, tt_col):
            continue

        txt = normalize_text_for_compare(line["text"])
        if re.fullmatch(r"\d{1,2}", txt):
            markers.append(line)

    markers.sort(key=lambda x: x["y_center"])

    deduped = []
    for m in markers:
        if not deduped:
            deduped.append(m)
            continue
        if abs(m["y_center"] - deduped[-1]["y_center"]) < 0.008:
            # gần như cùng một marker -> giữ marker confidence cao hơn
            if m["confidence"] > deduped[-1]["confidence"]:
                deduped[-1] = m
        else:
            deduped.append(m)

    return deduped


def build_row_ranges(markers: List[Dict[str, Any]], layout_table: Dict[str, Any]) -> List[Dict[str, float]]:
    if not markers:
        return []

    top = header_y_max(layout_table) + 0.002
    bottom = table_y_max(layout_table) + 0.003

    centers = [m["y_center"] for m in markers]
    ranges = []

    for i, marker in enumerate(markers):
        if i == 0:
            row_top = top
        else:
            row_top = (centers[i - 1] + centers[i]) / 2

        if i == len(markers) - 1:
            row_bottom = bottom
        else:
            row_bottom = (centers[i] + centers[i + 1]) / 2

        ranges.append(
            {
                "tt": marker["text"].strip(),
                "y_min": row_top,
                "y_max": row_bottom,
            }
        )

    return ranges


def collect_lines_for_row(
    ocr_lines: List[Dict[str, Any]],
    y_min: float,
    y_max: float,
) -> List[Dict[str, Any]]:
    row_lines = []
    for line in ocr_lines:
        if line["y_center"] < y_min:
            continue
        if line["y_center"] >= y_max:
            continue
        row_lines.append(line)
    row_lines.sort(key=lambda x: (x["y_center"], x["x_min"]))
    return row_lines


def join_line_texts(lines: List[Dict[str, Any]]) -> str:
    texts = []
    seen = set()

    for line in sorted(lines, key=lambda x: (x["y_center"], x["x_min"])):
        t = collapse_spaces(line["text"])
        if not t:
            continue
        key = (round(line["y_center"], 4), t)
        if key in seen:
            continue
        seen.add(key)
        texts.append(t)

    return collapse_spaces(" ".join(texts))


def assign_lines_to_columns(
    row_lines: List[Dict[str, Any]],
    column_regions: List[Dict[str, Any]],
) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    debug_columns: Dict[str, List[str]] = {}

    for col in column_regions:
        matched = [line for line in row_lines if line_hits_column(line, col)]
        text = join_line_texts(matched)

        result[col["field_key"]] = text
        debug_columns[col["field_key"]] = [m["text"] for m in matched]

    result["_debug_columns"] = debug_columns
    return result


def repair_rows_from_ocr(
    ocr_json_path: str | Path,
    layout_table: Dict[str, Any],
) -> List[Dict[str, Any]]:
    ocr_lines = extract_ocr_lines(ocr_json_path)
    markers = find_row_markers(ocr_lines, layout_table)
    row_ranges = build_row_ranges(markers, layout_table)

    repaired_rows: List[Dict[str, Any]] = []

    for row_range in row_ranges:
        row_lines = collect_lines_for_row(
            ocr_lines=ocr_lines,
            y_min=row_range["y_min"],
            y_max=row_range["y_max"],
        )
        row_data = assign_lines_to_columns(
            row_lines=row_lines,
            column_regions=layout_table["column_regions"],
        )

        row_data["tt"] = row_range["tt"]
        row_data["_row_range"] = row_range
        row_data["_raw_ocr_lines"] = row_lines
        row_data["repair_flag"] = True
        repaired_rows.append(row_data)

    return repaired_rows


if __name__ == "__main__":
    import argparse
    import json as jsonlib
    from parse_layout_table import extract_layout_table

    parser = argparse.ArgumentParser()
    parser.add_argument("ocr_json_path")
    parser.add_argument("layout_json_path")
    args = parser.parse_args()

    layout_table = extract_layout_table(args.layout_json_path)
    rows = repair_rows_from_ocr(args.ocr_json_path, layout_table)
    print(jsonlib.dumps(rows, ensure_ascii=False, indent=2))
