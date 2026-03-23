from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


HEADER_KEYWORDS = [
    "tt",
    "thẩm định viên",
    "số thẻ",
    "nội dung thông báo",
    "ngày hiệu lực",
    "chức danh đăng ký hành nghề",
    "lĩnh vực thẩm định giá",
]


def load_json(path: str | Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def collapse_spaces(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_for_match(text: str) -> str:
    return collapse_spaces(text).lower()


def bbox_from_normalized_vertices(vertices: List[Dict[str, float]]) -> Dict[str, float]:
    xs = [v.get("x", 0.0) for v in vertices]
    ys = [v.get("y", 0.0) for v in vertices]
    return {
        "x_min": min(xs) if xs else 0.0,
        "x_max": max(xs) if xs else 0.0,
        "y_min": min(ys) if ys else 0.0,
        "y_max": max(ys) if ys else 0.0,
    }


def union_bbox(boxes: List[Dict[str, float]]) -> Dict[str, float]:
    if not boxes:
        return {"x_min": 0.0, "x_max": 0.0, "y_min": 0.0, "y_max": 0.0}
    return {
        "x_min": min(b["x_min"] for b in boxes),
        "x_max": max(b["x_max"] for b in boxes),
        "y_min": min(b["y_min"] for b in boxes),
        "y_max": max(b["y_max"] for b in boxes),
    }


def cell_text(cell: Dict[str, Any]) -> str:
    texts: List[str] = []
    for block in cell.get("blocks", []):
        text = (
            block.get("textBlock", {}) or {}
        ).get("text", "")
        if text:
            texts.append(text)
    return collapse_spaces(" ".join(texts))


def cell_bbox(cell: Dict[str, Any]) -> Dict[str, float]:
    boxes: List[Dict[str, float]] = []
    for block in cell.get("blocks", []):
        bbox = block.get("boundingBox", {})
        vertices = bbox.get("normalizedVertices", [])
        if vertices:
            boxes.append(bbox_from_normalized_vertices(vertices))
    return union_bbox(boxes)


def to_field_key(header_text: str) -> str:
    t = normalize_for_match(header_text)
    if t == "tt":
        return "tt"
    if "thẩm định viên" in t:
        return "full_name"
    if "số thẻ" in t:
        return "card_no"
    if "nội dung thông báo" in t:
        return "notice_content"
    if "ngày hiệu lực" in t:
        return "effective_date"
    if "chức danh" in t:
        return "position"
    if "lĩnh vực" in t:
        return "valuation_scope"
    return re.sub(r"[^a-z0-9]+", "_", t).strip("_")


def row_to_cells(row: Dict[str, Any]) -> List[Dict[str, Any]]:
    cells_out: List[Dict[str, Any]] = []
    for idx, cell in enumerate(row.get("cells", [])):
        text = cell_text(cell)
        bbox = cell_bbox(cell)
        cells_out.append(
            {
                "cell_index": idx,
                "text": text,
                "row_span": int(cell.get("rowSpan", 1) or 1),
                "col_span": int(cell.get("colSpan", 1) or 1),
                "bbox": bbox,
                "raw": cell,
            }
        )
    return cells_out


def score_header_row(cells: List[Dict[str, Any]]) -> int:
    texts = [normalize_for_match(c["text"]) for c in cells]
    joined = " | ".join(texts)
    score = 0
    for kw in HEADER_KEYWORDS:
        if kw in joined:
            score += 1
    return score


def row_has_merge_signals(cells: List[Dict[str, Any]]) -> bool:
    date_pattern = r"\d{1,2}/\d{1,2}/\d{4}"
    signals = 0

    for cell in cells:
        text = cell["text"]
        if cell["row_span"] > 1 or cell["col_span"] > 1:
            return True
        if len(re.findall(date_pattern, text)) >= 2:
            signals += 1
        if len(re.findall(r"\b(TDV|TÐV|GĐ|GÐ|GD)\b", text, flags=re.IGNORECASE)) >= 2:
            signals += 1
        if len(re.findall(r"\b[IVX]+\d+[A-Z]*\.\d+\b", text.upper())) >= 2:
            signals += 1

    return signals > 0


def extract_tables(layout_json_path: str | Path) -> List[Dict[str, Any]]:
    data = load_json(layout_json_path)
    blocks = (data.get("documentLayout") or {}).get("blocks", [])
    tables: List[Dict[str, Any]] = []

    for block in blocks:
        table_block = block.get("tableBlock")
        if not table_block:
            continue

        raw_rows = table_block.get("bodyRows", []) or []
        rows = [row_to_cells(row) for row in raw_rows]

        table_bbox = union_bbox(
            [c["bbox"] for row in rows for c in row if c.get("bbox")]
        )

        tables.append(
            {
                "table_block_id": block.get("blockId"),
                "rows": rows,
                "table_bbox": table_bbox,
                "raw": block,
            }
        )

    return tables


def choose_target_table(tables: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    best = None
    best_score = -1

    for table in tables:
        rows = table["rows"]
        if not rows:
            continue

        local_best = max(score_header_row(row) for row in rows)
        if local_best > best_score:
            best_score = local_best
            best = table

    return best


def build_column_regions(header_row: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    cells = sorted(header_row, key=lambda c: c["bbox"]["x_min"])
    columns: List[Dict[str, Any]] = []

    for idx, cell in enumerate(cells):
        columns.append(
            {
                "order": idx,
                "header_text": cell["text"],
                "field_key": to_field_key(cell["text"]),
                "x_min": cell["bbox"]["x_min"],
                "x_max": cell["bbox"]["x_max"],
                "y_min": cell["bbox"]["y_min"],
                "y_max": cell["bbox"]["y_max"],
                "bbox": cell["bbox"],
            }
        )

    return columns


def extract_layout_table(layout_json_path: str | Path) -> Dict[str, Any]:
    tables = extract_tables(layout_json_path)
    if not tables:
        raise ValueError("Không tìm thấy tableBlock nào trong layout JSON.")

    target = choose_target_table(tables)
    if not target:
        raise ValueError("Không chọn được bảng mục tiêu.")

    rows = target["rows"]
    header_idx = max(range(len(rows)), key=lambda i: score_header_row(rows[i]))
    header_row = rows[header_idx]
    body_rows = rows[header_idx + 1 :]

    columns = build_column_regions(header_row)

    body_out = []
    for row_idx, row in enumerate(body_rows, start=1):
        body_out.append(
            {
                "row_index": row_idx,
                "cells": row,
                "merged_flag": row_has_merge_signals(row),
            }
        )

    return {
        "table_block_id": target["table_block_id"],
        "headers": [c["text"] for c in header_row],
        "header_row": header_row,
        "column_regions": columns,
        "raw_rows": body_out,
        "table_bbox": target["table_bbox"],
        "layout_json_path": str(layout_json_path),
    }


if __name__ == "__main__":
    import argparse
    from pprint import pprint

    parser = argparse.ArgumentParser()
    parser.add_argument("layout_json_path")
    args = parser.parse_args()

    table = extract_layout_table(args.layout_json_path)
    pprint(table["headers"])
    pprint(table["column_regions"])
    print("rows:", len(table["raw_rows"]))
