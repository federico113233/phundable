// Tiny DOM helpers — enough structure to keep views readable without a framework.
export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "class") node.className = value;
    else if (key.startsWith("on") && typeof value === "function") {
      node.addEventListener(key.slice(2).toLowerCase(), value);
    } else if (value === true) node.setAttribute(key, "");
    else node.setAttribute(key, value);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    node.appendChild(typeof child === "string" || typeof child === "number"
      ? document.createTextNode(String(child)) : child);
  }
  return node;
}

// Trim to a length without cutting mid-word, adding an ellipsis when shortened.
export function truncate(text, max) {
  const s = String(text || "").trim();
  if (s.length <= max) return s;
  const cut = s.slice(0, max);
  const space = cut.lastIndexOf(" ");
  return (space > max * 0.6 ? cut.slice(0, space) : cut).replace(/[,;:.\s]+$/, "") + "…";
}

export function mount(...nodes) {
  const view = document.getElementById("view");
  view.innerHTML = "";
  nodes.flat().forEach((n) => n && view.appendChild(n));
  window.scrollTo({ top: 0, behavior: "instant" in window ? "instant" : "auto" });
}

export function loading() {
  return el("div", { class: "loading" }, el("span", { class: "spinner dark" }), "…");
}

// 1-10 -> visual band. Deliberately generous at the top so a 7 doesn't look like failure.
export function scoreClass(score) {
  if (score >= 7) return "s-high";
  if (score >= 4.5) return "s-mid";
  return "s-low";
}

export function scoreBar(score) {
  return el("div", { class: `score-bar ${scoreClass(score)}` },
    el("i", { style: `width:${Math.max(4, (score / 10) * 100)}%` }));
}

export function scoreBadge(score, small) {
  // Always one decimal: a bare "6" beside "8.7" reads as a different scale.
  const n = Number(score);
  return el("span", { class: `score-badge${small ? " sm" : ""}` },
    el("span", { class: "n" }, Number.isFinite(n) ? n.toFixed(1) : "—"),
    el("span", { class: "d" }, "/10"));
}
