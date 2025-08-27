"""
Extract structured information from downloaded PDF files and write it
into the SQLite database.

This script uses Google Document AI to perform OCR and form parsing
on crawled PDF documents. It expects credentials for Document AI
to be provided via the ``GOOGLE_APPLICATION_CREDENTIALS_JSON``
environment variable. The original version of this script simply
called ``json.loads`` on that environment variable. However,
depending on how the JSON is provided (as a raw multi‑line string,
as a Python dictionary converted to a string, or containing
non‑standard control characters), naïve parsing can fail with
errors such as ``Invalid control character``. To make the
credentials parsing more robust, this version attempts multiple
strategies:

1. Parse using ``json.loads`` with ``strict=False`` to allow
   control characters inside strings.
2. If that fails, fall back to ``ast.literal_eval`` to handle
   Python dict representations (i.e. single quotes) and other
   non‑JSON formats.

If all attempts fail, the script will report the error and exit.

The rest of the logic remains faithful to the upstream project.
"""

import os
import sys
import json
import re
import ast
from typing import List, Dict, Tuple, Optional

from google.cloud import documentai_v1 as documentai
from google.oauth2 import service_account
from google.api_core.exceptions import GoogleAPICallError
from google.protobuf.json_format import MessageToDict

# DB helpers
from src.db import get_conn, init_schema

# Ensure the preprocessed directory exists. Although this
# script no longer uses it directly, the upstream project
# creates this directory and other scripts may depend on it.
os.makedirs("preprocessed", exist_ok=True)


def _load_credentials_from_env() -> service_account.Credentials:
    """Load Google service account credentials from env.

    The ``GOOGLE_APPLICATION_CREDENTIALS_JSON`` environment
    variable should contain either a JSON string or a Python
    representation of a dict containing the service account
    credentials. This helper attempts to parse the variable
    robustly, allowing certain non‑standard formats.

    Returns
    -------
    google.oauth2.service_account.Credentials
        The credentials object that can be passed to Document AI.

    Raises
    ------
    SystemExit
        If the environment variable is missing or malformed.
    """
    credentials_json = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON")
    if not credentials_json:
        print("❌ Thiếu biến GOOGLE_APPLICATION_CREDENTIALS_JSON.")
        sys.exit(1)

    # Try JSON parsing first, permitting control characters in strings.
    try:
        credentials_dict = json.loads(credentials_json, strict=False)
    except Exception:
        # Fall back to literal_eval for Python dict reprs (single quotes etc.)
        try:
            credentials_dict = ast.literal_eval(credentials_json)
        except Exception as e:
            print(f"❌ GOOGLE_APPLICATION_CREDENTIALS_JSON không hợp lệ: {e}")
            sys.exit(1)

    try:
        return service_account.Credentials.from_service_account_info(
            credentials_dict
        )
    except Exception as e:
        print(f"❌ Lỗi khởi tạo credentials: {e}")
        sys.exit(1)


# Load credentials using the helper defined above
credentials = _load_credentials_from_env()

project_id = os.environ.get("GOOGLE_PROJECT_ID")
processor_id = os.environ.get("GOOGLE_PROCESSOR_ID")  # Form Parser
processor_id_ocr = os.environ.get("GOOGLE_PROCESSOR_ID_OCR")  # Document OCR
location = os.environ.get("GOOGLE_LOCATION", "us")

if not project_id or not processor_id or not processor_id_ocr:
    print("❌ Thiếu GOOGLE_PROJECT_ID hoặc PROCESSOR_ID hoặc PROCESSOR_ID_OCR.")
    sys.exit(1)

# Create a Document AI client with the provided credentials
client = documentai.DocumentProcessorServiceClient(credentials=credentials)

# Build processor resource names
name_form_parser = f"projects/{project_id}/locations/{location}/processors/{processor_id}"
name_doc_ocr = f"projects/{project_id}/locations/{location}/processors/{processor_id_ocr}"


def extract_text(text_anchor, text: str) -> str:
    """Extract concatenated text segments from a Document AI text anchor."""
    if not text_anchor.text_segments:
        return ""
    result = ""
    for segment in text_anchor.text_segments:
        start = segment.start_index if segment.start_index else 0
        end = segment.end_index
        result += text[start:end]
    return result.strip()


def extract_tables(document) -> List[List[List[str]]]:
    """Return a list of tables; each table is a list of rows; each row is a list of cell strings."""
    out: List[List[List[str]]] = []
    text = document.text
    for page in document.pages:
        for table in page.tables:
            rows: List[List[str]] = []
            for row in list(table.header_rows) + list(table.body_rows):
                cells: List[str] = []
                for cell in row.cells:
                    cells.append(extract_text(cell.layout.text_anchor, text))
                rows.append(cells)
            out.append(rows)
    return out


def safe_lower(s: Optional[str]) -> str:
    """Normalize a string by stripping and converting to lowercase."""
    return (s or "").strip().lower()


# Candidate header names for the personal records table
PERSONAL_HEADER_CANDIDATES: Dict[str, List[str]] = {
    "full_name": ["thẩm định viên", "họ tên", "họ và tên"],
    "card_no": ["số thẻ", "sothe", "số thẻ tdv"],
    "position": ["chức danh", "chức danh đăng ký hành nghề", "chức danh đăng ky hanh nghe"],
    "valid_from": ["ngày hiệu lực", "kể từ ngày", "ke tu ngay"],
}


def map_header_indices(header_row: List[str]) -> Dict[str, int]:
    """Map header keywords to their column index in a table row."""
    idx: Dict[str, int] = {}
    lower = [safe_lower(x) for x in header_row]
    for key, cands in PERSONAL_HEADER_CANDIDATES.items():
        for cand in cands:
            for j, cell in enumerate(lower):
                if cand in cell:
                    idx[key] = j
                    break
            if key in idx:
                break
    return idx


