import streamlit as st
import requests
import pandas as pd
from io import BytesIO

# ----------------------------
# Page Configuration
# ----------------------------
st.set_page_config(
    page_title="Business Card OCR → MongoDB (OpenOCR)",
    page_icon="📇",
    layout="wide",
)

st.title("📇 Business Card OCR → MongoDB (OpenOCR)")
st.write(
    "Upload a visiting card image, extract details using FastAPI + OpenOCR, "
    "and store them in MongoDB. You can also download the extracted data as Excel."
)

# ----------------------------
# API BASE URL (update if deployed)
# ----------------------------
API_BASE = "https://ocr-backend-usi7.onrender.com"  # change to your deployed backend if needed

# ----------------------------
# Tabs: Upload & View All
# ----------------------------
tab1, tab2 = st.tabs(["📤 Upload Card", "📁 View All Cards"])

# ----------------------------
# TAB 1: Upload Card
# ----------------------------
with tab1:
    uploaded_file = st.file_uploader("Upload Visiting Card", type=["jpg", "jpeg", "png"])

    if uploaded_file is not None:
        col1, col2 = st.columns([1, 2])

        with col1:
            st.image(uploaded_file, caption="Uploaded Card", width=250)

        with col2:
            with st.spinner("🔍 Extracting text and inserting into MongoDB..."):
                files = {"file": (uploaded_file.name, uploaded_file.getvalue())}
                try:
                    response = requests.post(f"{API_BASE}/ocr/business-card", files=files)

                    if response.status_code == 200:
                        data = response.json()

                        if "extracted_data" in data:
                            extracted = data["extracted_data"]
                            st.success("✅ Extracted Successfully using OpenOCR")

                            df = pd.DataFrame([{
                                "Name": extracted.get("name", ""),
                                "Designation": extracted.get("designation", ""),
                                "Company": extracted.get("company", ""),
                                "Phone Numbers": ", ".join(extracted.get("phone_numbers", [])),
                                "Email": extracted.get("email", ""),
                                "Website": extracted.get("website", ""),
                                "Address": extracted.get("address", ""),
                                "Social Links": ", ".join(extracted.get("social_links", [])),
                                "Created At": data.get("created_at", "")
                            }])

                            st.dataframe(df, use_container_width=True)

                            # Excel Download
                            def to_excel(df):
                                output = BytesIO()
                                with pd.ExcelWriter(output, engine="openpyxl") as writer:
                                    df.to_excel(writer, index=False, sheet_name="BusinessCard")
                                return output.getvalue()

                            excel_data = to_excel(df)

                            st.download_button(
                                label="📥 Download as Excel",
                                data=excel_data,
                                file_name="business_card_data.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            )

                        else:
                            st.error(f"❌ Unexpected response: {data}")
                    else:
                        st.error(f"❌ API Error: {response.status_code} - {response.text}")

                except Exception as e:
                    st.error(f"❌ Request failed: {e}")

# ----------------------------
# TAB 2: View All Cards (optional if MongoDB enabled)
# ----------------------------
with tab2:
    st.info("Fetching all business cards from MongoDB (if backend has MongoDB enabled)...")
    try:
        response = requests.get(f"{API_BASE}/all_cards")
        if response.status_code == 200:
            data = response.json()
            if "data" in data and data["data"]:
                df_all = pd.DataFrame(data["data"])
                st.dataframe(df_all, use_container_width=True)

                # Excel download
                def to_excel(df):
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine="openpyxl") as writer:
                        df.to_excel(writer, index=False, sheet_name="AllBusinessCards")
                    return output.getvalue()

                excel_data = to_excel(df_all)

                st.download_button(
                    label="📥 Download All as Excel",
                    data=excel_data,
                    file_name="all_business_cards.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.warning("⚠️ No data found.")
        else:
            st.error(f"❌ API Error: {response.status_code}")
    except Exception as e:
        st.error(f"❌ Failed to fetch data: {e}")
