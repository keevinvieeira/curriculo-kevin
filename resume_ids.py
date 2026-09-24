"""Stable IDs for master_resume.json — the citable units of the evidence map.

Every experience (work_experience entry), project, role and bullet carries an `id`.
IDs are assigned once and never renumbered or reused: editing a bullet's text keeps
its ID; a new bullet gets the next free number in its container.

Scheme:
- experience: ``exp-<slug>``            (e.g. ``exp-wipro``)
- project:    ``proj-<slug>``           (e.g. ``proj-meu-barzin``)
- role:       ``<container>-role-NN``   (e.g. ``wipro-role-01``)
- bullet:     ``<container>-bNN``       (e.g. ``meu-barzin-b03``)
- responsibility (roles[].responsibilities): ``<container>-rNN``, with
  ``same_as`` pointing to the canonical bullet when it restates one.
- education ``edu-<slug>``, certification ``cert-<slug>``, volunteer ``vol-<slug>``,
  language ``lang-<slug>`` (same ID on the parallel pt/en entries).

Company-level bullets that mirror a project bullet word for word (AI Builder lists
each project bullet again at company level) share the project bullet's ID.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Iterator

BULLET_RE = re.compile(r"^(?P<prefix>.+)-(?P<kind>b|r)(?P<num>\d+)$")


def slug(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_value.lower()).strip("-")


def _prefix(container_id: str) -> str:
    return container_id.split("-", 1)[1] if container_id.startswith(("exp-", "proj-")) else container_id


def _heading(text: str) -> str:
    """'AI Career OS — Motor de Match: ...' -> 'motor de match' (text before ':' minus project prefix)."""
    head = text.split(":", 1)[0]
    head = head.split(" — ", 1)[-1]
    return slug(head)


def _next(items: list[dict[str, Any]], prefix: str, kind: str, taken: set[str]) -> str:
    used = [int(m["num"]) for i in items if (m := BULLET_RE.match(str(i.get("id", ""))))
            and m["prefix"] == prefix and m["kind"] == kind]
    n = max(used, default=0) + 1
    while f"{prefix}-{kind}{n:02d}" in taken:
        n += 1
    return f"{prefix}-{kind}{n:02d}"


def _with_id_first(item: dict[str, Any], new_id: str) -> dict[str, Any]:
    rest = {k: v for k, v in item.items() if k != "id"}
    item.clear()
    item.update({"id": new_id, **rest})
    return item


def assign_ids(master: dict[str, Any]) -> list[str]:
    """Fill in missing IDs in place. Existing IDs are never touched. Returns the new IDs."""
    taken = {i for i, _ in iter_ids(master)}
    created: list[str] = []

    def give(item: dict[str, Any], new_id: str) -> None:
        _with_id_first(item, new_id)
        taken.add(new_id)
        created.append(new_id)

    for exp in master.get("work_experience", []):
        if not exp.get("id"):
            first_words = " ".join(exp["company"].split(" — ")[0].split()[:2])
            give(exp, f"exp-{slug(first_words)}")
        exp_prefix = _prefix(exp["id"])

        text_to_id: dict[tuple[str, str], str] = {}
        heading_to_id: dict[str, str] = {}
        for project in exp.get("projects", []):
            if not project.get("id"):
                give(project, f"proj-{slug(project['name'].split(' & ')[0])}")
            prefix = _prefix(project["id"])
            for bullet in project.get("bullets", []):
                if not bullet.get("id"):
                    give(bullet, _next(project["bullets"], prefix, "b", taken))
                text_to_id[(bullet.get("pt", ""), bullet.get("en", ""))] = bullet["id"]
                heading_to_id[_heading(bullet.get("pt", ""))] = bullet["id"]

        for bullet in exp.get("bullets", []):
            if bullet.get("id"):
                continue
            mirrored = text_to_id.get((bullet.get("pt", ""), bullet.get("en", "")))
            if mirrored:
                _with_id_first(bullet, mirrored)
            else:
                give(bullet, _next(exp["bullets"], exp_prefix, "b", taken))

        for n, role in enumerate(exp.get("roles", []), start=1):
            if not role.get("id"):
                rid = f"{exp_prefix}-role-{n:02d}"
                while rid in taken:
                    n += 1
                    rid = f"{exp_prefix}-role-{n:02d}"
                give(role, rid)
            responsibilities = role.get("responsibilities", [])
            if not responsibilities:
                continue
            # Responsibilities belong to the project(s) the role covers; the first project names the prefix.
            owner = next((p for p in exp.get("projects", []) if slug(p["name"]).startswith(
                slug((role.get("projects") or [""])[-1]))), None)
            prefix = _prefix(owner["id"]) if owner else exp_prefix
            for resp in responsibilities:
                if not isinstance(resp, dict) or resp.get("id"):
                    continue
                give(resp, _next(responsibilities, prefix, "r", taken))
                same = heading_to_id.get(_heading(resp.get("pt", "")))
                if same and "same_as" not in resp:
                    rest = {k: v for k, v in resp.items() if k != "id"}
                    resp.clear()
                    resp.update({"id": created[-1], "same_as": same, **rest})

    def unique(base: str) -> str:
        candidate, n = base, 2
        while candidate in taken:
            candidate, n = f"{base}-{n}", n + 1
        return candidate

    for edu in master.get("education", []):
        if not edu.get("id"):
            degree = edu.get("degree", {}).get("en", "")
            give(edu, unique(f"edu-{slug(' '.join(degree.split()[:4]))}"))
    for cert in master.get("certifications", []):
        if not cert.get("id"):
            give(cert, unique(f"cert-{slug(' '.join(cert['name'].split()[:5]))}"))
    for vol in master.get("volunteer_experience", []):
        if not vol.get("id"):
            give(vol, unique(f"vol-{slug(vol['organization'].split(' (')[0])}"))
    languages = master.get("languages", {})
    for n, en_entry in enumerate(languages.get("en", [])):
        lang_id = en_entry.get("id") or unique(f"lang-{slug(en_entry['language'])}")
        if not en_entry.get("id"):
            give(en_entry, lang_id)
        for code, entries in languages.items():
            if code != "en" and n < len(entries) and not entries[n].get("id"):
                _with_id_first(entries[n], lang_id)
    return created


def iter_ids(master: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any]]]:
    """Yield (id, item) for every ID-bearing item, including mirrored duplicates."""
    for exp in master.get("work_experience", []):
        if exp.get("id"):
            yield exp["id"], exp
        for project in exp.get("projects", []):
            if project.get("id"):
                yield project["id"], project
            for bullet in project.get("bullets", []):
                if bullet.get("id"):
                    yield bullet["id"], bullet
        for bullet in exp.get("bullets", []):
            if bullet.get("id"):
                yield bullet["id"], bullet
        for role in exp.get("roles", []):
            if role.get("id"):
                yield role["id"], role
            for resp in role.get("responsibilities", []):
                if isinstance(resp, dict) and resp.get("id"):
                    yield resp["id"], resp
    for section in ("education", "certifications", "volunteer_experience"):
        for item in master.get(section, []):
            if item.get("id"):
                yield item["id"], item
    en_languages = master.get("languages", {}).get("en", [])
    for item in en_languages:
        if item.get("id"):
            yield item["id"], item


def build_index(master: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """id -> {kind, experience_id, project_id, pt, en} — the lookup the evidence map resolves against."""
    index: dict[str, dict[str, Any]] = {}
    for exp in master.get("work_experience", []):
        eid = exp.get("id")
        index[eid] = {"kind": "experience", "experience_id": eid, "company": exp.get("company")}
        for project in exp.get("projects", []):
            pid = project.get("id")
            index[pid] = {"kind": "project", "experience_id": eid, "name": project.get("name")}
            for b in project.get("bullets", []):
                index[b["id"]] = {"kind": "bullet", "experience_id": eid, "project_id": pid,
                                  "pt": b.get("pt"), "en": b.get("en")}
        for b in exp.get("bullets", []):
            index.setdefault(b["id"], {"kind": "bullet", "experience_id": eid, "project_id": None,
                                       "pt": b.get("pt"), "en": b.get("en")})
        for role in exp.get("roles", []):
            index[role["id"]] = {"kind": "role", "experience_id": eid, "title": role.get("title")}
            for r in role.get("responsibilities", []):
                if isinstance(r, dict):
                    index[r["id"]] = {"kind": "responsibility", "experience_id": eid, "role_id": role["id"],
                                      "same_as": r.get("same_as"), "pt": r.get("pt"), "en": r.get("en")}
    for edu in master.get("education", []):
        index[edu["id"]] = {"kind": "education", "institution": edu.get("institution"),
                            "pt": edu.get("degree", {}).get("pt"), "en": edu.get("degree", {}).get("en")}
    for cert in master.get("certifications", []):
        index[cert["id"]] = {"kind": "certification", "name": cert.get("name"), "issuer": cert.get("issuer"),
                             "pt": cert.get("status", {}).get("pt"), "en": cert.get("status", {}).get("en")}
    for vol in master.get("volunteer_experience", []):
        index[vol["id"]] = {"kind": "volunteer", "organization": vol.get("organization"),
                            "pt": vol.get("description", {}).get("pt"), "en": vol.get("description", {}).get("en")}
    languages = master.get("languages", {})
    for n, item in enumerate(languages.get("en", [])):
        pt_items = languages.get("pt", [])
        index[item["id"]] = {"kind": "language", "language": item.get("language"),
                             "pt": pt_items[n].get("proficiency") if n < len(pt_items) else None,
                             "en": item.get("proficiency")}
    return index


def validate_ids(master: dict[str, Any]) -> list[str]:
    """Every item has an ID; an ID repeats only for word-for-word mirrored bullets; same_as resolves."""
    errors: list[str] = []
    seen: dict[str, dict[str, Any]] = {}
    for exp in master.get("work_experience", []):
        containers = [exp, *exp.get("projects", []), *exp.get("roles", [])]
        bullets = [*exp.get("bullets", []), *(b for p in exp.get("projects", []) for b in p.get("bullets", []))]
        resps = [r for role in exp.get("roles", []) for r in role.get("responsibilities", []) if isinstance(r, dict)]
        for item in [*containers, *bullets, *resps]:
            if not item.get("id"):
                label = item.get("company") or item.get("name") or str(item.get("title") or item.get("pt", ""))[:60]
                errors.append(f"missing id: {label}")
    for section in ("education", "certifications", "volunteer_experience"):
        for item in master.get(section, []):
            if not item.get("id"):
                errors.append(f"missing id in {section}: {item.get('institution') or item.get('name') or item.get('organization')}")
    languages = master.get("languages", {})
    en_ids = [item.get("id") for item in languages.get("en", [])]
    for code, entries in languages.items():
        ids = [item.get("id") for item in entries]
        if None in ids or ids != en_ids:
            errors.append(f"languages.{code} ids must exist and match languages.en order: {ids} vs {en_ids}")
    for item_id, item in iter_ids(master):
        if item_id in seen:
            prev = seen[item_id]
            if (prev.get("pt"), prev.get("en")) != (item.get("pt"), item.get("en")) or "pt" not in item:
                errors.append(f"duplicate id with different content: {item_id}")
        else:
            seen[item_id] = item
    for item_id, item in seen.items():
        if item.get("same_as") and item["same_as"] not in seen:
            errors.append(f"{item_id}.same_as points to unknown id {item['same_as']}")
    return errors
