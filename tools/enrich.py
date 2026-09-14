# -*- coding: utf-8 -*-
"""
Offline enrichment: turn the prose funding database into structured, bilingual records.

Why this exists
---------------
The source CSV is human research: rich, accurate, and written in prose
("Association law 1901, apolitical, based in/near a QPV, >=3 years of existence").
Deterministic scoring needs comparable fields. This pass runs ONCE per data update,
uses the LLM purely as a parser/translator, and writes a structured file.

At runtime the app reads only that file. No LLM call ever influences a score.

Usage:
    .venv/bin/python tools/enrich.py           # only rows that changed
    .venv/bin/python tools/enrich.py --all     # re-do everything
    .venv/bin/python tools/enrich.py --limit 3 # try a few first
"""
import csv
import hashlib
import io
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "server"))

import llm  # noqa: E402

SOURCE = os.path.join(ROOT, "server", "data", "funders.source.csv")
TARGET = os.path.join(ROOT, "server", "data", "funders.enriched.json")
FIELDS = os.path.join(ROOT, "server", "config", "onboarding_fields.json")

# A funder's source `type` always yields this category; CSR is added on top when
# the support is CSR-shaped (dual-listing, per product decision).
BASE_CATEGORY = {
    "corporate_foundation": "corporate_funding",
    "private_foundation": "private_funding",
    "public_grant": "french_grants",
    "eu_grant": "eu_grants",
    "csr_program": "csr_programs",
}
CATEGORIES = ["corporate_funding", "private_funding", "csr_programs", "eu_grants", "french_grants"]


def vocabulary():
    """Allowed codes, read from the onboarding config so profile and funder data align."""
    data = json.load(io.open(FIELDS, encoding="utf-8"))
    vocab = {}
    for step in data["steps"]:
        for field in step["fields"]:
            if field.get("options"):
                vocab[field["id"]] = [o["value"] for o in field["options"]]
    return vocab


VOCAB = vocabulary()

SYSTEM = u"""You extract structured data from funding-programme descriptions and translate them.

ABSOLUTE RULES:
1. Extract ONLY what the source text states or unambiguously implies. Never invent a figure,
   a deadline, an eligibility rule or a requirement that is not supported by the text.
2. If a value is unknown, unstated, or the text says "not specified"/"not confirmed",
   use null (or an empty list). Unknown is a valid, expected answer — do not guess.
3. Never merge two separate facts into one claim.
4. Translations must preserve meaning exactly, in professional register. Do not embellish.

THEMES AND GEOGRAPHY - these drive matching, so be complete rather than minimal:
5. "cause_areas" must list EVERY theme the programme plausibly covers, not just the headline
   one. It must never be empty: if the focus is broad ("solidarity", "general interest"),
   choose the codes that best approximate it. A programme mentioning food almost always
   covers both food_security and food_waste; one mentioning "sustainable food" also covers
   environment and often circular_economy.
6. "regions": if the programme is open anywhere in mainland France, include "national".
   Use specific region codes ONLY when the programme is restricted to those regions
   (then do not also include "national"). Add "europe" IN ADDITION when it also operates
   in other European countries. A French charity must be able to match a programme that
   is open to it - never return a geography that silently excludes France when the source
   says the programme is available in France.
7. These completeness rules never override rule 1: do not invent an eligibility restriction,
   an amount, or a requirement. Being generous applies to THEMES and GEOGRAPHY only.

You reply with a single JSON object and nothing else."""

