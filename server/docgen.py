# -*- coding: utf-8 -*-
"""
Application-document generation, styled in the Phenix brand.

Three documents are AI-drafted (cover letter, project summary, eligibility
narrative) and three are pure templates (org one-pager, budget, checklist).

The model is a drafting assistant, never a source of facts: prompts carry only
the charity's own onboarding answers and the funder's record, with explicit
instructions never to invent. If the API is unavailable the document is still
produced from template prose, flagged in the response, so a demo never fails.
"""
import datetime
import io
import os
import re
import unicodedata

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor, Cm

import llm

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "generated")

BRAND_RED = RGBColor(0xF7, 0x40, 0x39)
BRAND_DARK = RGBColor(0x31, 0x02, 0x00)
BODY_GREY = RGBColor(0x3C, 0x34, 0x31)

DOCUMENTS = {
    "cover_letter":   {"en": "Cover letter",          "fr": "Lettre de motivation",     "ai": True},
    "project_summary": {"en": "Project summary",      "fr": "Note de présentation",     "ai": True},
    "eligibility_narrative": {"en": "Eligibility responses", "fr": "Réponses aux critères", "ai": True},
    "org_one_pager":  {"en": "Organisation profile",  "fr": "Fiche organisation",       "ai": False},
    "budget":         {"en": "Budget outline",        "fr": "Budget prévisionnel",      "ai": False},
    "checklist":      {"en": "Application checklist", "fr": "Checklist de candidature",  "ai": False},
}

# Two notices: only documents whose prose came from the model may say so.
DRAFT_NOTICE = {
    "en": "AI-assisted draft — review every figure and claim before submitting.",
    "fr": "Brouillon assisté par IA — vérifiez chaque chiffre et affirmation avant l'envoi.",
}
TEMPLATE_NOTICE = {
    "en": "Auto-filled from your profile — review and complete before submitting.",
    "fr": "Pré-rempli depuis votre profil — à vérifier et compléter avant l'envoi.",
}


class UnknownDocument(Exception):
    pass


def available_documents():
    return [{"type": k, "label": {"en": v["en"], "fr": v["fr"]}, "ai": v["ai"]}
            for k, v in DOCUMENTS.items()]


# --------------------------------------------------------------------------
# profile helpers
# --------------------------------------------------------------------------
def _val(profile, key, default=""):
    value = profile.get(key)
    if value in (None, "", [], {}):
        return default
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return value


def _fval(funder, key, default=""):
    """funder.get(key, default) returns None when the key exists but is null,
    which then blows up string formatting. This treats null as missing."""
    value = funder.get(key)
    if value is None or value == "":
        return default
    return value


def _money(value):
    try:
        return "{:,}".format(int(float(value))).replace(",", " ") + " EUR"
    except (TypeError, ValueError):
        return "—"


def _facts_block(profile, funder, lang):
    """Everything the model is allowed to know. Nothing else may appear in output."""
    lines = [
        "ORGANISATION",
        "- name: %s" % _val(profile, "org_name"),
        "- legal status: %s" % _val(profile, "legal_status"),
        "- accreditations: %s" % _val(profile, "accreditations", "none stated"),
        "- founded: %s" % _val(profile, "year_founded"),
        "- mission: %s" % _val(profile, "mission_statement"),
        "- cause areas: %s" % _val(profile, "cause_areas"),
        "- people served per year: %s" % _val(profile, "beneficiaries_per_year", "not stated"),
        "- target groups: %s" % _val(profile, "target_groups", "not stated"),
        "- annual budget (EUR): %s" % _val(profile, "annual_budget_eur", "not stated"),
        "- paid staff: %s" % _val(profile, "employees_count", "not stated"),
        "- volunteers: %s" % _val(profile, "volunteers_count", "not stated"),
        "- regions: %s" % _val(profile, "regions", "not stated"),
        "",
        "PROJECT",
        "- title: %s" % _val(profile, "project_title"),
        "- description: %s" % _val(profile, "project_description"),
        "- amount sought (EUR): %s" % _val(profile, "amount_sought_eur"),
        "- duration (months): %s" % _val(profile, "project_duration_months", "not stated"),
        "",
        "FUNDER",
        "- name: %s" % _fval(funder, "name", ""),
        "- organisation: %s" % _fval(funder, "organization", ""),
        "- priorities: %s" % _fval(funder, "sector_focus_en", ""),
        "- who they fund: %s" % _fval(funder, "eligible_org_type_en", ""),
        "- funding offered: %s" % _fval(funder, "funding_range_en", "not disclosed"),
        "- notes: %s" % _fval(funder, "notes_en", ""),
    ]
    return "\n".join(lines)


