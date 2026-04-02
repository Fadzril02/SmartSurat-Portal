from __future__ import annotations

import datetime as dt
import io
import json
import os
import re
import tempfile
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st


# --- SmartSurat • Team Invictus (JKR) — 100% local processing ---
TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
TEMP_STORAGE_DIR = "temp_storage"
DATA_LOG_PATH = "data_log.json"

ACCENT_RED = "#FF0000"
SECONDARY_SILVER = "#C0C0C0"
BG_BLACK = "#000000"

DEPT_CANON = ["Jalan", "Bangunan", "Korporat", "Strategik"]


@dataclass(frozen=True)
class User:
    id: str
    ic: str
    name: str
    role: str
    dept: str
    email: str
    jawatan: str
    gred: str


def _ensure_dirs() -> None:
    os.makedirs(TEMP_STORAGE_DIR, exist_ok=True)


def _load_users() -> List[User]:
    candidate_paths = ["users.json", "user.json"]
    data: List[Dict[str, Any]] = []
    for p in candidate_paths:
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            break
    users: List[User] = []
    for item in data:
        users.append(
            User(
                id=str(item.get("id", "")).strip(),
                ic=str(item.get("ic", "")).strip(),
                name=str(item.get("name", "")).strip(),
                role=str(item.get("role", "")).strip(),
                dept=str(item.get("dept", "")).strip(),
                email=str(item.get("email", "")).strip(),
                jawatan=str(item.get("jawatan", "")).strip(),
                gred=str(item.get("gred", "")).strip(),
            )
        )
    return users


def _auth(user_id: str, ic: str, users: List[User]) -> Optional[User]:
    user_id = (user_id or "").strip()
    ic = (ic or "").strip()
    for u in users:
        if u.id == user_id and u.ic == ic:
            return u
    return None


def _letters_read_from_disk() -> List[Dict[str, Any]]:
    if not os.path.exists(DATA_LOG_PATH):
        return []
    try:
        with open(DATA_LOG_PATH, "r", encoding="utf-8") as f:
            raw = f.read()
        if not raw.strip():
            return []
        data = json.loads(raw)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "letters" in data:
            return list(data["letters"])  # legacy shape
        return []
    except (json.JSONDecodeError, OSError):
        return []


def _letters_write_to_disk(letters: List[Dict[str, Any]]) -> None:
    """Atomic replace so other tabs/processes see a consistent file."""
    _ensure_dirs()
    payload = json.dumps(letters, ensure_ascii=False, indent=2)
    d = os.path.dirname(os.path.abspath(DATA_LOG_PATH)) or "."
    fd, tmp_path = tempfile.mkstemp(prefix="data_log_", suffix=".tmp", dir=d)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, DATA_LOG_PATH)
    except OSError:
        try:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _letters_get() -> List[Dict[str, Any]]:
    """Always read fresh from disk for multi-tab consistency."""
    return _letters_read_from_disk()


def _letters_save_all(letters: List[Dict[str, Any]]) -> None:
    _letters_write_to_disk(letters)


def _find_letter_in_list(letters: List[Dict[str, Any]], letter_id: str) -> Optional[int]:
    for i, rec in enumerate(letters):
        if rec.get("letter_id") == letter_id:
            return i
    return None


