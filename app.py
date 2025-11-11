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
# File Uploader
# ----------------------------
uploaded_file = st.file_uploader(
    "Upload Visiting Card", type=["jpg", "jpeg", "png"]
)

if uploaded_file is not None:
    st.image(uploaded_file, caption="Uploaded Card", use_container_width=True)

    with st.spinner("🔍 Extracting text and inserting into MongoDB..."):
        # Prepare file for POST request
        files = {"file": (uploaded_file.name, uploaded_file.getvalue())}

        try:
            # Replace this URL with your deployed FastAPI backend
            response = requests.post(
                "https://ocr-backend-usi7.onrender.com/upload_card", files=files
            )

            if response.status_code == 200:
                data = response.json()
                if "data" in data:
                    extracted = data["data"]
                    st.success("✅ Inserted Successfully into MongoDB")

                    # ----------------------------
                    # Display as Table
                    # ----------------------------
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

                    # ----------------------------
                    # Excel Download
                    # ----------------------------
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