SYSTEM_PROMPT = {
    "fr": u"""Tu rédiges des documents de demande de subvention pour des associations françaises.
Registre professionnel, sobre, sans superlatifs ni formules creuses.

RÈGLES ABSOLUES :
1. N'utilise QUE les faits fournis. N'invente jamais un chiffre, une date, un partenaire,
   une récompense, un résultat passé ou une référence.
2. Ne fusionne jamais deux faits distincts en une seule affirmation (si l'association est
   créée en 2019 et possède un agrément, n'écris pas qu'elle a l'agrément depuis 2019).
3. Si une information manque, écris le texte sans elle. N'écris jamais de marqueur du type
   [à compléter] sauf si on te le demande explicitement.
4. Réponds uniquement avec le texte du document, sans titre, sans commentaire, sans balises.
5. Rédige TOUJOURS en français, quelle que soit la langue des informations fournies.""",
    "en": u"""You draft grant application documents for charities.
Professional, restrained register. No superlatives, no filler.

ABSOLUTE RULES:
1. Use ONLY the facts provided. Never invent a figure, date, partner, award, past result
   or reference.
2. Never merge two separate facts into one claim (if the charity was founded in 2019 and
   holds an accreditation, do not write that it has held the accreditation since 2019).
3. If something is missing, write around it. Never emit placeholders like [to complete]
   unless explicitly asked.
4. Reply with the document text only — no title, no commentary, no markup.
5. ALWAYS write in English, whatever language the supplied information is in.""",
}

TASKS = {
    "cover_letter": {
        "fr": u"""Rédige une lettre de motivation pour cette demande de financement.
Structure : formule d'appel, un paragraphe de présentation de l'association, un paragraphe
sur le projet et le montant demandé, un paragraphe reliant le projet aux priorités du
financeur, formule de politesse. 350 à 450 mots.""",
        "en": u"""Write a cover letter for this funding request.
Structure: salutation, one paragraph introducing the organisation, one on the project and
the amount requested, one connecting the project to the funder's stated priorities, closing.
350-450 words.""",
    },
    "project_summary": {
        "fr": u"""Rédige une note de présentation du projet.
Sections, chacune en un paragraphe, précédée de son titre sur sa propre ligne :
Contexte et besoin / Objectifs / Public bénéficiaire / Mise en oeuvre / Résultats attendus.
N'invente aucun indicateur chiffré qui ne figure pas dans les faits fournis. 400 à 550 mots.""",
        "en": u"""Write a project summary note.
Sections, one paragraph each, each preceded by its title on its own line:
Context and need / Objectives / Beneficiaries / Implementation / Expected results.
Invent no numeric indicator absent from the supplied facts. 400-550 words.""",
    },
    "eligibility_narrative": {
        "fr": u"""Rédige les réponses aux critères d'éligibilité de ce financeur.
Pour chaque exigence identifiable dans la section FUNDER, écris le critère sur une ligne,
puis un court paragraphe expliquant comment l'association y répond, en t'appuyant uniquement
sur les faits fournis. Si un critère n'est manifestement pas rempli, dis-le honnêtement et
sobrement plutôt que de le contourner. 300 à 450 mots.""",
        "en": u"""Write responses to this funder's eligibility criteria.
For each requirement identifiable in the FUNDER section, put the criterion on one line,
then a short paragraph explaining how the organisation meets it, using only the supplied
facts. If a criterion is clearly not met, say so honestly and plainly rather than evading it.
300-450 words.""",
    },
}


