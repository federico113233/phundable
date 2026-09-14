import { el, mount } from "../dom.js";
import { t, pick, lang } from "../i18n.js";
import { api } from "../api.js";

export async function renderHome(go) {
  // Everything degrades: the landing must render even with the API down.
  let families = [], total = 0, docCount = 6, hasProfile = false;
  let partners = [];
  try {
    const d = await api.families();
    families = d.families || []; total = d.total || 0; docCount = d.documents || 6;
  } catch (e) { /* defaults */ }
  try { partners = (await api.partners()).partners || []; } catch (e) { /* defaults */ }
  try { hasProfile = !!(await api.getProfile()).complete; } catch (e) { /* first visit */ }

  mount(
    hero(hasProfile),
    statLine(total, docCount),
    partners.length ? ribbon(partners) : null,
    audienceSplit(),

    // ================= CHARITY TRACK =================
    el("div", { id: "charities" },
      section("band",
        head(t("land.how.tag"), t("land.how.title"), t("land.how.body")),
        el("div", { class: "grid-3" },
          stepCard("1", t("land.how.s1.title"), t("land.how.s1.body")),
          stepCard("2", t("land.how.s2.title"), t("land.how.s2.body")),
          stepCard("3", t("land.how.s3.title"), t("land.how.s3.body")))),

      // alternating showcase rows, each pairing copy with a live UI mockup
      showcase("band band-pink", false,
        t("land.mock.dash.title"), t("land.mock.dash.body"), mockDashboard(families)),
      showcase("band", true,
        t("land.mock.why.title"), t("land.mock.why.body"), mockScore()),
      showcase("band band-lav", false,
        t("land.mock.docs.title"), t("land.mock.docs.body"), mockDocs()),

      section("band band-tight",
        el("div", { class: "final-cta" },
          el("h2", {}, t("land.final.title")),
          el("p", {}, t("land.final.body")),
          el("a", { class: "btn btn-primary btn-lg", href: "#/onboarding" },
            t("land.hero.cta"), " →")))),

    // ================= COMPANY TRACK =================
    companyBand(partners),

    section("band band-tight",
      el("div", { class: "honest-note" },
        el("strong", {}, t("land.honest.title")),
        el("p", {}, t("land.honest.body"))))
  );
}

/* ---------------------------------------------------------------- hero */
function hero(hasProfile) {
  return el("div", { class: "container" },
    el("section", { class: "hero landing-hero" },
      el("span", { class: "eyebrow", style: "color:var(--red-hover)" }, t("land.eyebrow")),
      // Weight contrast carries the emphasis, since the brand is Ambit-only.
      el("h1", { class: "hero-title" },
        el("span", { class: "t-light" }, t("land.hero.lead")),
        " ",
        el("span", { class: "t-black" }, t("land.hero.rest"))),
      el("p", {}, t("land.hero.body")),
      el("div", { class: "hero-cta-row" },
        el("a", { class: "btn btn-primary btn-lg", href: "#/onboarding" },
          el("span", { class: "play" }, "▶"), t("land.hero.cta")),
        el("a", { class: "btn btn-onhero btn-lg", href: "#companies" },
          el("span", { class: "play" }, "▶"), t("land.hero.cta2"))),
      hasProfile
        ? el("a", { class: "hero-resume", href: "#/dashboard" }, t("land.hero.resume"), " →")
        : el("p", { class: "hero-note" }, t("land.hero.note"))));
}

function statLine(total, docs) {
  return el("section", { class: "statline" },
    el("div", { class: "container" },
      t("land.statline", { funders: total || "—", docs: docs })));
}

/* ------------------------------------------------- sliding logo ribbon */
function ribbon(partners) {
  // The track is duplicated so the CSS translation can loop seamlessly.
  const lane = (aria) => el("div", { class: "ribbon-track", "aria-hidden": aria ? "true" : null },
    partners.map((p) =>
      el("div", { class: "ribbon-item", title: p.name },
        el("img", { src: p.logo, alt: aria ? "" : p.name, loading: "lazy" }))));

  return el("section", { class: "ribbon-band" },
    el("p", { class: "logo-strip-title" }, t("comp.partners.title")),
    el("div", { class: "ribbon-viewport" }, lane(false), lane(true)));
}

/* ----------------------------------------------------- audience split */
function audienceSplit() {
  return el("section", { class: "split-band" },
    el("div", { class: "container split-row" },
      el("a", { class: "split-btn", href: "#charities" },
        el("span", { class: "play" }, "▶"), t("land.split.charity")),
      el("a", { class: "split-btn split-btn-alt", href: "#companies" },
        el("span", { class: "play" }, "▶"), t("land.split.company"))));
}

/* --------------------------------------------------------- primitives */
function section(cls, ...children) {
  return el("section", { class: cls }, el("div", { class: "container" }, children));
}

function head(tag, title, body) {
  return el("div", { class: "section-head" },
    tag ? el("span", { class: "eyebrow" }, tag) : null,
    el("h2", {}, title),
    body ? el("p", {}, body) : null);
}

function stepCard(n, title, body) {
  return el("div", { class: "card step-card" },
    el("div", { class: "step-num" }, n),
    el("h3", {}, title), el("p", {}, body));
}

