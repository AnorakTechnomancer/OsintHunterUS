"""Free public-source discovery for usernames and US people research.

Search leads are not identity verification. No data-broker scraping or collection
of residential addresses, phone numbers, relatives or sensitive personal records.
"""
from urllib.parse import urlencode
from .base import Module, register

def google(q):
    return "https://www.google.com/search?" + urlencode({"q": q})

@register
class PublicUsernameDiscovery(Module):
    name = "us_public_username_discovery"
    title = "Expanded free username discovery"
    description = "Public-source pivots for profiles, archives, code, forums and social sites; verify each result."
    inputs = ("username",)
    sources = ("GitHub", "Reddit", "Internet Archive", "Google", "Maigret", "WhatsMyName")

    async def run(self, ctx):
        handle = ctx.value.strip().lstrip("@")
        if len(handle) < 2:
            return
        links = [
            ["GitHub profile", f"https://github.com/{handle}"],
            ["Reddit user", f"https://www.reddit.com/user/{handle}/"],
            ["GitHub public code search", f"https://github.com/search?{urlencode({'q': handle, 'type': 'code'})}"],
            ["Public profiles indexed by search", google(f'"{handle}" (site:github.com OR site:reddit.com OR site:stackoverflow.com OR site:gitlab.com)')],
            ["Other indexed profile mentions", google(f'"{handle}" profile OR username')],
            ["Wayback public captures", f"https://web.archive.org/web/*/https://github.com/{handle}"],
            ["WhatsMyName free search", "https://whatsmyname.app/"],
            ["Maigret open-source checker", "https://github.com/soxoj/maigret"],
        ]
        ctx.enrich({"Expanded username research": "Source links are leads, not verified accounts or locations.",
                    "_links": links})
        ctx.found += len(links)

@register
class USPeoplePublicResearch(Module):
    name = "us_people_public_research"
    title = "US public people research"
    description = "Public professional, publication and historical search leads. No private-address or relatives aggregation."
    inputs = ("person",)
    sources = ("Google", "Google Scholar", "Internet Archive", "FEC")

    async def run(self, ctx):
        name = " ".join(ctx.value.split())
        if len(name) < 4:
            return
        links = [
            ["Public professional profiles", google(f'"{name}" (site:linkedin.com/in/ OR site:github.com OR site:scholar.google.com)')],
            ["Public publications", "https://scholar.google.com/scholar?" + urlencode({"q": f'"{name}"'})],
            ["Public web references", google(f'"{name}"')],
            ["Public historical web mentions", google(f'"{name}" archive OR historical')],
            ["FEC public finance data", "https://www.fec.gov/data/"],
        ]
        ctx.enrich({"People research": "Search leads only; namesakes are common. Confirm identity before linking.",
                    "_links": links})
        ctx.found += len(links)
