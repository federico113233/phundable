import { el, mount, scoreBar, scoreBadge, loading } from "../dom.js";
import { t, pick, lang } from "../i18n.js";
import { api } from "../api.js";

export async function renderDetail(opportunityId, go) {
  mount(loading());
  let data;
  try {
    data = await api.opportunity(opportunityId);
  } catch (err) {
    if (err.status === 404) return go("#/");
    return mount(el("div", { class: "page container" },
      el("div", { class: "banner banner-err" }, t("common.error"))));
  }

  const f = data.funder;
  const s = data.scoring;
  const L = lang();
  const steps = f[`application_steps_${L}`] || f.application_steps_en || [];
  const docs = f[`required_documents_${L}`] || f.required_documents_en || [];

  // ---- scoring panel ----
  const dims = s.breakdown.map((d) =>
    el("div", { class: `dim${d.applicable ? "" : " na"}` },
      el("div", { class: "dim-top" },
        el("span", { class: "dim-name" }, pick(d.label)),
        el("span", { class: "dim-val" },
          d.applicable ? `${Math.round(d.value * 100)}%` : t("score.na"))),
      d.applicable ? scoreBar(d.value * 10) : null,
      el("p", { class: "dim-text" }, pick(d.text))));

  const improvements = s.improvements.length
    ? el("div", { class: "panel" },
        el("h3", {}, t("detail.improve")),
        s.improvements.map((i) =>
          el("div", { class: `improve-item ${i.blocking ? "block" : "tip"}` },
            el("span", { class: "ico" }, i.blocking ? "✕" : "→"),
            el("span", {}, pick(i)))))
    : null;

  // ---- document generation ----
  const genRows = data.documents.map((d) => {
    const status = el("span", { class: "gen-sub" },
      d.ai ? t("detail.ai_badge") : t("detail.template_badge"));
    const action = el("button", { class: "btn btn-secondary btn-sm", type: "button" },
      t("detail.generate_btn"));

    action.addEventListener("click", async () => {
      action.disabled = true;
      action.textContent = t("detail.generating");
      status.textContent = "";
      try {
        const res = await api.generate(d.type, f.id, lang());
        action.disabled = false;
        action.textContent = t("detail.regenerate");
        status.innerHTML = "";
        status.appendChild(el("a", {
          href: res.url, class: "tag tag-ok", download: res.filename,
          style: "text-decoration:none",
        }, `↓ ${t("detail.download")}`));
        if (res.ai_warning) {
          status.appendChild(el("span", { class: "tag tag-warn", style: "margin-left:6px" },
            t("detail.ai_failed")));
        }
      } catch (e) {
        action.disabled = false;
        action.textContent = t("common.retry");
        status.textContent = t("common.error");
      }
    });

    return el("div", { class: "gen-row" },
      el("div", {}, el("div", { class: "gen-label" }, pick(d.label)), status),
      action);
  });

  const confidenceTag = {
    high: "tag-ok", medium: "tag-neutral",
    low: "tag-warn", "low-for-small-orgs": "tag-warn",
  }[f.confidence] || "tag-neutral";

  mount(el("div", { class: "page container" },
    el("a", { class: "back-link", href: `#/category/${(f.categories || [])[0] || ""}` },
      "←", " ", t("detail.back")),

    el("div", { class: "page-head" },
      f.is_partner
        ? el("div", { style: "margin-bottom:10px" },
            el("span", { class: "partner-badge" }, "◆ ", t("partner.badge")))
        : null,
      el("h1", {}, f.name),
      f.organization ? el("p", {}, f.organization) : null),

    el("div", { class: "detail-grid" },
      // ---------- main column ----------
      el("div", {},
        el("div", { class: s.eligible ? "banner banner-ok" : "banner banner-err" },
          el("span", {}, s.eligible ? "✓" : "✕"),
          el("span", {}, s.eligible ? t("detail.eligible_msg") : t("detail.not_eligible"))),

        el("div", { class: "panel" },
          el("h3", {}, t("detail.about")),
          el("h4", {}, t("detail.priorities")),
          el("p", { style: "font-size:14px;margin:0" },
            L === "fr" ? (f.sector_focus_fr || f.sector_focus_en) : f.sector_focus_en),
          el("h4", {}, t("detail.who")),
          el("p", { style: "font-size:14px;margin:0" },
            L === "fr" ? (f.eligible_org_type_fr || f.eligible_org_type_en) : f.eligible_org_type_en),
          el("h4", {}, t("detail.amount")),
          el("p", { style: "font-size:14px;margin:0" },
            (L === "fr" ? (f.funding_range_fr || f.funding_range_en) : f.funding_range_en)
              || t("detail.not_disclosed")),
          el("h4", {}, t("detail.cycle")),
          el("p", { style: "font-size:14px;margin:0" },
            (L === "fr" ? (f.deadline_cycle_fr || f.deadline_cycle_en) : f.deadline_cycle_en) || "—"),
          (f.notes_en || f.notes_fr) ? el("div", {},
            el("h4", {}, t("detail.notes")),
            el("p", { style: "font-size:13.5px;margin:0;color:var(--muted)" },
              L === "fr" ? (f.notes_fr || f.notes_en) : f.notes_en)) : null),

        el("div", { class: "panel" },
          el("h3", {}, t("detail.steps")),
          steps.length
            ? el("ol", { class: "steps-list" }, steps.map((x) => el("li", {}, x)))
            : el("p", { style: "color:var(--muted);font-size:14px;margin:0" }, "—")),

        el("div", { class: "panel" },
          el("h3", {}, t("detail.docs_needed")),
          docs.length
            ? el("div", { class: "doc-list" },
                docs.map((x) => el("div", { class: "doc-item" },
                  el("span", { class: "mark" }, "○"), el("span", {}, x))))
            : el("p", { style: "color:var(--muted);font-size:14px;margin:0" }, "—"))),

      // ---------- sidebar ----------
      el("div", {},
        f.is_partner && f.partner_logo
          ? el("div", { class: "panel" },
              el("div", { class: "detail-logo" },
                el("img", { src: f.partner_logo, alt: f.partner_name || f.name })),
              // Disclosure: charities must know what the badge does and does not mean.
              el("p", { class: "partner-note" }, t("partner.note")))
          : null,
        el("div", { class: "panel" },
          el("h3", { style: "margin-bottom:10px" }, t("detail.compat")),
          el("div", { style: "display:flex;align-items:center;gap:14px;margin-bottom:14px" },
            scoreBadge(s.score),
            el("div", { style: "flex:1" }, scoreBar(s.score))),
          el("h4", { style: "margin-top:4px" }, t("detail.why")),
          dims),

        improvements,

        el("div", { class: "panel" },
          el("h3", {}, t("detail.generate")),
          el("p", { style: "font-size:12.5px;color:var(--muted);margin:-6px 0 12px" },
            t("detail.generate_sub")),
          genRows),

        el("div", { class: "panel" },
          el("h3", {}, t("detail.confidence")),
          el("div", { class: "tag-row", style: "margin-bottom:10px" },
            el("span", { class: `tag ${confidenceTag}` }, f.confidence || "—")),
          el("p", { style: "font-size:12.5px;color:var(--muted);margin:0 0 14px" },
            t("detail.confidence_note")),
          f.official_link
            ? el("a", { class: "btn btn-primary btn-sm btn-block", href: f.official_link,
                target: "_blank", rel: "noopener noreferrer" }, t("detail.official_site"))
            : null)))));
}