LANGUAGE_DIRECTIVE = {
    "fr": u"LANGUE DE SORTIE : FRANÇAIS. Rédige l'intégralité du document en français, "
          u"même si les informations ci-dessous sont rédigées en anglais — dans ce cas, "
          u"traduis-les. N'utilise aucune autre langue.",
    "en": u"OUTPUT LANGUAGE: ENGLISH. Write the entire document in English, even if the "
          u"information below is written in French — in that case, translate it. "
          u"Do not use any other language.",
}


def _draft(doc_type, profile, funder, lang):
    """Returns (text, used_ai, warning_or_None)."""
    task = TASKS[doc_type][lang]
    facts = _facts_block(profile, funder, lang)
    user = "%s\n\n%s\n\n--- FACTS (the only information you may use) ---\n%s\n\n%s" % (
        LANGUAGE_DIRECTIVE[lang], task, facts, LANGUAGE_DIRECTIVE[lang])
    try:
        return llm.chat(SYSTEM_PROMPT[lang], user, temperature=0.35, max_tokens=1800), True, None
    except llm.LLMUnavailable as exc:
        fallback = {
            "fr": u"[Génération IA indisponible — texte de substitution]\n\n"
                  u"%s sollicite un financement de %s auprès de %s pour le projet « %s ».\n\n%s\n\n"
                  u"Merci de compléter et de personnaliser ce document avant envoi." % (
                      _val(profile, "org_name"), _money(profile.get("amount_sought_eur")),
                      _fval(funder, "name", ""), _val(profile, "project_title"),
                      _val(profile, "project_description")),
            "en": u"[AI generation unavailable — fallback text]\n\n"
                  u"%s is requesting %s from %s for the project \"%s\".\n\n%s\n\n"
                  u"Please complete and personalise this document before sending." % (
                      _val(profile, "org_name"), _money(profile.get("amount_sought_eur")),
                      _fval(funder, "name", ""), _val(profile, "project_title"),
                      _val(profile, "project_description")),
        }[lang]
        return fallback, False, str(exc)


# --------------------------------------------------------------------------
# docx construction
# --------------------------------------------------------------------------
def _new_document():
    document = Document()
    style = document.styles["Normal"]
    style.font.name = "Arial"          # Ambit is not installed on readers' machines
    style.font.size = Pt(10.5)
    style.font.color.rgb = BODY_GREY
    for section in document.sections:
        section.top_margin = Cm(2.2)
        section.bottom_margin = Cm(2.2)
        section.left_margin = Cm(2.4)
        section.right_margin = Cm(2.4)
    return document


def _title(document, text, subtitle=None):
    paragraph = document.add_paragraph()
    run = paragraph.add_run("PHENIX")
    run.bold = True
    run.font.size = Pt(9)
    run.font.color.rgb = BRAND_RED

    paragraph = document.add_paragraph()
    run = paragraph.add_run(text)
    run.bold = True
    run.font.size = Pt(19)
    run.font.color.rgb = BRAND_DARK
    paragraph.space_after = Pt(4)

    if subtitle:
        paragraph = document.add_paragraph()
        run = paragraph.add_run(subtitle)
        run.font.size = Pt(10)
        run.font.color.rgb = RGBColor(0x66, 0x66, 0x66)
        paragraph.space_after = Pt(14)


def _heading(document, text):
    paragraph = document.add_paragraph()
    run = paragraph.add_run(text)
    run.bold = True
    run.font.size = Pt(11.5)
    run.font.color.rgb = BRAND_DARK
    paragraph.space_before = Pt(12)
    paragraph.space_after = Pt(3)


def _body(document, text):
    for block in [b.strip() for b in text.split("\n") if b.strip()]:
        # A short line with no terminal punctuation is a section title from the model.
        if len(block) < 64 and not block.endswith((".", "!", "?", ":", ";", ",")):
            _heading(document, block)
            continue
        paragraph = document.add_paragraph(block)
        paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        paragraph.space_after = Pt(7)


