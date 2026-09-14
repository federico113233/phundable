import { el, mount } from "../dom.js";
import { t, pick } from "../i18n.js";
import { api } from "../api.js";
import { SAMPLES } from "../samples.js";

let config = null;
let profile = {};
let step = 0;
let attempted = false;   // only show validation errors once the user has tried to advance

export async function renderOnboarding(go) {
  if (!config) {
    mount(el("div", { class: "loading" }, el("span", { class: "spinner dark" }), t("common.loading")));
    config = await api.onboarding();
    const existing = await api.getProfile();
    if (existing.profile) profile = { ...existing.profile };
  }
  draw(go);
}

function draw(go) {
  const steps = config.steps;
  const current = steps[step];

  const nav = el("nav", { class: "steps-nav" },
    steps.map((s, i) =>
      el("button", {
        class: `step-item${i === step ? " active" : ""}${i < step ? " done" : ""}`,
        type: "button",
        onclick: () => { step = i; attempted = false; draw(go); },
      },
        el("span", { class: "dot" }, i < step ? "✓" : String(i + 1)),
        el("span", {}, pick(s.label)))));

  const filler = el("div", { class: "demo-fill" },
    el("span", { class: "demo-fill-label" }, t("onboarding.demo")),
    SAMPLES.map((s) =>
      el("button", {
        type: "button", class: "demo-chip", title: pick(s.hint),
        onclick: () => {
          // Replace rather than merge, so switching samples never leaves
          // stale values from the previous one behind.
          profile = JSON.parse(JSON.stringify(s.profile));
          step = 0;
          attempted = false;
          draw(go);
          const nav = document.querySelector(".demo-fill");
          if (nav) nav.appendChild(el("span", { class: "demo-filled" }, "✓ " + pick(s.label)));
        },
      }, pick(s.label))));

  const body = el("div", { class: "card" },
    el("div", {},
      el("span", { class: "eyebrow" },
        t("onboarding.step_of", { n: step + 1, total: steps.length })),
      el("h2", { style: "font-size:22px;font-weight:700;color:var(--dark);margin:0 0 6px" },
        pick(current.label)),
      current.hint ? el("p", { style: "color:var(--muted);font-size:14px;margin:0 0 24px" },
        pick(current.hint)) : null),
    el("div", { id: "fields" }, current.fields.map((f) => field(f))),
    el("div", { class: "wizard-actions" },
      step > 0
        ? el("button", { class: "btn btn-secondary", type: "button",
            onclick: () => { step--; attempted = false; draw(go); } }, t("onboarding.back"))
        : el("span"),
      el("button", { class: "btn btn-primary", type: "button", id: "next",
        onclick: () => advance(go) },
        step === steps.length - 1 ? t("onboarding.finish") : t("onboarding.next"))));

  mount(
    el("div", { class: "page container" },
      el("div", { class: "page-head" },
        el("h1", {}, t("onboarding.title")),
        el("p", {}, t("onboarding.subtitle"))),
      filler,
      el("div", { class: "wizard" }, nav, body)));
}

