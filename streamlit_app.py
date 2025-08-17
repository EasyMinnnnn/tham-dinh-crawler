import sqlite3, pandas as pd, streamlit as st
from db import init_schema, DB_PATH
import subprocess, os

st.set_page_config(page_title="Thẩm định crawler", layout="wide")
st.title("Theo dõi thẩm định viên & doanh nghiệp (không dùng Google Sheet)")

init_schema()

@st.cache_data(ttl=60)
def load_df(sql):
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(sql, conn)
    conn.close()
    return df

colA, colB, colC = st.columns([1,1,1])

with colA:
    if st.button("Crawl link năm 2025"):
        os.environ["CRAWL_YEAR"] = "2025"
        subprocess.run(["python", "src/crawl_links_and_classify.py"], check=False)
        st.success("Đã crawl xong.")

with colB:
    if st.button("Cập nhật dữ liệu cá nhân (OCR)"):
        # gọi script pipeline cá nhân hiện tại của bạn
        # ví dụ: run_pipeline_personal.py (hãy gom bước download/ocr/extract vào đây)
        subprocess.run(["python", "run_pipeline.py"], check=False)  # sửa tên nếu bạn tách riêng
        st.success("Đã cập nhật dữ liệu cá nhân.")

with colC:
    if st.button("Kiểm tra link mới (hằng ngày)"):
        # chỉ cần gọi lại crawler; phần UI là thủ công,
        # còn chạy tự động thì dùng cron/GitHub Actions (phần 6)
        os.environ["CRAWL_YEAR"] = "2025"
        subprocess.run(["python", "src/crawl_links_and_classify.py"], check=False)
        st.success("Đã kiểm tra xong.")

st.subheader("Bảng link đã crawl")
links_df = load_df("SELECT created_at, year, bucket, title, url FROM links ORDER BY created_at DESC")
st.dataframe(links_df, use_container_width=True)

st.subheader("Bảng Cá nhân (personal_records)")
p_df = load_df("""
SELECT card_no AS 'Số thẻ', full_name AS 'Họ tên', position AS 'Chức danh',
       company AS 'Công ty', valid_from AS 'Ngày hiệu lực',
       doc_no AS 'Số VB', signed_at AS 'Ngày văn bản', source_url AS 'Nguồn',
       updated_at
FROM personal_records
ORDER BY updated_at DESC
""")
st.dataframe(p_df, use_container_width=True)

st.subheader("Bảng Doanh nghiệp (company_decisions)")
c_df = load_df("""
SELECT company_name AS 'Công ty', decision_no AS 'Số QĐ',
       decision_type AS 'Loại', effective_date AS 'Hiệu lực',
       source_url AS 'Nguồn', updated_at
FROM company_decisions
ORDER BY updated_at DESC
""")
st.dataframe(c_df, use_container_width=True)
