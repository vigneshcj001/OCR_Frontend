# frontend/app.py
import os
import io
import time
from typing import Any, Dict, List

import streamlit as st
import pandas as pd
import requests
from io import BytesIO

# ----------------------------
# Page Configuration
# ----------------------------
st.set_page_config(
    page_title="Business Card OCR → MongoDB",
    page_icon="📇",
    layout="wide",
)

# Backend URL (env var or default)
BACKEND = os.environ.get("BACKEND_URL", "https://ocr-backend-usi7.onrender.com")

st.title("📇 Business Card OCR → MongoDB")
st.write("Upload → Extract OCR → Store → Edit → Download")

# ----------------------------
# Helpers
# ----------------------------
def to_excel_bytes(df: pd.DataFrame) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    return output.getvalue()

def list_to_csv_str(v):
    if isinstance(v, list):
        return ", ".join([str(x) for x in v])
    return v if v is not None else ""

def csv_str_to_list(s: str):
    if s is None:
        return []
    return [x.strip() for x in str(s).split(",") if x.strip()]

def fetch_all_cards(timeout=30) -> List[Dict[str, Any]]:
    try:
        resp = requests.get(f"{BACKEND}/all_cards", timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", [])
    except Exception as e:
        st.error(f"Failed to fetch cards: {e}")
        return []

def pretty_phone_list(v):
    # keep as simple string for display
    return list_to_csv_str(v)

# ----------------------------
# Layout: 70:30 columns for Upload + Preview (Tab 1)
# ----------------------------
tab1, tab2 = st.tabs(["📤 Upload Card", "📁 View All Cards"])

with tab1:
    col_preview, col_upload = st.columns([3, 7])  # 70:30 reversed because preview narrower
    # Upload column (larger)
    with col_upload:
        st.markdown("### Upload card")
        uploaded_file = st.file_uploader(
            "Drag and drop file here\nLimit 200MB • JPG, JPEG, PNG",
            type=["jpg", "jpeg", "png"]
        )

        if uploaded_file:
            # show progress bar + spinner for UX
            progress = st.progress(10)
            time.sleep(0.15)
            progress.progress(40)
            with st.spinner("Processing image with OCR..."):
                files = {"file": (uploaded_file.name, uploaded_file.getvalue())}
                try:
                    response = requests.post(f"{BACKEND}/upload_card", files=files, timeout=120)
                    response.raise_for_status()
                except Exception as e:
                    st.error(f"Failed to reach backend: {e}")
                    response = None

                if response and response.status_code in (200, 201):
                    res = response.json()
                    if "data" in res:
                        st.success("Inserted Successfully!")
                        card = res["data"]
                        df = pd.DataFrame([card]).drop(columns=["_id"], errors="ignore")
                        st.dataframe(df, use_container_width=True)
                        st.download_button(
                            "📥 Download as Excel",
                            to_excel_bytes(df),
                            "business_card.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                    else:
                        st.warning("Backend returned success but no data payload.")
                else:
                    if response is not None:
                        try:
                            err = response.json()
                        except Exception:
                            err = response.text
                        st.error(f"Upload failed: {err}")
                    else:
                        st.error("Upload failed (no response).")
            progress.progress(100)

    # Preview column (narrow)
    with col_preview:
        st.markdown("### Preview")
        if uploaded_file:
            st.image(uploaded_file, use_container_width=True)
        else:
            st.info("Upload a card to preview here.")

    st.markdown("---")

    # Manual form (collapsible)
    with st.expander("📋 Or fill details manually"):
        with st.form("manual_card_form"):
            c1, c2 = st.columns(2)
            name = c1.text_input("Full name")
            designation = c2.text_input("Designation / Title")
            company = c1.text_input("Company")
            phones = c2.text_input("Phone numbers (comma separated)")
            email = c1.text_input("Email")
            website = c2.text_input("Website")
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
                    r = requests.post(f"{BACKEND}/create_card", json=payload, timeout=30)
                    r.raise_for_status()
                except Exception as e:
                    st.error(f"Failed to reach backend: {e}")
                    r = None

                if r and r.status_code in (200, 201):
                    res = r.json()
                    if "data" in res:
                        st.success("Inserted Successfully!")
                        card = res["data"]
                        df = pd.DataFrame([card]).drop(columns=["_id"], errors="ignore")
                        st.dataframe(df, use_container_width=True)
                        st.download_button(
                            "📥 Download as Excel",
                            to_excel_bytes(df),
                            "business_card_manual.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                    else:
                        st.warning("Created but no data returned.")
                else:
                    if r is not None:
                        try:
                            err = r.json()
                        except Exception:
                            err = r.text
                        st.error(f"Failed to create card: {err}")
                    else:
                        st.error("Failed to create card (no response).")

# ========================================================================
# TAB 2 — View & Edit All Cards
# ========================================================================
with tab2:
    st.markdown("### All business cards")
    # Top control row
    top_col1, top_col2 = st.columns([3, 1])
    with top_col1:
        st.info("Edit any column → press **Save Changes** to apply edits to the backend.")
    with top_col2:
        # Fetch data to calculate download content
        data = fetch_all_cards()
        if data:
            df_all_for_download = pd.DataFrame(data)
            # convert lists to CSV strings for Excel
            for col in ["phone_numbers", "social_links"]:
                if col in df_all_for_download.columns:
                    df_all_for_download[col] = df_all_for_download[col].apply(list_to_csv_str)
            st.download_button(
                "📥 Download All as Excel",
                to_excel_bytes(df_all_for_download.drop(columns=["_id"], errors="ignore")),
                "all_business_cards.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.write("")  # placeholder for alignment

    # Fetch fresh data
    with st.spinner("Fetching all business cards..."):
        data = fetch_all_cards()

    if not data:
        st.warning("No cards found.")
    else:
        # Normalize into DataFrame for editing/display
        df_all = pd.DataFrame(data)

        # Ensure all expected columns exist (prevents editor crashing)
        expected_cols = ["_id", "name", "designation", "company", "phone_numbers", "email", "website", "address", "social_links", "additional_notes", "created_at", "edited_at"]
        for c in expected_cols:
            if c not in df_all.columns:
                df_all[c] = ""

        # Convert list columns to CSV strings for display/editing
        for col in ["phone_numbers", "social_links"]:
            df_all[col] = df_all[col].apply(list_to_csv_str)

        # Keep `_id` for updates, but disable editing it
        visible_df = df_all.copy()

        # Migrate timestamps to readable format if necessary (already strings from backend)
        # visible_df["created_at"] = visible_df["created_at"].fillna("")
        # visible_df["edited_at"] = visible_df["edited_at"].fillna("")

        # Place Save Changes button above the editor
        save_col_left, save_col_mid, save_col_right = st.columns([1, 3, 1])
        with save_col_left:
            save_clicked = st.button("💾 Save Changes")
        with save_col_mid:
            st.write("")  # spacer
        with save_col_right:
            st.write("")  # spacer

        # Use experimental_data_editor if available; fallback to data_editor
        try:
            edited = st.experimental_data_editor(
                visible_df,
                use_container_width=True,
                num_rows="fixed",    # prevents adding new rows (no duplicates)
                disabled=["_id"],    # ensure _id can't be changed
            )
        except Exception:
            edited = st.data_editor(
                visible_df,
                use_container_width=True,
                num_rows="fixed",
                disabled=["_id"],
            )

        # Helper: open an edit modal for a selected row (manual drawer)
        def open_edit_modal(row):
            # Use Streamlit modal (available in recent versions)
            with st.modal(f"Edit card — {_truncate_name(row.get('name', ''))}", clear_on_submit=False):
                c1, c2 = st.columns(2)
                name_m = c1.text_input("Full name", value=row.get("name", ""))
                designation_m = c2.text_input("Designation", value=row.get("designation", ""))
                company_m = c1.text_input("Company", value=row.get("company", ""))
                phones_m = c2.text_input("Phone numbers (comma separated)", value=list_to_csv_str(row.get("phone_numbers", "")))
                email_m = c1.text_input("Email", value=row.get("email", ""))
                website_m = c2.text_input("Website", value=row.get("website", ""))
                address_m = st.text_area("Address", value=row.get("address", ""))
                social_m = st.text_input("Social links (comma separated)", value=list_to_csv_str(row.get("social_links", "")))
                notes_m = st.text_area("Notes", value=row.get("additional_notes", ""))
                col_ok, col_del = st.columns([1, 1])
                with col_ok:
                    ok = st.button("Save changes")
                with col_del:
                    delete_it = st.button("🗑 Delete card", key=f"del-{row.get('_id')}")
                if ok:
                    payload = {
                        "name": name_m,
                        "designation": designation_m,
                        "company": company_m,
                        "phone_numbers": phones_m,
                        "email": email_m,
                        "website": website_m,
                        "address": address_m,
                        "social_links": social_m,
                        "additional_notes": notes_m,
                    }
                    try:
                        r = requests.patch(f"{BACKEND}/update_card/{row.get('_id')}", json=_clean_payload_for_backend(payload), timeout=30)
                        r.raise_for_status()
                        st.success("Updated")
                        st.experimental_rerun()
                    except Exception as e:
                        st.error(f"Failed to update: {e}")
                if delete_it:
                    try:
                        r = requests.delete(f"{BACKEND}/delete_card/{row.get('_id')}", timeout=30)
                        if r.status_code in (200, 204):
                            st.success("Deleted")
                            st.experimental_rerun()
                        else:
                            st.error(f"Delete failed: {r.text}")
                    except Exception as e:
                        st.error(f"Failed to delete: {e}")

        # Provide per-row "Edit" and "Open" buttons via selection (simple)
        # We'll show a small instruction and let user click a row index to open modal
        st.markdown("**Tip:** Click a row number in the left-most column to open the manual edit modal (acts like a drawer).")
        chosen_row_index = st.number_input("Open row index (0-based)", min_value=0, max_value=len(edited) - 1, value=0, step=1)

        if st.button("Open selected row in drawer"):
            row = edited.iloc[chosen_row_index].to_dict()
            open_edit_modal(row)

        # When Save Changes clicked, iterate rows and diff against original and send PATCHs
        if save_clicked:
            updates = 0
            problems = 0
            for i in range(len(edited)):
                orig = visible_df.iloc[i]
                new = edited.iloc[i]

                change_set = {}
                for col in visible_df.columns:
                    if col == "_id":
                        continue

                    o = "" if pd.isna(orig[col]) else orig[col]
                    n = "" if pd.isna(new[col]) else new[col]

                    if str(o) != str(n):
                        if col in ["phone_numbers", "social_links"]:
                            items = csv_str_to_list(n)
                            change_set[col] = items
                        else:
                            change_set[col] = n

                if change_set:
                    card_id = new["_id"]   # always track correct MongoDB row
                    try:
                        r = requests.patch(f"{BACKEND}/update_card/{card_id}", json=change_set, timeout=30)
                        if r.status_code in (200, 201):
                            updates += 1
                        else:
                            problems += 1
                            st.error(f"Failed to update {card_id}: {r.text}")
                    except Exception as e:
                        problems += 1
                        st.error(f"Failed to update {card_id}: {e}")

            if updates > 0:
                st.success(f"✅ Updated {updates} card(s). Refreshing...")
                # reload
                try:
                    st.experimental_rerun()
                except Exception:
                    pass
            else:
                if problems == 0:
                    st.info("No changes detected.")
                else:
                    st.warning(f"Save completed with {problems} failures.")

# ----------------------------
# Utilities used inside the UI
# ----------------------------
def _truncate_name(s: str, length: int = 30) -> str:
    if not s:
        return ""
    return s if len(s) <= length else s[: length - 3] + "..."

def _clean_payload_for_backend(payload: dict) -> dict:
    """
    Convert csv strings to lists when appropriate and drop empty fields.
    """
    out = {}
    for k, v in payload.items():
        if v is None:
            continue
        if k in ("phone_numbers", "social_links"):
            if isinstance(v, list):
                out[k] = v
            else:
                out[k] = csv_str_to_list(v)
        else:
            out[k] = v
    return out

# ----------------------------
# Notes:
# - This frontend expects the following backend endpoints:
#   POST /upload_card (file upload)
#   POST /create_card (json payload)
#   GET  /all_cards
#   PATCH /update_card/{card_id}
#   DELETE /delete_card/{card_id}  <-- optional, used by modal delete button
#
# If your backend doesn't have DELETE /delete_card/{id}, you can either
# - add it to the backend, or
# - remove the delete button logic (the modal will still allow editing).
#
# - The editor is configured with num_rows="fixed" and disabled ["_id"]
#   to prevent new rows from being created and to ensure edits map to the
#   original MongoDB documents (no duplicates).
#
# - For very large data sets, consider paging the results server-side.
#
