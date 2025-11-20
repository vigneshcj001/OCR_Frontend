# streamlit_frontend.py
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

if "refresh_counter" not in st.session_state:
    st.session_state["refresh_counter"] = 0

BACKEND = os.environ.get("BACKEND_URL", "http://localhost:8000")
FRONTEND_OPENAI_KEY = os.environ.get("FRONTEND_OPENAI_KEY")  # expected to be set in env (.env) so UI doesn't prompt

st.title("📇 Business Card OCR → MongoDB")
st.write("Upload → Extract OCR (OpenAI required) → Store → Edit → Download")

if not FRONTEND_OPENAI_KEY:
    st.error("FRONTEND_OPENAI_KEY environment variable is not set. Please set it to a valid OpenAI key (sk-...). The frontend will send this key to the backend for parsing.")
    st.stop()

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
    out = {}
    for k, v in payload.items():
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
        return data.get("data", data) if isinstance(data, dict) else data
    except Exception as e:
        st.error(f"Failed to fetch cards: {e}")
        return []

def patch_card(card_id: str, payload: dict, timeout: int = 30) -> Tuple[bool, str]:
    try:
        card_id = str(card_id)
        headers = {"Authorization": f"Bearer {FRONTEND_OPENAI_KEY}"} if FRONTEND_OPENAI_KEY else {}
        r = requests.patch(f"{BACKEND}/update_card/{card_id}", json=_clean_payload_for_backend(payload), headers=headers, timeout=timeout)
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
        headers = {"Authorization": f"Bearer {FRONTEND_OPENAI_KEY}"} if FRONTEND_OPENAI_KEY else {}
        r = requests.delete(f"{BACKEND}/delete_card/{card_id}", headers=headers, timeout=timeout)
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
                files = {
                    "file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type or "application/octet-stream")
                }
                headers = {"Authorization": f"Bearer {FRONTEND_OPENAI_KEY}"} if FRONTEND_OPENAI_KEY else {}

                try:
                    response = requests.post(f"{BACKEND}/extract", files=files, headers=headers, timeout=120)
                except Exception as e:
                    st.error(f"Failed to reach backend: {e}")
                    response = None

                if response is not None:
                    st.write(f"Backend status: {response.status_code}")
                    try:
                        st.json(response.json())
                    except Exception:
                        st.text(response.text)

                if response and response.status_code in (200, 201):
                    res = response.json()
                    card = res.get("data") if isinstance(res, dict) and "data" in res else res

                    if card:
                        st.success("Extracted — review and save below")
                        card_display = dict(card)
                        card_display["phone_numbers"] = list_to_csv_str(card_display.get("phone_numbers", []))
                        card_display["social_links"] = list_to_csv_str(card_display.get("social_links", []))

                        df = pd.DataFrame([card_display]).drop(columns=["_id"], errors="ignore")
                        st.dataframe(df, use_container_width=True)

                        if st.button("📥 Save extracted contact to DB"):
                            payload = {
                                "name": card.get("name"),
                                "designation": card.get("designation"),
                                "company": card.get("company"),
                                "phone_numbers": card.get("phone_numbers") or [],
                                "email": card.get("email"),
                                "website": card.get("website"),
                                "address": card.get("address"),
                                "social_links": card.get("social_links") or [],
                                "more_details": card.get("more_details") or "",
                                "additional_notes": card.get("additional_notes") or "",
                            }
                            try:
                                headers = {"Authorization": f"Bearer {FRONTEND_OPENAI_KEY}"} if FRONTEND_OPENAI_KEY else {}
                                r = requests.post(f"{BACKEND}/create_card", json=_clean_payload_for_backend(payload), headers=headers, timeout=30)
                                if r.status_code >= 400:
                                    try:
                                        err = r.json()
                                    except Exception:
                                        err = r.text
                                    st.error(f"Failed to create card: {err}")
                                else:
                                    res2 = r.json()
                                    saved = res2.get("data") if isinstance(res2, dict) and "data" in res2 else res2
                                    st.success("Inserted Successfully!")
                                    saved_display = dict(saved)
                                    saved_display["phone_numbers"] = list_to_csv_str(saved_display.get("phone_numbers", []))
                                    saved_display["social_links"] = list_to_csv_str(saved_display.get("social_links", []))
                                    df2 = pd.DataFrame([saved_display]).drop(columns=["_id"], errors="ignore")
                                    st.dataframe(df2, use_container_width=True)
                                    st.download_button(
                                        "📥 Download as Excel",
                                        to_excel_bytes(df2),
                                        "business_card.xlsx",
                                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                                    )
                            except Exception as e:
                                st.error(f"Failed to reach backend: {e}")
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

    with col_preview:
        st.markdown("### Preview")
        if uploaded_file:
            st.image(uploaded_file, use_container_width=True)
        else:
            st.info("Upload a card to preview here.")

    st.markdown("---")

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
                "phone_numbers": csv_str_to_list(phones),
                "email": email,
                "website": website,
                "address": address,
                "social_links": csv_str_to_list(social_links),
                "more_details": more_details or "",
                "additional_notes": additional_notes or "",
            }
            with st.spinner("Saving..."):
                try:
                    headers = {"Authorization": f"Bearer {FRONTEND_OPENAI_KEY}"} if FRONTEND_OPENAI_KEY else {}
                    r = requests.post(f"{BACKEND}/create_card", json=_clean_payload_for_backend(payload), headers=headers, timeout=30)
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
                    created = res.get("data") if isinstance(res, dict) and "data" in res else res
                    if created:
                        st.success("Inserted Successfully!")
                        created_display = dict(created)
                        created_display["phone_numbers"] = list_to_csv_str(created_display.get("phone_numbers", []))
                        created_display["social_links"] = list_to_csv_str(created_display.get("social_links", []))
                        df = pd.DataFrame([created_display]).drop(columns=["_id"], errors="ignore")
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
    top_col1, top_col2 = st.columns([3, 1])
    with top_col1:
        st.info("Edit any column → press **Save Changes** to apply edits to the backend.")
    with top_col2:
        data = fetch_all_cards()
        if data:
            for d in data:
                d.pop("field_validations", None)
            df_all_for_download = pd.DataFrame(data)
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
            st.write("")

    with st.spinner("Fetching all business cards..."):
        data = fetch_all_cards()

    if not data:
        st.warning("No cards found.")
    else:
        for d in data:
            d.pop("field_validations", None)

        df_all = pd.DataFrame(data)

        expected_cols = ["_id", "name", "designation", "company", "phone_numbers", "email", "website", "address", "social_links", "more_details", "additional_notes", "created_at", "edited_at"]
        for c in expected_cols:
            if c not in df_all.columns:
                df_all[c] = ""

        _ids = df_all["_id"].astype(str).tolist()

        display_df = df_all.copy()
        for col in ["phone_numbers", "social_links"]:
            display_df[col] = display_df[col].apply(list_to_csv_str)

        if "_id" in display_df.columns:
            display_df = display_df.drop(columns=["_id"])

        save_col_left, save_col_mid, save_col_right = st.columns([1, 3, 1])
        with save_col_left:
            save_clicked = st.button("💾 Save Changes")
        with save_col_mid:
            st.write("")
        with save_col_right:
            st.write("")

        try:
            edited = st.experimental_data_editor(
                display_df,
                use_container_width=True,
                num_rows="fixed",
            )
        except Exception:
            edited = st.data_editor(
                display_df,
                use_container_width=True,
                num_rows="fixed",
            )

        if "drawer_open" not in st.session_state:
            st.session_state["drawer_open"] = False
        if "drawer_row" not in st.session_state:
            st.session_state["drawer_row"] = None

        options = []
        for idx, r in df_all.reset_index(drop=True).iterrows():
            display_name = r.get("name") or r.get("company") or r.get("email") or f"Row {idx}"
            options.append(f"{idx} — {display_name}")

        selected = st.selectbox("Select a row to edit", options, index=0, help="Pick a contact to open the edit drawer")

        if st.button("Open selected row in drawer"):
            sel_idx = int(selected.split("—", 1)[0].strip())
            st.session_state["drawer_open"] = True
            st.session_state["drawer_row"] = sel_idx

        if st.session_state.get("drawer_open") and st.session_state.get("drawer_row") is not None:
            sel_idx = st.session_state["drawer_row"]
            if sel_idx < 0 or sel_idx >= len(df_all):
                st.warning("Selected row is no longer available.")
                st.session_state["drawer_open"] = False
                st.session_state["drawer_row"] = None
            else:
                row = df_all.iloc[sel_idx].to_dict()
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
                            # Convert comma-separated phone/social strings into lists (trim and drop empty)
                            def _csv_to_list(s: str):
                                if s is None:
                                    return []
                                return [x.strip() for x in str(s).split(",") if x.strip()]

                            payload = {
                                "name": name_m or None,
                                "designation": designation_m or None,
                                "company": company_m or None,
                                "phone_numbers": _csv_to_list(phones_m),
                                "email": email_m or None,
                                "website": website_m or None,
                                "address": address_m or None,
                                "social_links": _csv_to_list(social_m),
                                "more_details": more_m or None,
                                "additional_notes": notes_m or None,
                            }

                            success, msg = patch_card(id_str, payload)
                            if success:
                                st.success("Updated")
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
                    card_id = _ids[i]
                    success, msg = patch_card(card_id, change_set)
                    if success:
                        updates += 1
                    else:
                        problems += 1
                        st.error(f"Failed to update {card_id}: {msg}")

            if updates > 0:
                st.success(f"✅ Updated {updates} card(s). Refreshing...")
                st.session_state["refresh_counter"] = st.session_state.get("refresh_counter", 0) + 1
            else:
                if problems == 0:
                    st.info("No changes detected.")
                else:
                    st.warning(f"Save completed with {problems} failures.")
