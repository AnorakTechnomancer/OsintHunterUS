import unittest
from app.modules.us import normalize_ein, normalize_us_zip
from app.models import detect_type, normalize
from app.modules.us_api import find_sec_ticker, census_record, SECCompanyAPI, USASpendingRecipientAPI, CensusZipAPI, is_ticker_like, recipient_matches

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
        self.assertEqual(detect_type("AAPL"), "organization")
        self.assertEqual(detect_type("Boeing Inc"), "organization")
    def test_normalize(self):
        self.assertEqual(normalize("ein", "123456789"), "12-3456789")
        self.assertEqual(normalize("zip", " 63101-1234 "), "63101-1234")

class USAPITest(unittest.TestCase):
    def test_sec_exact_matching(self):
        rows = {"0": {"cik_str": 12345, "ticker": "EXM", "title": "Example Corp"}}
        self.assertEqual(find_sec_ticker(rows, "EXM")["cik_str"], 12345)
        self.assertEqual(find_sec_ticker(rows, "example corp")["ticker"], "EXM")
        self.assertIsNone(find_sec_ticker(rows, "Example"))
    def test_recipient_filtering(self):
        self.assertTrue(is_ticker_like("AAPL"))
        self.assertFalse(is_ticker_like("Boeing Inc"))
        rows = [{"recipient_name": "AAAPLIANCE SERVICES"}, {"recipient_name": "AAPL"}, {"recipient_name": "AAPL DRIVING SCHOOL"}]
        self.assertEqual([r["name"] for r in recipient_matches("AAPL", rows)], ["AAPL"])
        self.assertEqual(recipient_matches("Apple Inc", rows), [])

    def test_census_record(self):
        self.assertEqual(census_record([["NAME", "B01003_001E"], ["ZCTA5 63101", "1000"]])["B01003_001E"], "1000")
        self.assertIsNone(census_record([]))
    def test_balanced_module_flags(self):
        self.assertFalse(SECCompanyAPI.deep)
        self.assertFalse(USASpendingRecipientAPI.deep)
        self.assertFalse(CensusZipAPI.deep)

if __name__ == "__main__":
    unittest.main()
