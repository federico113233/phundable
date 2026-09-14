import { el, mount, scoreBar, scoreBadge, loading } from "../dom.js";
import { t, pick } from "../i18n.js";
import { api } from "../api.js";

export async function renderDashboard(go) {
  mount(loading());
  let data;
  try {
    data = await api.categories();
  } catch (err) {
    if (err.status === 404) return go("#/");      // no profile yet
    return mount(el("div", { class: "page container" },
      el("div", { class: "banner banner-err" }, t("common.error"))));
  }

  const cards = data.categories.map((c, index) => {
    // A category with no records has no score. Showing a number there would be a lie.
    const empty = c.score === null || c.score === undefined || c.count === 0;
    return el("button", {
      class: "cat-card" + (empty ? " is-empty" : ""),
      type: "button",
      disabled: empty || undefined,
      onclick: () => { if (!empty) go(`#/category/${c.id}`); },
    },
      el("div", { class: "top" },
        el("div", {},
          index === 0 && !empty && c.score >= 5
            ? el("span", { class: "tag tag-ok", style: "margin-bottom:8px;display:inline-block" },
                t("dash.best_match"))
            : null,
          el("h3", {}, pick(c.label))),
        empty
          ? el("span", { class: "tag tag-neutral" }, t("dash.no_data"))
          : scoreBadge(c.score)),
      el("p", { class: "blurb" }, pick(c.blurb)),
      empty ? el("div", { class: "score-bar" }, el("i", { style: "width:0" }))
            : scoreBar(c.score),
      el("div", { class: "meta" },
        el("span", {}, el("b", {}, String(c.count)), ` ${t("dash.opportunities")}`),
        el("span", {}, el("b", {}, String(c.eligible_count)), ` ${t("dash.eligible")}`),
        c.partner_count
          ? el("span", {}, el("b", {}, "◆ " + c.partner_count), ` ${t("dash.partners_here")}`)
          : null));
  });

  mount(el("div", { class: "page container" },
    el("div", { class: "page-head" },
      el("span", { class: "eyebrow" }, "Phenix"),
      el("h1", {}, t("dash.title")),
      el("p", {}, t("dash.subtitle"))),
    el("div", { class: "cat-grid" }, cards)));
}
