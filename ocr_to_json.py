import os
import sys
import json
import re
from typing import List, Dict, Any, Tuple, Optional

from google.cloud import documentai_v1 as documentai
from google.oauth2 import service_account
from google.api_core.exceptions import GoogleAPICallError
from google.protobuf.json_format import MessageToDict

# Thư mục I/O
INPUT_DIR = "outputs"
RAW_JSON_DIR = "preprocessed"     # dump JSON gốc từ Document AI (debug)
OUT_JSON_DIR = "outputs_json"     # JSON chuẩn hoá để các bước sau dùng

os.makedirs(RAW_JSON_DIR, exist_ok=True)
os.makedirs(OUT_JSON_DIR, exist_ok=True)

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

project_id      = os.environ.get("GOOGLE_PROJECT_ID")
processor_id    = os.environ.get("GOOGLE_PROCESSOR_ID")         # Form Parser
processor_id_ocr= os.environ.get("GOOGLE_PROCESSOR_ID_OCR")     # Document OCR
location        = os.environ.get("GOOGLE_LOCATION", "us")

if not project_id or not processor_id or not processor_id_ocr:
    print("❌ Thiếu GOOGLE_PROJECT_ID hoặc PROCESSOR_ID hoặc PROCESSOR_ID_OCR.")
    sys.exit(1)

client = documentai.DocumentProcessorServiceClient(credentials=credentials)
NAME_FORM  = f"projects/{project_id}/locations/{location}/processors/{processor_id}"
NAME_OCR   = f"projects/{project_id}/locations/{location}/processors/{processor_id_ocr}"

# ---------- Utils ----------
def _safe(s: Optional[str]) -> str:
    return (s or "").strip()

def _lower(s: Optional[str]) -> str:
    return (s or "").strip().lower()

def extract_text(text_anchor, full_text: str) -> str:
    if not text_anchor or not text_anchor.text_segments:
        return ""
    result = []
    for seg in text_anchor.text_segments:
        start = seg.start_index if seg.start_index else 0
        end = seg.end_index
        result.append(full_text[start:end])
    return "".join(result).strip()

def extract_tables(document: documentai.Document) -> List[List[List[str]]]:
    """Trả về list các bảng; mỗi bảng là list row; row là list cell text."""
    out: List[List[List[str]]] = []
    full_text = document.text
    for page in document.pages:
        for table in page.tables:
            rows: List[List[str]] = []
            for row in list(table.header_rows) + list(table.body_rows):
                cells = []
                for cell in row.cells:
                    cells.append(extract_text(cell.layout.text_anchor, full_text))
                rows.append(cells)
            out.append(rows)
    return out

# ---------- OCR free-text để lấy meta ----------
def extract_meta_from_ocr(pdf_bytes: bytes) -> Tuple[str, str, str]:
    """
    Return (company_name, doc_no, signed_at)
    - company_name: "Công ty ... (xxTĐG)" hoặc tương tự
    - doc_no:       "123/TB-BTC" (cho phép có khoảng trắng 2 bên dấu '/')
    - signed_at:    dòng sau 'Thời gian ký:' hoặc 'Ngày ký:'
    """
    try:
        raw = documentai.RawDocument(content=pdf_bytes, mime_type="application/pdf")
        req = documentai.ProcessRequest(name=NAME_OCR, raw_document=raw)
        result = client.process_document(request=req)
        text = result.document.text or ""

        # Công ty ... (…TĐG/TDG)
        company = ""
        m_comp = re.search(r"(Công\s*ty[\s\S]{0,200}?\([^)]+T[ĐD]G\))", text, re.IGNORECASE)
        if m_comp:
            company = m_comp.group(1).strip()

        # Số hiệu 123/TB-BTC (cho phép có khoảng trắng quanh '/')
        doc_no = ""
        m_doc = re.search(r"(\d{2,5}\s*/\s*TB-BTC)", text, re.IGNORECASE)
        if m_doc:
            doc_no = m_doc.group(1).replace(" ", "")

        # “Thời gian ký:” hoặc “Ngày ký:”
        signed_at = ""
        m_time = re.search(r"(Thời\s*gian\s*ký|Ngày\s*ký)[:\s]+([^\n]+)", text, re.IGNORECASE)
        if m_time:
            signed_at = m_time.group(2).strip()

        return company, doc_no, signed_at
    except Exception as e:
        print(f"⚠️ Lỗi OCR meta: {e}")
        return "", "", ""

# ---------- Form Parser ----------
def form_parse(pdf_bytes: bytes) -> documentai.Document:
    raw = documentai.RawDocument(content=pdf_bytes, mime_type="application/pdf")
    req = documentai.ProcessRequest(name=NAME_FORM, raw_document=raw)
    return client.process_document(request=req).document

# ---------- Ghi JSON chuẩn ----------
def write_normalized_json(out_path: str, payload: Dict[str, Any]) -> None:
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

# ---------- Pipeline 1 file ----------
def process_file(pdf_path: str) -> bool:
    print(f"\n📄 Đang xử lý file: {pdf_path}")
    base = os.path.splitext(os.path.basename(pdf_path))[0]
    raw_json_path = os.path.join(RAW_JSON_DIR, base + ".documentai.json")
    out_json_path = os.path.join(OUT_JSON_DIR, base + ".json")

    # Có thể set từ caller để lưu nguồn link
    source_url = os.environ.get("CURRENT_SOURCE_URL", "")

    try:
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

        # 1) Lấy meta tự do từ OCR
        company_name, doc_no, signed_at = extract_meta_from_ocr(pdf_bytes)

        # 2) Form Parser để lấy bảng
        document = form_parse(pdf_bytes)
        if not (document.text or "").strip():
            print("⚠️ Document AI không trả về văn bản.")
            return False

        # Dump JSON gốc để debug (không bắt buộc)
        try:
            doc_dict = MessageToDict(document._pb, preserving_proto_field_name=True)
            with open(raw_json_path, "w", encoding="utf-8") as f:
                json.dump(doc_dict, f, ensure_ascii=False, indent=2)
            print(f"📝 Đã lưu JSON gốc: {raw_json_path}")
        except Exception:
            pass

        tables = extract_tables(document)

        # 3) JSON chuẩn hoá cho bước sau (ghi DB/hiển thị)
        normalized = {
            "pdf_name": os.path.basename(pdf_path),
            "source_url": source_url,
            "company_name": company_name,
            "doc_no": doc_no,
            "signed_at": signed_at,
            "tables": tables,  # list[table] -> table: list[row] -> row: list[cells]
            "raw_documentai_json_path": raw_json_path,
        }
        write_normalized_json(out_json_path, normalized)
        print(f"✅ Đã lưu JSON chuẩn: {out_json_path}")

        # Không còn push lên Google Sheet; để file JSON cho bước kế tiếp dùng
        try:
            os.remove(pdf_path)
        except Exception:
            pass
        return True

    except GoogleAPICallError as api_error:
        print(f"❌ Lỗi từ Google API: {api_error}")
    except Exception as e:
        print(f"❌ Lỗi khi xử lý {pdf_path}: {e}")
    return False

# ---------- Entry ----------
if __name__ == "__main__":
    os.makedirs(INPUT_DIR, exist_ok=True)
    files = [f for f in os.listdir(INPUT_DIR) if f.lower().endswith(".pdf")]
    success = 0
    for f in files:
        if process_file(os.path.join(INPUT_DIR, f)):
            success += 1
    print(f"\n📊 Tổng số file đã xử lý thành công: {success}")
