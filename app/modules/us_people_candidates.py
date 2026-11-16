"""Public professional profile candidates. No identity merges or sensitive record aggregation."""
import re
from .base import Module, register

def name_matches(requested, displayed):
    def parts(s):
        return re.findall(r"[a-z]+", (s or "").casefold())
    a, b = parts(requested), parts(displayed)
    return len(a) >= 2 and len(b) >= 2 and a[0] == b[0] and a[-1] == b[-1]

def location_matches(city, state, zipcode, public_location):
    loc = (public_location or "").casefold()
    tokens = [v.strip().casefold() for v in (city, state, zipcode) if v and v.strip()]
    if not tokens:
        return "not supplied"
    return "self-reported location overlap" if any(t in loc for t in tokens) else "not established"

@register
class GitHubPeopleCandidates(Module):
    name = "us_github_people_candidates"
    title = "Public GitHub people candidates"
    description = "Live, bounded public-profile search by full name; location is compared against self-reported profile location. No identity automatically linked."
    inputs = ("person",)
    sources = ("GitHub public REST API",)
    timeout = 35

    async def run(self, ctx):
        name = " ".join(ctx.value.split())
        if len(name.split()) < 2:
            return
        attrs = ctx.entity.get("attrs") or {}
        city = str(attrs.get("Search city") or "")
        state = str(attrs.get("Search state") or "")
        zipcode = str(attrs.get("Search ZIP") or "")
        headers = {"Accept": "application/vnd.github+json"}
        # A token is optional, never required; public data works without one.
        token = ctx.key("github")
        if token:
            headers["Authorization"] = "Bearer " + token
        try:
            st, result = await ctx.get_json("https://api.github.com/search/users",
                                            params={"q": f"{name} in:fullname", "per_page": 12},
                                            headers=headers)
        except Exception as exc:
            ctx.message = f"GitHub search unavailable ({type(exc).__name__})"
            return
        if st in (403, 429):
            ctx.message = "GitHub search rate-limited; try later or configure a GitHub token."
            return
        if st != 200 or not isinstance(result, dict):
            ctx.message = f"GitHub search returned HTTP {st}"
            return
        candidates = []
        links = []
        for item in (result.get("items") or [])[:12]:
            login = item.get("login")
            if not isinstance(login, str) or not re.fullmatch(r"[A-Za-z0-9-]{1,39}", login):
                continue
            try:
                status, profile = await ctx.get_json(f"https://api.github.com/users/{login}", headers=headers)
            except Exception:
                continue
            if status != 200 or not isinstance(profile, dict):
                continue
            display_name = profile.get("name")
            if not name_matches(name, display_name):
                continue
            public_location = profile.get("location") or ""
            candidates.append({
                "name": display_name, "handle": login,
                "public_location": public_location or "not supplied",
                "location_match": location_matches(city, state, zipcode, public_location),
                "company": profile.get("company") or None,
                "bio": (profile.get("bio") or "")[:240] or None,
                "profile": f"https://github.com/{login}",
                "status": "unverified candidate — public self-reported profile",
            })
            links.append([f"GitHub candidate: {login}", f"https://github.com/{login}"])
        ctx.enrich({"GitHub public people candidates (unverified)": candidates,
                    "_links": links}, replace=True)
        ctx.found += len(candidates)
        ctx.message = f"{len(candidates)} public profiles with matching first and last names; identity unverified."
