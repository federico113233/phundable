import { setLang, initialLang, onLangChange, applyStatic, t } from "./i18n.js";
import { api } from "./api.js";
import { renderHome } from "./views/home.js";
import { renderOnboarding, refreshOnboarding } from "./views/onboarding.js";
import { renderDashboard } from "./views/dashboard.js";
import { renderList } from "./views/list.js";
import { renderDetail } from "./views/detail.js";
import { renderCompanySignup } from "./views/company.js";
import { renderAdmin } from "./views/admin.js";

function go(hash) {
  if (location.hash === hash) route();
  else location.hash = hash;
}

async function route() {
  const hash = location.hash || "#/";
  const parts = hash.replace(/^#\//, "").split("/");

  await updateNav();

  if (parts[0] === "onboarding") return renderOnboarding(go);
  if (parts[0] === "for-companies") return renderCompanySignup(go);
  if (parts[0] === "admin") return renderAdmin(go);
  if (parts[0] === "dashboard") return renderDashboard(go);
  if (parts[0] === "category" && parts[1]) return renderList(parts[1], go);
  if (parts[0] === "opportunity" && parts[1]) return renderDetail(parts[1], go);
  return renderHome(go);
}

async function updateNav() {
  try {
    const { complete } = await api.getProfile();
    document.getElementById("nav-dash").hidden = !complete;
    document.getElementById("nav-profile").hidden = !complete;
  } catch (e) { /* nav stays hidden */ }
}

async function boot() {
  await setLang(initialLang(), { silent: true });

  document.querySelectorAll(".lang-toggle button").forEach((button) => {
    button.addEventListener("click", async () => {
      await setLang(button.dataset.lang);
    });
  });

  // A language switch re-renders the current view so funder content follows too.
  onLangChange(() => {
    applyStatic();
    if ((location.hash || "").startsWith("#/onboarding")) refreshOnboarding(go);
    else route();
  });

  window.addEventListener("hashchange", route);
  route();
}

boot();
