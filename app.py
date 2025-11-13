import streamlit as st
import requests
import pandas as pd
from io import BytesIO

# ----------------------------
# Page Configuration
# ----------------------------
st.set_page_config(
    page_title="Business Card OCR → MongoDB",
    page_icon="📇",
    layout="wide",
)

BACKEND = "https://ocr-backend-usi7.onrender.com"

st.title("📇 Business Card OCR → MongoDB")
st.write("Upload → Extract OCR → Store → Edit → Download")

# ----------------------------
# Tabs
# ----------------------------
tab1, tab2 = st.tabs(["📤 Upload Card", "📁 View All Cards"])

# ========================================================================
# TAB 1 — Upload Card
# ========================================================================
with tab1:
    col_preview, col_upload = st.columns([3, 7])

    # Upload column
    with col_upload:
        uploaded_file = st.file_uploader(
            "Drag and drop file here\nLimit 200MB • JPG, JPEG, PNG",
            type=["jpg", "jpeg", "png"]
        )

        if uploaded_file:
            st.write("Upload progress:")
            st.progress(70)

            with st.spinner("Processing..."):
                files = {"file": (uploaded_file.name, uploaded_file.getvalue())}
                response = requests.post(f"{BACKEND}/upload_card", files=files)

                if response.status_code == 200:
                    res = response.json()
                    if "data" in res:
                        st.success("Inserted Successfully!")

                        card = res["data"]
                        df = pd.DataFrame([card])

                        st.dataframe(df, use_container_width=True)

                        # Download Excel
                        def to_excel(df):
                            output = BytesIO()
                            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                                df.to_excel(writer, index=False)
                            return output.getvalue()

                        st.download_button(
                            "📥 Download as Excel",
                            to_excel(df),
                            "business_card.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                else:
                    st.error("Upload failed")

    # Preview column
    with col_preview:
        st.markdown("### Preview")
        if uploaded_file:
            st.image(uploaded_file, use_container_width=True)
        else:
            st.info("Upload a card to preview here.")

# ========================================================================
# TAB 2 — View & Edit All Cards
# ========================================================================
with tab2:
    st.info("Fetching all business cards...")

    try:
        response = requests.get(f"{BACKEND}/all_cards")
        data = response.json()

        if "data" in data and data["data"]:
            df_all = pd.DataFrame(data["data"])

            # Remove _id from UI but keep mapping
            ids = df_all["_id"].astype(str).tolist()
            df_all["_id"] = df_all["_id"].astype(str)

            # Convert list fields into editable CSV strings
            def to_csv(v):
                return ", ".join(v) if isinstance(v, list) else v

            for col in ["phone_numbers", "social_links"]:
                if col in df_all.columns:
                    df_all[col] = df_all[col].apply(to_csv)

            # Prepare editor table (hide _id)
            visible_df = df_all.drop(columns=["_id"])

            # Download button (top)
            def all_to_excel(df):
                output = BytesIO()
                with pd.ExcelWriter(output, engine="openpyxl") as writer:
                    df.to_excel(writer, index=False)
                return output.getvalue()

            st.download_button(
                "📥 Download All as Excel",
                all_to_excel(visible_df),
                "all_business_cards.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

            st.markdown("### 📝 Edit Cards Inline")
            st.write("Make changes → then click **Save Changes** below.")

            try:
                edited = st.experimental_data_editor(
                    visible_df,
                    use_container_width=True,
                    num_rows="dynamic"
                )
            except:
                edited = st.data_editor(
                    visible_df,
                    use_container_width=True,
                    num_rows="dynamic"
                )

            # Save button
            if st.button("💾 Save Changes"):
                updates = 0

                for i in range(len(edited)):
                    orig = visible_df.iloc[i]
                    new = edited.iloc[i]

                    change_set = {}

                    for col in visible_df.columns:
                        o = "" if pd.isna(orig[col]) else orig[col]
                        n = "" if pd.isna(new[col]) else new[col]
                        if str(o) != str(n):
                            # Restore list fields
                            if col in ["phone_numbers", "social_links"]:
                                items = [x.strip() for x in n.split(",") if x.strip()]
                                change_set[col] = items
                            else:
                                change_set[col] = n

                    if change_set:
                        card_id = ids[i]
                        r = requests.patch(f"{BACKEND}/update_card/{card_id}", json=change_set)
                        if r.status_code in (200, 201):
                            updates += 1

                if updates > 0:
                    st.success(f"Updated {updates} card(s). Refreshing...")
                    st.experimental_rerun()
                else:
                    st.info("No changes detected.")

        else:
            st.warning("No cards found.")

    except Exception as e:
        st.error(f"Failed to fetch data: {e}")
