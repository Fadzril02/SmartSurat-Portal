from __future__ import annotations

import datetime as dt
import hashlib
import io
import os
import re
from typing import Any, Dict, List

import cv2
import numpy as np
import pandas as pd
import streamlit as st

from models import DEPT_CANON, User, departments_match
from processor_service import extract_fields_from_text, ocr_first_page, pil_from_bgr, scan_document_bgr
from google_drive_service import upload_letter_to_drive_and_store
from storage_service import (
    ensure_dirs,
    find_letter_in_list,
    is_admin_user,
    letter_assigned_department,
    letter_owner_id,
    letters_for_session_user,
    letters_get,
    letters_save_all,
    new_letter_record,
    now_ts,
    stamp_filename,
    TEMP_STORAGE_DIR,
)


def user_from_session(sess: Dict[str, Any]) -> User:
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


def sidebar(user: User) -> str:
    st.sidebar.markdown("### SmartSurat")
    st.sidebar.caption("Team Invictus")
    st.sidebar.markdown('<span class="invictus-badge">JKR</span>', unsafe_allow_html=True)
    st.sidebar.markdown("")
    st.sidebar.markdown(f"**{user.name}**")
    st.sidebar.markdown(f"`{user.id}` · {user.role}")
    st.sidebar.markdown("---")

    pages: List[str] = []
    if user.role in ("Admin", "Staff", "User"):
        pages.append("Muat Naik")
    if user.role == "Admin":
        pages.append("Daftar & Agih")
    if user.role in ("Admin", "Wakil Penerima"):
        pages.append("Pengesahan")
    if user.role in ("Admin", "Staff"):
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


def centered_login(users: List[User], authenticate, user_dict_from_user) -> None:
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
            u = authenticate(user_id, ic, users)
            if u:
                st.session_state.authed_user = user_dict_from_user(u)
                st.rerun()
            else:
                st.error("Maklumat log masuk tidak sah.")


def letters_df(letters: List[Dict[str, Any]]) -> pd.DataFrame:
    if not letters:
        return pd.DataFrame()
    df = pd.DataFrame(letters)
    preferred = [
        "letter_id",
        "status",
        "tarikh_direkod",
        "owner_id",
        "tarikh_surat",
        "tarikh_cop_terima",
        "nombor_rujukan",
        "perkara",
        "maklumat_pengirim",
        "bahagian_diminitkan",
        "assigned_dept",
        "assigned_at",
        "received_at",
        "file_name",
        "uploaded_by_name",
        "drive_file_id",
    ]
    cols = [c for c in preferred if c in df.columns] + [c for c in df.columns if c not in preferred]
    return df[cols]


