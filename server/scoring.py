# -*- coding: utf-8 -*-
"""
Deterministic compatibility scoring.

No LLM is involved here, by design: a charity deciding where to spend three weeks
of unpaid effort deserves a score it can interrogate. Every number this module
produces comes with the reason it was produced and what would change it.

Scale is 1-10. A hard-eligibility failure caps the score (never a silent low number).
"""
import datetime

CATEGORIES = ["corporate_funding", "private_funding", "csr_programs", "eu_grants", "french_grants"]

# Per-category weights: the five families genuinely reward different things.
# Each column sums to 1.0. `size` is deliberately light everywhere because only a
# handful of real records disclose an amount.
WEIGHTS = {
    "corporate_funding": {"theme": 0.38, "geo": 0.24, "eligibility": 0.20, "capacity": 0.08, "size": 0.05, "timing": 0.05},
    "private_funding":   {"theme": 0.40, "geo": 0.18, "eligibility": 0.22, "capacity": 0.10, "size": 0.05, "timing": 0.05},
    "csr_programs":      {"theme": 0.34, "geo": 0.26, "eligibility": 0.22, "capacity": 0.10, "size": 0.03, "timing": 0.05},
    "eu_grants":         {"theme": 0.24, "geo": 0.12, "eligibility": 0.16, "capacity": 0.40, "size": 0.04, "timing": 0.04},
    "french_grants":     {"theme": 0.28, "geo": 0.22, "eligibility": 0.32, "capacity": 0.10, "size": 0.04, "timing": 0.04},
}

HARD_FAIL_CAP = 3.0   # eligibility gate failed
SOFT_CAP = 6.5        # eligible, but something substantial is missing

REGION_ANY = ("national", "europe")


def _as_list(value):
    """Coerce anything to a list of strings. Profile data arrives from a browser
    and may be any JSON type; scoring must never raise on bad input."""
    if value is None or value == "":
        return []
    if isinstance(value, (list, tuple, set)):
        return [v for v in value if isinstance(v, (str, int, float))]
    if isinstance(value, dict):
        return [k for k in value.keys()]
    if isinstance(value, str):
        return [value]
    return []


def _as_number(value):
    """Return a finite float, or None. Never raises."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):  # NaN / inf
        return None
    return number


def _overlap(a, b):
    """Jaccard-ish overlap biased toward the funder's requirements being met."""
    sa, sb = set(_as_list(a)), set(_as_list(b))
    if not sb:
        return None          # funder states no preference -> dimension not applicable
    if not sa:
        return 0.0
    hit = len(sa & sb)
    if not hit:
        return 0.0
    # Proportion of the funder's priorities we actually cover. The floor is low on
    # purpose: matching 1 of 6 stated priorities is a weak match, not a good one.
    return min(1.0, 0.30 + 0.70 * (hit / float(len(sb))))


def _theme(profile, funder):
    score = _overlap(profile.get("cause_areas"), funder.get("cause_areas"))
    if score is None:
        # No stated priorities means we cannot verify a match, not that one exists.
        return 0.5, "This funder states no thematic restriction — fit unverified.", \
               "Ce financeur n'indique pas de restriction thématique — correspondance non vérifiée."
    shared = sorted(set(_as_list(profile.get("cause_areas"))) & set(_as_list(funder.get("cause_areas"))))
    if not shared:
        return 0.0, "None of your cause areas match this funder's priorities.", \
               "Aucun de vos domaines d'action ne correspond aux priorités de ce financeur."
    return score, "Shared priorities: %s." % ", ".join(shared), \
           "Priorités communes : %s." % ", ".join(shared)


def _geo(profile, funder):
    funder_regions = set(_as_list(funder.get("regions")))
    if not funder_regions:
        return 0.55, "No geography stated — could not be verified.", \
               "Aucune zone indiquée — non vérifiable."
    mine = set(_as_list(profile.get("regions")))
    if funder_regions & set(REGION_ANY):
        return 1.0, "Open across your territory.", "Ouvert sur l'ensemble de votre territoire."
    if not mine:
        return 0.5, "You haven't listed your regions, so this could not be checked.", \
               "Vous n'avez pas indiqué vos régions : vérification impossible."
    shared = mine & funder_regions
    if shared:
        return 1.0, "Covers your region.", "Couvre votre région."
    return 0.0, "This programme is limited to regions you don't operate in.", \
           "Ce programme est limité à des régions où vous n'intervenez pas."