function showcase(cls, reverse, title, body, mock) {
  return el("section", { class: cls },
    el("div", { class: `container showcase${reverse ? " showcase-rev" : ""}` },
      el("div", { class: "showcase-copy" },
        el("h2", {}, title),
        el("p", {}, body)),
      el("div", { class: "showcase-mock" }, mock)));
}

/* -------------------------------------------------- live UI mockups
   Built as real markup rather than screenshots: always crisp, always in
   step with the app, and they follow the language toggle.                */
function browserFrame(...children) {
  return el("div", { class: "frame" },
    el("div", { class: "frame-bar" },
      el("span", { class: "dot d1" }), el("span", { class: "dot d2" }), el("span", { class: "dot d3" }),
      el("span", { class: "frame-url" }, "phundable.fr")),
    el("div", { class: "frame-body" }, children));
}

function mockDashboard(families) {
  const sample = (families.length ? families : [
    { label: { fr: "Subventions françaises", en: "French grants" }, count: 7 },
    { label: { fr: "Financement privé", en: "Private funding" }, count: 7 },
    { label: { fr: "Financement d'entreprise", en: "Corporate funding" }, count: 30 },
    { label: { fr: "Programmes RSE", en: "CSR programmes" }, count: 8 },
  ]).slice(0, 4);
  const scores = [8.7, 8.5, 8.2, 6.0];

  return browserFrame(
    el("div", { class: "m-grid" },
      sample.map((f, i) =>
        el("div", { class: "m-card" },
          el("div", { class: "m-card-top" },
            el("span", { class: "m-card-title" }, pick(f.label)),
            el("span", { class: "m-score" }, scores[i].toFixed(1),
              el("i", {}, "/10"))),
          el("div", { class: `m-bar ${scores[i] >= 7 ? "hi" : "mid"}` },
            el("i", { style: `width:${scores[i] * 10}%` })),
          el("div", { class: "m-meta" },
            el("span", {}, `${f.count} ${t("dash.opportunities")}`),
            i === 2 ? el("span", { class: "m-meta-p" }, `◆ 7 ${t("dash.partners_here")}`) : null)))));
}

function mockScore() {
  const dims = [
    ["Correspondance thématique", "Thematic fit", 92, "hi"],
    ["Correspondance géographique", "Geographic fit", 100, "hi"],
    ["Éligibilité", "Eligibility", 72, "hi"],
    ["Votre capacité", "Your capacity", 48, "mid"],
    ["Montant", "Funding size", 0, "na"],
  ];
  return browserFrame(
    el("div", { class: "m-score-head" },
      el("span", { class: "m-score big" }, "8.6", el("i", {}, "/10")),
      el("div", { class: "m-bar hi", style: "flex:1" }, el("i", { style: "width:86%" }))),
    el("div", { class: "m-dims" },
      dims.map(([fr, en, v, kind]) =>
        el("div", { class: "m-dim" },
          el("div", { class: "m-dim-top" },
            el("span", {}, lang() === "en" ? en : fr),
            el("span", { class: "m-dim-v" }, kind === "na" ? "—" : `${v}%`)),
          el("div", { class: `m-bar ${kind}` },
            el("i", { style: `width:${kind === "na" ? 0 : v}%` }))))));
}

function mockDocs() {
  const docs = [["land.docs.d1", true], ["land.docs.d2", true], ["land.docs.d3", true],
                ["land.docs.d4", false], ["land.docs.d5", false], ["land.docs.d6", false]];
  return browserFrame(
    el("div", { class: "m-docs" },
      docs.map(([key, ai]) =>
        el("div", { class: "m-doc" },
          el("span", { class: "m-doc-ico" }, "📄"),
          el("div", {},
            el("div", { class: "m-doc-name" }, t(key)),
            el("span", { class: "m-doc-tag" }, t(ai ? "land.docs.ai" : "land.docs.auto"))),
          el("span", { class: "m-doc-dl" }, "↓")))));
}

/* ----------------------------------------------------- company track */
function companyBand(partners) {
  return el("section", { class: "band company-band", id: "companies" },
    el("div", { class: "container" },
      head(t("comp.tag"), t("comp.title"), t("comp.body")),
      el("div", { class: "company-grid" },
        el("div", { class: "company-benefits" },
          [["comp.b1.title", "comp.b1.body"], ["comp.b2.title", "comp.b2.body"],
           ["comp.b3.title", "comp.b3.body"], ["comp.b4.title", "comp.b4.body"],
           ["comp.b5.title", "comp.b5.body"]].map(([title, body], i) =>
            el("div", { class: "benefit" + (i === 4 ? " benefit-trust" : "") },
              el("span", { class: "benefit-mark" }, i === 4 ? "◆" : "✓"),
              el("div", {},
                el("h4", {}, t(title)),
                el("p", {}, t(body)))))),
        el("div", { class: "pricing-card" },
          el("span", { class: "pricing-label" }, t("comp.price.label")),
          el("div", { class: "price-custom" }, t("comp.price.custom")),
          el("p", { class: "pricing-includes" }, t("comp.price.note")),
          el("a", { class: "btn btn-primary btn-block", href: "#/for-companies" },
            t("comp.cta")),
          el("p", { class: "pricing-sub" }, t("comp.cta.sub"))))));
}
