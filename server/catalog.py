# -*- coding: utf-8 -*-
"""
Loads the enriched funding catalogue and the charity profile.

Reads server/data/funders.enriched.json (produced by tools/enrich.py).
Reloads automatically when the file changes, so re-running enrichment while the
server is up is picked up without a restart.
"""
import io
import json
import os
import threading

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
ENRICHED = os.path.join(DATA_DIR, "funders.enriched.json")
PARTNERS = os.path.join(DATA_DIR, "partners.json")
SIGNUPS = os.path.join(DATA_DIR, "company_signups.json")
SOURCE_CSV = os.path.join(DATA_DIR, "funders.source.csv")
PROFILE = os.path.join(DATA_DIR, "profile.json")

CATEGORY_LABELS = {
    "corporate_funding": {"en": "Corporate funding", "fr": "Financement d'entreprise"},
    "private_funding": {"en": "Private funding", "fr": "Financement privé"},
    "csr_programs": {"en": "CSR programmes", "fr": "Programmes RSE"},
    "eu_grants": {"en": "EU grants", "fr": "Subventions européennes"},
    "french_grants": {"en": "French grants", "fr": "Subventions françaises"},
}
CATEGORY_BLURB = {
    "corporate_funding": {
        "en": "Company foundations and corporate giving programmes.",
        "fr": "Fondations d'entreprise et programmes de mécénat."},
    "private_funding": {
        "en": "Independent, family and private foundations.",
        "fr": "Fondations indépendantes, familiales et privées."},
    "csr_programs": {
        "en": "In-kind donations, employee volunteering and matching schemes.",
        "fr": "Dons en nature, mécénat de compétences et abondement."},
    "eu_grants": {
        "en": "European programmes — larger sums, heavier requirements.",
        "fr": "Programmes européens — montants élevés, exigences lourdes."},
    "french_grants": {
        "en": "French public funding: state, regions, departments and agencies.",
        "fr": "Financements publics français : État, régions, départements et agences."},
}
CATEGORY_ORDER = ["corporate_funding", "private_funding", "csr_programs", "eu_grants", "french_grants"]

_lock = threading.Lock()
_cache = {"mtime": None, "funders": []}
_partner_lock = threading.Lock()
_partner_cache = {"mtime": None, "data": {"partners": {}}}


def load_partners():
    """Paying partners, from a file separate to the enriched catalogue.

    Kept separate on purpose: tools/enrich.py rewrites funders.enriched.json in
    full, so commercial data stored there would be destroyed on every re-run.
    """
    with _partner_lock:
        if not os.path.exists(PARTNERS):
            return {"partners": {}}
        mtime = os.path.getmtime(PARTNERS)
        if _partner_cache["mtime"] != mtime:
            with io.open(PARTNERS, encoding="utf-8") as handle:
                _partner_cache["data"] = json.load(handle)
            _partner_cache["mtime"] = mtime
        return _partner_cache["data"]


def partner_list():
    """Partners in catalogue order, for the landing page logo strip."""
    registry = load_partners().get("partners", {})
    out = []
    for funder in load_funders():
        entry = registry.get(funder.get("id"))
        if entry:
            out.append({
                "id": funder["id"],
                "name": entry.get("display_name") or funder.get("organization") or funder.get("name"),
                "logo": entry.get("logo", ""),
                "since": entry.get("since", ""),
            })
    return out


def _normalise_link(value):
    """Source links are hand-collected: some omit the protocol, some are prose.

    Returns (href, note). A bare domain becomes a real URL; anything that isn't a
    URL at all is returned as a note so the UI can show it as text rather than
    rendering a relative link that would navigate inside the app.
    """
    raw = (value or "").strip()
    if not raw:
        return "", ""
    if raw.lower().startswith(("http://", "https://")):
        return raw, ""
    if " " in raw or "." not in raw:
        return "", raw          # prose such as "varies by municipality"
    return "https://" + raw, ""


def _apply_partner(funder):
    """Attach partner presentation data.

    These fields are for display only. scoring.py does not read them, so paying
    can never move a compatibility score - that promise is enforced structurally,
    not by convention.
    """
    entry = (load_partners().get("partners") or {}).get(funder.get("id"))
    funder["is_partner"] = bool(entry)
    funder["partner_logo"] = entry.get("logo", "") if entry else ""
    funder["partner_name"] = (entry.get("display_name") if entry else "") or ""
    return funder


def _normalise(funder):
    # The source prose rarely describes administrative burden, so the extractor
    # rates almost everything "medium". EU programmes are reliably the heaviest
    # (consortium building, co-financing, English reporting, audit trails), so we
    # set that floor from the category rather than pretending we learned it.
    if "eu_grants" in (funder.get("categories") or []) and funder.get("complexity") != "high":
        funder["complexity"] = "high"

    href, note = _normalise_link(funder.get("official_link"))
    funder["official_link"] = href
    funder["official_link_note"] = note
    source_href, _ = _normalise_link(funder.get("source_verified_url"))
    funder["source_verified_url"] = source_href
    return _apply_partner(funder)


def load_funders():
    """Enriched records, reloaded when the file changes on disk."""
    with _lock:
        if not os.path.exists(ENRICHED):
            return []
        mtime = os.path.getmtime(ENRICHED)
        if _cache["mtime"] != mtime:
            with io.open(ENRICHED, encoding="utf-8") as handle:
                _cache["funders"] = [_normalise(f) for f in json.load(handle)]
            _cache["mtime"] = mtime
        return _cache["funders"]


def funders_in(category):
    """Dual-listing: a funder appears in every category it genuinely belongs to."""
    return [f for f in load_funders() if category in (f.get("categories") or [])]


def get_funder(funder_id):
    for funder in load_funders():
        if funder.get("id") == funder_id:
            return funder
    return None


def catalogue_status():
    funders = load_funders()
    counts = dict((c, len(funders_in(c))) for c in CATEGORY_ORDER)
    return {
        "total": len(funders),
        "per_category": counts,
        "enriched_present": os.path.exists(ENRICHED),
        "source_present": os.path.exists(SOURCE_CSV),
    }


def read_signups():
    if not os.path.exists(SIGNUPS):
        return []
    try:
        with io.open(SIGNUPS, encoding="utf-8") as handle:
            return json.load(handle)
    except ValueError:
        return []


def add_signup(record):
    with _lock:
        if not os.path.isdir(DATA_DIR):
            os.makedirs(DATA_DIR)
        rows = []
        if os.path.exists(SIGNUPS):
            try:
                with io.open(SIGNUPS, encoding="utf-8") as handle:
                    rows = json.load(handle)
            except ValueError:
                rows = []
        rows.append(record)
        with io.open(SIGNUPS, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(rows, ensure_ascii=False, indent=1))
        return record


def read_profile():
    if not os.path.exists(PROFILE):
        return None
    try:
        with io.open(PROFILE, encoding="utf-8") as handle:
            return json.load(handle)
    except ValueError:
        return None


def write_profile(profile):
    with _lock:
        if not os.path.isdir(DATA_DIR):
            os.makedirs(DATA_DIR)
        with io.open(PROFILE, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(profile, ensure_ascii=False, indent=1))
    return profile
