import os
import sys
import json
import re
from typing import List, Dict, Tuple, Optional

from google.cloud import documentai_v1 as documentai
from google.oauth2 import service_account
from google.api_core.exceptions import GoogleAPICallError
from google.protobuf.json_format import MessageToDict

# DB helpers
from src.db import get_conn, init_schema

os.makedirs("preprocessed", exist_ok=True)

# ---------- Load Document AI credentials ----------
credentials_json = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON")
if not credentials_json:
    print("❌ Thiếu biến GOOGLE_APPLICATION_CREDENTIALS_JSON.")
    sys.exit(1)

try:
    credentials_dict = json.loads(credentials_json)
    credentials = service_account.Credentials.from_service_account_info(credentials_dict)
except Exception as e:
    print(f"❌ GOOGLE_APPLICATION_CREDENTIALS_JSON không hợp lệ: {e}")
    sys.exit(1)

project_id = os.environ.get("GOOGLE_PROJECT_ID")
processor_id = os.environ.get("GOOGLE_PROCESSOR_ID")            # Form Parser
processor_id_ocr = os.environ.get("GOOGLE_PROCESSOR_ID_OCR")    # Document OCR
location = os.environ.get("GOOGLE_LOCATION", "us")

if not project_id or not processor_id or not processor_id_ocr:
    print("❌ Thiếu GOOGLE_PROJECT_ID hoặc PROCESSOR_ID hoặc PROCESSOR_ID_OCR.")
    sys.exit(1)

client = documentai.DocumentProcessorServiceClient(credentials=credentials)
name_form_parser = f"projects/{project_id}/locations/{location}/processors/{processor_id}"
name_doc_ocr     = f"projects/{project_id}/locations/{location}/processors/{processor_id_ocr}"

# ---------- Small utils ----------
def extract_text(text_anchor, text):
    if not text_anchor.text_segments:
        return ""
    result = ""
    for segment in text_anchor.text_segments:
        start = segment.start_index if segment.start_index else 0
        end = segment.end_index
        result += text[start:end]
    return result.strip()

def extract_tables(document) -> List[List[List[str]]]:
    """Return list of tables; each table is list of rows; row is list of cell strings."""
    out = []
    text = document.text
    for page in document.pages:
        for table in page.tables:
            rows = []
            for row in list(table.header_rows) + list(table.body_rows):
                cells = []
                for cell in row.cells:
                    cells.append(extract_text(cell.layout.text_anchor, text))
                rows.append(cells)
            out.append(rows)
    return out

def safe_lower(s: Optional[str]) -> str:
    return (s or "").strip().lower()

# ---------- OCR free-text to get metadata ----------
def extract_meta_from_ocr(pdf_bytes: bytes) -> Tuple[str, str, str]:
    """
    Return (company_name, doc_no, signed_at)
    """
    try:
        raw_document = documentai.RawDocument(content=pdf_bytes, mime_type="application/pdf")
        request = documentai.ProcessRequest(name=name_doc_ocr, raw_document=raw_document)
        result = client.process_document(request=request)
        text = result.document.text

        # Công ty ... (…TĐG/TDG)
        company_match = re.search(r"(Công\s*ty[\s\S]{0,200}?\([^\)]+T[ĐD]G\))", text, re.IGNORECASE)
        company_name = company_match.group(1).strip() if company_match else ""

        # Số hiệu văn bản dạng 123/TB-BTC
        docno_match = re.search(r"(\d{2,5}\s*/\s*TB-BTC)", text, re.IGNORECASE)
        doc_no = docno_match.group(1).replace(" ", "") if docno_match else ""

        # “Thời gian ký:” hoặc “Ngày ký:”
        time_match = re.search(r"(Thời\s*gian\s*ký|Ngày\s*ký)[:\s]+([^\n]+)", text, re.IGNORECASE)
        signed_at = time_match.group(2).strip() if time_match else ""

        return company_name, doc_no, signed_at
    except Exception as e:
        print(f"⚠️ Lỗi OCR meta: {e}")
        return "", "", ""