def _eligibility(profile, funder):
    """Returns (score, blocking_reasons, notes). Blocking reasons cap the final score."""
    blocking, notes = [], []
    score = 1.0

    required_status = _as_list(funder.get("legal_status_required"))
    if required_status and profile.get("legal_status") not in required_status:
        blocking.append({
            "en": "Legal status: this funder requires %s." % ", ".join(required_status),
            "fr": "Statut juridique : ce financeur exige %s." % ", ".join(required_status),
        })

    required_accreditations = set(_as_list(funder.get("accreditations_required")))
    missing = required_accreditations - set(_as_list(profile.get("accreditations")))
    if missing:
        blocking.append({
            "en": "Missing required accreditation: %s." % ", ".join(sorted(missing)),
            "fr": "Agrément requis manquant : %s." % ", ".join(sorted(missing)),
        })

    min_age = _as_number(funder.get("min_org_age_years"))
    year = _as_number(profile.get("year_founded"))
    if min_age and year:
        age = datetime.date.today().year - int(year)
        if age < int(min_age):
            blocking.append({
                "en": "Organisation age: %d years required, you have %d." % (int(min_age), age),
                "fr": "Ancienneté : %d ans requis, vous en avez %d." % (int(min_age), age),
            })
        elif age < int(min_age) + 1:
            score -= 0.15
            notes.append({"en": "You only just meet the minimum age.",
                          "fr": "Vous atteignez tout juste l'ancienneté minimale."})

    if blocking:
        return 0.0, blocking, notes

    # Distinguish "we checked their conditions and you meet them" from
    # "they publish no conditions" - the second is weaker evidence, not equal.
    stated_anything = bool(required_status or required_accreditations or min_age)
    if not stated_anything:
        score = min(score, 0.72)
    return max(0.0, score), [], notes


def _capacity(profile, funder):
    """Can this organisation actually carry the administrative load?"""
    # Starts below 1.0: an unknown burden is not a proven-light burden.
    score, reasons_en, reasons_fr = 0.86, [], []

    need_pct = _as_number(funder.get("cofinancing_required_pct"))
    if need_pct:
        need_pct = max(0, min(100, int(need_pct)))
        have = _as_number(profile.get("cofinancing_capacity_pct"))
        have = 0 if have is None else max(0, min(100, int(have)))
        if have >= int(need_pct):
            score = min(1.0, score + 0.14)   # verified capability earns the top band
            reasons_en.append("You can cover the %d%% co-financing." % int(need_pct))
            reasons_fr.append("Vous pouvez couvrir les %d%% de cofinancement." % int(need_pct))
        else:
            gap = int(need_pct) - have
            score -= min(0.55, 0.1 + 0.045 * gap)
            reasons_en.append("Requires %d%% co-financing; you reported %d%%." % (int(need_pct), have))
            reasons_fr.append("Exige %d%% de cofinancement ; vous avez indiqué %d%%." % (int(need_pct), have))

    if funder.get("requires_english") and not profile.get("can_report_in_english"):
        score -= 0.30
        reasons_en.append("Application and reporting are in English.")
        reasons_fr.append("La candidature et le reporting se font en anglais.")

    if funder.get("requires_partner_abroad"):
        if (profile.get("grant_experience") or "") == "eu":
            reasons_en.append("A partner in another country is needed — your EU experience helps.")
            reasons_fr.append("Un partenaire étranger est requis — votre expérience européenne aide.")
        else:
            score -= 0.20
            reasons_en.append("Requires a partner organisation in another country.")
            reasons_fr.append("Exige une organisation partenaire dans un autre pays.")

    if funder.get("complexity") == "low":
        score = min(1.0, score + 0.10)

    complexity = funder.get("complexity") or "medium"
    experience = profile.get("grant_experience")
    if not isinstance(experience, str):
        experience = "none"
    ladder = {"none": 0, "local": 1, "national": 2, "eu": 3}
    demand = {"low": 0, "medium": 1, "high": 3}
    shortfall = demand.get(complexity, 1) - ladder.get(experience, 0)
    if shortfall > 0:
        penalty = 0.12 * shortfall
        if profile.get("has_grant_writer"):
            penalty *= 0.5
            reasons_en.append("Demanding paperwork, eased by having a dedicated fundraiser.")
            reasons_fr.append("Dossier exigeant, atténué par une personne dédiée à la recherche de fonds.")
        else:
            reasons_en.append("Paperwork is demanding relative to your grant experience.")
            reasons_fr.append("Le dossier est exigeant au regard de votre expérience.")
        score -= penalty

    if funder.get("complexity") == "high" and not profile.get("has_audited_accounts"):
        score -= 0.15
        reasons_en.append("Certified accounts are usually expected at this level.")
        reasons_fr.append("Des comptes certifiés sont généralement attendus à ce niveau.")

    return max(0.0, min(1.0, score)), reasons_en, reasons_fr