def page_muat_naik(user: User) -> None:
    st.markdown("## Muat Naik")
    st.markdown(
        '<div class="invictus-sub">Muat naik PDF atau imej, atau imbas dengan kamera. Tarikh Direkod ditangkap secara automatik. '
        "Semua data disimpan dalam <code>data_log.json</code> (kongsi antara tab).</div>",
        unsafe_allow_html=True,
    )

    tab_file, tab_cam = st.tabs(["Fail Muat Naik", "Imbasan Kamera"])

    with tab_file:
        uploaded = st.file_uploader("Pilih fail", type=["pdf", "png", "jpg", "jpeg"], accept_multiple_files=False)
        if uploaded:
            ensure_dirs()
            saved_name = stamp_filename(uploaded.name)
            saved_path = os.path.join(TEMP_STORAGE_DIR, saved_name)
            with open(saved_path, "wb") as f:
                f.write(uploaded.getbuffer())

            record = new_letter_record(
                uploaded_by=user,
                original_filename=uploaded.name,
                saved_path=saved_path,
                mime_type=getattr(uploaded, "type", "") or "",
            )
            letters = letters_get()
            letters.insert(0, record)
            letters_save_all(letters)
            upload_letter_to_drive_and_store(record["letter_id"], saved_path)

            st.success(f"Berjaya dimuat naik. ID Surat: **{record['letter_id']}**")

    with tab_cam:
        st.markdown(
            '<div class="invictus-sub">Arahkan kamera ke dokumen. Sistem akan cuba mengesan tepi, '
            "meratakan perspektif, dan meningkatkan kontras untuk OCR.</div>",
            unsafe_allow_html=True,
        )
        shot = st.camera_input("Kamera", label_visibility="collapsed")
        if shot is not None:
            raw_bytes = shot.getvalue()
            digest = hashlib.sha256(raw_bytes).hexdigest()
            arr = np.frombuffer(raw_bytes, dtype=np.uint8)
            bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if bgr is None:
                st.error("Tidak dapat membaca imej kamera.")
            else:
                processed_bgr, used_transform = scan_document_bgr(bgr)
                st.caption(f"Pemprosesan dokumen: {'Perspektif & ambang adaptif' if used_transform else 'Ambang adaptif (tiada segi empat tepat / fallback)'}")
                st.image(cv2.cvtColor(processed_bgr, cv2.COLOR_BGR2RGB), use_container_width=True)

                if st.button("Simpan imbasan sebagai surat baru", key="btn_save_camera_scan"):
                    last = st.session_state.get("last_camera_saved_digest")
                    if last == digest:
                        st.warning("Imbasan ini sudah direkod. Ambil gambar baharu jika perlu.")
                    else:
                        ensure_dirs()
                        saved_name = stamp_filename("imbasan_kamera.png")
                        saved_path = os.path.join(TEMP_STORAGE_DIR, saved_name)
                        cv2.imwrite(saved_path, processed_bgr)
                        record = new_letter_record(
                            uploaded_by=user,
                            original_filename="imbasan_kamera.png",
                            saved_path=saved_path,
                            mime_type="image/png",
                        )
                        letters = letters_get()
                        letters.insert(0, record)
                        letters_save_all(letters)
                        upload_letter_to_drive_and_store(record["letter_id"], saved_path)
                        st.session_state.last_camera_saved_digest = digest
                        st.success(f"Imbasan disimpan. ID Surat: **{record['letter_id']}**")
                        st.rerun()

    st.markdown("---")
    st.markdown("### Status Saya")
    letters = letters_get()
    mine = [l for l in letters if letter_owner_id(l) == user.id]
    if not mine:
        st.info("Tiada muat naik direkod untuk ID anda.")
        return
    df = pd.DataFrame(mine)
    show_cols = [
        c
        for c in ["letter_id", "status", "tarikh_direkod", "nombor_rujukan", "perkara", "file_name"]
        if c in df.columns
    ]
    st.dataframe(df[show_cols], use_container_width=True, hide_index=True)
    st.caption("Aliran status: **Baru** → **Diminitkan** → **Diterima**")


def page_admin(user: User) -> None:
    st.markdown("## Daftar & Agih")
    st.markdown(
        '<div class="invictus-sub">Surat berstatus <b>Baru</b>: OCR halaman 1 (PDF), ekstrak medan, '
        "kemaskini, agih ke Bahagian. Status menjadi <b>Diminitkan</b> selepas simpan.</div>",
        unsafe_allow_html=True,
    )

    letters = letters_get()
    baru = [l for l in letters if l.get("status") == "Baru"]
    if not baru:
        st.info("Tiada surat berstatus Baru buat masa ini.")
        return

    options = [f"{l['letter_id']} • {l.get('file_name', '')}" for l in baru]
    by_key = {f"{l['letter_id']} • {l.get('file_name', '')}": l["letter_id"] for l in baru}
    pick = st.selectbox("Pilih surat", options)
    letter_id = by_key.get(pick)
    idx = find_letter_in_list(letters, letter_id) if letter_id else None
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
                text, _ = ocr_first_page(rec["file_path"])

            letters = letters_get()
            idx2 = find_letter_in_list(letters, letter_id)

            if idx2 is None:
                st.error("Rekod hilang semasa OCR. Sila cuba lagi.")
                st.stop()

            rec = letters[idx2]
            rec["ocr_text"] = text

            extracted = extract_fields_from_text(text)
            for k, v in extracted.items():
                if not (rec.get(k) or "").strip():
                    rec[k] = v

            letters_save_all(letters)
            st.success("OCR selesai. Sila semak medan dan sahkan.")
            st.rerun()

        except Exception as e:
            st.error(f"Ralat OCR: {str(e)}")
            st.warning(
                "Sila pastikan Tesseract tersedia (Windows: Program Files path; Linux/Cloud: `tesseract` dalam PATH) "
                "atau semak fail dokumen anda."
            )

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
        letters = letters_get()
        idx3 = find_letter_in_list(letters, letter_id)
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
        rec["assigned_dept"] = bahagian.strip()
        rec["assigned_at"] = now_ts()
        rec["status"] = "Diminitkan"
        letters_save_all(letters)
        st.success("Surat telah diminitkan dan diagih.")
        st.rerun()


