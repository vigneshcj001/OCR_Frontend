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

st.title("📇 Business Card OCR → MongoDB")
st.write(
    "Upload a visiting card image, extract details using FastAPI + Tesseract, "
    "and store them in MongoDB. You can also download the extracted data as Excel."
)

# ----------------------------
# Tabs: Upload & View All
# ----------------------------
tab1, tab2 = st.tabs(["📤 Upload Card", "📁 View All Cards"])

# ----------------------------
# TAB 1: Upload Card
# ----------------------------
with tab1:
    col_preview, col_uploader = st.columns([3, 7])

    # RIGHT: uploader & actions
    with col_uploader:
        uploaded_file = st.file_uploader(
            "Drag and drop file here\nLimit 200MB per file • JPG, JPEG, PNG",
            type=["jpg", "jpeg", "png"]
        )

        if uploaded_file is not None:
            st.write("Upload progress:")
            st.progress(70)

            with st.spinner("🔍 Extracting text and inserting into MongoDB..."):
                files = {"file": (uploaded_file.name, uploaded_file.getvalue())}

                try:
                    response = requests.post(
                        "https://ocr-backend-usi7.onrender.com/upload_card",
                        files=files,
                        timeout=60
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
                                "Notes": extracted.get("additional_notes", ""),
                                "Created At": extracted.get("created_at", "")
                            }])

                            st.dataframe(df, use_container_width=True)

                            # Excel export
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
                            st.error("❌ Unexpected server response.")
                    else:
                        st.error(f"❌ API error: {response.status_code}")
                except Exception as e:
                    st.error(f"❌ Request failed: {e}")

    # LEFT: preview
    with col_preview:
        st.markdown("### Preview")
        if uploaded_file is not None:
            st.image(
                uploaded_file,
                caption="Uploaded Card Preview",
                use_container_width=True
            )
        else:
            st.info("Upload a card to see preview here.")

# ----------------------------
# TAB 2: View All Cards (full inline edit + top download)
# ----------------------------
with tab2:
    st.info("Fetching all business cards from MongoDB...")
    try:
        response = requests.get("https://ocr-backend-usi7.onrender.com/all_cards", timeout=30)

        if response.status_code == 200:
            data = response.json()
            if "data" in data and data["data"]:
                df_all = pd.DataFrame(data["data"])

                # Ensure _id is string
                if "_id" in df_all.columns:
                    df_all["_id"] = df_all["_id"].astype(str)
                else:
                    # If backend changed, ensure there's an id column
                    df_all["_id"] = df_all.index.astype(str)

                # Convert list columns to editable comma-separated strings for the editor
                def list_to_csv(x):
                    if isinstance(x, list):
                        return ", ".join(x)
                    return x

                for col in ("phone_numbers", "social_links"):
                    if col in df_all.columns:
                        df_all[col] = df_all[col].apply(list_to_csv)

                # --- Download all button at the top ---
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
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="download_all_top"
                )

                st.markdown("### 🗂️ All Cards (editable)")
                st.write("Edit cells directly. When finished click **Save Changes** to persist edits to MongoDB.")

                # Use experimental_data_editor or data_editor depending on Streamlit version
                try:
                    edited = st.experimental_data_editor(df_all, num_rows="dynamic", use_container_width=True)
                except Exception:
                    edited = st.data_editor(df_all, num_rows="dynamic", use_container_width=True)

                # Save changes button
                if st.button("💾 Save Changes"):
                    updates = []
                    for i in range(len(df_all)):
                        orig = df_all.iloc[i]
                        new = edited.iloc[i]

                        changed_cols = {}
                        for col in df_all.columns:
                            if col == "_id":
                                continue
                            orig_val = "" if pd.isna(orig[col]) else orig[col]
                            new_val = "" if pd.isna(new[col]) else new[col]
                            if str(orig_val) != str(new_val):
                                # Convert CSV strings back to lists for list fields
                                if col in ("phone_numbers", "social_links"):
                                    if isinstance(new_val, str):
                                        parsed = [x.strip() for x in new_val.split(",") if x.strip()]
                                        changed_cols[col] = parsed
                                    else:
                                        changed_cols[col] = new_val
                                else:
                                    changed_cols[col] = new_val

                        if changed_cols:
                            card_id = str(orig["_id"])
                            try:
                                resp = requests.patch(
                                    f"https://ocr-backend-usi7.onrender.com/update_card/{card_id}",
                                    json=changed_cols,
                                    timeout=15
                                )
                                if resp.status_code in (200, 201):
                                    updates.append((card_id, "OK", list(changed_cols.keys())))
                                else:
                                    updates.append((card_id, f"ERR {resp.status_code}", resp.text))
                            except Exception as e:
                                updates.append((card_id, f"ERR {e}", None))

                    # User feedback
                    if not updates:
                        st.info("No changes detected.")
                    else:
                        ok = [u for u in updates if u[1] == "OK"]
                        errs = [u for u in updates if u[1] != "OK"]
                        if ok:
                            st.success(f"✅ Updated {len(ok)} card(s).")
                        if errs:
                            st.error(f"⚠️ {len(errs)} update(s) failed. See details below.")
                            for card_id, status, detail in errs:
                                st.write(f"- Card {card_id}: {status} — {detail}")

                # Optional: show the current dataframe snapshot below
                st.markdown("---")
                st.write("Current data snapshot:")
                st.dataframe(df_all, use_container_width=True)

            else:
                st.warning("⚠️ No data found.")
        else:
            st.error(f"❌ API Error: {response.status_code}")

    except Exception as e:
        st.error(f"❌ Failed to fetch data: {e}")
