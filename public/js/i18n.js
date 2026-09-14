// Bilingual engine. Language is a global concern here: it changes the UI chrome,
// the funder content, AND the language of generated documents.
const STORAGE_KEY = "phenix.lang";
let dict = {};
let current = "fr";
const listeners = [];

export function lang() { return current; }

export function t(key, vars) {
  let text = dict[key];
  if (text === undefined) return key;          // surfaces missing keys instead of hiding them
  if (vars) for (const k in vars) text = text.replace("{" + k + "}", vars[k]);
  return text;
}

// Picks the right side of a {en, fr} pair coming from the API, with fallback.
export function pick(obj) {
  if (!obj) return "";
  if (typeof obj === "string") return obj;
  return obj[current] || obj.fr || obj.en || "";
}

export async function setLang(next, { silent = false } = {}) {
  current = next === "en" ? "en" : "fr";
  try { localStorage.setItem(STORAGE_KEY, current); } catch (e) { /* private mode */ }
  const res = await fetch(`i18n/${current}.json`);
  dict = await res.json();
  document.documentElement.lang = current;
  applyStatic();
  document.querySelectorAll(".lang-toggle button").forEach((b) =>
    b.classList.toggle("active", b.dataset.lang === current));
  if (!silent) listeners.forEach((fn) => fn(current));
}

export function onLangChange(fn) { listeners.push(fn); }

export function applyStatic(root = document) {
  root.querySelectorAll("[data-i18n]").forEach((el) => {
    el.textContent = t(el.getAttribute("data-i18n"));
  });
}

export function initialLang() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "en" || saved === "fr") return saved;
  } catch (e) { /* ignore */ }
  return (navigator.language || "fr").toLowerCase().startsWith("en") ? "en" : "fr";
}