def page_rep(user: User) -> None:
    st.markdown("## Pengesahan")
    st.markdown(
        f'<div class="invictus-sub">Hanya surat yang diagih kepada bahagian anda '
        f"(<b>{user.dept}</b>) dipaparkan — padanan mengikut <code>assigned_dept</code> / bahagian.</div>",
        unsafe_allow_html=True,
    )

    letters = letters_get()
    if is_admin_user(user):
        diminit = [l for l in letters if l.get("status") == "Diminitkan"]
    else:
        diminit = [
            l
            for l in letters
            if l.get("status") == "Diminitkan"
            and departments_match(user.dept, letter_assigned_department(l))
        ]

    if not diminit:
        st.info("Tiada surat untuk pengesahan.")
        return

    options = [f"{l['letter_id']} • {(l.get('perkara') or '(tiada perkara)')[:56]}" for l in diminit]
    by_key = {f"{l['letter_id']} • {(l.get('perkara') or '(tiada perkara)')[:56]}": l["letter_id"] for l in diminit}
    pick = st.selectbox("Pilih surat", options)
    letter_id = by_key.get(pick)
    idx = find_letter_in_list(letters, letter_id) if letter_id else None
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
            "Assigned Dept": rec.get("assigned_dept") or rec.get("bahagian_diminitkan"),
            "Tarikh Diminitkan": rec.get("assigned_at"),
        }
    )

    if st.button("Sahkan Penerimaan", use_container_width=True):
        letters = letters_get()
        idx4 = find_letter_in_list(letters, letter_id)
        if idx4 is None:
            st.error("Rekod tidak dijumpai.")
            return
        rec = letters[idx4]
        rec["status"] = "Diterima"
        rec["received_by"] = user.id
        rec["received_at"] = now_ts()
        letters_save_all(letters)
        st.success("Penerimaan disahkan (Diterima).")
        st.rerun()


def export_excel_bytes(df: pd.DataFrame) -> bytes:
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


