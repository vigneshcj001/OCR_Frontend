import streamlit as st
import requests

st.set_page_config(page_title="Business Card OCR", page_icon="📇")

st.title("📇 Business Card OCR → MongoDB")
st.write("Upload a visiting card image to extract details and insert into MongoDB automatically.")

uploaded_file = st.file_uploader("Upload Visiting Card", type=["jpg", "jpeg", "png"])

if uploaded_file is not None:
    st.image(uploaded_file, caption="Uploaded Card", use_container_width=True)

    with st.spinner("Extracting text and inserting into MongoDB..."):
        # Prepare file as tuple (filename, filebytes)
        files = {"file": (uploaded_file.name, uploaded_file.getvalue())}

        try:
            response = requests.post("https://ocr-backend-usi7.onrender.com/upload_card", files=files)

            if response.status_code == 200:
                data = response.json()
                if "data" in data:
                    st.success("✅ Inserted Successfully into MongoDB")
                    st.json(data["data"])
                else:
                    st.error("❌ Failed: " + str(data))
            else:
                st.error(f"❌ API Error: {response.status_code}")
        except Exception as e:
            st.error(f"❌ Request failed: {e}")
