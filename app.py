# File: app.py
import os
import time
from typing import Any, Dict, List, Tuple

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

# Ensure a refresh counter exists in session_state (mutating this triggers a rerun)
if "refresh_counter" not in st.session_state:
    st.session_state["refresh_counter"] = 0

# Backend URL (env var or default)
BACKEND = os.environ.get("BACKEND_URL", "https://business-card-scanner-backend.onrender.com")

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

def _truncate_name(s: str, length: int = 30) -> str:
    if not s:
        return ""
    return s if len(s) <= length else s[: length - 3] + "..."

def _clean_payload_for_backend(payload: dict) -> dict:
    """
    Convert csv strings to lists when appropriate and drop empty/none fields.
    """
    out = {}
    for k, v in payload.items():
        # drop None or empty string entirely
        if v is None:
            continue
        if isinstance(v, str) and v.strip() == "":
            continue
        if k in ("phone_numbers", "social_links"):
            if isinstance(v, list):
                out[k] = v
            else:
                out[k] = csv_str_to_list(v)
        else:
            out[k] = v
    return out

def fetch_all_cards(timeout=20) -> List[Dict[str, Any]]:
    try:
        resp = requests.get(f"{BACKEND}/all_cards", timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", [])
    except Exception as e:
        st.error(f"Failed to fetch cards: {e}")
        return []

def patch_card(card_id: str, payload: dict, timeout: int = 30) -> Tuple[bool, str]:
    """
    Unified helper to PATCH a single card. Returns (success, message).
    """
    try:
        # ensure id is string
        card_id = str(card_id)
        r = requests.patch(f"{BACKEND}/update_card/{card_id}", json=_clean_payload_for_backend(payload), timeout=timeout)
        if r.status_code in (200, 201):
            return True, "Updated"
        else:
            try:
                err = r.json()
            except Exception:
                err = r.text
            return False, f"Failed: {err}"
    except Exception as e:
        return False, str(e)

def delete_card(card_id: str, timeout: int = 30) -> Tuple[bool, str]:
    try:
        card_id = str(card_id)
        r = requests.delete(f"{BACKEND}/delete_card/{card_id}", timeout=timeout)
        if r.status_code in (200, 204):
            return True, "Deleted"
        else:
            try:
                err = r.json()
            except Exception:
                err = r.text
            return False, f"Failed to delete: {err}"
    except Exception as e:
        return False, str(e)

# ----------------------------
# Layout: Tabs
# ----------------------------
tab1, tab2 = st.tabs(["📤 Upload Card", "📁 View All Cards"])

# ----------------------------
# TAB 1 — Upload Card + Manual Form
# ----------------------------
with tab1:
    col_preview, col_upload = st.columns([3, 7])

    # Upload column (larger)
    with col_upload:
        st.markdown("### Upload card")
        uploaded_file = st.file_uploader(
            "Drag and drop file here\nLimit 200MB • JPG, JPEG, PNG",
            type=["jpg", "jpeg", "png"]
        )

        if uploaded_file:
            progress = st.progress(10)
            time.sleep(0.08)
            progress.progress(30)
            with st.spinner("Processing image with OCR and uploading..."):
                files = {"file": (uploaded_file.name, uploaded_file.getvalue())}
                try:
                    response = requests.post(f"{BACKEND}/upload_card", files=files, timeout=120)
                    try:
                        response.raise_for_status()
                    except requests.exceptions.HTTPError:
                        try:
                            err = response.json()
                        except Exception:
                            err = response.text
                        st.error(f"Upload failed: {err}")
                        response = None
                except Exception as e:
                    st.error(f"Failed to reach backend: {e}")
                    response = None

                if response and response.status_code in (200, 201):
                    res = response.json()
                    if "data" in res:
                        st.success("Inserted Successfully!")
                        card = res["data"]
                        # hide backend-only fields if present
                        card.pop("field_validations", None)
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
            more_details = st.text_area("More details (leave empty to fill later)")
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
                "more_details": more_details or "",
                "additional_notes": additional_notes,
            }
            with st.spinner("Saving..."):
                try:
                    r = requests.post(f"{BACKEND}/create_card", json=_clean_payload_for_backend(payload), timeout=30)
                    if r.status_code >= 400:
                        try:
                            err = r.json()
                        except Exception:
                            err = r.text
                        st.error(f"Failed to create card: {err}")
                        r = None
                except Exception as e:
                    st.error(f"Failed to reach backend: {e}")
                    r = None

                if r and r.status_code in (200, 201):
                    res = r.json()
                    if "data" in res:
                        st.success("Inserted Successfully!")
                        card = res["data"]
                        card.pop("field_validations", None)
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
            # Remove backend-only field_validations from download data
            for d in data:
                d.pop("field_validations", None)
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
        # Remove field_validations from each record to avoid showing it
        for d in data:
            d.pop("field_validations", None)

        df_all = pd.DataFrame(data)

        # Ensure all expected columns exist (prevents editor crashing)
        expected_cols = ["_id", "name", "designation", "company", "phone_numbers", "email", "website", "address", "social_links", "more_details", "additional_notes", "created_at", "edited_at"]
        for c in expected_cols:
            if c not in df_all.columns:
                df_all[c] = ""

        # Keep a separate list of ids (do NOT show these to the user)
        _ids = df_all["_id"].astype(str).tolist()

        # Convert list columns to CSV strings for display/editing
        display_df = df_all.copy()
        for col in ["phone_numbers", "social_links"]:
            display_df[col] = display_df[col].apply(list_to_csv_str)

        # Drop the _id column from the displayed dataframe so users don't see it
        if "_id" in display_df.columns:
            display_df = display_df.drop(columns=["_id"])

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
                display_df,
                use_container_width=True,
                num_rows="fixed",    # prevents adding new rows (no duplicates)
            )
        except Exception:
            edited = st.data_editor(
                display_df,
                use_container_width=True,
                num_rows="fixed",
            )

        # -----------------------
        # Persisted drawer implementation using session_state
        # -----------------------
        # Ensure session state defaults
        if "drawer_open" not in st.session_state:
            st.session_state["drawer_open"] = False
        if "drawer_row" not in st.session_state:
            st.session_state["drawer_row"] = None

        # Build friendly options list for selectbox
        options = []
        for idx, r in df_all.reset_index(drop=True).iterrows():
            display_name = r.get("name") or r.get("company") or r.get("email") or f"Row {idx}"
            options.append(f"{idx} — {display_name}")

        selected = st.selectbox("Select a row to edit", options, index=0, help="Pick a contact to open the edit drawer")

        # When user clicks to open, persist the chosen row index in session_state
        if st.button("Open selected row in drawer"):
            sel_idx = int(selected.split("—", 1)[0].strip())
            st.session_state["drawer_open"] = True
            st.session_state["drawer_row"] = sel_idx

        # If drawer_open, render the expander every run (so its buttons can be clicked)
        if st.session_state.get("drawer_open") and st.session_state.get("drawer_row") is not None:
            sel_idx = st.session_state["drawer_row"]
            # guard in case data changed length
            if sel_idx < 0 or sel_idx >= len(df_all):
                st.warning("Selected row is no longer available.")
                st.session_state["drawer_open"] = False
                st.session_state["drawer_row"] = None
            else:
                row = df_all.iloc[sel_idx].to_dict()

                # Use a string id for keys and backend calls
                id_str = str(row.get("_id"))

                title = f"Edit card — {_truncate_name(row.get('name', ''))}"
                with st.expander(title, expanded=True):
                    c1, c2 = st.columns(2)
                    name_m = c1.text_input("Full name", value=row.get("name", ""), key=f"name-{id_str}")
                    designation_m = c2.text_input("Designation", value=row.get("designation", ""), key=f"desig-{id_str}")
                    company_m = c1.text_input("Company", value=row.get("company", ""), key=f"company-{id_str}")
                    phones_m = c2.text_input("Phone numbers (comma separated)", value=list_to_csv_str(row.get("phone_numbers", "")), key=f"phones-{id_str}")
                    email_m = c1.text_input("Email", value=row.get("email", ""), key=f"email-{id_str}")
                    website_m = c2.text_input("Website", value=row.get("website", ""), key=f"website-{id_str}")
                    address_m = st.text_area("Address", value=row.get("address", ""), key=f"address-{id_str}")
                    social_m = st.text_input("Social links (comma separated)", value=list_to_csv_str(row.get("social_links", "")), key=f"social-{id_str}")
                    more_m = st.text_area("More details", value=row.get("more_details", ""), key=f"more-{id_str}")
                    notes_m = st.text_area("Notes", value=row.get("additional_notes", ""), key=f"notes-{id_str}")

                    col_ok, col_del, col_close = st.columns([1,1,1])
                    with col_ok:
                        if st.button("Save changes", key=f"drawer-save-{id_str}"):
                            payload = {
                                "name": name_m,
                                "designation": designation_m,
                                "company": company_m,
                                "phone_numbers": phones_m,
                                "email": email_m,
                                "website": website_m,
                                "address": address_m,
                                "social_links": social_m,
                                "more_details": more_m,
                                "additional_notes": notes_m,
                            }
                            success, msg = patch_card(id_str, payload)
                            if success:
                                st.success("Updated")
                                # close drawer and trigger rerun via session_state mutation
                                st.session_state["drawer_open"] = False
                                st.session_state["drawer_row"] = None
                                st.session_state["refresh_counter"] = st.session_state.get("refresh_counter", 0) + 1
                            else:
                                st.error(f"Failed to update: {msg}")

                    with col_del:
                        if st.button("🗑 Delete card", key=f"drawer-del-{id_str}"):
                            success, msg = delete_card(id_str)
                            if success:
                                st.success("Deleted")
                                st.session_state["drawer_open"] = False
                                st.session_state["drawer_row"] = None
                                st.session_state["refresh_counter"] = st.session_state.get("refresh_counter", 0) + 1
                            else:
                                st.error(f"Failed to delete: {msg}")

                    with col_close:
                        if st.button("Close drawer", key=f"drawer-close-{id_str}"):
                            st.session_state["drawer_open"] = False
                            st.session_state["drawer_row"] = None
                            st.session_state["refresh_counter"] = st.session_state.get("refresh_counter", 0) + 1

        # When Save Changes clicked, iterate rows and diff against original and send PATCHs (uses patch_card)
        if save_clicked:
            updates = 0
            problems = 0
            for i in range(len(edited)):
                orig = display_df.iloc[i]
                new = edited.iloc[i]

                change_set = {}
                for col in display_df.columns:
                    o = "" if pd.isna(orig[col]) else orig[col]
                    n = "" if pd.isna(new[col]) else new[col]

                    if str(o) != str(n):
                        if col in ["phone_numbers", "social_links"]:
                            items = csv_str_to_list(n)
                            change_set[col] = items
                        else:
                            change_set[col] = n

                if change_set:
                    card_id = _ids[i]   # always track correct MongoDB row
                    success, msg = patch_card(card_id, change_set)
                    if success:
                        updates += 1
                    else:
                        problems += 1
                        st.error(f"Failed to update {card_id}: {msg}")

            if updates > 0:
                st.success(f"✅ Updated {updates} card(s). Refreshing...")
                # trigger rerun via session_state mutation
                st.session_state["refresh_counter"] = st.session_state.get("refresh_counter", 0) + 1
            else:
                if problems == 0:
                    st.info("No changes detected.")
                else:
                    st.warning(f"Save completed with {problems} failures.")
