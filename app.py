import streamlit as st
import requests
import pandas as pd
from io import BytesIO

# ----------------------------
# Page Configuration
# ----------------------------
st.set_page_config(page_title="Business Card OCR → MongoDB", page_icon="📇", layout="centered")

st.title("📇 Business Card OCR → MongoDB")
st.write(
    "Upload a visiting card image, extract details using FastAPI + Tesseract, "
    "and store them in MongoDB. You can also download the extracted data as Excel."
)

# ----------------------------
# Tabs: Upload & View All
# ----------------------------
tab1, tab2 = st.tabs(["Upload Card", "View All Cards"])

# ----------------------------
# TAB 1: Upload Card
# ----------------------------
with tab1:
    uploaded_file = st.file_uploader(
        "Upload Visiting Card", type=["jpg", "jpeg", "png"]
    )

    if uploaded_file is not None:
        st.image(uploaded_file, caption="Uploaded Card", use_container_width=True)

        with st.spinner("🔍 Extracting text and inserting into MongoDB..."):
            files = {"file": (uploaded_file.name, uploaded_file.getvalue())}
            try:
                response = requests.post(
                    "https://ocr-backend-usi7.onrender.com/upload_card", files=files
                )

                if response.status_code == 200:
                    data = response.json()
                    if "data" in data:
                        extracted = data["data"]
                        st.success("✅ Inserted Successfully into MongoDB")

                        df = pd.DataFrame([{
                            "Name": extracted.get("name", ""),
                            "Designation": extracted.get("designation", ""),
                            "Company": extracted.get("company", ""),
                            "Phone Numbers": ", ".join(extracted.get("phone_numbers", [])),
                            "Email": extracted.get("email", ""),
                            "Website": extracted.get("website", ""),
                            "Address": extracted.get("address", ""),
                            "Notes": extracted.get("additional_notes", "")
                        }])

                        st.dataframe(df, use_container_width=True)

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
                        st.error("❌ Failed: " + str(data))
                else:
                    st.error(f"❌ API Error: {response.status_code}")

            except Exception as e:
                st.error(f"❌ Request failed: {e}")

# ----------------------------
# TAB 2: View All Cards
# ----------------------------
with tab2:
    st.info("Fetching all business cards from MongoDB...")
    try:
        # Replace with your FastAPI endpoint for fetching all records
        response = requests.get("https://ocr-backend-usi7.onrender.com/all_cards")

        if response.status_code == 200:
            data = response.json()
            if "data" in data:
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
                st.warning("No data found.")
        else:
            st.error(f"❌ API Error: {response.status_code}")

    except Exception as e:
        st.error(f"❌ Failed to fetch data: {e}")