def _footer_notice(document, lang, ai_warning=None, ai_used=True):
    document.add_paragraph()
    paragraph = document.add_paragraph()
    run = paragraph.add_run((DRAFT_NOTICE if ai_used else TEMPLATE_NOTICE)[lang])
    run.italic = True
    run.font.size = Pt(8.5)
    run.font.color.rgb = RGBColor(0x66, 0x66, 0x66)
    if ai_warning:
        paragraph = document.add_paragraph()
        run = paragraph.add_run(
            {"fr": "Service IA indisponible lors de la génération : %s",
             "en": "AI service unavailable during generation: %s"}[lang] % ai_warning[:120])
        run.italic = True
        run.font.size = Pt(8)
        run.font.color.rgb = BRAND_RED


def _kv_table(document, rows):
    table = document.add_table(rows=0, cols=2)
    table.style = "Table Grid"
    for label, value in rows:
        cells = table.add_row().cells
        cells[0].text = label
        cells[1].text = "" if value is None else str(value)
        for paragraph in cells[0].paragraphs:
            for run in paragraph.runs:
                run.bold = True
                run.font.size = Pt(9.5)
        for paragraph in cells[1].paragraphs:
            for run in paragraph.runs:
                run.font.size = Pt(9.5)
    return table


# --------------------------------------------------------------------------
# the six documents
# --------------------------------------------------------------------------
def _build_ai_document(doc_type, profile, funder, lang):
    text, used_ai, warning = _draft(doc_type, profile, funder, lang)
    document = _new_document()
    _title(document,
           DOCUMENTS[doc_type][lang],
           "%s — %s" % (_val(profile, "org_name"), _fval(funder, "name", "")))
    _body(document, text)
    _footer_notice(document, lang, warning, ai_used=used_ai)
    return document, used_ai, warning


def _build_org_one_pager(profile, funder, lang):
    document = _new_document()
    _title(document, DOCUMENTS["org_one_pager"][lang], _val(profile, "org_name"))
    labels = {
        "fr": [("Nom", "org_name"), ("Statut juridique", "legal_status"), ("Agréments", "accreditations"),
               ("SIRET / RNA", "siret_rna"), ("Année de création", "year_founded"), ("Site internet", "website"),
               ("Domaines d'action", "cause_areas"), ("Publics", "target_groups"),
               ("Bénéficiaires / an", "beneficiaries_per_year"), ("Salariés", "employees_count"),
               ("Bénévoles", "volunteers_count"), ("Régions", "regions")],
        "en": [("Name", "org_name"), ("Legal status", "legal_status"), ("Accreditations", "accreditations"),
               ("SIRET / RNA", "siret_rna"), ("Founded", "year_founded"), ("Website", "website"),
               ("Cause areas", "cause_areas"), ("Target groups", "target_groups"),
               ("Beneficiaries / year", "beneficiaries_per_year"), ("Paid staff", "employees_count"),
               ("Volunteers", "volunteers_count"), ("Regions", "regions")],
    }[lang]
    _kv_table(document, [(label, _val(profile, key, "—")) for label, key in labels])
    _heading(document, {"fr": "Mission", "en": "Mission"}[lang])
    _body(document, _val(profile, "mission_statement", "—"))
    budget_label = {"fr": "Budget annuel", "en": "Annual budget"}[lang]
    _heading(document, budget_label)
    document.add_paragraph(_money(profile.get("annual_budget_eur")))
    _footer_notice(document, lang, ai_used=False)
    return document, False, None


