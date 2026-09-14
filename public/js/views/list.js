import { el, mount, scoreBar, scoreBadge, loading, truncate } from "../dom.js";
import { t, pick } from "../i18n.js";
import { api } from "../api.js";

export async function renderList(categoryId, go) {
  mount(loading());
  let data;
  try {
    data = await api.opportunities(categoryId);
  } catch (err) {
    if (err.status === 404) return go("#/");
    return mount(el("div", { class: "page container" },
      el("div", { class: "banner banner-err" }, t("common.error"))));
  }

  const rows = data.opportunities.map((o) =>
    el("button", { class: "opp-row", type: "button", onclick: () => go(`#/opportunity/${o.id}`) },
      el("div", { class: "opp-score" }, scoreBadge(o.score, true), scoreBar(o.score)),
      o.is_partner && o.partner_logo
        ? el("div", { class: "opp-logo" },
            el("img", { src: o.partner_logo, alt: o.partner_name || o.name, loading: "lazy" }))
        : null,
      el("div", {},
        el("h4", {}, o.name),
        o.organization ? el("p", { class: "org" }, o.organization) : null,
        el("p", { class: "sum" }, pick(o.summary)),
        el("div", { class: "tag-row", style: "margin-top:9px" },
          o.is_partner ? el("span", { class: "partner-badge" }, "◆ ", t("partner.badge")) : null,
          o.eligible
            ? el("span", { class: "tag tag-ok" }, t("list.eligible"))
            : el("span", { class: "tag tag-block" },
                o.blocking_count === 1 ? t("list.blocking_one")
                                       : t("list.blocking_many", { n: o.blocking_count })),
          o.amount_disclosed
            ? el("span", { class: "tag tag-neutral" }, truncate(pick(o.funding_range), 40))
            : null,
          o.confidence === "low" || o.confidence === "low-for-small-orgs"
            ? el("span", { class: "tag tag-warn" }, `${t("detail.confidence")}: ${o.confidence}`)
            : null)),
      el("span", { class: "btn btn-secondary btn-sm opp-cta" }, t("list.open"))));

  mount(el("div", { class: "page container" },
    el("a", { class: "back-link", href: "#/dashboard" }, "←", " ", t("list.back")),
    el("div", { class: "page-head" },
      el("h1", {}, pick(data.category.label)),
      el("p", {}, pick(data.category.blurb))),
    data.opportunities.length
      ? el("div", {},
          el("p", { style: "font-size:13px;color:var(--muted);margin:0 0 16px" }, t("list.sorted")),
          rows)
      : el("div", { class: "empty" }, t("list.empty"))));
}
