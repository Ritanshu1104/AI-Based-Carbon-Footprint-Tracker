"""Local electricity-bill OCR with quantity extraction and validation signals."""

import hashlib
import io
import re
import shutil


class BillOcrService:
    MAX_BYTES = 8 * 1024 * 1024
    ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}

    @property
    def capability(self):
        try:
            import PIL  # noqa: F401
            import pytesseract  # noqa: F401
            python_packages = True
        except ImportError:
            python_packages = False
        executable = shutil.which("tesseract")
        return {
            "available": bool(python_packages and executable),
            "python_packages": python_packages,
            "tesseract_executable": executable,
            "processing": "local-only",
            "supported_images": sorted(self.ALLOWED_EXTENSIONS),
        }

    def extract(self, content, filename):
        extension = "." + str(filename or "").lower().rsplit(".", 1)[-1]
        if extension not in self.ALLOWED_EXTENSIONS:
            raise ValueError("Upload a PNG, JPEG, TIFF, BMP, or WebP image")
        if not content or len(content) > self.MAX_BYTES:
            raise ValueError("Bill image must be between 1 byte and 8 MB")
        if not self.capability["available"]:
            raise ValueError("Local OCR is unavailable; install the Tesseract 5 executable")
        from PIL import Image, ImageOps
        import pytesseract

        try:
            image = Image.open(io.BytesIO(content))
            image.verify()
            image = Image.open(io.BytesIO(content)).convert("L")
            image = ImageOps.autocontrast(image)
        except Exception as error:
            raise ValueError("The uploaded file is not a readable image") from error
        text = pytesseract.image_to_string(image, config="--oem 1 --psm 6", lang="eng")
        result = self.extract_from_text(text)
        result.update({
            "method": "Tesseract 5 local OCR", "sha256": hashlib.sha256(content).hexdigest(),
            "filename": str(filename), "raw_text_excerpt": text[:1200],
        })
        return result

    def extract_from_text(self, text):
        normalized = " ".join(str(text or "").split())
        candidates = []
        patterns = (
            (r"(?:units?\s+consumed|energy\s+consumed|consumption|total\s+units?)\s*[:=-]?\s*(\d+(?:\.\d+)?)\s*(?:kwh|units?)?", 0.92),
            (r"(\d+(?:\.\d+)?)\s*kwh\b", 0.82),
        )
        for pattern, confidence in patterns:
            for match in re.finditer(pattern, normalized, re.IGNORECASE):
                value = float(match.group(1))
                if 0 < value < 1_000_000:
                    candidates.append({"kwh": value, "confidence": confidence,
                                       "evidence_text": match.group(0)})

        current = self._reading(normalized, r"current\s+(?:meter\s+)?reading")
        previous = self._reading(normalized, r"previous\s+(?:meter\s+)?reading")
        if current is not None and previous is not None and current >= previous:
            candidates.append({
                "kwh": round(current - previous, 3), "confidence": 0.88,
                "evidence_text": "difference between current and previous meter readings",
            })
        unique = {}
        for candidate in candidates:
            key = candidate["kwh"]
            if key not in unique or unique[key]["confidence"] < candidate["confidence"]:
                unique[key] = candidate
        ranked = sorted(unique.values(), key=lambda item: -item["confidence"])
        return {
            "status": "quantity-found" if ranked else "review-required",
            "recommended_kwh": ranked[0]["kwh"] if ranked else None,
            "confidence": ranked[0]["confidence"] if ranked else 0.0,
            "candidates": ranked[:8],
            "review_required": len(ranked) != 1 or (ranked and ranked[0]["confidence"] < 0.9),
        }

    @staticmethod
    def _reading(text, label_pattern):
        match = re.search(label_pattern + r"\s*[:=-]?\s*(\d+(?:\.\d+)?)", text, re.IGNORECASE)
        return float(match.group(1)) if match else None
