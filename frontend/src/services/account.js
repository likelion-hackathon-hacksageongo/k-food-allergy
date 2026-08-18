const API_HEADERS = { "Content-Type": "application/json" };

async function request(path, options = {}) {
  const response = await fetch(path, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok)
    throw new Error(
      data.detail || Object.values(data).flat().join(" ") || "Request failed.",
    );
  return data;
}

export async function authenticate(mode, username, email, password) {
  const path =
    mode === "signup" ? "/api/accounts/register/" : "/api/accounts/login/";
  const body =
    mode === "signup"
      ? { username, email, password, password_confirm: password }
      : { username, password };
  return request(path, {
    method: "POST",
    headers: API_HEADERS,
    body: JSON.stringify(body),
  });
}

export async function saveProfile(allergens, preferred_language) {
  const token = localStorage.getItem("kfood-access-token");
  if (!token) throw new Error("Please sign in first.");
  return request("/api/profiles/me/", {
    method: "PATCH",
    headers: { ...API_HEADERS, Authorization: `Bearer ${token}` },
    body: JSON.stringify({ allergens, preferred_language }),
  });
}

export async function loadProfile() {
  const token = localStorage.getItem("kfood-access-token");
  if (!token) return null;
  return request("/api/profiles/me/", {
    headers: { Authorization: `Bearer ${token}` },
  });
}
