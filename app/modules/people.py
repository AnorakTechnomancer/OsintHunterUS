"""Persona en fuentes públicas estructuradas: publicaciones académicas (OpenAlex, ORCID) y Wikidata."""
import asyncio
import re
import unicodedata
from collections import Counter

from .base import Module, register
from .username import PROFILE_URLS

# Wikimedia exige un User-Agent que identifique la herramienta
WIKI_UA = {"User-Agent": "OsintHunter/1.0 (https://github.com/osinthunter; herramienta OSINT local de escritorio)",
           "Accept": "application/json"}


def tokens(s: str) -> list[str]:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z ]+", " ", s).split()


def same_name(a: str, b: str) -> bool:
    """Mismo nombre ignorando tildes y mayúsculas; admite que uno omita el segundo nombre o apellido."""
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return False
    if ta == tb:
        return True
    short, long_ = sorted((ta, tb), key=len)
    return len(short) >= 2 and short[0] == long_[0] and all(t in long_ for t in short)


PARTICLES = {"de", "del", "la", "las", "los", "y", "da", "das", "do", "dos", "di", "van", "von", "der", "san"}


def name_parts(full: str) -> list[str]:
    """Palabras del nombre con las partículas pegadas al apellido siguiente («de la Fuente»)."""
    out, pending = [], []
    for w in full.split():
        if w.lower() in PARTICLES:
            pending.append(w)
            continue
        out.append(" ".join(pending + [w]))
        pending = []
    if pending and out:
        out[-1] += " " + " ".join(pending)
    return out


def name_variants(full: str) -> list[str]:
    """Formas abreviadas con las que la gente suele aparecer en redes (sin segundo nombre o apellido)."""
    p = name_parts(full)
    n = len(p)
    if n < 3:
        return []
    f, s1, s2 = p[0], p[-2], p[-1]
    if n == 3:
        # «Nombre Apellido Apellido» o «Nombre SegundoNombre Apellido»
        v = [f"{f} {p[1]}", f"{f} {s2}", f"{p[1]} {s2}"]
    else:
        mids = p[1:-2]
        v = [f"{f} {s1} {s2}", f"{f} {s1}", f"{f} {' '.join(mids)} {s1}", f"{mids[0]} {s1} {s2}",
             f"{mids[0]} {s1}", f"{f} {mids[0][0]}. {s1}", f"{f} {s2}"]
    full_t = tokens(full)
    return [x for x in dict.fromkeys(v) if tokens(x) != full_t]


def _contains_seq(hay: list[str], seq: list[str]) -> bool:
    n = len(seq)
    return any(hay[i:i + n] == seq for i in range(len(hay) - n + 1))


def name_match(text: str, full: str, variants: list[str] | None = None) -> tuple[str, str] | None:
    """('exacta', nombre) si el texto trae el nombre completo, ('parcial', variante) si sólo una forma corta."""
    hay = tokens(text)
    ft = tokens(full)
    if _contains_seq(hay, ft) or (len(ft) >= 3 and all(t in hay for t in ft)):
        return "exacta", full
    for v in variants if variants is not None else name_variants(full):
        vt = [t for t in tokens(v) if len(t) > 1]
        if len(vt) >= 2 and _contains_seq([t for t in hay if len(t) > 1], vt):
            return "parcial", v
    return None


@register
class Academic(Module):
    name = "academic"
    title = "Publicaciones académicas (OpenAlex, ORCID)"
    description = "Artículos, tesis y patentes firmados con ese nombre: afiliación, coautores, temas y ORCID"
    inputs = ("person",)
    deep = True  # Academic profiles are opt-in, not default people-search evidence.
    sources = ("api.openalex.org", "pub.orcid.org")

    async def run(self, ctx):
        name = ctx.value.strip()
        if len(tokens(name)) < 2:
            ctx.message = "Hace falta nombre y apellido"
            return
        await asyncio.gather(self._openalex(ctx, name), self._orcid(ctx, name))

    async def _openalex(self, ctx, name):
        for query in [name] + name_variants(name)[:2]:
            st, d = await ctx.get_json("https://api.openalex.org/authors", params={"search": query, "per-page": 15})
            if st != 200 or not isinstance(d, dict):
                return
            matches = [a for a in d.get("results") or []
                       if same_name(a.get("display_name", ""), name)
                       or any(same_name(x, name) for x in a.get("display_name_alternatives") or [])]
            if matches:
                break
        else:
            return
        matches.sort(key=lambda a: -(a.get("works_count") or 0))
        if query != name:
            ctx.enrich({
                "OpenAlex: autores con nombre parecido": [
                    f"{a['display_name']} · {a.get('works_count', 0)} trabajos · "
                    + ", ".join(i.get("display_name", "") for i in a.get("last_known_institutions") or [])[:80]
                    for a in matches[:8]],
                "_links": [[f"OpenAlex {a['display_name']}", f"https://openalex.org/authors/{a['id'].rsplit('/', 1)[-1]}"]
                           for a in matches[:5]],
            })
            ctx.found += len(matches)
            return
        # A shared name is not evidence that an academic author is the searched person.
        # Keep each result as an unverified candidate; never attach the top author's
        # publications, metrics, ORCID or affiliations to the searched identity.
        candidates = []
        links = []
        for author in matches[:12]:
            aid = str(author.get("id") or "").rsplit("/", 1)[-1]
            institutions = ", ".join(i.get("display_name", "") for i in author.get("last_known_institutions") or [])
            candidates.append({
                "name": author.get("display_name"),
                "works": author.get("works_count"),
                "institution": institutions or None,
                "openalex_id": aid,
                "status": "unverified name match",
            })
            if aid:
                links.append([f"OpenAlex candidate: {author.get('display_name')}", f"https://openalex.org/authors/{aid}"])
        ctx.enrich({"OpenAlex candidate authors (not attributed to searched person)": candidates,
                    "_links": links})
        ctx.message = f"{len(matches)} matching author profiles; no identity selected or linked."
        ctx.found += len(candidates)

    async def _orcid(self, ctx, name):
        t = name.split()
        given, family = t[0], t[1] if len(t) >= 3 else t[-1]
        q = f'given-names:"{given}" AND family-names:"{family}"'
        st, d = await ctx.get_json("https://pub.orcid.org/v3.0/expanded-search/", params={"q": q, "rows": 20},
                                   headers={"Accept": "application/json"})
        if st != 200 or not isinstance(d, dict):
            return
        hits = [h for h in d.get("expanded-result") or []
                if same_name(f"{h.get('given-names') or ''} {h.get('family-names') or ''}", name)
                or same_name(h.get("credit-name") or "", name)]
        if not hits:
            return
        lines, links = [], []
        for h in hits[:10]:
            inst = ", ".join((h.get("institution-name") or [])[:2])
            full = f"{h.get('given-names') or ''} {h.get('family-names') or ''}".strip()
            lines.append(f"{h['orcid-id']} · {full}" + (f" · {inst}" if inst else ""))
            links.append([f"ORCID {full}", f"https://orcid.org/{h['orcid-id']}"])
        ctx.enrich({"ORCID: perfiles con este nombre": lines, "_links": links[:5]})
        ctx.found += len(hits)