function field(f) {
  const invalid = attempted && f.required && isEmpty(profile[f.id]);
  const wrap = el("div", { class: `field${invalid ? " invalid" : ""}`, "data-field": f.id });

  wrap.appendChild(el("label", { for: `f-${f.id}` },
    pick(f.label),
    f.required ? el("span", { class: "req" }, "*") : null,
    !f.required ? el("span", { style: "font-weight:400;color:var(--muted);font-size:12px" },
      `  (${t("onboarding.optional")})`) : null));

  if (f.hint) wrap.appendChild(el("div", { class: "hint" }, pick(f.hint)));

  const value = profile[f.id];

  if (f.type === "multiselect") {
    const selected = new Set(Array.isArray(value) ? value : []);
    const chips = el("div", { class: "chips" },
      f.options.map((o) =>
        el("button", {
          type: "button",
          class: `chip${selected.has(o.value) ? " on" : ""}`,
          onclick: (ev) => {
            selected.has(o.value) ? selected.delete(o.value) : selected.add(o.value);
            profile[f.id] = [...selected];
            ev.currentTarget.classList.toggle("on");
            if (attempted) revalidate(f);
          },
        }, pick(o.label))));
    wrap.appendChild(chips);
  } else if (f.type === "select") {
    const select = el("select", { id: `f-${f.id}`, onchange: (e) => {
      profile[f.id] = e.target.value || undefined;
      if (attempted) revalidate(f);
    } },
      el("option", { value: "" }, t("onboarding.select_placeholder")),
      f.options.map((o) => {
        const opt = el("option", { value: o.value }, pick(o.label));
        if (value === o.value) opt.selected = true;
        return opt;
      }));
    wrap.appendChild(select);
  } else if (f.type === "boolean") {
    const on = value === true;
    const sw = el("button", { type: "button", class: `switch${on ? " on" : ""}`,
      "aria-pressed": on ? "true" : "false" });
    const label = el("span", {}, on ? t("onboarding.yes") : t("onboarding.no"));
    sw.addEventListener("click", () => {
      const next = !sw.classList.contains("on");
      sw.classList.toggle("on", next);
      sw.setAttribute("aria-pressed", next ? "true" : "false");
      label.textContent = next ? t("onboarding.yes") : t("onboarding.no");
      profile[f.id] = next;
    });
    wrap.appendChild(el("div", { class: "switch-row" }, sw, label));
  } else if (f.type === "textarea") {
    wrap.appendChild(el("textarea", {
      id: `f-${f.id}`, maxlength: f.maxlength || 2000,
      placeholder: f.placeholder ? pick(f.placeholder) : "",
      oninput: (e) => { profile[f.id] = e.target.value; if (attempted) revalidate(f); },
    }, value || ""));
  } else {
    const input = el("input", {
      id: `f-${f.id}`,
      type: f.type === "number" ? "number" : "text",
      placeholder: f.placeholder ? pick(f.placeholder) : "",
      min: f.min, max: f.max,
      oninput: (e) => {
        const raw = e.target.value;
        profile[f.id] = f.type === "number"
          ? (raw === "" ? undefined : Number(raw))
          : raw;
        if (attempted) revalidate(f);
      },
    });
    if (value !== undefined && value !== null) input.value = value;
    wrap.appendChild(input);
  }
  return wrap;
}

function isEmpty(v) {
  return v === undefined || v === null || v === "" ||
    (Array.isArray(v) && v.length === 0);
}

function revalidate(f) {
  const node = document.querySelector(`[data-field="${f.id}"]`);
  if (node) node.classList.toggle("invalid", f.required && isEmpty(profile[f.id]));
}

async function advance(go) {
  attempted = true;
  const current = config.steps[step];
  const missing = current.fields.filter((f) => f.required && isEmpty(profile[f.id]));
  if (missing.length) {
    draw(go);
    const first = document.querySelector(".field.invalid");
    if (first) first.scrollIntoView({ behavior: "smooth", block: "center" });
    const actions = document.querySelector(".wizard-actions");
    actions.parentNode.insertBefore(
      el("div", { class: "banner banner-err", style: "margin-top:16px" },
        t("onboarding.required_missing")), actions);
    return;
  }

  if (step < config.steps.length - 1) {
    step++;
    attempted = false;
    draw(go);
    return;
  }

  const button = document.getElementById("next");
  button.disabled = true;
  button.textContent = t("onboarding.saving");
  try {
    await api.saveProfile(profile);
    step = 0;
    attempted = false;
    go("#/dashboard");
  } catch (err) {
    button.disabled = false;
    button.textContent = t("onboarding.finish");
    const actions = document.querySelector(".wizard-actions");
    actions.parentNode.insertBefore(
      el("div", { class: "banner banner-err", style: "margin-top:16px" },
        (err.body && err.body.fields)
          ? `${t("onboarding.required_missing")} (${err.body.fields.join(", ")})`
          : t("common.error")), actions);
  }
}

// Re-render on language switch so labels follow immediately.
export function refreshOnboarding(go) { if (config) draw(go); }