def upsert_personal(record: Dict[str, str]) -> None:
    """
    Insert or update a personal record in the database.

    Record keys:
    ``card_no``, ``full_name``, ``position``, ``company``, ``valid_from``,
    ``doc_no``, ``signed_at``, ``source_url``.
    """
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO personal_records(
                card_no, full_name, position, company,
                valid_from, doc_no, signed_at, source_url
            )
            VALUES (
                :card_no, :full_name, :position, :company,
                :valid_from, :doc_no, :signed_at, :source_url
            )
            ON CONFLICT(card_no) DO UPDATE SET
                full_name = excluded.full_name,
                position  = excluded.position,
                company   = excluded.company,
                valid_from= excluded.valid_from,
                doc_no    = excluded.doc_no,
                signed_at = excluded.signed_at,
                source_url= excluded.source_url,
                updated_at= CURRENT_TIMESTAMP
            """,
            record,
        )


def extract_meta_from_ocr(pdf_bytes: bytes) -> Tuple[str, str, str]:
    """Return (company_name, doc_no, signed_at) extracted from free‑text OCR."""
    try:
        raw_document = documentai.RawDocument(content=pdf_bytes, mime_type="application/pdf")
        request = documentai.ProcessRequest(name=name_doc_ocr, raw_document=raw_document)
        result = client.process_document(request=request)
        text = result.document.text
        # Match 'Công ty ... (…TĐG/TDG)'
        company_match = re.search(r"(Công\s*ty[\s\S]{0,200}?\([^)]+T[ĐD]G\))", text, re.IGNORECASE)
        company_name = company_match.group(1).strip() if company_match else ""
        # Match document number like 123/TB-BTC
        docno_match = re.search(r"(\d{2,5}\s*/\s*TB-BTC)", text, re.IGNORECASE)
        doc_no = docno_match.group(1).replace(" ", "") if docno_match else ""
        # Match “Thời gian ký:” or “Ngày ký:”
        time_match = re.search(r"(Thời\s*gian\s*ký|Ngày\s*ký)[:\s]+([^\n]+)", text, re.IGNORECASE)
        signed_at = time_match.group(2).strip() if time_match else ""
        return company_name, doc_no, signed_at
    except Exception as e:
        print(f"⚠️ Lỗi OCR meta: {e}")
        return "", "", ""


def process_file(pdf_path: str) -> bool:
    """Process a single PDF: OCR, parse table, and upsert to DB."""
    # Ensure DB schema exists
    init_schema()
    json_path = pdf_path.replace(".pdf", ".json")
    print(f"\n Đang xử lý file: {pdf_path}")
    source_url = os.environ.get("CURRENT_SOURCE_URL", "")
    try:
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()
        # 1) Meta from free‑text OCR
        company_name, doc_no, signed_at = extract_meta_from_ocr(pdf_bytes)
        # 2) Form Parser to extract tables
        raw_document = documentai.RawDocument(content=pdf_bytes, mime_type="application/pdf")
        request = documentai.ProcessRequest(name=name_form_parser, raw_document=raw_document)
        result = client.process_document(request=request)
        document = result.document
        if not document.text.strip():
            print(f"⚠️ Không có văn bản OCR được từ: {pdf_path}")
            return False
        # Save raw JSON for debugging
        try:
            document_dict = MessageToDict(document._pb, preserving_proto_field_name=True)
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(document_dict, f, ensure_ascii=False, indent=2)
            print(f"✅ Đã lưu file JSON: {json_path}")
        except Exception:
            pass
        tables = extract_tables(document)
        if not tables:
            print("⚠️ Không phát hiện bảng.")
            return False
        # Use the first table with a recognisable header
        used_any_row = False
        for table in tables:
            if not table or len(table) < 2:
                continue
            header = table[0]
            idx_map = map_header_indices(header)
            if "card_no" not in idx_map or "full_name" not in idx_map:
                continue  # skip tables without expected columns
            for row in table[1:]:
                # Avoid index errors when rows have missing cells
                def get(i: int) -> str:
                    return row[i].strip() if i < len(row) else ""
                rec = {
                    "card_no": get(idx_map.get("card_no", -1)),
                    "full_name": get(idx_map.get("full_name", -1)),
                    "position": get(idx_map.get("position", -1)),
                    "company": company_name,
                    "valid_from": get(idx_map.get("valid_from", -1)),
                    "doc_no": doc_no,
                    "signed_at": signed_at,
                    "source_url": source_url,
                }
                # Skip empty rows
                if not rec["card_no"] and not rec["full_name"]:
                    continue
                upsert_personal(rec)
                used_any_row = True
        if used_any_row:
            print(" Đã ghi/ cập nhật dữ liệu vào SQLite (personal_records).")
            try:
                os.remove(pdf_path)
            except Exception:
                pass
            return True
        print("⚠️ Không có dòng hợp lệ để ghi.")
        return False
    except GoogleAPICallError as api_error:
        print(f"❌ Lỗi từ Google API: {api_error}")
    except Exception as e:
        print(f"❌ Lỗi khi xử lý {pdf_path}: {e}")
    return False


if __name__ == "__main__":
    input_dir = "outputs"
    os.makedirs(input_dir, exist_ok=True)
    files = [f for f in os.listdir(input_dir) if f.endswith(".pdf")]
    success = 0
    for f in files:
        path = os.path.join(input_dir, f)
        if process_file(path):
            success += 1
    print(f"\n Tổng số file đã xử lý thành công: {success}")
