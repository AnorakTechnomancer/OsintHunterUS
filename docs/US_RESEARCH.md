# US research guide

OsintHunterUS preserves the original graph, source history, confidence scoring,
case storage, reports, and general-purpose OSINT modules. Its US-specific layer is
intentionally **source-first**: it supplies official research launchpads and does
not silently treat a matching name as a verified identity.

## Suggested workflows

1. **Company / nonprofit**: add an `organization` entity; run **US business and nonprofit records**. Cross-check the entity name, state of incorporation, entity number and dates before attaching results. Look at SEC EDGAR for reporting companies, IRS EOS for nonprofits, SAM.gov for federal registrations and USAspending for federal spending.
2. **Public figure / lobbyist**: add a `person` entity and run **US federal election and lobbying records**. FEC name matches are not automatically attributable to a person; compare location, employer, committee and dates.
3. **Email / username / domain / IP**: use existing generic modules, pivots and confidence evidence. Preserve the direct URL and date of retrieval in case notes.
4. **Telephone**: enter a US 10-digit number or +1 E.164 and run the phone analysis module. Area codes are not current-location evidence; numbers can be ported or spoofed.
5. **ZIP / EIN**: format validation only; ZIPs are not precise locations, and an EIN-shaped string is not proof that an EIN was issued.
6. **License plates**: manually select `plate` if necessary; state plate schemes vary and no owner-identification service is provided. For vehicle-history questions use an authorized VIN-based source.

## Evidence quality

- Distinguish *lead*, *corroborated association*, and *confirmed fact*.
- Record the source URL, retrieval date, and any identifier used to disambiguate.
- Avoid speculative automatic linking of unrelated namesakes.
- Public records can have disclosure restrictions, errors, and delays.
- Do not use this tool to obtain protected DMV information, private identifiers or to bypass access controls.

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m app
```

The application binds to loopback by default. Existing user settings are stored
in `data/settings.json`; change `default_region` to `US` and `lang` to `en`
on existing installations if you previously chose different defaults.

## Live API modules (balanced automation)

- **Census ZIP** runs for ZIP entities with a bounded request to the 2024 ACS 5-year API. ZIP tabulation areas (ZCTAs) are not the same as postal delivery ZIPs.
- **SEC EDGAR** runs as an explicitly selected deep module for organizations. Set `sec_user_agent` to a contact string such as `Research Team contact@example.org` in settings.json; SEC requires an identified requester. Exact name/ticker matches only. No fuzzy identity merges.
- **USAspending** runs as an explicitly selected deep module for organizations. Recipient autocomplete yields candidate names/UEIs, not verified corporate relationships. Confirm the recipient before associating awards.
- Deep modules do not automatically run in ordinary scans; this implements balanced automation by default, with user-controlled wider searches.
- All modules cap result counts and use request timeouts; no automatic second-hop person searches.

API reference: [SEC EDGAR](https://www.sec.gov/search-filings/edgar-application-programming-interfaces), [USAspending](https://api.usaspending.gov/docs/endpoints), [Census ACS](https://api.census.gov/data/2024/acs/acs5/examples.html).
