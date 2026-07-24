export async function api(path, options = {}) {
  const response = await fetch(`/api${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || `请求失败 (${response.status})`);
  }
  return payload;
}

export function post(path, body) {
  return api(path, { method: "POST", body: JSON.stringify(body) });
}

export function put(path, body) {
  return api(path, { method: "PUT", body: JSON.stringify(body) });
}

export function remove(path) {
  return api(path, { method: "DELETE" });
}
