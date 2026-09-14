import { el, mount } from "../dom.js";
import { t } from "../i18n.js";
import { api } from "../api.js";

export async function renderCompanySignup(go) {
  const status = el("div", { class: "form-status" });
  const field = (id, labelKey, type = "text", required = false) =>
    el("div", { class: "field", "data-field": id },
      el("label", { for: `c-${id}` }, t(labelKey), required ? el("span", { class: "req" }, "*") : null),
      type === "textarea"
        ? el("textarea", { id: `c-${id}`, maxlength: 1500 })
        : el("input", { id: `c-${id}`, type: type === "email" ? "email" : "text", maxlength: 300 }));

  const form = el("div", { class: "form-card" },
    field("company", "comp.form.company", "text", true),
    field("contact_name", "comp.form.contact", "text", true),
    field("email", "comp.form.email", "email", true),
    el("div", { class: "field", "data-field": "size" },
      el("label", { for: "c-size" }, t("comp.form.size")),
      el("select", { id: "c-size" },
        el("option", { value: "" }, t("comp.form.size.placeholder")),
        ["s1", "s2", "s3", "s4", "s5", "s6"].map((k) =>
          el("option", { value: k }, t("comp.form.size." + k))))),
    field("phone", "comp.form.phone"),
    field("programme", "comp.form.programme"),
    field("message", "comp.form.message", "textarea"),
    el("button", { class: "btn btn-primary btn-block", type: "button", id: "c-submit",
      onclick: submit }, t("comp.form.submit")),
    el("p", { class: "form-footnote" }, t("comp.form.no_payment")),
    status);

  async function submit() {
    const get = (id) => (document.getElementById(`c-${id}`).value || "").trim();
    const payload = {
      company: get("company"), contact_name: get("contact_name"), email: get("email"),
      org_size: get("size"), phone: get("phone"), programme: get("programme"),
      message: get("message"),
    };
    ["company", "contact_name", "email"].forEach((id) =>
      document.querySelector(`[data-field="${id}"]`)
        .classList.toggle("invalid", !payload[id]));

    if (!payload.company || !payload.contact_name || !payload.email) {
      return show(t("comp.form.required"), "err");
    }
    const button = document.getElementById("c-submit");
    button.disabled = true;
    button.textContent = t("comp.form.sending");
    try {
      await api.companySignup(payload);
      form.querySelectorAll("input, textarea").forEach((i) => { i.value = ""; });
      show(t("comp.form.success"), "ok");
    } catch (err) {
      show(err.body && err.body.error === "invalid_email"
        ? t("comp.form.bad_email") : t("comp.form.error"), "err");
    } finally {
      button.disabled = false;
      button.textContent = t("comp.form.submit");
    }
  }

  function show(message, kind) {
    status.textContent = message;
    status.className = `form-status show ${kind}`;
  }

  mount(el("div", { class: "page container" },
    el("a", { class: "back-link", href: "#/" }, "←", " ", t("comp.form.back")),
    el("div", { class: "company-signup" },
      el("div", {},
        el("span", { class: "eyebrow" }, t("comp.tag")),
        el("h1", { style: "font-size:30px;font-weight:700;color:var(--dark);margin:0 0 12px" },
          t("comp.form.title")),
        el("p", { style: "color:var(--muted);font-size:15.5px;line-height:1.6" },
          t("comp.form.body")),
        el("div", { class: "price-box" },
          el("span", { class: "pricing-label" }, t("comp.price.label")),
          el("div", { class: "price-custom" }, t("comp.price.custom")),
          el("p", {}, t("comp.price.note")))),
      form)));
}
