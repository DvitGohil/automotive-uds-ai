export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1";

function extractErrorMessage(body) {
  if (!body) return "Request failed";
  const detail = body.detail;
  if (!detail) return "Request failed";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((d) => d.msg || JSON.stringify(d)).join("; ");
  if (detail.errors) return detail.errors.join("; ");
  return JSON.stringify(detail);
}

async function request(method, path, body) {
  let res;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers: { "Content-Type": "application/json" },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new Error("Backend unreachable. Check that the API server is running.");
  }

  let json = null;
  try {
    json = await res.json();
  } catch {
    // no JSON body
  }

  if (!res.ok) {
    if (res.status === 401) throw new Error("Authentication failed (invalid or missing API key).");
    throw new Error(extractErrorMessage(json));
  }
  return json;
}

export const apiGet = (path) => request("GET", path);
export const apiPost = (path, body) => request("POST", path, body);
