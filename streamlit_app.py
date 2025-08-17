"""
Streamlit application for monitoring valuation experts and companies from the
Ministry of Finance announcements.

This app assumes two CSV files exist in the working directory:

* ``personal_data.csv`` – extracted records from announcements that have
  titles containing "danh sách thẩm định viên về giá" or
  "điều chỉnh thông tin về thẩm định viên".  Each record should include
  fields such as company name, appraiser name, certificate number,
  effective date, registered position, document number, document date,
  and source URL.

* ``company_data.csv`` – extracted records from announcements that have
  titles containing keywords like "thu hồi", "đình chỉ" or "Quyết định".
  These documents typically concern companies rather than individual
  appraisers.  Fields can include company name, document number,
  decision type, effective date, and source URL.

The app also provides buttons to trigger data crawling and extraction.
Those operations are encapsulated in functions ``crawl_links()``,
``update_personal_data()`` and ``update_company_data()`` defined
below.  Currently the functions are placeholders – they illustrate
how you might integrate your crawling and OCR pipeline.  You should
replace the stub implementations with calls into your own modules.

To run this application locally, install streamlit and pandas via

    pip install streamlit pandas

Then start the app with

    streamlit run streamlit_app.py

"""

import os
import pandas as pd
import streamlit as st
from datetime import datetime


###############################################################################
# Placeholder functions for crawling and updating datasets
###############################################################################


def crawl_links(year: int = 2025) -> list[dict]:
    """Return a list of metadata for announcement pages in the given year.

    Each item in the returned list should be a dictionary with at least
    ``title`` and ``url`` keys.  You might also include ``category`` to
    distinguish between personal and company documents.

    This stub simply returns an empty list.  In your production code you
    should reuse or extend ``crawl_links_and_classify.py`` from the
    repository to load the main page via Playwright, extract links
    whose titles contain the supplied year and classify them.  For
    example:

        from src.crawl_links_and_classify import crawl_links_and_classify
        links = crawl_links_and_classify(year)
        return links

    """
    # TODO: integrate your crawler here
    st.info(
        "[crawl_links()] is a stub – integrate your Playwright crawler to "
        "return announcement metadata for the selected year."
    )
    return []


def update_personal_data(new_links: list[dict]) -> None:
    """Download and process personal announcements and update personal_data.csv.

    ``new_links`` should be a list of dictionaries for personal announcements
    that have not yet been processed.  This function should download each
    PDF, run your OCR extraction pipeline and merge the resulting rows
    into ``personal_data.csv``, replacing existing rows when certificate
    numbers match (for "điều chỉnh" documents) and appending new rows
    otherwise.  You may also record the document number and signing date
    to a history table if needed.

    This stub only writes an informational message.  Replace it with
    logic that imports your ``download_pdf.py`` and extraction code.
    """
    st.info(
        "[update_personal_data()] is a stub – implement PDF download, OCR "
        "extraction and CSV merging for personal announcements."
    )


def update_company_data(new_links: list[dict]) -> None:
    """Download and process company announcements and update company_data.csv.

    ``new_links`` should be a list of dictionaries for company
    announcements that have not yet been processed.  This function
    downloads each PDF, runs your OCR extraction (once implemented) and
    appends or updates rows in ``company_data.csv`` accordingly.
    """
    st.info(
        "[update_company_data()] is a stub – implement PDF download, OCR "
        "extraction and CSV merging for company announcements."
    )


###############################################################################
# Streamlit user interface
###############################################################################


def load_dataset(csv_path: str) -> pd.DataFrame:
    """Load a CSV file into a DataFrame; return an empty frame if missing."""
    if os.path.exists(csv_path):
        try:
            return pd.read_csv(csv_path)
        except Exception as exc:
            st.error(f"Failed to load {csv_path}: {exc}")
    return pd.DataFrame()


def main() -> None:
    st.set_page_config(page_title="Thẩm định giá – Monitoring", layout="wide")
    st.title("Theo dõi thông tin thẩm định viên và doanh nghiệp")

    # Sidebar configuration
    st.sidebar.header("Cấu hình crawl")
    year = st.sidebar.number_input(
        "Năm cần lấy dữ liệu", min_value=2000, max_value=datetime.now().year,
        value=2025, step=1
    )
    if st.sidebar.button("Crawl danh sách link"):
        links = crawl_links(year)
        if links:
            st.sidebar.success(f"Đã tìm thấy {len(links)} link cho năm {year}")
        else:
            st.sidebar.warning(
                "Chưa tìm thấy link nào hoặc crawler chưa được triển khai."
            )

    # Load datasets
    personal_df = load_dataset("personal_data.csv")
    company_df = load_dataset("company_data.csv")

    st.subheader("Dữ liệu cá nhân")
    st.markdown(
        "Các thông báo có tiêu đề chứa 'danh sách thẩm định viên về giá' "
        "hoặc 'điều chỉnh thông tin về thẩm định viên'."
    )
    if personal_df.empty:
        st.info(
            "Chưa có dữ liệu cá nhân. Hãy chạy crawler và pipeline để tạo file "
            "personal_data.csv."
        )
    else:
        st.dataframe(personal_df)

    st.subheader("Dữ liệu doanh nghiệp/Công ty")
    st.markdown(
        "Các thông báo có tiêu đề chứa 'thu hồi', 'đình chỉ' hoặc "
        "'Quyết định'."
    )
    if company_df.empty:
        st.info(
            "Chưa có dữ liệu doanh nghiệp. Hãy chạy crawler và pipeline để tạo "
            "file company_data.csv."
        )
    else:
        st.dataframe(company_df)

    # Buttons for updating data
    st.sidebar.header("Cập nhật dữ liệu")
    st.sidebar.markdown(
        "Những nút dưới đây sẽ chạy luồng tải PDF, OCR và cập nhật các CSV."
    )
    if st.sidebar.button("Cập nhật dữ liệu cá nhân"):
        # In practice you would supply only the new personal links here
        update_personal_data([])
    if st.sidebar.button("Cập nhật dữ liệu doanh nghiệp"):
        # In practice you would supply only the new company links here
        update_company_data([])


if __name__ == "__main__":
    main()