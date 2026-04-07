from __future__ import annotations

import os
from typing import Optional

# Set in environment or replace for deployment (folder must be shared with the service account email).
SERVICE_ACCOUNT_JSON = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "service_account.json")
GOOGLE_DRIVE_FOLDER_ID = os.environ.get("GOOGLE_DRIVE_FOLDER_ID", "")

_SCOPES = ("https://www.googleapis.com/auth/drive.file",)


def _build_drive_service():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    if not os.path.isfile(SERVICE_ACCOUNT_JSON):
        return None
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_JSON,
        scopes=_SCOPES,
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def upload_to_drive(file_path: str, folder_id: Optional[str] = None) -> str:
    """
    Upload a local file to Google Drive using a service account JSON key.
    Returns the Drive file id, or an empty string if upload is skipped or fails.
    """
    fid = (folder_id if folder_id is not None else GOOGLE_DRIVE_FOLDER_ID) or ""
    if not fid or not os.path.isfile(file_path):
        return ""

    service = _build_drive_service()
    if service is None:
        return ""

    from googleapiclient.http import MediaFileUpload

    name = os.path.basename(file_path)
    media = MediaFileUpload(file_path, resumable=True)
    body = {"name": name, "parents": [fid]}
    try:
        created = (
            service.files()
            .create(body=body, media_body=media, fields="id", supportsAllDrives=True)
            .execute()
        )
        return str(created.get("id", "") or "")
    except Exception:
        return ""


def upload_letter_to_drive_and_store(letter_id: str, file_path: str, folder_id: Optional[str] = None) -> str:
    """
    Upload file to Drive and persist drive_file_id on the letter row in data_log.json.
    Returns drive file id or empty string.
    """
    drive_id = upload_to_drive(file_path, folder_id=folder_id)
    if drive_id:
        from storage_service import patch_letter_drive_id

        patch_letter_drive_id(letter_id, drive_id)
    return drive_id