TEMPLATE = u"""Extract structured fields from this funding programme.

--- SOURCE RECORD ---
name: {name}
organization: {organization}
type: {type}
fit: {fit}
geography: {geography}
sector_focus: {sector_focus}
eligible_org_type: {eligible_org_type}
funding_type: {funding_type}
funding_range: {funding_range}
application_process: {application_process}
required_documents: {required_documents}
deadline_cycle: {deadline_cycle}
notes: {notes}
--- END ---

Return JSON with EXACTLY these keys:

{{
  "cause_areas": [],            // codes from: {cause_areas}. NEVER empty. Be complete.
  "regions": [],                // codes from: {regions}. Include "national" if open across France.
                                // Specific regions only if restricted. Add "europe" if multi-country.
  "geo_scope": "",              // one of: "local", "regional", "national", "international"
  "legal_status_required": [],  // codes from: {legal_status}. [] if not restricted.
  "accreditations_required": [],// codes from: {accreditations}. [] if none stated.
  "min_org_age_years": null,    // integer or null
  "grant_min_eur": null,        // integer or null - ONLY if a figure is stated
  "grant_max_eur": null,        // integer or null - ONLY if a figure is stated
  "amount_disclosed": false,    // true only if a usable figure appears
  "cofinancing_required_pct": null,  // integer 0-100 or null
  "requires_english": false,    // true if applying/reporting needs English
  "requires_partner_abroad": false,
  "support_types": [],          // any of: "grant","in_kind","volunteering","matching","loan","support"
  "is_csr_shaped": false,       // true if it offers in-kind goods, employee volunteering,
                                // skills-based support, round-up or crowdfunding matching
  "deadline_type": "",          // one of: "annual","periodic","rolling","one_off","unknown"
  "complexity": "",             // "low","medium","high" - administrative burden to apply
  "application_steps_en": [],   // ordered steps, from application_process. [] if unstated.
  "application_steps_fr": [],   // same steps in French
  "required_documents_en": [],  // list items, from required_documents
  "required_documents_fr": [],
  "sector_focus_fr": "",        // French translation of sector_focus
  "eligible_org_type_fr": "",   // French translation of eligible_org_type
  "funding_range_fr": "",       // French translation of funding_range
  "deadline_cycle_fr": "",      // French translation of deadline_cycle
  "notes_fr": "",               // French translation of notes
  "summary_en": "",             // ONE sentence: what this funder offers and to whom
  "summary_fr": ""              // the same sentence in French
}}"""


def row_hash(row):
    blob = u"|".join((row.get(k) or "") for k in sorted(row.keys()))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def clean_list(values, allowed):
    if not isinstance(values, list):
        return []
    return [v for v in values if v in allowed]


def clean_int(value, low=None, high=None):
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return None
    if low is not None and number < low:
        return None
    if high is not None and number > high:
        return None
    return number


