from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict


DEPT_CANON = ["Jalan", "Bangunan", "Korporat", "Strategik"]


@dataclass(frozen=True)
class User:
    id: str
    ic: str
    name: str
    role: str
    dept: str
    email: str = ""
    jawatan: str = ""
    gred: str = ""


@dataclass
class Letter:
    letter_id: str
    tarikh_direkod: str
    status: str
    uploaded_by: str
    uploaded_by_name: str
    owner_id: str
    file_name: str
    file_path: str
    mime_type: str
    ocr_text: str = ""
    tarikh_surat: str = ""
    tarikh_terima: str = ""
    tarikh_daftar: str = ""
    tarikh_cop_terima: str = ""  # legacy alias (kept for older records / UI)
    perkara: str = ""
    nombor_rujukan: str = ""
    maklumat_pengirim: str = ""
    bahagian_diminitkan: str = ""
    assigned_dept: str = ""
    assigned_at: str = ""
    received_by: str = ""
    received_at: str = ""
    drive_file_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "letter_id": self.letter_id,
            "tarikh_direkod": self.tarikh_direkod,
            "status": self.status,
            "uploaded_by": self.uploaded_by,
            "uploaded_by_name": self.uploaded_by_name,
            "owner_id": self.owner_id,
            "file_name": self.file_name,
            "file_path": self.file_path,
            "mime_type": self.mime_type,
            "ocr_text": self.ocr_text,
            "tarikh_surat": self.tarikh_surat,
            "tarikh_terima": self.tarikh_terima,
            "tarikh_daftar": self.tarikh_daftar,
            "tarikh_cop_terima": self.tarikh_cop_terima,
            "perkara": self.perkara,
            "nombor_rujukan": self.nombor_rujukan,
            "maklumat_pengirim": self.maklumat_pengirim,
            "bahagian_diminitkan": self.bahagian_diminitkan,
            "assigned_dept": self.assigned_dept,
            "assigned_at": self.assigned_at,
            "received_by": self.received_by,
            "received_at": self.received_at,
            "drive_file_id": self.drive_file_id,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> Letter:
        uploaded_by = str(d.get("uploaded_by", ""))
        owner_id = str(d.get("owner_id", "") or uploaded_by)
        tarikh_terima = str(d.get("tarikh_terima", "") or d.get("tarikh_cop_terima", ""))
        tarikh_daftar = str(d.get("tarikh_daftar", "") or "")
        return cls(
            letter_id=str(d.get("letter_id", "")),
            tarikh_direkod=str(d.get("tarikh_direkod", "")),
            status=str(d.get("status", "")),
            uploaded_by=uploaded_by,
            uploaded_by_name=str(d.get("uploaded_by_name", "")),
            owner_id=owner_id,
            file_name=str(d.get("file_name", "")),
            file_path=str(d.get("file_path", "")),
            mime_type=str(d.get("mime_type", "")),
            ocr_text=str(d.get("ocr_text", "")),
            tarikh_surat=str(d.get("tarikh_surat", "")),
            tarikh_terima=tarikh_terima,
            tarikh_daftar=tarikh_daftar,
            tarikh_cop_terima=str(d.get("tarikh_cop_terima", "") or tarikh_terima),
            perkara=str(d.get("perkara", "")),
            nombor_rujukan=str(d.get("nombor_rujukan", "")),
            maklumat_pengirim=str(d.get("maklumat_pengirim", "")),
            bahagian_diminitkan=str(d.get("bahagian_diminitkan", "")),
            assigned_dept=str(d.get("assigned_dept", "") or d.get("bahagian_diminitkan", "")),
            assigned_at=str(d.get("assigned_at", "")),
            received_by=str(d.get("received_by", "")),
            received_at=str(d.get("received_at", "")),
            drive_file_id=str(d.get("drive_file_id", "")),
        )


def normalize_dept_label(s: str) -> str:
    """Normalize department strings for comparison (handles 'Bahagian Jalan' vs 'Jalan')."""
    t = re.sub(r"\s+", " ", (s or "").strip().lower())
    for prefix in ("bahagian ", "jabatan ", "bhg "):
        if t.startswith(prefix):
            t = t[len(prefix) :].strip()
    return t


def departments_match(user_dept: str, letter_assigned: str) -> bool:
    """True when the user's department matches the letter's assigned department (case-insensitive, prefix-tolerant)."""
    a = normalize_dept_label(user_dept)
    b = normalize_dept_label(letter_assigned)
    if not a or not b:
        return False
    return a == b
