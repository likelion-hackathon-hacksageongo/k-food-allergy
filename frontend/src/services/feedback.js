const headers = () => {
  const token = localStorage.getItem("kfood-access-token");
  return token ? { "Content-Type": "application/json", Authorization: `Bearer ${token}` } : null;
};

async function request(path, options = {}) {
  const response = await fetch(path, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || "Feedback request failed.");
  return data;
}

export async function fetchMyFeedback() {
  const auth = headers();
  if (!auth) return null;
  return request("/api/feedback/", { headers: auth });
}

export async function createFeedback(feedback) {
  const auth = headers();
  if (!auth) throw new Error("Please sign in first.");
  return request("/api/feedback/create/", { method: "POST", headers: auth, body: JSON.stringify(feedback) });
}