# ---------------------------------------------------------------- Wikidata

WD_ITEM_PROPS = {
    "P19": "Lugar de nacimiento", "P27": "Nacionalidad", "P106": "Ocupación", "P39": "Cargos",
    "P108": "Empleadores", "P69": "Estudios", "P102": "Partido político", "P26": "Cónyuge", "P22": "Padre",
    "P25": "Madre", "P40": "Hijos", "P3373": "Hermanos",
}
WD_SOCIAL = {
    "P2002": ("X/Twitter", None), "P2003": ("Instagram", None), "P2013": ("Facebook", None),
    "P6634": ("LinkedIn", None), "P2037": ("GitHub", None), "P7085": ("TikTok", None),
    "P2397": ("YouTube", "https://www.youtube.com/channel/{}"), "P11892": ("Threads", None),
}


def _claims(entity: dict, pid: str) -> list:
    out = []
    for c in entity.get("claims", {}).get(pid, []):
        v = ((c.get("mainsnak") or {}).get("datavalue") or {}).get("value")
        if v is not None:
            out.append(v)
    return out


@register
class Wikidata(Module):
    name = "wikidata"
    title = "Wikidata / Wikipedia"
    description = ("Si la persona es pública: fecha y lugar de nacimiento, cargos, estudios, familia, "
                   "web y redes oficiales")
    inputs = ("person",)
    deep = True  # Public-figure research is opt-in.
    sources = ("wikidata.org",)

    async def run(self, ctx):
        name = ctx.value.strip()
        for query in [name] + name_variants(name)[:2]:
            st, d = await ctx.get_json("https://www.wikidata.org/w/api.php", headers=WIKI_UA, params={
                "action": "wbsearchentities", "search": query, "language": "en", "uselang": "en", "type": "item",
                "limit": 10, "format": "json",
            })
            if st != 200 or not isinstance(d, dict):
                raise RuntimeError(f"Wikidata respondió {st}")
            cands = [c["id"] for c in d.get("search") or []
                     if same_name(c.get("label", ""), name) or any(same_name(a, name) for a in c.get("aliases") or [])][:5]
            if cands:
                break
        else:
            return
        partial = query != name
        st, ents = await ctx.get_json("https://www.wikidata.org/w/api.php", headers=WIKI_UA, params={
            "action": "wbgetentities", "ids": "|".join(cands), "props": "claims|sitelinks|descriptions|labels",
            "languages": "en|es", "format": "json",
        })
        if st != 200 or not isinstance(ents, dict):
            return
        humans = [e for e in (ents.get("entities") or {}).values()
                  if any(v.get("id") == "Q5" for v in _claims(e, "P31") if isinstance(v, dict))]
        if not humans:
            return
        desc = lambda e: ((e.get("descriptions") or {}).get("en") or (e.get("descriptions") or {}).get("es") or {}).get("value", "")  # noqa: E731
        # Even one Wikidata result is only a name match, not verified identity.
        label = lambda ent: ((ent.get("labels") or {}).get("en") or (ent.get("labels") or {}).get("es") or {}).get("value", "")
        key = "Wikidata candidate people (unverified)"
        ctx.enrich({key: [f"{ent['id']} · {label(ent)} · {desc(ent)}" for ent in humans],
                    "_links": [[f"Wikidata candidate {ent['id']}", f"https://www.wikidata.org/wiki/{ent['id']}"] for ent in humans]})
        ctx.message = f"{len(humans)} public profiles with matching names; none attributed to searched person."
        ctx.found += len(humans)

    async def _labels(self, ctx, ids: set[str]) -> dict[str, str]:
        out: dict[str, str] = {}
        ids_l = sorted(ids)
        for i in range(0, len(ids_l), 50):
            st, d = await ctx.get_json("https://www.wikidata.org/w/api.php", headers=WIKI_UA, params={
                "action": "wbgetentities", "ids": "|".join(ids_l[i:i + 50]), "props": "labels",
                "languages": "es|en", "format": "json",
            })
            if st == 200 and isinstance(d, dict):
                for qid, ent in (d.get("entities") or {}).items():
                    lab = ent.get("labels") or {}
                    out[qid] = (lab.get("es") or lab.get("en") or {}).get("value", qid)
        return out