# ---------- Map headers to indices flexibly ----------
PERSONAL_HEADER_CANDIDATES = {
    "full_name": ["thẩm định viên", "họ tên", "họ và tên"],
    "card_no":   ["số thẻ", "sothe", "số thẻ tdv"],
    "position":  ["chức danh", "chức danh đăng ký hành nghề", "chức danh đăng ky hanh nghe"],
    "valid_from":["ngày hiệu lực", "kể từ ngày", "ke tu ngay"],
}

def map_header_indices(header_row: List[str]) -> Dict[str, int]:
    idx = {}
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

# ---------- Write to DB ----------
def upsert_personal(record: Dict[str, str]) -> None:
    """
    record keys: card_no, full_name, position, company, valid_from, doc_no, signed_at, source_url
    """
    with get_conn() as conn:
        conn.execute("""
        INSERT INTO personal_records(card_no, full_name, position, company, valid_from, doc_no, signed_at, source_url)
        VALUES (:card_no,:full_name,:position,:company,:valid_from,:doc_no,:signed_at,:source_url)
        ON CONFLICT(card_no) DO UPDATE SET
            full_name = excluded.full_name,
            position  = excluded.position,
            company   = excluded.company,
            valid_from= excluded.valid_from,
            doc_no    = excluded.doc_no,
            signed_at = excluded.signed_at,
            source_url= excluded.source_url,
            updated_at= CURRENT_TIMESTAMP
        """, record)

# ---------- Main processing ----------
def process_file(pdf_path: str) -> bool:
    init_schema()
    json_path = pdf_path.replace(".pdf", ".json")
    print(f"\n📄 Đang xử lý file: {pdf_path}")

    source_url = os.environ.get("CURRENT_SOURCE_URL", "")

    try:
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

        # 1) Meta từ OCR văn bản tự do
        company_name, doc_no, signed_at = extract_meta_from_ocr(pdf_bytes)

        # 2) Form Parser để lấy bảng
        raw_document = documentai.RawDocument(content=pdf_bytes, mime_type="application/pdf")
        request = documentai.ProcessRequest(name=name_form_parser, raw_document=raw_document)
        result = client.process_document(request=request)
        document = result.document

        if not document.text.strip():
            print(f"⚠️ Không có văn bản OCR được từ: {pdf_path}")
            return False

        # Lưu JSON gốc (debug)
        try:
            document_dict = MessageToDict(document._pb, preserving_proto_field_name=True)
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(document_dict, f, ensure_ascii=False, indent=2)
            print(f"✅ Đã lưu file JSON: {json_path}")
        except Exception as _:
            pass

        tables = extract_tables(document)
        if not tables:
            print("⚠️ Không phát hiện bảng.")
            return False

        # Lấy bảng đầu tiên có header phù hợp
        used_any_row = False
        for table in tables:
            if not table or len(table) < 2:
                continue
            header = table[0]
            idx_map = map_header_indices(header)
            if "card_no" not in idx_map or "full_name" not in idx_map:
                continue  # không đúng dạng mong muốn

            for row in table[1:]:
                # chống index out of range nếu hàng thiếu ô
                def get(i): 
                    return row[i].strip() if i < len(row) else ""

                rec = {
                    "card_no":   get(idx_map.get("card_no", -1)),
                    "full_name": get(idx_map.get("full_name", -1)),
                    "position":  get(idx_map.get("position", -1)),
                    "company":   company_name,
                    "valid_from":get(idx_map.get("valid_from", -1)),
                    "doc_no":    doc_no,
                    "signed_at": signed_at,
                    "source_url": source_url,
                }
                # bỏ qua dòng rỗng/không có số thẻ
                if not rec["card_no"] and not rec["full_name"]:
                    continue
                upsert_personal(rec)
                used_any_row = True

        if used_any_row:
            print("💾 Đã ghi/ cập nhật dữ liệu vào SQLite (personal_records).")
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
    print(f"\n📊 Tổng số file đã xử lý thành công: {success}")
