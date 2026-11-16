"""US-focused public-record research launchpads and locally verifiable identifiers.

These modules do not scrape people-search aggregators, pull private records,
or equate matching names with matching identities. Links are research leads.
"""
import re
from urllib.parse import quote, urlencode
from .base import Module, register

STATE_CODES = set("""AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC""".split())

def normalize_us_zip(value: str) -> str | None:
    value = (value or "").strip()
    return value if re.fullmatch(r"\d{5}(?:-\d{4})?", value) else None

def normalize_ein(value: str) -> str | None:
    value = (value or "").strip()
    m = re.fullmatch(r"(\d{2})-?(\d{7})", value)
    return f"{m.group(1)}-{m.group(2)}" if m else None

def research_link(label: str, url: str, fields=None):
    return [label, url] if fields is None else [label, url, fields]

def search_url(query: str) -> str:
    return "https://www.google.com/search?" + urlencode({"q": query})

@register
class USBusinessSources(Module):
    name = "us_business_sources"
    title = "US business and nonprofit records"
    description = "Research launchpads for SEC filings, IRS nonprofit records, federal contractors, trademarks, and state registries. Manual verification required."
    inputs = ("organization",)
    sources = ("SEC EDGAR", "IRS", "SAM.gov", "USPTO", "State registries")

    async def run(self, ctx):
        name = ctx.value.strip()
        if not name:
            return
        links = [
            research_link("SEC EDGAR · company filings", "https://www.sec.gov/edgar/search/", [["Company name", name]]),
            research_link("IRS · tax exempt organization search", "https://apps.irs.gov/app/eos/", [["Organization name", name]]),
            research_link("SAM.gov · entity information", "https://sam.gov/search/?index=entity", [["Entity name", name]]),
            research_link("USAspending · federal awards", "https://www.usaspending.gov/search", [["Recipient name", name]]),
            research_link("USPTO · trademark search", "https://tmsearch.uspto.gov/", [["Owner / mark", name]]),
            research_link("State business registries · locate state SOS", search_url(f'"{name}" secretary of state business entity search')),
        ]
        ctx.enrich({"US public-record research": "Unverified research leads; confirm identifiers before associating records.",
                    "_links": links})
        ctx.found += len(links)

@register
class USElectionSources(Module):
    name = "us_election_sources"
    title = "US federal election and lobbying records"
    description = "Manual lookups of publicly available FEC and Senate lobbying filings; name matches alone do not confirm identity."
    inputs = ("person", "organization")
    sources = ("FEC", "US Senate LDA")

    async def run(self, ctx):
        name = ctx.value.strip()
        if not name:
            return
        links = [
            research_link("FEC · campaign finance search", "https://www.fec.gov/data/", [["Search name", name]]),
            research_link("Senate LDA · lobbying disclosures", "https://lda.senate.gov/system/public/", [["Name or organization", name]]),
        ]
        ctx.enrich({"US public-record research": "Name matches are leads, not identity verification.", "_links": links})
        ctx.found += len(links)

@register
class USZipInfo(Module):
    name = "us_zip_info"
    title = "US ZIP code"
    description = "Recognize US ZIP/ZIP+4 and offer USPS and Census research links; ZIP is not an exact location."
    inputs = ("zip",)
    sources = ("USPS", "US Census")

    async def run(self, ctx):
        zipcode = normalize_us_zip(ctx.value)
        if not zipcode:
            ctx.message = "Not a US ZIP or ZIP+4 code"
            return
        ctx.enrich({
            "ZIP code": zipcode,
            "Location precision": "ZIP areas are approximate; do not infer a person's exact address.",
            "_links": [
                research_link("USPS · ZIP code lookup", "https://tools.usps.com/zip-code-lookup.htm", [["ZIP", zipcode]]),
                research_link("Census QuickFacts", "https://www.census.gov/quickfacts/", [["ZIP", zipcode[:5]]]),
            ],
        })
        ctx.found += 1

@register
class USEinInfo(Module):
    name = "us_ein_info"
    title = "US employer identification number (EIN)"
    description = "Format-only EIN inspection and official research links; does not validate issuance or ownership."
    inputs = ("ein",)
    sources = ("IRS", "SEC EDGAR")

    async def run(self, ctx):
        ein = normalize_ein(ctx.value)
        if not ein:
            ctx.message = "Expected 9 digits, optionally formatted NN-NNNNNNN"
            return
        ctx.enrich({"EIN format": ein, "Verification": "Format only — not proof of IRS issuance or entity ownership.",
                    "_links": [
                        research_link("IRS nonprofit search", "https://apps.irs.gov/app/eos/", [["EIN", ein]]),
                        research_link("SEC EDGAR filings", "https://www.sec.gov/edgar/search/", [["EIN", ein]]),
                    ]})
        ctx.found += 1

@register
class USPlateResearch(Module):
    name = "us_plate_research"
    title = "US license plate research guidance"
    description = "US plates are state-dependent; provides general DMV/NMVTIS pointers without attempting owner identification."
    inputs = ("plate",)
    sources = ("AAMVA", "NMVTIS")

    async def run(self, ctx):
        plate = re.sub(r"[\s-]", "", ctx.value or "").upper()
        if not re.fullmatch(r"[A-Z0-9]{2,8}", plate):
            ctx.message = "Plate format requires a state and cannot be verified nationally."
            return
        ctx.enrich({"Plate": plate, "Verification": "US formats vary by state. Plate text alone does not identify a vehicle or owner.",
                    "_links": [
                        research_link("AAMVA · state motor vehicle agencies", "https://www.aamva.org/", [["Plate", plate]]),
                        research_link("NMVTIS · vehicle history (requires VIN; not plate-owner search)", "https://vehiclehistory.bja.ojp.gov/"),
                    ]})
        ctx.found += 1
