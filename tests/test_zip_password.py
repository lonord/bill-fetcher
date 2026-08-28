import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from parsers import zip_password
from parsers.zip_password import (
    PasswordNotFoundError,
    recover_numeric_zip_password,
)


class NumericZipPasswordTest(unittest.TestCase):
    def setUp(self):
        seven_zip = shutil.which("7z")
        if not seven_zip:
            self.skipTest("7z is required only to build the encrypted test fixture")

        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.archive = root / "fixture.zip"
        payload = root / "payload.txt"
        payload.write_text("test payload", encoding="utf-8")
        subprocess.run(
            [
                seven_zip,
                "a",
                "-tzip",
                "-mem=ZipCrypto",
                "-p000042",
                self.archive.name,
                payload.name,
            ],
            cwd=root,
            check=True,
            capture_output=True,
        )

    def tearDown(self):
        if hasattr(self, "temp_dir"):
            self.temp_dir.cleanup()

    def test_recovers_six_digit_password_with_leading_zeroes(self):
        result = recover_numeric_zip_password(self.archive, stop=100)

        self.assertEqual(result.password, b"000042")
        self.assertEqual(result.attempts, 43)

    def test_raises_when_password_is_outside_search_range(self):
        with self.assertRaises(PasswordNotFoundError):
            recover_numeric_zip_password(self.archive, stop=42)

    def test_python_fallback_recovers_password(self):
        with patch.object(zip_password, "_NATIVE_HELPER", Path("/does/not/exist")):
            result = recover_numeric_zip_password(self.archive, stop=100)

        self.assertEqual(result.password, b"000042")


if __name__ == "__main__":
    unittest.main()
