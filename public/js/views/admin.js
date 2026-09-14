import { el, mount, loading } from "../dom.js";
import { t, lang } from "../i18n.js";
import { api } from "../api.js";

const SIZE_LABEL = {
  s1: "comp.form.size.s1", s2: "comp.form.size.s2", s3: "comp.form.size.s3",
  s4: "comp.form.size.s4", s5: "comp.form.size.s5", s6: "comp.form.size.s6",
};
const STATUS_CLASS = {
  new: "tag-warn", contacted: "tag-neutral", quoted: "tag-neutral", won: "tag-ok",
};

export async function renderAdmin(go) {
  mount(loading());
  let data;
  try {
    data = await api.adminOverview();
  } catch (e) {
    return mount(el("div", { class: "page container" },
      el("div", { class: "banner banner-err" }, t("common.error"))));
  }

  const s = data.summary;
  const rows = data.signups.map((r) =>
    el("tr", {},
      el("td", {}, el("b", {}, r.company || "—"),
        r.message ? el("div", { class: "admin-msg" }, r.message) : null),
      el("td", {},
        el("div", {}, r.contact_name || "—"),
        el("div", { class: "admin-sub" }, r.email || ""),
        r.phone ? el("div", { class: "admin-sub" }, r.phone) : null),
      el("td", {}, SIZE_LABEL[r.org_size] ? t(SIZE_LABEL[r.org_size]) : "—"),
      el("td", {}, r.programme || "—"),
      el("td", { class: "admin-nowrap" }, formatDate(r.received_at)),
      el("td", {},
        el("span", { class: `tag ${STATUS_CLASS[r.status] || "tag-neutral"}` },
          t(`admin.status.${r.status || "new"}`)))));

  mount(el("div", { class: "page container" },
    el("a", { class: "back-link", href: "#/" }, "←", " ", t("admin.back")),
    el("div", { class: "page-head" },
      el("h1", {}, t("admin.title"))),
    el("div", { class: "banner banner-warn" }, "⚠ ", t("admin.internal")),

    el("div", { class: "kpi-row" },
      kpi(s.partners, t("admin.kpi.partners")),
      kpi(s.requests, t("admin.kpi.requests")),
      kpi(s.by_status.new || 0, t("admin.kpi.new"))),

    el("div", { class: "panel" },
      el("h3", {}, t("admin.listings")),
      el("p", { class: "admin-sub", style: "margin:-8px 0 16px" }, t("admin.listings.sub")),
      el("div", { class: "admin-listings" },
        data.partners.map((p) =>
          el("div", { class: "admin-listing" },
            el("div", { class: "admin-listing-logo" },
              el("img", { src: p.logo, alt: p.name, loading: "lazy" })),
            el("div", {},
              el("div", { class: "admin-listing-name" }, p.name),
              p.since ? el("div", { class: "admin-sub" }, `${t("admin.since")} ${p.since}`) : null))))),

    el("div", { class: "panel" },
      el("h3", {}, t("admin.pipeline")),
      el("p", { class: "admin-sub", style: "margin:-8px 0 16px" }, t("admin.pipeline.sub")),
      rows.length
        ? el("div", { class: "table-scroll" },
            el("table", { class: "admin-table" },
              el("thead", {}, el("tr", {},
                ["admin.col.company", "admin.col.contact", "admin.col.size",
                 "admin.col.programme", "admin.col.received", "admin.col.status"]
                  .map((k) => el("th", {}, t(k))))),
              el("tbody", {}, rows)))
        : el("p", { class: "admin-sub" }, t("admin.empty")))));
}

function kpi(value, label) {
  return el("div", { class: "kpi" },
    el("div", { class: "kpi-n" }, String(value)),
    el("div", { class: "kpi-l" }, label));
}

function formatDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d)) return iso;
  return d.toLocaleDateString(lang() === "fr" ? "fr-FR" : "en-GB",
    { day: "2-digit", month: "short", year: "numeric" });
}
