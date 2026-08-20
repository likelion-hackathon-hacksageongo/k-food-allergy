const headers = () => {
  const token = localStorage.getItem("kfood-access-token");
  return token ? { "Content-Type": "application/json", Authorization: `Bearer ${token}` } : null;
};

async function request(path, options = {}) {
  const response = await fetch(path, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = data.detail || Object.values(data).flat().join(" ");
    throw new Error(message || `Feedback request failed (HTTP ${response.status}).`);
  }
  return data;
}

export async function fetchMyFeedback() {
  const auth = headers();
  if (!auth) return null;
  const data = await request("/api/feedback/", { headers: auth });
  return Array.isArray(data) ? data : data.results || [];
}

export async function createFeedback(feedback) {
  const auth = headers();
  if (!auth) throw new Error("Please sign in first.");
  return request("/api/feedback/create/", { method: "POST", headers: auth, body: JSON.stringify(feedback) });
}
