import unittest
from app.modules.us import normalize_ein, normalize_us_zip
from app.models import detect_type, normalize
from app.modules.us_api import find_sec_ticker, census_record, SECCompanyAPI, USASpendingRecipientAPI, CensusZipAPI, is_ticker_like, recipient_matches, company_core

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

class PeopleWebSearchTest(unittest.IsolatedAsyncioTestCase):
    async def test_location_queries_and_no_automatic_identity_link(self):
        from types import SimpleNamespace
        from unittest.mock import AsyncMock, Mock, patch
        from app.modules.websearch import WebSearch
        ctx = SimpleNamespace(
            value="Jane Example",
            entity={"id": "person:jane example",
                    "attrs": {"Search city": "Chicago", "Search state": "Illinois"}},
            http=object(), case_id=1, job=SimpleNamespace(emit=Mock()),
            found=0, enriched=False, message="",
            add=Mock(side_effect=AssertionError("unverified profiles must not auto-link")),
        )
        rows = [("Jane Example — professional profile",
                 "https://www.linkedin.com/in/jane-example",
                 "Jane Example in Chicago, Illinois")]
        with patch("app.modules.websearch.settings.key", return_value=None), \
             patch("app.modules.websearch.free_search", new_callable=AsyncMock) as search, \
             patch("app.modules.websearch.db.update_attrs", return_value=None) as update:
            search.return_value = (rows, ["DuckDuckGo"], None)
            await WebSearch().run(ctx)
        queries = search.call_args.args[1]
        self.assertTrue(any("Chicago Illinois" in q for q in queries))
        self.assertIn('"Jane Example"', queries)
        ctx.add.assert_not_called()
        hits = update.call_args.args[2]["_web"]
        self.assertEqual(hits[0]["location_evidence"], "location mentioned in search result")
        self.assertEqual(hits[0]["identity_status"], "unverified search result")


class USAPITest(unittest.TestCase):
    def test_sec_exact_matching(self):
        rows = {"0": {"cik_str": 12345, "ticker": "EXM", "title": "Example Corp"}}
        self.assertEqual(find_sec_ticker(rows, "EXM")["cik_str"], 12345)
        self.assertEqual(find_sec_ticker(rows, "example corp")["ticker"], "EXM")
        self.assertEqual(find_sec_ticker(rows, "Example")["ticker"], "EXM")
        self.assertIsNone(find_sec_ticker(rows, "Example Holdings"))
    def test_public_profile_candidate_matching(self):
        from app.modules.us_people_candidates import name_matches, location_matches
        self.assertTrue(name_matches("Nathaniel Miller", "Nathaniel E. Miller"))
        self.assertFalse(name_matches("Nathaniel Miller", "Nathan R. Miller"))
        self.assertEqual(location_matches("Granite City", "IL", "", "Granite City, IL"),
                         "self-reported location overlap")
        self.assertEqual(location_matches("Granite City", "IL", "", "Austin, TX"),
                         "not established")

    def test_academic_sources_are_opt_in(self):
        from app.modules.people import Academic, Wikidata
        self.assertTrue(Academic.deep)
        self.assertTrue(Wikidata.deep)

    def test_people_name_matching_not_identity(self):
        from app.modules.people import same_name
        self.assertTrue(same_name("Nathaniel Miller", "Nathaniel Miller"))
        # Name equality is a search candidate, never proof of identity.
        self.assertTrue(same_name("Nathaniel E. Miller", "Nathaniel Miller"))

    def test_sec_legal_name_variants(self):
        rows = {"0": {"cik_str": 12927, "ticker": "BA", "title": "THE BOEING COMPANY"},
                "1": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}}
        self.assertEqual(company_core("Boeing Inc"), ("boeing",))
        self.assertEqual(find_sec_ticker(rows, "Boeing Inc")["ticker"], "BA")
        self.assertEqual(find_sec_ticker(rows, "The Boeing Company")["ticker"], "BA")
        self.assertEqual(find_sec_ticker(rows, "BA")["cik_str"], 12927)
        self.assertIsNone(find_sec_ticker(rows, "Boeing Aerospace"))
        ambiguous = {"0": {"ticker": "X", "title": "Example Inc"},
                     "1": {"ticker": "Y", "title": "The Example Company"}}
        self.assertIsNone(find_sec_ticker(ambiguous, "Example LLC"))

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
