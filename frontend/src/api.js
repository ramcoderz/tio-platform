import Console from './utils/console';
import { config } from './config';

export async function api(path, options = {}) {
  const token = localStorage.getItem("token");
  const headers = { 
    ...(options.isFormData ? {} : { "Content-Type": "application/json" }),
    ...(token ? { "Authorization": `Bearer ${token}` } : {}),
    ...(options.headers || {}) 
  };
  
  // Console.info(`START ${options.method || 'GET'} ${path}`, 'API');
  try {
    const res = await fetch(`${config.apiBase}/api${path}`, {
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
    
    
    // Console.success(`END ${path} Status: ${res.status}`, 'API');
    if (!res.ok) throw new Error(json.detail || "Request failed");
    return json;
  } catch (err) {
    Console.error(`FAILED ${path}: ${err.message}`, 'API');
    throw err;
  }
}
