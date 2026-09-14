# -*- coding: utf-8 -*-
"""
Phundable — application server.

Serves the static frontend and a small JSON API. Python 3.9 compatible,
stdlib only apart from python-docx (used for document generation).

Run:
    .venv/bin/python server/server.py [port]     # default 8010
"""
import datetime
import io
import json
import os
import posixpath
import sys
import traceback
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, unquote

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import catalog        # noqa: E402
import scoring        # noqa: E402
import docgen         # noqa: E402
import llm            # noqa: E402

PUBLIC_DIR = os.path.join(os.path.dirname(HERE), "public")
CONFIG_FILE = os.path.join(HERE, "config", "onboarding_fields.json")


def _load_config():
    with io.open(CONFIG_FILE, encoding="utf-8") as handle:
        return json.load(handle)


def _all_fields():
    for step in _load_config()["steps"]:
        for field in step["fields"]:
            yield field


def _required_field_ids():
    return [f["id"] for f in _all_fields() if f.get("required")]


def _finite(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number


def _validate_profile(profile):
    """Type- and range-check against the onboarding config.

    Presence alone is not enough: a browser (or a curl) can send any JSON type,
    and bad values would otherwise reach scoring and document generation.
    Returns a list of {field, problem} - empty when the profile is sound.
    """
    if not isinstance(profile, dict):
        return [{"field": "_root", "problem": "not_an_object"}]

    errors = []
    for field in _all_fields():
        fid = field["id"]
        if fid not in profile:
            continue
        value = profile[fid]
        if value in (None, "", [], {}):
            continue
        kind = field.get("type", "text")
        options = [o["value"] for o in field.get("options", [])]

        if kind in ("text", "textarea"):
            if not isinstance(value, str):
                errors.append({"field": fid, "problem": "expected_text"})
            elif field.get("maxlength") and len(value) > int(field["maxlength"]) * 2:
                errors.append({"field": fid, "problem": "too_long"})
        elif kind == "number":
            number = _finite(value)
            if number is None:
                errors.append({"field": fid, "problem": "expected_number"})
            elif field.get("min") is not None and number < float(field["min"]):
                errors.append({"field": fid, "problem": "below_min"})
            elif field.get("max") is not None and number > float(field["max"]):
                errors.append({"field": fid, "problem": "above_max"})
        elif kind == "boolean":
            if not isinstance(value, bool):
                errors.append({"field": fid, "problem": "expected_boolean"})
        elif kind == "select":
            if not isinstance(value, str) or (options and value not in options):
                errors.append({"field": fid, "problem": "not_an_option"})
        elif kind == "multiselect":
            if not isinstance(value, list):
                errors.append({"field": fid, "problem": "expected_list"})
            elif options and any(v not in options for v in value):
                errors.append({"field": fid, "problem": "unknown_option"})
    return errors


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=PUBLIC_DIR, **kwargs)

    def log_message(self, fmt, *args):
        sys.stderr.write("[phenix] " + (fmt % args) + "\n")

    # ---------- helpers ----------
    def _json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except ValueError:
            return None

    def _profile_or_error(self):
        profile = catalog.read_profile()
        if not profile:
            self._json(404, {"error": "no_profile",
                             "message": {"en": "Complete the onboarding first.",
                                         "fr": "Complétez d'abord l'onboarding."}})
            return None
        return profile

    def _admin_authorized(self):
        """Gate /api/admin/overview behind HTTP Basic Auth when credentials are
        configured (ADMIN_USER / ADMIN_PASS env vars). Left open when they are
        not set, so local development is unaffected."""
        expected_user = os.environ.get("ADMIN_USER")
        expected_pass = os.environ.get("ADMIN_PASS")
        if not expected_user or not expected_pass:
            return True
        header = self.headers.get("Authorization", "")
        if not header.startswith("Basic "):
            return False
        try:
            import base64
            decoded = base64.b64decode(header[6:]).decode("utf-8")
            user, _, password = decoded.partition(":")
        except Exception:
            return False
        return user == expected_user and password == expected_pass

    def _require_admin_auth(self):
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="admin"')
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps({"error": "unauthorized"}).encode("utf-8"))

    # ---------- GET ----------
    def do_GET(self):
        path = urlparse(self.path).path
        try:
            if path == "/api/health":
                return self._json(200, {
                    "ok": True,
                    "catalogue": catalog.catalogue_status(),
                    "profile": bool(catalog.read_profile()),
                    "llm": llm.health(),
                })
            if path == "/api/config/onboarding":
                with io.open(CONFIG_FILE, encoding="utf-8") as handle:
                    return self._json(200, json.load(handle))
            if path == "/api/profile":
                profile = catalog.read_profile()
                return self._json(200, {"profile": profile, "complete": bool(profile)})
            if path == "/api/admin/overview":
                if not self._admin_authorized():
                    return self._require_admin_auth()
                return self._admin_overview()
            if path == "/api/partners":
                return self._json(200, {"partners": catalog.partner_list()})
            if path == "/api/families":
                return self._families()
            if path == "/api/categories":
                return self._categories()
            if path.startswith("/api/categories/"):
                return self._opportunities(unquote(path.split("/api/categories/", 1)[1]))
            if path.startswith("/api/opportunities/"):
                return self._opportunity(unquote(path.split("/api/opportunities/", 1)[1]))
            if path.startswith("/api/documents/"):
                return self._download(unquote(path.split("/api/documents/", 1)[1]))
            if path.startswith("/api/"):
                return self._json(404, {"error": "unknown_endpoint"})
        except Exception:
            traceback.print_exc()
            return self._json(500, {"error": "server_error"})

        # SPA: unknown non-file routes fall back to index.html
        candidate = os.path.join(PUBLIC_DIR, posixpath.normpath(path).lstrip("/"))
        if path != "/" and not os.path.exists(candidate):
            self.path = "/index.html"
        return super().do_GET()

    # ---------- POST ----------
    def do_POST(self):
        path = urlparse(self.path).path
        try:
            if path == "/api/profile":
                return self._save_profile()
            if path == "/api/company-signup":
                return self._company_signup()
            if path.startswith("/api/documents/"):
                return self._generate(unquote(path.split("/api/documents/", 1)[1]))
            return self._json(404, {"error": "unknown_endpoint"})
        except Exception:
            traceback.print_exc()
            return self._json(500, {"error": "server_error"})

    # ---------- endpoints ----------
    def _save_profile(self):
        data = self._body()
        if data is None:
            return self._json(400, {"error": "invalid_json"})
        profile = data.get("profile", data)
        if not isinstance(profile, dict):
            return self._json(400, {"error": "invalid_profile"})

        missing = [f for f in _required_field_ids()
                   if profile.get(f) in (None, "", [], {})]
        if missing:
            return self._json(400, {"error": "missing_fields", "fields": missing})

        invalid = _validate_profile(profile)
        if invalid:
            return self._json(400, {"error": "invalid_fields", "fields": invalid})

        # Persist only fields the configuration declares, so unknown keys from a
        # tampered client never reach scoring or the document templates.
        known = set(f["id"] for f in _all_fields())
        catalog.write_profile(dict((k, v) for k, v in profile.items() if k in known))
        return self._json(200, {"ok": True, "profile": profile})

    def _admin_overview(self):
        """Internal commercial view: active listings plus the inbound pipeline.

        Deliberately unauthenticated for the prototype and not linked from the
        public navigation. Do not expose this on a real deployment as-is.
        """
        signups = catalog.read_signups()
        by_status = {}
        by_size = {}
        for row in signups:
            status = row.get("status") or "new"
            by_status[status] = by_status.get(status, 0) + 1
            size = row.get("org_size") or "unknown"
            by_size[size] = by_size.get(size, 0) + 1
        # newest first
        ordered = sorted(signups, key=lambda r: r.get("received_at", ""), reverse=True)
        return self._json(200, {
            "partners": catalog.partner_list(),
            "signups": ordered,
            "summary": {
                "partners": len(catalog.partner_list()),
                "requests": len(signups),
                "by_status": by_status,
                "by_size": by_size,
            },
        })

    def _company_signup(self):
        """Records a company's interest in a listing. Deliberately takes no
        payment details: card data must never pass through this application."""
        data = self._body()
        if data is None:
            return self._json(400, {"error": "invalid_json"})

        fields = {}
        for key in ("company", "contact_name", "email", "org_size", "phone",
                    "programme", "message"):
            value = data.get(key)
            fields[key] = value.strip() if isinstance(value, str) else ""

        missing = [k for k in ("company", "contact_name", "email") if not fields[k]]
        if missing:
            return self._json(400, {"error": "missing_fields", "fields": missing})
        if "@" not in fields["email"] or "." not in fields["email"].split("@")[-1]:
            return self._json(400, {"error": "invalid_email"})
        for key, value in fields.items():
            if len(value) > 2000:
                return self._json(400, {"error": "too_long", "field": key})

        record = dict(fields)
        record["status"] = "new"
        record["received_at"] = datetime.datetime.now(
            datetime.timezone.utc).isoformat(timespec="seconds")
        # No price is recorded: pricing is quoted per organisation after contact.
        catalog.add_signup(record)
        return self._json(200, {"ok": True})

    def _families(self):
        """Public counts for the landing page - deliberately needs no profile."""
        out = []
        for category in catalog.CATEGORY_ORDER:
            out.append({
                "id": category,
                "label": catalog.CATEGORY_LABELS[category],
                "blurb": catalog.CATEGORY_BLURB[category],
                "count": len(catalog.funders_in(category)),
            })
        return self._json(200, {
            "families": out,
            "total": catalog.catalogue_status()["total"],
            "documents": len(docgen.available_documents()),
        })

    def _categories(self):
        profile = self._profile_or_error()
        if profile is None:
            return
        out = []
        for category in catalog.CATEGORY_ORDER:
            funders = catalog.funders_in(category)
            result = scoring.score_category(profile, funders, category)
            result.update({
                "id": category,
                "label": catalog.CATEGORY_LABELS[category],
                "blurb": catalog.CATEGORY_BLURB[category],
                "partner_count": sum(1 for f in funders if f.get("is_partner")),
            })
            out.append(result)
        # Empty categories (score None) sort last rather than breaking the comparison.
        out.sort(key=lambda c: (c["score"] is not None, c["score"] or 0), reverse=True)
        return self._json(200, {"categories": out})

    def _opportunities(self, category):
        if category not in catalog.CATEGORY_ORDER:
            return self._json(404, {"error": "unknown_category"})
        profile = self._profile_or_error()
        if profile is None:
            return
        items = []
        for funder in catalog.funders_in(category):
            result = scoring.score_opportunity(profile, funder, category)
            items.append({
                "id": funder["id"],
                "name": funder["name"],
                "organization": funder.get("organization", ""),
                "summary": {"en": funder.get("summary_en", ""), "fr": funder.get("summary_fr", "")},
                "confidence": funder.get("confidence", ""),
                "deadline_type": funder.get("deadline_type", "unknown"),
                "amount_disclosed": funder.get("amount_disclosed", False),
                "funding_range": {"en": funder.get("funding_range_en", ""),
                                  "fr": funder.get("funding_range_fr", "")},
                "score": result["score"],
                "eligible": result["eligible"],
                "blocking_count": len(result["blocking"]),
                "is_partner": funder.get("is_partner", False),
                "partner_logo": funder.get("partner_logo", ""),
                "partner_name": funder.get("partner_name", ""),
            })
        items.sort(key=lambda i: i["score"], reverse=True)
        return self._json(200, {
            "category": {"id": category, "label": catalog.CATEGORY_LABELS[category],
                         "blurb": catalog.CATEGORY_BLURB[category]},
            "opportunities": items,
        })

    def _opportunity(self, funder_id):
        funder = catalog.get_funder(funder_id)
        if not funder:
            return self._json(404, {"error": "unknown_opportunity"})
        profile = self._profile_or_error()
        if profile is None:
            return
        category = (funder.get("categories") or ["corporate_funding"])[0]
        result = scoring.score_opportunity(profile, funder, category)
        return self._json(200, {
            "funder": funder,
            "scoring": result,
            "documents": docgen.available_documents(),
        })

    def _generate(self, doc_type):
        profile = self._profile_or_error()
        if profile is None:
            return
        data = self._body() or {}
        funder = catalog.get_funder(data.get("opportunity_id", ""))
        if not funder:
            return self._json(400, {"error": "unknown_opportunity"})
        lang = data.get("lang") if data.get("lang") in ("en", "fr") else "fr"
        try:
            result = docgen.generate(doc_type, profile, funder, lang)
        except docgen.UnknownDocument:
            return self._json(404, {"error": "unknown_document_type"})
        return self._json(200, result)

    def _download(self, filename):
        safe = os.path.basename(filename)
        path = os.path.join(docgen.OUTPUT_DIR, safe)
        if not os.path.exists(path):
            return self._json(404, {"error": "not_found"})
        with open(path, "rb") as handle:
            blob = handle.read()
        self.send_response(200)
        self.send_header("Content-Type",
                         "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        self.send_header("Content-Disposition", 'attachment; filename="%s"' % safe)
        self.send_header("Content-Length", str(len(blob)))
        self.end_headers()
        self.wfile.write(blob)


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("PORT", 8010))
    status = catalog.catalogue_status()
    print("[phenix] catalogue: %d funders %s" % (status["total"], status["per_category"]))
    if not status["enriched_present"]:
        print("[phenix] WARNING: no enriched data. Run: .venv/bin/python tools/enrich.py --all")
    if not (os.environ.get("ADMIN_USER") and os.environ.get("ADMIN_PASS")):
        print("[phenix] WARNING: ADMIN_USER/ADMIN_PASS not set — /api/admin/overview is unauthenticated")
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print("[phenix] http://localhost:%d" % port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[phenix] shutting down")
        server.shutdown()


if __name__ == "__main__":
    main()