def _build_budget(profile, funder, lang):
    document = _new_document()
    _title(document, DOCUMENTS["budget"][lang],
           "%s — %s" % (_val(profile, "project_title"), _fval(funder, "name", "")))
    try:
        sought = float(profile.get("amount_sought_eur") or 0)
    except (TypeError, ValueError):
        sought = 0.0
    cofinancing_pct = funder.get("cofinancing_required_pct")
    own = sought * (float(cofinancing_pct) / 100.0) if cofinancing_pct else 0.0
    total = sought + own

    headers = {"fr": ("Poste", "Montant (EUR)"), "en": ("Line", "Amount (EUR)")}[lang]
    rows = {
        "fr": [("Montant demandé à " + _fval(funder, "name", "ce financeur"), _money(sought)),
               ("Cofinancement / fonds propres", _money(own) if own else "—"),
               ("Coût total du projet", _money(total))],
        "en": [("Requested from " + _fval(funder, "name", "this funder"), _money(sought)),
               ("Co-financing / own funds", _money(own) if own else "—"),
               ("Total project cost", _money(total))],
    }[lang]
    _kv_table(document, [headers] + rows)

    note = {
        "fr": u"Ce budget est une trame. Détaillez vos postes de dépenses (personnel, "
              u"logistique, équipement, frais de structure) avant de l'envoyer.",
        "en": u"This budget is an outline. Break down your cost lines (staff, logistics, "
              u"equipment, overheads) before sending it.",
    }[lang]
    if cofinancing_pct:
        note += {
            "fr": u" Ce financeur exige %s%% de cofinancement." % cofinancing_pct,
            "en": u" This funder requires %s%% co-financing." % cofinancing_pct,
        }[lang]
    _heading(document, {"fr": "Note", "en": "Note"}[lang])
    _body(document, note)
    _footer_notice(document, lang, ai_used=False)
    return document, False, None


def _build_checklist(profile, funder, lang):
    document = _new_document()
    _title(document, DOCUMENTS["checklist"][lang],
           "%s — %s" % (_val(profile, "org_name"), _fval(funder, "name", "")))

    documents = funder.get("required_documents_%s" % lang) or funder.get("required_documents_en") or []
    steps = funder.get("application_steps_%s" % lang) or funder.get("application_steps_en") or []

    # Which required documents can we already say the charity has?
    have_signals = {
        "accounts": bool(profile.get("has_audited_accounts")),
        "comptes": bool(profile.get("has_audited_accounts")),
    }

    _heading(document, {"fr": "Documents à réunir", "en": "Documents to gather"}[lang])
    if documents:
        for item in documents:
            mark = "[ ]"
            lowered = item.lower()
            for token, present in have_signals.items():
                if token in lowered and present:
                    mark = "[x]"
            document.add_paragraph("%s  %s" % (mark, item))
    else:
        document.add_paragraph({"fr": "Non précisé par le financeur — vérifiez sur son site.",
                                "en": "Not specified by the funder — check their website."}[lang])

    _heading(document, {"fr": "Étapes de candidature", "en": "Application steps"}[lang])
    if steps:
        for index, step in enumerate(steps, 1):
            document.add_paragraph("%d.  %s" % (index, step))
    else:
        document.add_paragraph({"fr": "Non précisées — consultez le site officiel.",
                                "en": "Not specified — see the official site."}[lang])

    link = funder.get("official_link") or ""
    if link:
        _heading(document, {"fr": "Lien officiel", "en": "Official link"}[lang])
        document.add_paragraph(link)
    _footer_notice(document, lang, ai_used=False)
    return document, False, None


BUILDERS = {
    "org_one_pager": _build_org_one_pager,
    "budget": _build_budget,
    "checklist": _build_checklist,
}


def _slug(text):
    """Filename-safe slug that keeps accented letters legible: é -> e, not dropped."""
    plain = unicodedata.normalize("NFKD", str(text or ""))
    plain = "".join(c for c in plain if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", plain.lower()).strip("-")[:40] or "doc"


def generate(doc_type, profile, funder, lang="fr"):
    if doc_type not in DOCUMENTS:
        raise UnknownDocument(doc_type)
    if not os.path.isdir(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    if doc_type in BUILDERS:
        document, used_ai, warning = BUILDERS[doc_type](profile, funder, lang)
    else:
        document, used_ai, warning = _build_ai_document(doc_type, profile, funder, lang)

    filename = "%s_%s_%s_%s.docx" % (
        _slug(profile.get("org_name")), doc_type, _slug(_fval(funder, "id")), lang)
    document.save(os.path.join(OUTPUT_DIR, filename))
    return {
        "ok": True,
        "filename": filename,
        "url": "/api/documents/%s" % filename,
        "label": {"en": DOCUMENTS[doc_type]["en"], "fr": DOCUMENTS[doc_type]["fr"]},
        "ai_used": used_ai,
        "ai_warning": warning,
        "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