def _apply_invictus_theme() -> None:
    st.markdown(
        f"""
        <style>
          .stApp {{
            background: {BG_BLACK};
            color: #FFFFFF;
          }}
          .block-container {{
            padding-top: 2rem;
            padding-bottom: 2rem;
          }}
          section[data-testid="stSidebar"] {{
            background: #050505;
            border-right: 1px solid rgba(192,192,192,0.25);
          }}
          section[data-testid="stSidebar"] * {{
            color: #FFFFFF;
          }}
          /* Red active indicator — sidebar navigation */
          section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {{
            border-left: 4px solid {ACCENT_RED};
            padding-left: 10px;
            margin-left: -4px;
            background: rgba(255,0,0,0.06);
          }}
          div[data-baseweb="input"] > div {{
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(192,192,192,0.35);
            border-radius: 8px;
          }}
          div[data-baseweb="textarea"] > div {{
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(192,192,192,0.35);
            border-radius: 8px;
          }}
          div[data-baseweb="select"] > div {{
            border-radius: 8px;
          }}
          .stButton>button {{
            background: {ACCENT_RED};
            color: #FFFFFF;
            border: 1px solid rgba(255,255,255,0.15);
            border-radius: 10px;
            padding: 0.6rem 1rem;
            font-weight: 700;
          }}
          .stButton>button:hover {{
            background: #d80000;
            border-color: rgba(255,255,255,0.3);
          }}
          div[data-testid="stMetric"] {{
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(192,192,192,0.25);
            border-radius: 14px;
            padding: 1rem;
          }}
          .stDataFrame {{
            border: 1px solid rgba(192,192,192,0.25);
            border-radius: 12px;
            overflow: hidden;
          }}
          h1, h2, h3 {{
            letter-spacing: 0.2px;
          }}
          .invictus-badge {{
            display: inline-block;
            padding: 0.25rem 0.6rem;
            border: 1px solid rgba(192,192,192,0.35);
            border-radius: 999px;
            color: {SECONDARY_SILVER};
            font-size: 0.85rem;
          }}
          .invictus-sub {{
            color: rgba(192,192,192,0.9);
          }}
          .invictus-grid-hr {{
            border: 0;
            border-top: 1px solid rgba(192,192,192,0.2);
            margin: 1.25rem 0;
          }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _init_state() -> None:
    if "authed_user" not in st.session_state:
        st.session_state.authed_user = None


def _now_ts() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _stamp_filename(original: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_\-\.]+", "_", original or "fail")
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{ts}_{safe}"


def _new_letter_record(
    uploaded_by: User,
    original_filename: str,
    saved_path: str,
    mime_type: str,
) -> Dict[str, Any]:
    return {
        "letter_id": str(uuid.uuid4())[:8].upper(),
        "tarikh_direkod": _now_ts(),
        "status": "Baru",
        "uploaded_by": uploaded_by.id,
        "uploaded_by_name": uploaded_by.name,
        "file_name": original_filename,
        "file_path": saved_path,
        "mime_type": mime_type,
        "ocr_text": "",
        "tarikh_surat": "",
        "tarikh_cop_terima": "",
        "perkara": "",
        "nombor_rujukan": "",
        "maklumat_pengirim": "",
        "bahagian_diminitkan": "",
        "assigned_at": "",
        "received_by": "",
        "received_at": "",
    }


DATE_RE = re.compile(r"\b(\d{2}/\d{2}/\d{4})\b")
RUJ_RE = re.compile(r"(?:Ruj\.?\s*Kami\s*[:\-]\s*|Ruj(?:ukan)?\s*[:\-]\s*)(.+)", re.IGNORECASE)
PERKARA_RE = re.compile(r"(?:Perkara\s*[:\-]\s*)(.+)", re.IGNORECASE)


def _clean_line(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def _extract_fields_from_text(text: str) -> Dict[str, str]:
    lines = [_clean_line(l) for l in (text or "").splitlines() if _clean_line(l)]
    joined = "\n".join(lines)

    dates = DATE_RE.findall(joined)
    tarikh_surat = dates[0] if len(dates) >= 1 else ""
    tarikh_cop = dates[1] if len(dates) >= 2 else ""

    nombor_rujukan = ""
    perkara = ""
    maklumat_pengirim = ""

    for l in lines:
        if not nombor_rujukan:
            m = RUJ_RE.search(l)
            if m:
                nombor_rujukan = _clean_line(m.group(1))
        if not perkara:
            m = PERKARA_RE.search(l)
            if m:
                perkara = _clean_line(m.group(1))

    sender_keywords = ("daripada", "pengirim", "from", "kepada", "to")
    for i, l in enumerate(lines[:30]):
        low = l.lower()
        if any(k in low for k in sender_keywords):
            nxt = lines[i + 1] if i + 1 < len(lines) else ""
            if nxt and len(nxt) >= 4:
                maklumat_pengirim = nxt
                break
    if not maklumat_pengirim:
        for l in lines[:15]:
            if len(l) >= 12 and sum(ch.isupper() for ch in l) >= max(6, len(l) // 2):
                maklumat_pengirim = l
                break

    return {
        "tarikh_surat": tarikh_surat,
        "tarikh_cop_terima": tarikh_cop,
        "perkara": perkara,
        "nombor_rujukan": nombor_rujukan,
        "maklumat_pengirim": maklumat_pengirim,
    }


def _ocr_first_page(file_path: str) -> Tuple[str, str]:
    import pytesseract
    from PIL import Image

    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        import fitz

        with fitz.open(file_path) as doc:
            if doc.page_count < 1:
                return "", "none"
            page = doc.load_page(0)
            mat = fitz.Matrix(2, 2)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img_bytes = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_bytes))
            text = pytesseract.image_to_string(img)
            return text, "image"

    img = Image.open(file_path)
    text = pytesseract.image_to_string(img)
    return text, "image"


def _dept_to_canon(dept: str) -> str:
    d = (dept or "").lower()
    if "jalan" in d:
        return "Jalan"
    if "bangunan" in d:
        return "Bangunan"
    if "korporat" in d:
        return "Korporat"
    if "strategik" in d:
        return "Strategik"
    return ""


def _user_from_session(sess: Dict[str, Any]) -> User:
    # Backward compatible if older sessions lack new fields
    return User(
        id=str(sess.get("id", "")),
        ic=str(sess.get("ic", "")),
        name=str(sess.get("name", "")),
        role=str(sess.get("role", "")),
        dept=str(sess.get("dept", "")),
        email=str(sess.get("email", "")),
        jawatan=str(sess.get("jawatan", "")),
        gred=str(sess.get("gred", "")),
    )


def _sidebar(user: User) -> str:
    st.sidebar.markdown("### SmartSurat")
    st.sidebar.caption("Team Invictus")
    st.sidebar.markdown('<span class="invictus-badge">JKR</span>', unsafe_allow_html=True)
    st.sidebar.markdown("")
    st.sidebar.markdown(f"**{user.name}**")
    st.sidebar.markdown(f"`{user.id}` · {user.role}")
    st.sidebar.markdown("---")

    pages: List[str] = []
    if user.role == "User":
        pages.append("Muat Naik")
    if user.role == "Admin":
        pages.append("Daftar & Agih")
    if user.role == "Wakil Penerima":
        pages.append("Pengesahan")
    if user.role == "Senior Admin":
        pages.append("Dashboard")
    pages.append("Profil")
    pages.append("Manual Pengguna")
    pages.append("Aduan / Cadangan")

    choice = st.sidebar.radio("Navigasi", pages, index=0, label_visibility="collapsed")
    st.sidebar.markdown("---")
    if st.sidebar.button("Log Keluar", use_container_width=True):
        st.session_state.authed_user = None
        st.rerun()
    return choice


def _centered_login(users: List[User]) -> None:
    st.markdown("## SmartSurat")
    st.markdown('<span class="invictus-badge">Team Invictus · JKR</span>', unsafe_allow_html=True)
    st.markdown('<p class="invictus-sub"><i>Segalanya Lebih Cekap</i></p>', unsafe_allow_html=True)
    st.markdown('<hr class="invictus-grid-hr"/>', unsafe_allow_html=True)

    left, mid, right = st.columns([1.1, 1, 1.1])
    with mid:
        st.markdown("#### Log Masuk")
        with st.form("login_form", clear_on_submit=False):
            user_id = st.text_input("ID Pengguna")
            ic = st.text_input("No. Kad Pengenalan", type="password")
            submitted = st.form_submit_button("Masuk", use_container_width=True)
        if submitted:
            u = _auth(user_id, ic, users)
            if u:
                st.session_state.authed_user = {
                    "id": u.id,
                    "ic": u.ic,
                    "name": u.name,
                    "role": u.role,
                    "dept": u.dept,
                    "email": u.email,
                    "jawatan": u.jawatan,
                    "gred": u.gred,
                }
                st.rerun()
            else:
                st.error("Maklumat log masuk tidak sah.")


def _letters_df(letters: List[Dict[str, Any]]) -> pd.DataFrame:
    if not letters:
        return pd.DataFrame()
    df = pd.DataFrame(letters)
    preferred = [
        "letter_id",
        "status",
        "tarikh_direkod",
        "tarikh_surat",
        "tarikh_cop_terima",
        "nombor_rujukan",
        "perkara",
        "maklumat_pengirim",
        "bahagian_diminitkan",
        "assigned_at",
        "received_at",
        "file_name",
        "uploaded_by_name",
    ]
    cols = [c for c in preferred if c in df.columns] + [c for c in df.columns if c not in preferred]
    return df[cols]


def _page_muat_naik(user: User) -> None:
    st.markdown("## Muat Naik")
    st.markdown(
        '<div class="invictus-sub">Muat naik PDF atau imej. Tarikh Direkod ditangkap secara automatik. '
        "Semua data disimpan dalam <code>data_log.json</code> (kongsi antara tab).</div>",
        unsafe_allow_html=True,
    )

    uploaded = st.file_uploader("Pilih fail", type=["pdf", "png", "jpg", "jpeg"], accept_multiple_files=False)
    if uploaded:
        _ensure_dirs()
        saved_name = _stamp_filename(uploaded.name)
        saved_path = os.path.join(TEMP_STORAGE_DIR, saved_name)
        with open(saved_path, "wb") as f:
            f.write(uploaded.getbuffer())

        record = _new_letter_record(
            uploaded_by=user,
            original_filename=uploaded.name,
            saved_path=saved_path,
            mime_type=getattr(uploaded, "type", "") or "",
        )
        letters = _letters_get()
        letters.insert(0, record)
        _letters_save_all(letters)

        st.success(f"Berjaya dimuat naik. ID Surat: **{record['letter_id']}**")

    st.markdown("---")
    st.markdown("### Status Saya")
    letters = _letters_get()
    mine = [l for l in letters if l.get("uploaded_by") == user.id]
    if not mine:
        st.info("Tiada muat naik direkod untuk ID anda.")
        return
    df = pd.DataFrame(mine)
    show_cols = [c for c in ["letter_id", "status", "tarikh_direkod", "nombor_rujukan", "perkara", "file_name"] if c in df.columns]
    st.dataframe(df[show_cols], use_container_width=True, hide_index=True)
    st.caption("Aliran status: **Baru** → **Diminitkan** → **Diterima**")


def _page_admin(user: User) -> None:
    st.markdown("## Daftar & Agih")
    st.markdown(
        '<div class="invictus-sub">Surat berstatus <b>Baru</b>: OCR halaman 1 (PDF), ekstrak medan, '
        "kemaskini, agih ke Bahagian. Status menjadi <b>Diminitkan</b> selepas simpan.</div>",
        unsafe_allow_html=True,
    )

    letters = _letters_get()
    baru = [l for l in letters if l.get("status") == "Baru"]
    if not baru:
        st.info("Tiada surat berstatus Baru buat masa ini.")
        return

    options = [f"{l['letter_id']} • {l.get('file_name', '')}" for l in baru]
    by_key = {f"{l['letter_id']} • {l.get('file_name', '')}": l["letter_id"] for l in baru}
    pick = st.selectbox("Pilih surat", options)
    letter_id = by_key.get(pick)
    idx = _find_letter_in_list(letters, letter_id) if letter_id else None
    if idx is None:
        st.error("Rekod tidak dijumpai.")
        return

    rec = letters[idx]

    c0, c1, c2 = st.columns([1, 1, 1.2])
    with c0:
        run = st.button("Jalankan OCR", key="btn_ocr")
    with c1:
        show_text = st.toggle("Papar teks OCR", value=False)
    with c2:
        st.markdown(f"**Fail:** `{rec.get('file_name', '')}`")

    if run:
        try:
            with st.spinner("Menjalankan OCR..."):
                # Runs the OCR on the first page of the file
                text, _ = _ocr_first_page(rec["file_path"])
            
            # Refresh data and update the specific record
            letters = _letters_get()
            idx2 = _find_letter_in_list(letters, letter_id)
            
            if idx2 is None:
                st.error("Rekod hilang semasa OCR. Sila cuba lagi.")
                st.stop()
            
            rec = letters[idx2]
            rec["ocr_text"] = text
            
            # Extract fields using the regex/logic we discussed
            extracted = _extract_fields_from_text(text)
            for k, v in extracted.items():
                if not (rec.get(k) or "").strip():
                    rec[k] = v
            
            # Save the updated metadata back to data_log.json
            _letters_save_all(letters)
            st.success("OCR selesai. Sila semak medan dan sahkan.")
            st.rerun()
            
        except Exception as e:
            # This is the "except" block that was missing
            st.error(f"Ralat OCR: {str(e)}")
            st.warning("Sila pastikan Tesseract dipasang di 'C:\\Program Files\\Tesseract-OCR' atau semak fail dokumen anda.")

    # This part was outside the try block, now it has its indentation back
    if show_text:
        st.text_area("Teks OCR", value=rec.get("ocr_text", ""), height=220, disabled=True)

    st.markdown("### Medan surat (edit) & agihan")
    with st.form("admin_assign_form"):
        a1, a2 = st.columns(2)
        with a1:
            tarikh_surat = st.text_input("Tarikh Surat", value=rec.get("tarikh_surat", ""), placeholder="DD/MM/YYYY")
            nombor_rujukan = st.text_input("No. Rujukan", value=rec.get("nombor_rujukan", ""))
            current_b = rec.get("bahagian_diminitkan", "") or ""
            bi = DEPT_CANON.index(current_b) + 1 if current_b in DEPT_CANON else 0
            bahagian = st.selectbox("Bahagian", [""] + DEPT_CANON, index=bi, format_func=lambda x: "(pilih)" if x == "" else x)
        with a2:
            tarikh_cop = st.text_input("Tarikh Cop Terima", value=rec.get("tarikh_cop_terima", ""), placeholder="DD/MM/YYYY")
            perkara = st.text_area("Perkara", value=rec.get("perkara", ""), height=90)
            pengirim = st.text_area("Maklumat Pengirim", value=rec.get("maklumat_pengirim", ""), height=90)
        save = st.form_submit_button("Sahkan & Diminitkan", use_container_width=True)

    if save:
        if not bahagian:
            st.error("Sila pilih Bahagian sebelum diminitkan.")
            return
        letters = _letters_get()
        idx3 = _find_letter_in_list(letters, letter_id)
        if idx3 is None:
            st.error("Rekod tidak dijumpai.")
            return
        rec = letters[idx3]
        rec["tarikh_surat"] = tarikh_surat.strip()
        rec["tarikh_cop_terima"] = tarikh_cop.strip()
        rec["nombor_rujukan"] = nombor_rujukan.strip()
        rec["perkara"] = perkara.strip()
        rec["maklumat_pengirim"] = pengirim.strip()
        rec["bahagian_diminitkan"] = bahagian.strip()
        rec["assigned_at"] = _now_ts()
        rec["status"] = "Diminitkan"
        _letters_save_all(letters)
        st.success("Surat telah diminitkan dan diagih.")
        st.rerun()


def _page_rep(user: User) -> None:
    st.markdown("## Pengesahan")
    my_dept = _dept_to_canon(user.dept)
    st.markdown(
        f'<div class="invictus-sub">Hanya surat yang diagih ke bahagian anda '
        f"(<b>{my_dept or user.dept}</b>) dipaparkan.</div>",
        unsafe_allow_html=True,
    )

    letters = _letters_get()
    target = my_dept
    diminit = [
        l
        for l in letters
        if l.get("status") == "Diminitkan" and (not target or l.get("bahagian_diminitkan") == target)
    ]

    if not diminit:
        st.info("Tiada surat untuk pengesahan.")
        return

    options = [f"{l['letter_id']} • {(l.get('perkara') or '(tiada perkara)')[:56]}" for l in diminit]
    by_key = {f"{l['letter_id']} • {(l.get('perkara') or '(tiada perkara)')[:56]}": l["letter_id"] for l in diminit}
    pick = st.selectbox("Pilih surat", options)
    letter_id = by_key.get(pick)
    idx = _find_letter_in_list(letters, letter_id) if letter_id else None
    if idx is None:
        st.error("Rekod tidak dijumpai.")
        return

    rec = letters[idx]
    st.markdown("### Ringkasan")
    st.json(
        {
            "ID Surat": rec.get("letter_id"),
            "No. Rujukan": rec.get("nombor_rujukan"),
            "Perkara": rec.get("perkara"),
            "Bahagian": rec.get("bahagian_diminitkan"),
            "Tarikh Diminitkan": rec.get("assigned_at"),
        }
    )

    if st.button("Sahkan Penerimaan", use_container_width=True):
        letters = _letters_get()
        idx4 = _find_letter_in_list(letters, letter_id)
        if idx4 is None:
            st.error("Rekod tidak dijumpai.")
            return
        rec = letters[idx4]
        rec["status"] = "Diterima"
        rec["received_by"] = user.id
        rec["received_at"] = _now_ts()
        _letters_save_all(letters)
        st.success("Penerimaan disahkan (Diterima).")
        st.rerun()


def _export_excel_bytes(df: pd.DataFrame) -> bytes:
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="xlsxwriter") as writer:
        sheet = "SmartSurat"
        df.to_excel(writer, sheet_name=sheet, index=False, startrow=5)
        wb = writer.book
        ws = writer.sheets[sheet]

        fmt_title = wb.add_format(
            {"bold": True, "font_color": "white", "bg_color": "#111111", "align": "left", "valign": "vcenter", "font_size": 14}
        )
        fmt_sub = wb.add_format({"font_color": "#C0C0C0", "bg_color": "#111111"})
        fmt_hdr = wb.add_format({"bold": True, "bg_color": "#222222", "font_color": "white", "border": 1})

        ncols = max(0, len(df.columns) - 1)
        ws.set_row(0, 24)
        ws.merge_range(0, 0, 0, ncols, "JKR · SmartSurat (Team Invictus)", fmt_title)
        ws.merge_range(1, 0, 1, ncols, "Laporan Induk Surat Masuk", fmt_sub)
        ws.merge_range(2, 0, 2, ncols, f"Dijana: {dt.datetime.now().strftime('%d/%m/%Y %H:%M')}", fmt_sub)

        for col_idx, col_name in enumerate(df.columns):
            ws.write(5, col_idx, col_name, fmt_hdr)
            width = min(55, max(12, len(str(col_name)) + 2))
            ws.set_column(col_idx, col_idx, width)
        ws.freeze_panes(6, 0)
    out.seek(0)
    return out.getvalue()


def _page_dashboard() -> None:
    st.markdown("## Dashboard")
    st.markdown(
        '<div class="invictus-sub">Statistik ringkas, jadual induk dengan tapisan, dan eksport Excel '
        "(pandas / xlsxwriter). Semua pemprosesan setempat.</div>",
        unsafe_allow_html=True,
    )

    letters = _letters_get()
    df = _letters_df(letters)
    if df.empty:
        st.info("Tiada rekod dalam data log.")
        return

    total_baru = int((df["status"] == "Baru").sum()) if "status" in df.columns else 0
    total_dim = int((df["status"] == "Diminitkan").sum()) if "status" in df.columns else 0
    total_dit = int((df["status"] == "Diterima").sum()) if "status" in df.columns else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Baru", total_baru)
    c2.metric("Diminitkan", total_dim)
    c3.metric("Diterima", total_dit)
    c4.metric("Jumlah", len(df))

    st.markdown("### Jadual induk & carian")
    f1, f2, f3 = st.columns((1.2, 1, 1))
    with f1:
        q_ruj = st.text_input("Tapis No. Rujukan", value="", placeholder="Substring carian")
    with f2:
        st_opts = ["Semua", "Baru", "Diminitkan", "Diterima"]
        q_status = st.selectbox("Tapis Status", st_opts, index=0)
    with f3:
        q_free = st.text_input("Carian umum", value="", placeholder="ID / Perkara / Pengirim / Bahagian")

    dff = df.copy()
    if q_ruj.strip() and "nombor_rujukan" in dff.columns:
        dff = dff[dff["nombor_rujukan"].astype(str).str.lower().str.contains(q_ruj.strip().lower(), na=False)]
    if q_status != "Semua" and "status" in dff.columns:
        dff = dff[dff["status"] == q_status]
    if q_free.strip():
        ql = q_free.strip().lower()
        mask = pd.Series(False, index=dff.index)
        for col in ["letter_id", "nombor_rujukan", "perkara", "maklumat_pengirim", "bahagian_diminitkan", "status", "uploaded_by_name"]:
            if col in dff.columns:
                mask = mask | dff[col].astype(str).str.lower().str.contains(re.escape(ql), na=False)
        dff = dff[mask]

    st.dataframe(dff, use_container_width=True, hide_index=True)

    excel_bytes = _export_excel_bytes(dff)
    st.download_button(
        "Muat Turun & Cetak (Excel)",
        data=excel_bytes,
        file_name=f"SmartSurat_Invictus_{dt.datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )


def _page_profile(user: User) -> None:
    st.markdown("## Profil")
    st.markdown('<div class="invictus-sub">Maklumat akaun daripada pendaftaran (<code>users.json</code>).</div>', unsafe_allow_html=True)

    st.table(
        pd.DataFrame(
            [
                {"Medan": "Emel", "Nilai": user.email or "—"},
                {"Medan": "Jawatan", "Nilai": user.jawatan or "—"},
                {"Medan": "Gred", "Nilai": user.gred or "—"},
                {"Medan": "Bahagian", "Nilai": user.dept or "—"},
                {"Medan": "Peranan Sistem", "Nilai": user.role},
                {"Medan": "Nama", "Nilai": user.name},
            ]
        )
    )


def _page_placeholder(title: str, body: str) -> None:
    st.markdown(f"## {title}")
    st.info(body)


def main() -> None:
    st.set_page_config(page_title="SmartSurat · Invictus", page_icon="📄", layout="wide")
    _apply_invictus_theme()
    _ensure_dirs()
    _init_state()

    users = _load_users()
    authed = st.session_state.authed_user

    if not authed:
        _centered_login(users)
        return

    user = _user_from_session(authed)
    page = _sidebar(user)

    if page == "Muat Naik":
        _page_muat_naik(user)
    elif page == "Daftar & Agih":
        _page_admin(user)
    elif page == "Pengesahan":
        _page_rep(user)
    elif page == "Dashboard":
        _page_dashboard()
    elif page == "Profil":
        _page_profile(user)
    elif page == "Manual Pengguna":
        _page_placeholder("Manual Pengguna", "Placeholder — dokumentasi pengguna akan disediakan oleh Team Invictus.")
    elif page == "Aduan / Cadangan":
        _page_placeholder("Aduan / Cadangan", "Placeholder — saluran maklum balas dalaman (tiada panggilan API luaran).")
    else:
        st.markdown("## SmartSurat")
        st.warning("Halaman tidak dikenali.")


if __name__ == "__main__":
    main()
