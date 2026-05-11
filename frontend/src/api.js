export async function api(path, options = {}) {
  const token = localStorage.getItem("token");
  const headers = { 
    "Content-Type": "application/json", 
    ...(token ? { "Authorization": `Bearer ${token}` } : {}),
    ...(options.headers || {}) 
  };
  
  const res = await fetch(`/api${path}`, {
    ...options,
    headers
  });
  
  const text = await res.text();
  let json = {};
  try {
    json = text ? JSON.parse(text) : {};
  } catch {
    json = { detail: text };
  }
  if (!res.ok) throw new Error(json.detail || "Request failed");
  return json;
}
