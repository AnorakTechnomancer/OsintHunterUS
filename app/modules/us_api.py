"""Live US government APIs. Bounded lookups; ambiguous name matches remain leads."""
import re

from .base import Module, Skip, register

SEC_HEADERS = {"Accept": "application/json"}
SEC_TICKERS = "https://www.sec.gov/files/company_tickers.json"
USA_AUTOCOMPLETE = "https://api.usaspending.gov/api/v2/autocomplete/recipient/"
CENSUS_ACS = "https://api.census.gov/data/2024/acs/acs5"

def exact_company_match(query, candidate):
    def clean(s):
        return re.sub(r"[^a-z0-9]", "", (s or "").lower())
    return bool(clean(query)) and clean(query) == clean(candidate)

def find_sec_ticker(rows, name):
    if not isinstance(rows, dict):
        return None
    for row in rows.values():
        if isinstance(row, dict) and (exact_company_match(name, row.get("title")) or
                                      name.upper() == str(row.get("ticker", "")).upper()):
            return row
    return None

def is_ticker_like(value):
    return bool(re.fullmatch(r"[A-Z]{2,5}(?:[.-][A-Z])?", value.strip()))

def recipient_matches(query, rows):
    """Only return exact-name matches; autocomplete prefixes are not identities."""
    matches = []
    for row in rows[:10]:
        if not isinstance(row, dict):
            continue
        name = row.get("recipient_name") or row.get("name")
        if name and exact_company_match(query, name):
            matches.append({"name": name, "uei": row.get("recipient_uei") or row.get("uei"),
                            "match": "exact name; identity unverified"})
    return matches

def census_record(rows):
    if not isinstance(rows, list) or len(rows) < 2 or not isinstance(rows[0], list):
        return None
    if len(rows[0]) != len(rows[1]):
        return None
    return dict(zip(rows[0], rows[1]))

async def fetch_json(ctx, url, *, method="GET", params=None, json=None, headers=None):
    """Small bounded request; no retries on throttling, no arbitrary URLs."""
    try:
        if method == "POST":
            response = await ctx.http.post(url, json=json, headers=headers, timeout=15)
        else:
            response = await ctx.http.get(url, params=params, headers=headers, timeout=15)
        if response.status_code in (403, 429):
            ctx.message = f"Source throttled or denied access (HTTP {response.status_code})"
            return None
        if response.status_code != 200:
            ctx.message = f"Source returned HTTP {response.status_code}"
            return None
        return response.json()
    except Exception as exc:
        # Do not expose API credentials or entire request URLs in user-visible errors.
        ctx.message = f"Source unavailable ({type(exc).__name__})"
        return None

@register
class SECCompanyAPI(Module):
    name = "us_sec_api"
    title = "SEC EDGAR live filings"
    description = "Lookup exact company name or ticker; retrieve CIK and recent filings. Exact matches only."
    inputs = ("organization",)
    sources = ("SEC EDGAR API",)
    timeout = 45
    deep = False

    async def run(self, ctx):
        agent = (ctx.settings.get("sec_user_agent") or "").strip()
        if not agent or "@" not in agent:
            raise Skip("Set SEC contact User-Agent in Settings (organization contact email required).")
        headers = {**SEC_HEADERS, "User-Agent": agent}
        rows = await fetch_json(ctx, SEC_TICKERS, headers=headers)
        if rows is None:
            ctx.enrich({"SEC status": "Automated SEC lookup unavailable; no company identity verified.",
                        "_links": [["SEC EDGAR company search", "https://www.sec.gov/edgar/search/"],
                                   ["SEC company/ticker search", "https://www.sec.gov/edgar/browse/"]]})
            ctx.message = "SEC denied or throttled automated access. Check contact User-Agent and network; use SEC search links manually."
            return
        company = find_sec_ticker(rows, ctx.value)
        if not company:
            ctx.message = ctx.message or "No exact SEC company/ticker match; try the company's ticker."
            return
        cik = int(company["cik_str"])
        url = f"https://data.sec.gov/submissions/CIK{cik:010d}.json"
        data = await fetch_json(ctx, url, headers=headers)
        if not isinstance(data, dict):
            return
        filings = (data.get("filings") or {}).get("recent") or {}
        forms, accessions, dates = (filings.get(k) or [] for k in ("form", "accessionNumber", "filingDate"))
        recent = [{"form": f, "filed": d, "accession": a}
                  for f, a, d in list(zip(forms, accessions, dates))[:12]]
        ctx.enrich({"SEC CIK": str(cik), "SEC ticker": company.get("ticker"),
                    "SEC filing name": data.get("name"), "SEC recent filings": recent,
                    "SEC evidence": url, "SEC matching": "Exact name or ticker; verify legal entity",
                    "_links": [["SEC filings", f"https://www.sec.gov/edgar/browse/?CIK={cik}"],
                               ["SEC submissions JSON", url]]})
        ctx.found += 1

@register
class USASpendingRecipientAPI(Module):
    name = "us_usaspending_api"
    title = "USAspending recipient lookup"
    description = "Find potential federal award recipients; results are unverified leads, not confirmed identity."
    inputs = ("organization",)
    sources = ("USAspending API",)
    timeout = 30
    deep = False

    async def run(self, ctx):
        query = ctx.value.strip()
        if len(query) < 3:
            raise Skip("Enter at least three characters.")
        if is_ticker_like(query):
            raise Skip("Ticker-like input: USAspending searches recipient names, not stock tickers. Search the full legal company name.")
        data = await fetch_json(ctx, USA_AUTOCOMPLETE, method="POST",
                                json={"search_text": query, "limit": 10})
        if not isinstance(data, dict):
            return
        rows = data.get("results") or []
        leads = recipient_matches(query, rows)
        if not leads:
            ctx.message = "No exact recipient-name matches among the first 10 autocomplete results; broader matches intentionally hidden."
            return
        ctx.enrich({"USAspending candidate recipients": leads,
                    "USAspending source": USA_AUTOCOMPLETE,
                    "_links": [["USAspending recipient search", "https://www.usaspending.gov/search"]]})
        ctx.found += len(leads)
        ctx.message = f"{len(leads)} exact-name candidate(s); verify UEI before linking."

@register
class CensusZipAPI(Module):
    name = "us_census_zip_api"
    title = "Census ACS ZIP geography"
    description = "2024 ACS 5-year ZIP tabulation area population and median household income; not an address lookup."
    inputs = ("zip",)
    sources = ("US Census ACS API",)
    timeout = 30

    async def run(self, ctx):
        zipcode = ctx.value.strip()[:5]
        if not re.fullmatch(r"\d{5}", zipcode):
            raise Skip("Expected a US five-digit ZIP code.")
        data = await fetch_json(ctx, CENSUS_ACS,
                                params={"get": "NAME,B01003_001E,B19013_001E",
                                        "for": f"zip code tabulation area:{zipcode}"})
        row = census_record(data)
        if not row:
            ctx.message = ctx.message or "No matching Census ZCTA; not all USPS ZIPs have a ZCTA."
            return
        ctx.enrich({"Census geography": row.get("NAME"), "Census ACS vintage": "2024 ACS 5-year",
                    "Census population estimate": row.get("B01003_001E"),
                    "Census median household income": row.get("B19013_001E"),
                    "Census evidence": str(CENSUS_ACS),
                    "Census caveat": "ZCTA approximates a ZIP geography; figures are estimates, not personal data."})
        ctx.found += 1
