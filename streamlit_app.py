# streamlit_app.py
import os, sys, json, sqlite3, pathlib, subprocess
import pandas as pd
import streamlit as st

# ---- Import DB helpers từ package src ----
from src.db import init_schema, DB_PATH, get_conn

st.set_page_config(page_title="Thẩm định crawler", layout="wide")
st.title("Theo dõi thẩm định viên & doanh nghiệp (không dùng Google Sheet)")

# ---- Đồng bộ secrets -> env để subprocess (crawler/OCR) cũng đọc được ----
def sync_secrets_to_env():
    keys = [
        "GOOGLE_PROJECT_ID", "GOOGLE_PROCESSOR_ID", "GOOGLE_PROCESSOR_ID_OCR",
        "GOOGLE_LOCATION", "CRAWL_YEAR", "PIPELINE_LIMIT", "PLAYWRIGHT_HEADLESS"
    ]
    for k in keys:
        if k in st.secrets:
            os.environ[k] = str(st.secrets[k])
    if "GOOGLE_APPLICATION_CREDENTIALS_JSON" in st.secrets:
        val = st.secrets["GOOGLE_APPLICATION_CREDENTIALS_JSON"]
        # secrets có thể là dict hoặc string
        os.environ["GOOGLE_APPLICATION_CREDENTIALS_JSON"] = (
            json.dumps(val) if isinstance(val, dict) else str(val)
        )

sync_secrets_to_env()

# ---- Cài Chromium cho Playwright (Streamlit Cloud lần đầu) ----
def ensure_chromium():
    cache_dir = pathlib.Path.home() / ".cache" / "ms-playwright"
    if not cache_dir.exists():
        try:
            subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=False)
        except Exception:
            pass

ensure_chromium()

# ---- Khởi tạo DB schema ----
init_schema()

@st.cache_data(ttl=60)
def load_df(sql: str):
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query(sql, conn)
        conn.close()
        return df
    except Exception as e:
        st.warning(f"Không đọc được dữ liệu: {e}")
        return pd.DataFrame()

def run_script(args, env=None, title="Đang chạy..."):
    with st.spinner(title):
        proc = subprocess.run(args, capture_output=True, text=True, env=env or os.environ.copy())
    if proc.stdout:
        with st.expander("Log (stdout)", expanded=False):
            st.code(proc.stdout)
    if proc.stderr:
        with st.expander("Log (stderr)", expanded=False):
            st.code(proc.stderr)
    if proc.returncode == 0:
        st.success("Hoàn tất.")
    else:
        st.error(f"Lỗi (exit={proc.returncode}). Xem log phía trên.")

colA, colB, colC = st.columns([1,1,1])

with colA:
    if st.button("Crawl link năm 2025"):
        os.environ.setdefault("CRAWL_YEAR", "2025")
        run_script([sys.executable, "src/crawl_links_and_classify.py"], title="Crawling…")

with colB:
    if st.button("Cập nhật dữ liệu cá nhân (OCR)"):
        # run_pipeline.py: crawler -> lấy link personal -> download -> extract_to_db
        run_script([sys.executable, "run_pipeline.py"], title="OCR & cập nhật DB…")

with colC:
    if st.button("Kiểm tra link mới (hằng ngày)"):
        os.environ.setdefault("CRAWL_YEAR", "2025")
        run_script([sys.executable, "src/crawl_links_and_classify.py"], title="Kiểm tra link mới…")

st.markdown("---")

st.subheader("Bảng link đã crawl")
links_df = load_df("SELECT created_at, year, bucket, title, url FROM links ORDER BY created_at DESC")
st.dataframe(links_df, use_container_width=True, hide_index=True)

st.subheader("Bảng Cá nhân (personal_records)")
p_df = load_df("""
SELECT card_no AS 'Số thẻ', full_name AS 'Họ tên', position AS 'Chức danh',
       company AS 'Công ty', valid_from AS 'Ngày hiệu lực',
       doc_no AS 'Số VB', signed_at AS 'Ngày văn bản', source_url AS 'Nguồn',
       updated_at
FROM personal_records
ORDER BY updated_at DESC
""")
st.dataframe(p_df, use_container_width=True, hide_index=True)

st.subheader("Bảng Doanh nghiệp (company_decisions)")
c_df = load_df("""
SELECT company_name AS 'Công ty', decision_no AS 'Số QĐ',
       decision_type AS 'Loại', effective_date AS 'Hiệu lực',
       source_url AS 'Nguồn', updated_at
FROM company_decisions
ORDER BY updated_at DESC
""")
st.dataframe(c_df, use_container_width=True, hide_index=True)