def enrich_row(row):
    prompt = TEMPLATE.format(
        cause_areas=", ".join(VOCAB["cause_areas"]),
        regions=", ".join(VOCAB["regions"]),
        legal_status=", ".join(VOCAB["legal_status"]),
        accreditations=", ".join(VOCAB["accreditations"]),
        **dict((k, (row.get(k) or "").strip() or "(not stated)") for k in
               ["name", "organization", "type", "fit", "geography", "sector_focus",
                "eligible_org_type", "funding_type", "funding_range",
                "application_process", "required_documents", "deadline_cycle", "notes"])
    )
    raw = llm.chat_json(SYSTEM, prompt, temperature=0.1, max_tokens=2600, retries=5)

    # Trust nothing: constrain every extracted value to the known vocabulary.
    base = BASE_CATEGORY.get((row.get("type") or "").strip(), "corporate_funding")
    categories = [base]
    if raw.get("is_csr_shaped") and "csr_programs" not in categories:
        categories.append("csr_programs")

    record = {
        "id": (row.get("id") or "").strip(),
        "name": (row.get("name") or "").strip(),
        "organization": (row.get("organization") or "").strip(),
        "source_type": (row.get("type") or "").strip(),
        "categories": [c for c in categories if c in CATEGORIES],
        "fit": (row.get("fit") or "").strip(),
        "confidence": (row.get("confidence") or "").strip(),
        "official_link": (row.get("official_link") or "").strip(),
        "source_verified_url": (row.get("source_verified_url") or "").strip(),

        "sector_focus_en": (row.get("sector_focus") or "").strip(),
        "eligible_org_type_en": (row.get("eligible_org_type") or "").strip(),
        "funding_range_en": (row.get("funding_range") or "").strip(),
        "deadline_cycle_en": (row.get("deadline_cycle") or "").strip(),
        "notes_en": (row.get("notes") or "").strip(),
        "funding_type_en": (row.get("funding_type") or "").strip(),
        "geography_en": (row.get("geography") or "").strip(),

        "cause_areas": clean_list(raw.get("cause_areas"), VOCAB["cause_areas"]),
        "regions": clean_list(raw.get("regions"), VOCAB["regions"]),
        "geo_scope": raw.get("geo_scope") if raw.get("geo_scope") in
                     ("local", "regional", "national", "international") else "national",
        "legal_status_required": clean_list(raw.get("legal_status_required"), VOCAB["legal_status"]),
        "accreditations_required": clean_list(raw.get("accreditations_required"), VOCAB["accreditations"]),
        "min_org_age_years": clean_int(raw.get("min_org_age_years"), 0, 100),
        "grant_min_eur": clean_int(raw.get("grant_min_eur"), 0),
        "grant_max_eur": clean_int(raw.get("grant_max_eur"), 0),
        "cofinancing_required_pct": clean_int(raw.get("cofinancing_required_pct"), 0, 100),
        "requires_english": bool(raw.get("requires_english")),
        "requires_partner_abroad": bool(raw.get("requires_partner_abroad")),
        "support_types": clean_list(raw.get("support_types"),
                                    ["grant", "in_kind", "volunteering", "matching", "loan", "support"]),
        "deadline_type": raw.get("deadline_type") if raw.get("deadline_type") in
                         ("annual", "periodic", "rolling", "one_off", "unknown") else "unknown",
        "complexity": raw.get("complexity") if raw.get("complexity") in ("low", "medium", "high") else "medium",

        "application_steps_en": [s for s in (raw.get("application_steps_en") or []) if isinstance(s, str)],
        "application_steps_fr": [s for s in (raw.get("application_steps_fr") or []) if isinstance(s, str)],
        "required_documents_en": [s for s in (raw.get("required_documents_en") or []) if isinstance(s, str)],
        "required_documents_fr": [s for s in (raw.get("required_documents_fr") or []) if isinstance(s, str)],
        "sector_focus_fr": raw.get("sector_focus_fr") or "",
        "eligible_org_type_fr": raw.get("eligible_org_type_fr") or "",
        "funding_range_fr": raw.get("funding_range_fr") or "",
        "deadline_cycle_fr": raw.get("deadline_cycle_fr") or "",
        "notes_fr": raw.get("notes_fr") or "",
        "summary_en": raw.get("summary_en") or "",
        "summary_fr": raw.get("summary_fr") or "",
        "_hash": row_hash(row),
    }
    record["amount_disclosed"] = record["grant_min_eur"] is not None or record["grant_max_eur"] is not None
    return record


def main():
    args = sys.argv[1:]
    force = "--all" in args
    limit = None
    if "--limit" in args:
        limit = int(args[args.index("--limit") + 1])

    rows = list(csv.DictReader(io.open(SOURCE, encoding="utf-8-sig")))
    existing = {}
    if os.path.exists(TARGET) and not force:
        for rec in json.load(io.open(TARGET, encoding="utf-8")):
            existing[rec["id"]] = rec

    output, done, skipped, failed = [], 0, 0, []
    for index, row in enumerate(rows, 1):
        rid = (row.get("id") or "").strip()
        previous = existing.get(rid)
        if previous and previous.get("_hash") == row_hash(row):
            output.append(previous)
            skipped += 1
            continue
        if limit is not None and done >= limit:
            if previous:
                output.append(previous)
            continue
        try:
            record = enrich_row(row)
            output.append(record)
            done += 1
            print("  [%2d/%d] %-14s %s" % (index, len(rows), rid, record["name"][:46]))
            time.sleep(2.0)  # free-tier rate limits are tight; pace deliberately
        except Exception as exc:
            failed.append((rid, repr(exc)[:120]))
            print("  [%2d/%d] %-14s FAILED %r" % (index, len(rows), rid, exc))
            if previous:
                output.append(previous)

    with io.open(TARGET, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(output, ensure_ascii=False, indent=1))

    print("\nenriched %d | reused %d | failed %d | total %d" %
          (done, skipped, len(failed), len(output)))
    for rid, err in failed:
        print("   FAILED %s: %s" % (rid, err))
    print("wrote %s" % TARGET)


if __name__ == "__main__":
    main()
