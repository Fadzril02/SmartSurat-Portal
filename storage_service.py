from __future__ import annotations

import datetime as dt
import json
import os
import re
import tempfile
import uuid
from typing import Any, Dict, List, Optional

from models import User


def is_admin_user(user: User) -> bool:
    return (user.role or "").strip().lower() == "admin"


def is_staff_user(user: User) -> bool:
    return (user.role or "").strip().lower() == "staff"


def letter_owner_id(rec: Dict[str, Any]) -> str:
    """Stable owner key for filtering (legacy rows without owner_id use uploaded_by)."""
    v = rec.get("owner_id")
    if v is not None and str(v).strip():
        return str(v).strip()
    return str(rec.get("uploaded_by", "") or "").strip()


def letters_for_session_user(letters: List[Dict[str, Any]], user: User) -> List[Dict[str, Any]]:
    """Staff: own records only. Admin: all records."""
    if is_admin_user(user):
        return list(letters)
    return [r for r in letters if letter_owner_id(r) == user.id]


TEMP_STORAGE_DIR = "temp_storage"
DATA_LOG_PATH = "data_log.json"


def ensure_dirs() -> None:
    os.makedirs(TEMP_STORAGE_DIR, exist_ok=True)


def load_users() -> List[User]:
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


def authenticate(user_id: str, ic: str, users: List[User]) -> Optional[User]:
    user_id = (user_id or "").strip()
    ic = (ic or "").strip()
    for u in users:
        if u.id == user_id and u.ic == ic:
            return u
    return None


def letters_read_from_disk() -> List[Dict[str, Any]]:
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
            return list(data["letters"])
        return []
    except (json.JSONDecodeError, OSError):
        return []


def letters_write_to_disk(letters: List[Dict[str, Any]]) -> None:
    """Atomic replace so other tabs/processes see a consistent file."""
    ensure_dirs()
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


def letters_get() -> List[Dict[str, Any]]:
    """Always read fresh from disk for multi-tab consistency."""
    return letters_read_from_disk()


def letters_save_all(letters: List[Dict[str, Any]]) -> None:
    letters_write_to_disk(letters)


def patch_letter_drive_id(letter_id: str, drive_file_id: str) -> bool:
    letters = letters_get()
    idx = find_letter_in_list(letters, letter_id)
    if idx is None:
        return False
    letters[idx]["drive_file_id"] = drive_file_id
    letters_save_all(letters)
    return True


def find_letter_in_list(letters: List[Dict[str, Any]], letter_id: str) -> Optional[int]:
    for i, rec in enumerate(letters):
        if rec.get("letter_id") == letter_id:
            return i
    return None


def now_ts() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def stamp_filename(original: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_\-\.]+", "_", original or "fail")
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{ts}_{safe}"


def new_letter_record(
    uploaded_by: User,
    original_filename: str,
    saved_path: str,
    mime_type: str,
) -> Dict[str, Any]:
    return {
        "letter_id": str(uuid.uuid4())[:8].upper(),
        "tarikh_direkod": now_ts(),
        "status": "Baru",
        "uploaded_by": uploaded_by.id,
        "uploaded_by_name": uploaded_by.name,
        "owner_id": uploaded_by.id,
        "file_name": original_filename,
        "file_path": saved_path,
        "mime_type": mime_type,
        "drive_file_id": "",
        "ocr_text": "",
        "tarikh_surat": "",
        "tarikh_cop_terima": "",
        "perkara": "",
        "nombor_rujukan": "",
        "maklumat_pengirim": "",
        "bahagian_diminitkan": "",
        "assigned_dept": "",
        "assigned_at": "",
        "received_by": "",
        "received_at": "",
    }


def letter_assigned_department(letter: Dict[str, Any]) -> str:
    """Department key used for Wakil filtering (new field + legacy)."""
    v = letter.get("assigned_dept")
    if v is not None and str(v).strip():
        return str(v).strip()
    return str(letter.get("bahagian_diminitkan", "") or "").strip()


def user_dict_from_user(u: User) -> Dict[str, str]:
    return {
        "id": u.id,
        "ic": u.ic,
        "name": u.name,
        "role": u.role,
        "dept": u.dept,
        "email": u.email,
        "jawatan": u.jawatan,
        "gred": u.gred,
    }