def page_dashboard(user: User) -> None:
    st.markdown("## Dashboard")
    st.markdown(
        '<div class="invictus-sub">Statistik ringkas, jadual induk dengan tapisan, dan eksport Excel '
        "(pandas / xlsxwriter). Kakitangan melihat data milik sendiri; Pentadbir melihat keseluruhan jabatan.</div>",
        unsafe_allow_html=True,
    )

    letters = letters_get()
    visible = letters_for_session_user(letters, user)
    df = letters_df(visible)
    if df.empty:
        st.info("Tiada rekod dalam data log untuk paparan anda.")
        return

    total_baru = int((df["status"] == "Baru").sum()) if "status" in df.columns else 0
    total_dim = int((df["status"] == "Diminitkan").sum()) if "status" in df.columns else 0
    total_dit = int((df["status"] == "Diterima").sum()) if "status" in df.columns else 0

    if is_admin_user(user):
        st.markdown("### Gambaran Jabatan")
        if "uploaded_by_name" in df.columns:
            vol = df.groupby(df["uploaded_by_name"].astype(str)).size()
            vol = vol[vol.index.astype(str).str.len() > 0].sort_values(ascending=False)
            if not vol.empty:
                st.caption("Bilangan surat mengikut pemilik rekod (muat naik)")
                st.bar_chart(vol)
        dept_series = None
        if "assigned_dept" in df.columns:
            dcol = df["assigned_dept"].fillna("").astype(str).str.strip()
            dept_series = dcol[dcol.ne("") & dcol.ne("nan")]
        if dept_series is None or dept_series.empty:
            if "bahagian_diminitkan" in df.columns:
                d2 = df["bahagian_diminitkan"].fillna("").astype(str).str.strip()
                dept_series = d2[d2.ne("") & d2.ne("nan")]
        if dept_series is not None and not dept_series.empty:
            st.caption("Surat mengikut bahagian (diminitkan)")
            st.bar_chart(dept_series.value_counts())
    else:
        st.markdown("### Kemajuan Peribadi")
        n = len(df)
        selesai = int((df["status"] == "Diterima").sum()) if "status" in df.columns else 0
        pct = (selesai / n) if n else 0.0
        st.progress(min(1.0, float(pct)))
        st.caption(
            f"Kemajuan peribadi: **{selesai}** / **{n}** surat telah **Diterima** ({pct * 100:.0f}%). "
            "Hanya rekod dengan `owner_id` anda dikira."
        )

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
        for col in ["letter_id", "nombor_rujukan", "perkara", "maklumat_pengirim", "bahagian_diminitkan", "assigned_dept", "status", "uploaded_by_name"]:
            if col in dff.columns:
                mask = mask | dff[col].astype(str).str.lower().str.contains(re.escape(ql), na=False)
        dff = dff[mask]

    st.dataframe(dff, use_container_width=True, hide_index=True)

    excel_bytes = export_excel_bytes(dff)
    export_label = "Eksport Induk (Master)" if is_admin_user(user) else "Eksport Peribadi (Excel)"
    fname = (
        f"SmartSurat_Master_{dt.datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        if is_admin_user(user)
        else f"SmartSurat_Peribadi_{user.id}_{dt.datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    )
    st.download_button(
        export_label,
        data=excel_bytes,
        file_name=fname,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )


def page_profile(user: User) -> None:
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


def page_manual() -> None:
    st.markdown("## Manual Pengguna")
    st.markdown(
        '<div class="invictus-sub">Panduan ringkas SmartSurat — Team Invictus. '
        "Kembangkan setiap bahagian untuk butiran.</div>",
        unsafe_allow_html=True,
    )

    with st.expander("📷 Kedudukan telefon untuk imbasan terbaik", expanded=True):
        st.markdown(
            """
            - Letakkan dokumen di atas permukaan rata dengan **cahaya sekata** (elak bayang teruk).
            - Arahkan kamera **tegak dari atas** supaya empat penjuru dokumen kelihatan dalam bingkai.
            - Jarak **30–45 cm** biasanya sesuai; elak terlalu dekat (blur) atau terlalu jauh (teks kecil).
            - Tunggu fokus sebelum menekan tangkap — gunakan **Imbasan Kamera** sebagai pencetus utama.
            - Selepas tangkap, sistem akan cuba **meratakan perspektif** (transformasi 4 titik) seperti skener.
            """
        )

    with st.expander("📝 Menafsir keputusan OCR", expanded=False):
        st.markdown(
            """
            - OCR mengekstrak teks daripada imej; **huruf mungkin salah** jika kualiti imej rendah atau latar bercorak.
            - Medan seperti **Tarikh**, **Rujukan**, dan **Perkara** diisi secara automatik apabila Admin menjalankan OCR —
              **semak semula** sebelum diminitkan.
            - Jika teks keluar kosong atau janggal, cuba **imbas semula** dengan pencahayaan lebih baik atau muat naik PDF asal.
            - PDF: hanya **halaman pertama** diproses untuk OCR permulaan.
            """
        )

    with st.expander("☁️ Fail dalam Google Drive", expanded=False):
        st.markdown(
            """
            - Setiap fail yang disimpan (muat naik atau imbasan kamera) dihantar ke **folder Drive** yang dikonfigurasikan
              (perkhidmatan akaun perkhidmatan / `service_account.json`).
            - ID fail Drive disimpan dalam medan **`drive_file_id`** pada rekod dalam `data_log.json`.
            - Pastikan folder Drive telah **dikongsi** dengan e-mel akaun perkhidmatan daripada fail JSON anda,
              dan tetapkan pembolehubah persekitaran `GOOGLE_DRIVE_FOLDER_ID` serta laluan `GOOGLE_SERVICE_ACCOUNT_JSON`
              jika perlu.
            - Dalam Drive, cari folder tersebut — nama fail mengikut **timestamp** dan nama asal.
            """
        )

    with st.expander("🔐 Pemilikan data & peranan", expanded=False):
        st.markdown(
            """
            - Setiap surat mempunyai **`owner_id`** (pemilik rekod).
            - **Kakitangan (Staff)** melihat dan mengeksport hanya rekod sendiri dalam Dashboard.
            - **Pentadbir (Admin)** melihat keseluruhan jabatan dan boleh menggunakan **Eksport Induk (Master)**.
            """
        )


def page_placeholder(title: str, body: str) -> None:
    st.markdown(f"## {title}")
    st.info(body)