def _size(profile, funder):
    if not funder.get("amount_disclosed"):
        return None, "Amount not disclosed by this funder — not scored.", \
               "Montant non communiqué par ce financeur — non noté."
    want = _as_number(profile.get("amount_sought_eur"))
    if not want or want <= 0:
        return None, "You haven't stated an amount.", "Vous n'avez pas indiqué de montant."
    low = _as_number(funder.get("grant_min_eur"))
    high = _as_number(funder.get("grant_max_eur"))
    if low is not None and want < float(low):
        return 0.55, "You're asking below their usual minimum (%s EUR)." % format(int(low), ","), \
               "Votre demande est inférieure à leur minimum habituel (%s EUR)." % format(int(low), ",")
    if high is not None and want > float(high):
        return 0.25, "You're asking above their maximum (%s EUR)." % format(int(high), ","), \
               "Votre demande dépasse leur plafond (%s EUR)." % format(int(high), ",")
    return 1.0, "Your request sits inside their funding range.", \
           "Votre demande se situe dans leur fourchette de financement."


def _timing(funder):
    kind = funder.get("deadline_type")
    if not isinstance(kind, str):
        kind = "unknown"
    table = {
        "rolling": (1.0, "Applications accepted continuously.", "Candidatures acceptées en continu."),
        "annual": (0.75, "Runs on an annual cycle — timing matters.", "Cycle annuel — le calendrier compte."),
        "periodic": (0.8, "Several sessions per year.", "Plusieurs sessions par an."),
        "one_off": (0.5, "One-off call; check whether it is still open.", "Appel ponctuel ; vérifiez s'il est encore ouvert."),
    }
    return table.get(kind, (0.6, "Deadline cycle unclear — verify on the funder's site.",
                            "Calendrier peu clair — à vérifier sur le site du financeur."))


def score_opportunity(profile, funder, category=None):
    """Score one funder for one charity. Returns a fully explained result."""
    if not category:
        cats = _as_list(funder.get("categories"))
        category = cats[0] if cats else "corporate_funding"
    weights = WEIGHTS.get(category, WEIGHTS["corporate_funding"])

    theme, theme_en, theme_fr = _theme(profile, funder)
    geo, geo_en, geo_fr = _geo(profile, funder)
    elig, blocking, elig_notes = _eligibility(profile, funder)
    capacity, cap_en, cap_fr = _capacity(profile, funder)
    size, size_en, size_fr = _size(profile, funder)
    timing, timing_en, timing_fr = _timing(funder)

    parts = {"theme": theme, "geo": geo, "eligibility": elig, "capacity": capacity,
             "size": size, "timing": timing}

    # Dimensions that don't apply are dropped and their weight redistributed,
    # so a funder is never punished for information it simply doesn't publish.
    active = dict((k, v) for k, v in parts.items() if v is not None)
    total_weight = sum(weights[k] for k in active) or 1.0
    raw = sum(weights[k] * active[k] for k in active) / total_weight

    score = 1.0 + raw * 9.0

    # We are only as sure as our research on this funder. A "low" confidence record
    # should not present as a verified 9/10.
    score = 1.0 + (score - 1.0) * {
        "high": 1.0, "medium": 0.93, "low": 0.82, "low-for-small-orgs": 0.82,
    }.get(funder.get("confidence") or "medium", 0.93)

    if blocking:
        score = min(score, HARD_FAIL_CAP)
    elif theme == 0.0 or geo == 0.0:
        score = min(score, SOFT_CAP)

    breakdown = []
    labels = {
        "theme": ("Thematic fit", "Correspondance thématique"),
        "geo": ("Geographic fit", "Correspondance géographique"),
        "eligibility": ("Eligibility", "Éligibilité"),
        "capacity": ("Your capacity", "Votre capacité"),
        "size": ("Funding size", "Montant"),
        "timing": ("Timing", "Calendrier"),
    }
    texts = {
        "theme": (theme_en, theme_fr), "geo": (geo_en, geo_fr),
        "eligibility": ("All stated eligibility conditions are met." if not blocking
                        else "Blocking conditions found.",
                        "Toutes les conditions d'éligibilité sont remplies." if not blocking
                        else "Conditions bloquantes identifiées."),
        "capacity": ("; ".join(cap_en) or "No particular demands stated.",
                     "; ".join(cap_fr) or "Aucune exigence particulière."),
        "size": (size_en, size_fr), "timing": (timing_en, timing_fr),
    }
    for key in ["theme", "geo", "eligibility", "capacity", "size", "timing"]:
        breakdown.append({
            "key": key,
            "label": {"en": labels[key][0], "fr": labels[key][1]},
            "value": parts[key],
            "applicable": parts[key] is not None,
            "weight": weights[key],
            "text": {"en": texts[key][0], "fr": texts[key][1]},
        })

    return {
        "score": round(score, 1),
        "eligible": not blocking,
        "blocking": blocking,
        "notes": elig_notes,
        "breakdown": breakdown,
        "improvements": _improvements(profile, funder, parts, blocking),
    }


