# streamlit_app.py
import streamlit as st
import requests
import pandas as pd
from io import BytesIO
import os
from typing import Any

# ----------------------------
# Config
# ----------------------------
st.set_page_config(
    page_title="Business Card OCR → MongoDB",
    page_icon="📇",
    layout="wide",
)

# Default backend URL (change to your deployed FastAPI address or http://localhost:8000)
DEFAULT_BACKEND = os.getenv("OCR_BACKEND_URL", "https://ocr-backend-usi7.onrender.com")

# ----------------------------
# Helpers
# ----------------------------
def to_excel_bytes(df: pd.DataFrame, sheet_name: str = "Sheet1") -> bytes:
    out = BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return out.getvalue()

def normalize_extracted(extracted: Any) -> dict:
    """Normalize one extracted document (handles lists, strings etc)."""
    # If backend returns JSON-encoded ObjectId etc, this should already be plain JSON.
    # Ensure phone_numbers represented as string for display.
    normalized = dict(extracted) if isinstance(extracted, dict) else {}
    phones = normalized.get("phone_numbers", [])
    if isinstance(phones, list):
        normalized["phone_numbers"] = ", ".join(phones)
    return normalized

# ----------------------------
# App header & backend selector
# ----------------------------
st.title("📇 Business Card OCR → MongoDB")
st.write(
    "Upload a visiting card image — the backend extracts details (Tesseract OCR + heuristics) "
    "and stores them in MongoDB. You can view records and download Excel files."
)

backend_url = st.text_input("OCR Backend URL", value=DEFAULT_BACKEND, help="Base URL for the FastAPI OCR backend (e.g. http://localhost:8000)")

tab1, tab2 = st.tabs(["📤 Upload Card", "📁 View All Cards"])

# ----------------------------
# TAB 1: Upload Card
# ----------------------------
with tab1:
    uploaded_file = st.file_uploader("Upload Visiting Card (jpg, jpeg, png)", type=["jpg", "jpeg", "png"])
    strong_bin = st.checkbox("Use strong binarization (may help stylized cards)", value=False)
    if uploaded_file is not None:
        # show preview and action area
        col1, col2 = st.columns([1, 2])
        with col1:
            st.image(uploaded_file, caption="Uploaded Card", use_column_width=False, width=300)
        with col2:
            if st.button("🔍 Extract & Save to MongoDB"):
                # prepare request
                try:
                    files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
                    params = {"strong_binarize": str(bool(strong_bin)).lower()}  # backend expects bool query param
                    with st.spinner("Extracting text and inserting into MongoDB..."):
                        resp = requests.post(f"{backend_url.rstrip('/')}/upload_card", files=files, params=params, timeout=90)
                    if resp.status_code == 200:
                        resp_json = resp.json()
                        if "data" in resp_json:
                            extracted = resp_json["data"]
                            normalized = normalize_extracted(extracted)
                            st.success("✅ Inserted Successfully into MongoDB")
                            # Build display DataFrame
                            df = pd.DataFrame([{
                                "Name": normalized.get("name", ""),
                                "Designation": normalized.get("designation", ""),
                                "Company": normalized.get("company", ""),
                                "Phone Numbers": normalized.get("phone_numbers", ""),
                                "Email": normalized.get("email", ""),
                                "Website": normalized.get("website", ""),
                                "Address": normalized.get("address", ""),
                                "Notes": normalized.get("additional_notes", ""),
                                "Created At": normalized.get("created_at", "")
                            }])
                            st.dataframe(df, use_container_width=True)

                            excel_bytes = to_excel_bytes(df, sheet_name="BusinessCard")
                            st.download_button(
                                label="📥 Download as Excel",
                                data=excel_bytes,
                                file_name="business_card_data.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            )
                        else:
                            st.error("❌ Unexpected response (no data). Response content: " + str(resp_json))
                    else:
                        st.error(f"❌ API Error: {resp.status_code} — {resp.text}")
                except requests.exceptions.RequestException as e:
                    st.error(f"❌ Request failed: {e}")

# ----------------------------
# TAB 2: View All Cards
# ----------------------------
with tab2:
    st.info("Fetching all business cards from backend...")
    try:
        resp = requests.get(f"{backend_url.rstrip('/')}/all_cards", timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            # backend returns {"data": [...]} where each item is a dict
            if "data" in data and data["data"]:
                # Ensure we have a DataFrame
                df_all = pd.DataFrame(data["data"])
                # Normalize phone numbers if necessary
                if "phone_numbers" in df_all.columns:
                    df_all["phone_numbers"] = df_all["phone_numbers"].apply(
                        lambda x: ", ".join(x) if isinstance(x, list) else x
                    )
                st.dataframe(df_all, use_container_width=True)

                st.markdown("---")
                st.subheader("📝 Edit Notes")
                # Provide editable notes area for each row
                # We iterate rows and show a text_area + update button
                for i, row in df_all.iterrows():
                    name_display = row.get("name") or f"Record {i}"
                    # use a unique key for text_area using the _id if present
                    key_text = f"notes_{row.get('_id', i)}"
                    notes_current = row.get("additional_notes", "")
                    notes_new = st.text_area(f"Notes for {name_display}", value=notes_current, key=key_text, height=120)
                    btn_key = f"btn_update_{row.get('_id', i)}"
                    if st.button(f"Update Notes for {name_display}", key=btn_key):
                        # call backend update endpoint
                        card_id = row.get("_id")
                        if card_id is None:
                            st.error("Cannot update this row: no `_id` present.")
                        else:
                            try:
                                payload = {"additional_notes": notes_new}
                                update_resp = requests.put(f"{backend_url.rstrip('/')}/update_notes/{card_id}", json=payload, timeout=30)
                                if update_resp.status_code == 200:
                                    st.success("✅ Notes updated successfully")
                                else:
                                    st.error(f"❌ Update failed: {update_resp.status_code} — {update_resp.text}")
                            except requests.exceptions.RequestException as e:
                                st.error(f"❌ Update request failed: {e}")

                st.markdown("---")
                st.subheader("Export")
                excel_all = to_excel_bytes(df_all, sheet_name="AllBusinessCards")
                st.download_button(
                    label="📥 Download All as Excel",
                    data=excel_all,
                    file_name="all_business_cards.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.warning("⚠️ No data found in the backend.")
        else:
            st.error(f"❌ Backend returned status {resp.status_code}: {resp.text}")
    except requests.exceptions.RequestException as e:
        st.error(f"❌ Failed to fetch data: {e}")
