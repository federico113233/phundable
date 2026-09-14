async function request(path, options) {
  const res = await fetch(path, options);
  let body = null;
  try { body = await res.json(); } catch (e) { /* non-JSON (file download) */ }
  if (!res.ok) {
    const err = new Error((body && body.error) || `HTTP ${res.status}`);
    err.status = res.status;
    err.body = body;
    throw err;
  }
  return body;
}

const json = (payload) => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(payload),
});

export const api = {
  health:        () => request("/api/health"),
  families:      () => request("/api/families"),
  partners:      () => request("/api/partners"),
  adminOverview: () => request("/api/admin/overview"),
  companySignup: (payload) => request("/api/company-signup", json(payload)),
  onboarding:    () => request("/api/config/onboarding"),
  getProfile:    () => request("/api/profile"),
  saveProfile:   (profile) => request("/api/profile", json({ profile })),
  categories:    () => request("/api/categories"),
  opportunities: (id) => request(`/api/categories/${encodeURIComponent(id)}`),
  opportunity:   (id) => request(`/api/opportunities/${encodeURIComponent(id)}`),
  generate:      (docType, opportunityId, lang) =>
                   request(`/api/documents/${encodeURIComponent(docType)}`,
                           json({ opportunity_id: opportunityId, lang })),
};