def _improvements(profile, funder, parts, blocking):
    """Concrete, honest next actions. Only ever suggests things that are actually true."""
    out = []
    for block in blocking:
        out.append({"en": block["en"], "fr": block["fr"], "blocking": True})

    need_pct = _as_number(funder.get("cofinancing_required_pct"))
    have_pct = _as_number(profile.get("cofinancing_capacity_pct")) or 0
    if need_pct and have_pct < int(need_pct):
        out.append({
            "en": "Secure co-financing up to %d%% — this is the single biggest lever here." % int(need_pct),
            "fr": "Sécuriser un cofinancement jusqu'à %d%% — c'est le levier le plus important ici." % int(need_pct),
            "blocking": False})
    if funder.get("requires_english") and not profile.get("can_report_in_english"):
        out.append({"en": "Arrange English-language capacity for the application and reporting.",
                    "fr": "Prévoir une capacité en anglais pour la candidature et le reporting.",
                    "blocking": False})
    if funder.get("complexity") == "high" and not profile.get("has_audited_accounts"):
        out.append({"en": "Have your accounts certified — expected at this funding level.",
                    "fr": "Faire certifier vos comptes — attendu à ce niveau de financement.",
                    "blocking": False})
    if parts.get("theme") == 0.0:
        out.append({"en": "Frame your project around this funder's stated priorities, or deprioritise it.",
                    "fr": "Reformuler votre projet selon les priorités affichées, ou le dépriorisier.",
                    "blocking": False})
    return out


def score_category(profile, funders, category):
    """Category score = weighted blend of its best matches, so one strong fit lifts the card."""
    scored = []
    for funder in funders:
        result = score_opportunity(profile, funder, category)
        scored.append((result["score"], funder, result))
    scored.sort(key=lambda item: item[0], reverse=True)

    if not scored:
        # No data is not a bad score - the UI shows an empty state instead of a number.
        return {"score": None, "count": 0, "eligible_count": 0, "top": []}

    # Quality is judged on opportunities the charity can actually pursue. A funder
    # that has barred them (missing accreditation, wrong legal status) is not a
    # worse prospect - it is not a prospect at all, and averaging its capped score
    # into the family would understate families the charity is genuinely strong in.
    # Depth below still reflects how many are open to them.
    usable = [item for item in scored if item[2]["eligible"]] or scored
    top = [s for s, _, _ in usable[:3]]
    if len(top) == 1:
        blended = top[0]
    elif len(top) == 2:
        blended = top[0] * 0.65 + top[1] * 0.35
    else:
        blended = top[0] * 0.5 + top[1] * 0.3 + top[2] * 0.2

    # Depth matters as much as peak quality: one strong match is a lead,
    # five is a strategy. Saturates at 5 so a huge category doesn't run away with it.
    eligible = sum(1 for _, _, r in scored if r["eligible"])  # depth counts only the open ones
    depth = 0.80 + 0.20 * min(1.0, eligible / 5.0)
    blended = 1.0 + (blended - 1.0) * depth

    return {
        "score": round(blended, 1),
        "count": len(scored),
        "eligible_count": sum(1 for _, _, r in scored if r["eligible"]),
        "top": [{"id": f.get("id"), "name": f.get("name"), "score": s} for s, f, _ in scored[:3]],
    }
