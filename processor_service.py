from __future__ import annotations

import io
import os
import platform
import re
import shutil
from typing import Dict, Tuple

import numpy as np
import pytesseract
from PIL import Image

# --- SmartSurat • Team Invictus (JKR) — Cloud-Friendly Tesseract path ---
if platform.system() == "Windows":
    TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
else:
    TESSERACT_CMD = shutil.which("tesseract")

if TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD


DATE_RE = re.compile(r"\b(\d{2}/\d{2}/\d{4})\b")
RUJ_RE = re.compile(r"(?:Ruj\.?\s*Kami\s*[:\-]\s*|Ruj(?:ukan)?\s*[:\-]\s*)(.+)", re.IGNORECASE)
PERKARA_RE = re.compile(r"(?:Perkara\s*[:\-]\s*)(.+)", re.IGNORECASE)


def clean_line(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def extract_fields_from_text(text: str) -> Dict[str, str]:
    lines = [clean_line(l) for l in (text or "").splitlines() if clean_line(l)]
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
                nombor_rujukan = clean_line(m.group(1))
        if not perkara:
            m = PERKARA_RE.search(l)
            if m:
                perkara = clean_line(m.group(1))

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


def _order_points(pts: np.ndarray) -> np.ndarray:
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect


def _four_point_transform(image: np.ndarray, pts: np.ndarray) -> np.ndarray:
    import cv2

    rect = _order_points(pts)
    (tl, tr, br, bl) = rect
    width_a = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
    width_b = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
    max_width = max(int(width_a), int(width_b))
    height_a = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
    height_b = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
    max_height = max(int(height_a), int(height_b))
    dst = np.array(
        [[0, 0], [max_width - 1, 0], [max_width - 1, max_height - 1], [0, max_height - 1]],
        dtype="float32",
    )
    m = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(image, m, (max_width, max_height))


def _find_document_quad(gray: np.ndarray) -> np.ndarray | None:
    import cv2

    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edged = cv2.Canny(blurred, 75, 200)
    cnts, _ = cv2.findContours(edged.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cnts = sorted(cnts, key=cv2.contourArea, reverse=True)[:8]
    for c in cnts:
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        if len(approx) == 4:
            return approx.reshape(4, 2)
    return None


def preprocess_for_ocr_bgr(bgr: np.ndarray, *, apply_scale: bool = True) -> np.ndarray:
    """
    Grayscale → optional 2× rescale (DPI) → bilateral denoise → adaptive threshold.
    Returns 3-channel BGR for compatibility with PIL / file writers.
    """
    import cv2

    if bgr is None or bgr.size == 0:
        raise ValueError("Empty image")
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    if apply_scale:
        h, w = gray.shape[:2]
        gray = cv2.resize(gray, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)
    filtered = cv2.bilateralFilter(gray, 9, 75, 75)
    th = cv2.adaptiveThreshold(
        filtered,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        11,
    )
    return cv2.cvtColor(th, cv2.COLOR_GRAY2BGR)


def scan_document_bgr(bgr: np.ndarray) -> Tuple[np.ndarray, bool]:
    """
    4-point perspective flatten (when a document quad is found), then OCR preprocessing.
    Returns (processed BGR, perspective_used).
    """
    import cv2

    if bgr is None or bgr.size == 0:
        raise ValueError("Empty image")

    original = bgr.copy()
    try:
        h, w = bgr.shape[:2]
        if h < 20 or w < 20:
            return preprocess_for_ocr_bgr(original, apply_scale=True), False

        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        quad = _find_document_quad(gray)

        if quad is None:
            source = bgr
            used_transform = False
        else:
            source = _four_point_transform(bgr, quad.astype("float32"))
            used_transform = True

        out = preprocess_for_ocr_bgr(source, apply_scale=True)
        return out, used_transform
    except Exception:
        try:
            return preprocess_for_ocr_bgr(original, apply_scale=True), False
        except Exception:
            return original, False


def pil_from_bgr(bgr: np.ndarray) -> Image.Image:
    import cv2

    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)


def _imread_bgr(path: str) -> np.ndarray | None:
    import cv2

    try:
        data = np.fromfile(path, dtype=np.uint8)
        return cv2.imdecode(data, cv2.IMREAD_COLOR)
    except Exception:
        return cv2.imread(path)


def ocr_first_page(file_path: str) -> Tuple[str, str]:
    """OCR first page of PDF or image; preprocessing before Tesseract."""
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
            rgb = np.array(img.convert("RGB"))
            import cv2

            bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
            proc = preprocess_for_ocr_bgr(bgr, apply_scale=False)
            text = pytesseract.image_to_string(pil_from_bgr(proc))
            return text, "image"

    bgr = _imread_bgr(file_path)
    if bgr is None:
        img = Image.open(file_path).convert("RGB")
        rgb = np.array(img)
        import cv2

        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

    proc, _ = scan_document_bgr(bgr)
    text = pytesseract.image_to_string(pil_from_bgr(proc))
    return text, "image"


def ocr_pil_image(img: Image.Image) -> str:
    import cv2

    rgb = np.array(img.convert("RGB"))
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    proc = preprocess_for_ocr_bgr(bgr, apply_scale=True)
    return pytesseract.image_to_string(pil_from_bgr(proc))
