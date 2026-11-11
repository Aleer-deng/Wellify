const base = (import.meta.env?.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '');
let csrfToken;
let csrfRequest;
export class ApiError extends Error {
  constructor(message, status = 0, details = null) { super(message); this.name = 'ApiError'; this.status = status; this.details = details; }
}
function describe(value, prefix = '') {
  if (Array.isArray(value)) return value.map(item => describe(item, prefix)).join(' ');
  if (value && typeof value === 'object') return Object.entries(value).map(([key, item]) => describe(item, key === 'detail' || key === 'non_field_errors' ? '' : `${key}: `)).join(' ');
  return `${prefix}${String(value ?? 'Request failed.')}`;
}
async function request(path, method, body, retry = true) {
  const writing = !['GET', 'HEAD', 'OPTIONS'].includes(method);
  if (writing && !csrfToken) await csrf();
  let response;
  try {
    response = await fetch(`${base}${path}`, { method, credentials: 'include',
      headers: { Accept: 'application/json', ...(body === undefined ? {} : { 'Content-Type': 'application/json' }), ...(writing ? { 'X-CSRFToken': csrfToken } : {}) },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
  } catch { throw new ApiError('Unable to connect. Please try again shortly.'); }
  const text = response.status === 204 ? '' : await response.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch { /* Django/proxy errors may be HTML. */ }
  if (response.status === 403 && writing && retry && /csrf/i.test(text)) {
    csrfToken = undefined; await csrf(); return request(path, method, body, false);
  }
  if (!response.ok) {
    if (response.status === 403 && data?.detail === 'Authentication credentials were not provided.' && typeof window !== 'undefined') window.dispatchEvent(new Event('wellify:session-expired'));
    throw new ApiError(response.status >= 500 ? 'Something went wrong. Please try again shortly.' : data ? describe(data) : 'Unable to complete your request. Please try again.', response.status, data);
  }
  if (data?.csrfToken) csrfToken = data.csrfToken;
  return data;
}
export function csrf() {
  if (!csrfRequest) csrfRequest = request('/auth/csrf/', 'GET').then(data => { csrfToken = data.csrfToken; return csrfToken; }).finally(() => { csrfRequest = undefined; });
  return csrfRequest;
}
export const api = (path, method = 'GET', body) => request(path, method, body);
export async function signInWithProvider(provider) {
  if (!['google', 'apple', 'microsoft'].includes(provider)) throw new ApiError('Unknown sign-in provider.');
  const token = await csrf();
  // A navigation POST lets the provider redirect the browser; fetch cannot do this.
  const form = document.createElement('form');
  form.method = 'POST';
  form.action = `${base}/auth/social/${provider}/login/`;
  const field = document.createElement('input');
  field.type = 'hidden'; field.name = 'csrfmiddlewaretoken'; field.value = token;
  form.append(field); document.body.append(form); form.submit(); form.remove();
}
export async function list(path) {
  const records = [];
  for (let page = 1; ; page++) {
    const data = await api(`${path}${path.includes('?') ? '&' : '?'}page=${page}`);
    if (Array.isArray(data)) return data;
    if (!Array.isArray(data?.results)) throw new ApiError('Unexpected list response from the API.');
    records.push(...data.results);
    if (!data.next) return records;
  }
}
