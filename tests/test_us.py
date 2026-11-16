import unittest
from app.modules.us import normalize_ein, normalize_us_zip
from app.models import detect_type, normalize

class USInputsTest(unittest.TestCase):
    def test_zip(self):
        self.assertEqual(normalize_us_zip("63101"), "63101")
        self.assertEqual(normalize_us_zip("63101-1234"), "63101-1234")
        self.assertIsNone(normalize_us_zip("1234"))
    def test_ein(self):
        self.assertEqual(normalize_ein("12-3456789"), "12-3456789")
        self.assertEqual(normalize_ein("123456789"), "12-3456789")
        self.assertIsNone(normalize_ein("12345678"))
    def test_detection(self):
        self.assertEqual(detect_type("63101"), "zip")
        self.assertEqual(detect_type("12-3456789"), "ein")
        self.assertEqual(detect_type("user@example.com"), "email")
        self.assertEqual(detect_type("314-555-0123"), "phone")
        self.assertEqual(detect_type("example.com"), "domain")
        self.assertEqual(detect_type("203.0.113.9"), "ip")
        self.assertEqual(detect_type("Jane Example"), "person")
    def test_normalize(self):
        self.assertEqual(normalize("ein", "123456789"), "12-3456789")
        self.assertEqual(normalize("zip", " 63101-1234 "), "63101-1234")

if __name__ == "__main__":
    unittest.main()
