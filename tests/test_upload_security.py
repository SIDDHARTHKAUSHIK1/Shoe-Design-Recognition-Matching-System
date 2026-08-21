import io
import unittest
from PIL import Image
from fastapi import HTTPException

from backend.main import validate_and_sanitize_image


class TestUploadSecurityValidation(unittest.TestCase):

    def test_01_legitimate_jpeg_accepted(self):
        """Confirm valid JPEG image bytes pass validation and return sanitized filename."""
        img = Image.new("RGB", (200, 200), color=(100, 150, 200))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        contents = buf.getvalue()

        filename = validate_and_sanitize_image("shoe_photo_123.jpg", contents)
        self.assertTrue(filename.endswith(".jpg"))

    def test_02_legitimate_png_and_webp_accepted(self):
        """Confirm valid PNG and WEBP image bytes pass validation."""
        # PNG
        png_img = Image.new("RGB", (100, 100), color=(50, 50, 50))
        png_buf = io.BytesIO()
        png_img.save(png_buf, format="PNG")
        png_name = validate_and_sanitize_image("sample_shoe.png", png_buf.getvalue())
        self.assertTrue(png_name.endswith(".png"))

        # WEBP
        webp_img = Image.new("RGB", (100, 100), color=(200, 200, 200))
        webp_buf = io.BytesIO()
        webp_img.save(webp_buf, format="WEBP")
        webp_name = validate_and_sanitize_image("sample_shoe.webp", webp_buf.getvalue())
        self.assertTrue(webp_name.endswith(".webp"))

    def test_03_malicious_script_disguised_as_jpg_rejected(self):
        """Confirm non-image script bytes disguised with .jpg extension trigger HTTP 400."""
        fake_bytes = b"<?php echo 'malicious shell'; ?>"
        with self.assertRaises(HTTPException) as cm:
            validate_and_sanitize_image("shell.jpg", fake_bytes)

        self.assertEqual(cm.exception.status_code, 400)
        self.assertIn("not a valid or readable image", cm.exception.detail)

    def test_04_oversized_file_rejected(self):
        """Confirm files exceeding 10MB limit trigger HTTP 413 Payload Too Large."""
        large_bytes = b"0" * (10 * 1024 * 1024 + 1)
        with self.assertRaises(HTTPException) as cm:
            validate_and_sanitize_image("huge.jpg", large_bytes)

        self.assertEqual(cm.exception.status_code, 413)

    def test_05_path_traversal_filename_sanitized(self):
        """Confirm path components in filenames are sanitized."""
        img = Image.new("RGB", (50, 50), color=(255, 0, 0))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        
        name = validate_and_sanitize_image("../../../etc/passwd_photo.jpg", buf.getvalue())
        self.assertNotIn("/", name)
        self.assertNotIn("..", name)


if __name__ == "__main__":
    unittest.main()
