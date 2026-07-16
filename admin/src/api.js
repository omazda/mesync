/* api.js — клиент админ-API (/api/admin/*). Сессия — в HttpOnly-cookie, поэтому запросы
 * идут с credentials: 'include'; токен в JS не хранится и недоступен. */
const BASE = '/api/admin'

class AdminError extends Error {
  constructor(message, status, code) { super(message); this.status = status; this.code = code }
}

async function req(method, path, body) {
  let resp
  try {
    resp = await fetch(BASE + path, {
      method,
      credentials: 'include',
      headers: body != null ? { 'Content-Type': 'application/json' } : undefined,
      body: body != null ? JSON.stringify(body) : undefined,
      cache: 'no-store',
    })
  } catch (_) {
    throw new AdminError('Нет соединения с сервером.', 0, 'network')
  }
  let data = null
  try { data = await resp.json() } catch (_) {}
  if (!resp.ok) {
    // Сессия истекла/невалидна в середине работы → сообщаем приложению вернуться на вход.
    if (resp.status === 401) { try { window.dispatchEvent(new Event('admin-unauth')) } catch (_) {} }
    const msg = (data && data.detail && data.detail.message) || 'Что-то пошло не так.'
    throw new AdminError(msg, resp.status, data && data.detail && data.detail.code)
  }
  return data
}

async function download(path) {
  let resp
  try {
    resp = await fetch(BASE + path, {
      method: 'POST',
      credentials: 'include',
      cache: 'no-store',
    })
  } catch (_) {
    throw new AdminError('Нет соединения с сервером.', 0, 'network')
  }
  if (!resp.ok) {
    let data = null
    try { data = await resp.json() } catch (_) {}
    if (resp.status === 401) { try { window.dispatchEvent(new Event('admin-unauth')) } catch (_) {} }
    const msg = (data && data.detail && data.detail.message) || 'Не удалось скачать резервную копию.'
    throw new AdminError(msg, resp.status, data && data.detail && data.detail.code)
  }
  const disposition = resp.headers.get('Content-Disposition') || ''
  const match = disposition.match(/filename="([^"]+)"/i)
  return {
    blob: await resp.blob(),
    filename: match ? match[1] : 'mesync-control-backup.json',
  }
}

async function uploadBackup(path, file, headers = {}) {
  let resp
  try {
    resp = await fetch(BASE + path, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json', ...headers },
      body: file,
      cache: 'no-store',
    })
  } catch (_) {
    throw new AdminError('Нет соединения с сервером.', 0, 'network')
  }
  let data = null
  try { data = await resp.json() } catch (_) {}
  if (!resp.ok) {
    if (resp.status === 401) { try { window.dispatchEvent(new Event('admin-unauth')) } catch (_) {} }
    const msg = (data && data.detail && data.detail.message) || 'Не удалось обработать резервную копию.'
    throw new AdminError(msg, resp.status, data && data.detail && data.detail.code)
  }
  return data
}

function qs(params) {
  const p = new URLSearchParams()
  for (const [k, v] of Object.entries(params || {})) if (v !== '' && v != null) p.set(k, v)
  const s = p.toString()
  return s ? '?' + s : ''
}

export const api = {
  me: () => req('GET', '/me'),
  login: (password) => req('POST', '/login', { password }),
  logout: () => req('POST', '/logout'),
  getSettings: () => req('GET', '/settings'),
  putSettings: (patch) => req('PUT', '/settings', patch),
  getAudit: () => req('GET', '/audit'),
  ops: () => req('GET', '/ops'),
  downloadBackup: () => download('/backup'),
  validateBackup: (file) => uploadBackup('/backup/validate', file),
  restoreBackup: (file, sha256) => uploadBackup('/backup/restore', file, {
    'X-MeSync-Backup-SHA256': sha256,
    'X-MeSync-Restore-Confirm': 'restore',
  }),

  // --- Модерация (этап 4.2) ---
  modReports: (params) => req('GET', '/moderation/reports' + qs(params)),
  modReport: (id) => req('GET', `/moderation/reports/${id}`),
  modAction: (id, body) => req('POST', `/moderation/reports/${id}/action`, body),
  modClassify: (text) => req('POST', '/moderation/classify', { text }),
  getStoplist: () => req('GET', '/moderation/stoplist'),
  putStoplist: (text) => req('PUT', '/moderation/stoplist', { text }),

  // --- Аккаунты + биллинг (этап 4.3) ---
  accounts: (params) => req('GET', '/accounts' + qs(params)),
  account: (id) => req('GET', `/accounts/${id}`),
  accountAction: (id, body) => req('POST', `/accounts/${id}/action`, body),
  subscriptions: (params) => req('GET', '/subscriptions' + qs(params)),
  genCodes: (count) => req('POST', '/codes', { count }),
  listCodes: () => req('GET', '/codes'),
  revokeCode: (code) => req('POST', `/codes/${encodeURIComponent(code)}/action`, { action: 'revoke' }),

  // --- Правила / Источники / Трафик (этап 4.4) ---
  rules: (params) => req('GET', '/rules' + qs(params)),
  rule: (id) => req('GET', `/rules/${id}`),
  ruleAction: (id, body) => req('POST', `/rules/${id}/action`, body),
  sources: (params) => req('GET', '/sources' + qs(params)),
  traffic: (params) => req('GET', '/traffic' + qs(params)),
  trafficAction: (id, body) => req('POST', `/traffic/${id}/action`, body),

  // --- Рассылки в личку (этап 4.6) ---
  broadcasts: (params) => req('GET', '/broadcasts' + qs(params)),
  broadcast: (id) => req('GET', `/broadcasts/${id}`),
  broadcastPreview: (body) => req('POST', '/broadcasts/preview', body),
  createBroadcast: (body) => req('POST', '/broadcasts', body),
  cancelBroadcast: (id) => req('POST', `/broadcasts/${id}/action`, { action: 'cancel' }),
}

export { AdminError }
