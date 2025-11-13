# streamlit_app.py
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

# Change this to your backend URL (include protocol)
BACKEND = st.secrets.get("BACKEND_URL", "http://localhost:8000")

st.title("📇 Business Card OCR → MongoDB")
st.write("Upload → Extract OCR → Store → Edit → Download")

# ----------------------------
# Tabs
# ----------------------------
tab1, tab2 = st.tabs(["📤 Upload Card", "📁 View All Cards"])

# ----------------------------
# Helpers
# ----------------------------
def to_excel_bytes(df: pd.DataFrame) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    return output.getvalue()

# ========================================================================
# TAB 1 — Upload Card + Manual Form
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
                try:
                    response = requests.post(f"{BACKEND}/upload_card", files=files)
                except Exception as e:
                    st.error(f"Failed to reach backend: {e}")
                    response = None

                if response and response.status_code in (200, 201):
                    res = response.json()
                    if "data" in res:
                        st.success("Inserted Successfully!")

                        card = res["data"]
                        df = pd.DataFrame([card])

                        st.dataframe(df, use_container_width=True)

                        st.download_button(
                            "📥 Download as Excel",
                            to_excel_bytes(df),
                            "business_card.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                else:
                    if response is not None:
                        try:
                            err = response.json()
                        except:
                            err = response.text
                        st.error(f"Upload failed: {err}")
                    else:
                        st.error("Upload failed (no response).")

    # Preview column
    with col_preview:
        st.markdown("### Preview")
        if uploaded_file:
            st.image(uploaded_file, use_container_width=True)
        else:
            st.info("Upload a card to preview here.")

    # Manual form below
    st.markdown("---")
    st.markdown("### Or fill details manually")

    with st.form("manual_card_form"):
        name = st.text_input("Full name")
        designation = st.text_input("Designation / Title")
        company = st.text_input("Company")
        phones = st.text_input("Phone numbers (comma separated)")
        email = st.text_input("Email")
        website = st.text_input("Website (include http:// or https:// if possible)")
        address = st.text_area("Address")
        social_links = st.text_input("Social links (comma separated)")
        additional_notes = st.text_area("Notes / extra info")
        submitted = st.form_submit_button("📤 Create Card (manual)")

    if submitted:
        payload = {
            "name": name,
            "designation": designation,
            "company": company,
            "phone_numbers": phones,
            "email": email,
            "website": website,
            "address": address,
            "social_links": social_links,
            "additional_notes": additional_notes,
        }
        with st.spinner("Saving..."):
            try:
                r = requests.post(f"{BACKEND}/create_card", json=payload)
            except Exception as e:
                st.error(f"Failed to reach backend: {e}")
                r = None

            if r and r.status_code in (200, 201):
                res = r.json()
                if "data" in res:
                    st.success("Inserted Successfully!")
                    card = res["data"]
                    df = pd.DataFrame([card])
                    st.dataframe(df, use_container_width=True)

                    st.download_button(
                        "📥 Download as Excel",
                        to_excel_bytes(df),
                        "business_card_manual.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
            else:
                if r is not None:
                    try:
                        err = r.json()
                    except:
                        err = r.text
                    st.error(f"Failed to create card: {err}")
                else:
                    st.error("Failed to create card (no response).")

# ========================================================================
# TAB 2 — View & Edit All Cards
# ========================================================================
with tab2:
    st.info("Fetching all business cards...")

    try:
        response = requests.get(f"{BACKEND}/all_cards")
        data = response.json()
    except Exception as e:
        st.error(f"Failed to fetch data: {e}")
        data = {}

    if "data" in data and data["data"]:
        df_all = pd.DataFrame(data["data"])

        # keep mapping of ids
        ids = df_all["_id"].astype(str).tolist()
        df_all["_id"] = df_all["_id"].astype(str)

        # Convert list fields into editable CSV strings
        def to_csv(v):
            if isinstance(v, list):
                return ", ".join(v)
            return v

        for col in ["phone_numbers", "social_links"]:
            if col in df_all.columns:
                df_all[col] = df_all[col].apply(to_csv)

        visible_df = df_all.drop(columns=["_id"])

        # Download button (top)
        st.download_button(
            "📥 Download All as Excel",
            to_excel_bytes(visible_df),
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
        except Exception:
            edited = st.data_editor(
                visible_df,
                use_container_width=True,
                num_rows="dynamic"
            )

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
                        if col in ["phone_numbers", "social_links"]:
                            items = [x.strip() for x in n.split(",") if x.strip()]
                            change_set[col] = items
                        else:
                            change_set[col] = n

                if change_set:
                    card_id = ids[i]
                    try:
                        r = requests.patch(f"{BACKEND}/update_card/{card_id}", json=change_set)
                        if r.status_code in (200, 201):
                            updates += 1
                    except Exception as e:
                        st.error(f"Failed to update card {card_id}: {e}")

            if updates > 0:
                st.success(f"✅ Updated {updates} card(s). Refreshing...")
                try:
                    st.experimental_rerun()
                except Exception:
                    pass
            else:
                st.info("No changes detected.")
    else:
        st.warning("No cards found.")
