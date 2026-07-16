/* client.js — клиент control-API mini-app.
 *
 * Все операции выполняются через реальный backend (FastAPI, src/control).
 */

const TOKEN_KEY = 'mesync_token'
const LOGGED_OUT_KEY = 'mesync_logged_out'
const BASE = (import.meta.env?.VITE_API_BASE || '/api').replace(/\/$/, '')
let LOGGED_OUT_MEMORY = false

export function getToken() { try { return localStorage.getItem(TOKEN_KEY) } catch (_) { return null } }
export function setToken(t) { try { t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY) } catch (_) {} }
export function clearToken() { setToken(null) }
export function isLoggedOut() {
  try { if (localStorage.getItem(LOGGED_OUT_KEY) === '1') return true } catch (_) {}
  try { if (sessionStorage.getItem(LOGGED_OUT_KEY) === '1') return true } catch (_) {}
  return LOGGED_OUT_MEMORY
}
export function setLoggedOut(value) {
  LOGGED_OUT_MEMORY = !!value
  try { value ? localStorage.setItem(LOGGED_OUT_KEY, '1') : localStorage.removeItem(LOGGED_OUT_KEY) } catch (_) {}
  try { value ? sessionStorage.setItem(LOGGED_OUT_KEY, '1') : sessionStorage.removeItem(LOGGED_OUT_KEY) } catch (_) {}
}

class ApiError extends Error {
  constructor(message, status, code) { super(message); this.status = status; this.code = code }
}

/* Дружелюбная заглушка вместо сырого текста ошибки. Пользователю показываем только
 * человеческие сообщения backend'а (detail.message — они написаны по-русски);
 * всё техническое (Internal Server Error, statusText, пустое тело) прячем. */
const FRIENDLY_FALLBACK = 'Что-то пошло не так. Попробуйте ещё раз чуть позже.'

function friendlyMessage(data, status) {
  const msg = data && (data.detail?.message || data.message)
  if (msg && typeof msg === 'string') return msg
  // detail-строка — только для клиентских ошибок (4xx): это наши тексты валидации.
  if (status < 500 && typeof data?.detail === 'string' && data.detail !== 'Not Found') return data.detail
  return FRIENDLY_FALLBACK
}

/* Текст ошибки для показа пользователю: сообщение ApiError (оно уже дружелюбное) либо
 * заглушка — внутренние ошибки JS (без .status) пользователю не показываем. */
export function errorMessage(err, fallback = FRIENDLY_FALLBACK) {
  if (err && err.status != null && typeof err.message === 'string' && err.message) return err.message
  return fallback
}

async function http(method, path, body) {
  const headers = { 'Content-Type': 'application/json' }
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  let resp
  try {
    resp = await fetch(`${BASE}${path}`, {
      method, headers, body: body != null ? JSON.stringify(body) : undefined,
      cache: 'no-store',  // вебвью мессенджеров кэшируют GET — берём всегда свежие данные
    })
  } catch (err) {
    // В реальном мессенджере недоступный backend — это явная ошибка авторизации.
    throw new ApiError('network', 0, 'network')
  }
  if (resp.status === 401) { clearToken(); throw new ApiError('unauthorized', 401, 'unauthorized') }
  let data = null
  try { data = await resp.json() } catch (_) {}
  if (!resp.ok) throw new ApiError(friendlyMessage(data, resp.status), resp.status, data && (data.detail?.code || data.code))
  return data
}

export const api = {
  setToken, getToken, clearToken, isLoggedOut, setLoggedOut,

  // --- Auth ---
  authContact: (p) => http('POST', '/auth/contact', p),
  authContactDiagnostic: (p) => http('POST', '/auth/contact/diagnostic', p),
  authSilent: (p) => http('POST', '/auth/silent', p),
  authOtpRequest: (p) => http('POST', '/auth/otp/request', p),
  authOtpVerify: (p) => http('POST', '/auth/otp/verify', p),
  getAccount: () => http('GET', '/account'),
  setAccountFlag: (flag) => http('POST', '/account/flags', { flag }),
  acceptLegal: (body) => http('POST', '/legal/accept', body),

  // --- Subscription / оплата ЮKassa ---
  getSubscription: () => http('GET', '/subscription'),
  payCheckout: (body) => http('POST', '/pay/checkout', body),
  payStatus: () => http('GET', '/pay/status'),
  payCancel: () => http('POST', '/pay/cancel'),
  payAutopay: (enabled) => http('POST', '/pay/autopay', { enabled }),
  activateCode: (code) => http('POST', '/pay/activate', { code }),

  // --- Sources ---
  getSources: () => http('GET', '/sources'),
  getSource: (id) => http('GET', `/sources/${id}`),
  createSourceCode: (messenger) => http('POST', '/sources/code', { messenger }),
  getPendingSource: () => http('GET', '/sources/pending'),
  deleteSource: (id) => http('DELETE', `/sources/${id}`),

  // --- Rules ---
  getRules: () => http('GET', '/rules'),
  createRule: (p) => http('POST', '/rules', p),
  updateRule: (id, patch) => http('PATCH', `/rules/${id}`, patch),
  setRuleStatus: (id, status) => http('POST', `/rules/${id}/${status === 'paused' ? 'pause' : 'resume'}`),
  deleteRule: (id) => http('DELETE', `/rules/${id}`),
  dismissRuleWarning: (id) => http('POST', `/rules/${id}/dismiss-warning`),

  // --- Traffic ---
  getTraffic: () => http('GET', '/traffic'),
  topupTraffic: () => http('POST', '/traffic/topup'),

  // --- Notifications ---
  getNotifications: () => http('GET', '/notifications'),
  readNotifications: (ids) => http('POST', '/notifications/read', ids ? { ids } : undefined),

  // --- Reports (жалоба на пересланный контент; без сессии — по initData) ---
  reportCheck: (body) => http('POST', '/report/check', body),
  report: (body) => http('POST', '/report', body),
}

export { ApiError }
export default api
