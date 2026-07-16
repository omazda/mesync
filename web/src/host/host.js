/* host.js — единый слой над хостами mini-app.
 *
 * Приложение запускается внутри двух мессенджеров и в обычном браузере:
 *   - Telegram Mini Apps: window.Telegram.WebApp (хорошо документирован);
 *   - MAX: window.WebApp / MAX Bridge (поверхность определяем по факту,
 *     методы вызываем только при наличии — деградируем мягко);
 *   - браузер: публичный переход к настроенным ссылкам на ботов.
 *
 * Наружу отдаём ОДИН объект `host` со стабильным API. Нативные кнопки
 * MainButton мы НЕ используем (CTA рисуем в футере экрана, как в макетах);
 * нативную BackButton подключаем, когда хост её предоставляет.
 */

const tg = typeof window !== 'undefined' ? window.Telegram?.WebApp : undefined
// MAX кладёт мост в window.WebApp (его нет ни в обычном вебе, ни в Telegram).
const mx = typeof window !== 'undefined' ? window.WebApp : undefined

// Важно: подключённый telegram-web-app.js определяет window.Telegram.WebApp ВСЕГДА
// (даже в обычном браузере), поэтому само наличие объекта не значит «мы в Telegram».
// Реальный запуск Telegram даёт непустой initData или platform ≠ 'unknown'.
function isRealTelegram() {
  if (!tg) return false
  if (tg.initData) return true
  const p = tg.platform
  return !!(p && p !== 'unknown')
}

// Аналогично: max-web-app.js ставит window.WebApp ВСЕГДА (constructor синхронно читает
// launch-данные из location.hash). Реальный запуск внутри MAX даёт непустой initData,
// объект user или валидный platform; в обычном браузере initData пуст, platform = null.
function isRealMax() {
  if (!mx) return false
  if (mx.initData) return true
  if (mx.initDataUnsafe && mx.initDataUnsafe.user) return true
  const p = mx.platform
  return !!(p && p !== 'unknown')
}

function detect() {
  if (isRealMax()) return 'max'
  if (isRealTelegram()) return 'telegram'
  return 'browser'
}

const NAME = detect()
if (typeof window !== 'undefined') { try { window.__mesyncHost = NAME } catch (_) { /* ignore */ } }
const listeners = new Set()
let _scheme = initialScheme()

function initialScheme() {
  if (NAME === 'telegram') return tg.colorScheme || 'light'
  if (NAME === 'max') return mx.colorScheme || mx.theme || 'light'
  if (typeof window !== 'undefined' && window.matchMedia) {
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  }
  return 'light'
}

function emit() { for (const l of listeners) { try { l(_scheme) } catch (_) { /* ignore */ } } }
function setScheme(s) { if (s && s !== _scheme) { _scheme = s; emit() } }

/* ---- подписка на смену темы ---- */
if (NAME === 'telegram') {
  try { tg.onEvent('themeChanged', () => setScheme(tg.colorScheme || 'light')) } catch (_) {}
} else if (NAME === 'max') {
  // У MAX событие может называться иначе — пробуем известные варианты.
  try { mx.onEvent?.('themeChanged', () => setScheme(mx.colorScheme || mx.theme || 'light')) } catch (_) {}
} else if (typeof window !== 'undefined' && window.matchMedia) {
  const mq = window.matchMedia('(prefers-color-scheme: dark)')
  const handler = (e) => setScheme(e.matches ? 'dark' : 'light')
  mq.addEventListener ? mq.addEventListener('change', handler) : mq.addListener(handler)
}

function platform() {
  if (NAME === 'telegram') return normPlatform(tg.platform)
  if (NAME === 'max') return normPlatform(mx.platform || mx.os)
  return 'web'
}
function normPlatform(p) {
  p = String(p || '').toLowerCase()
  if (p.includes('ios') || p.includes('iphone') || p.includes('ipad')) return 'ios'
  if (p.includes('android')) return 'android'
  if (['tdesktop', 'macos', 'windows', 'linux', 'web', 'weba', 'webk'].some((x) => p.includes(x))) return 'web'
  return p || 'web'
}

function themeParams() {
  if (NAME === 'telegram') return tg.themeParams || {}
  if (NAME === 'max') return mx.themeParams || mx.theme_params || {}
  return {}
}

const host = {
  name: NAME,
  platform: platform(),
  bridgeVersion: NAME === 'max' ? String(mx.version || '') : '',

  get colorScheme() { return _scheme },
  themeParams,

  onThemeChanged(cb) { listeners.add(cb); return () => listeners.delete(cb) },

  ready() {
    try {
      if (NAME === 'telegram') {
        tg.ready(); tg.expand?.()
        // Скролл списков не должен сворачивать mini-app свайпом вниз (Bot API 7.7+;
        // на старых клиентах SDK сам игнорирует вызов).
        tg.disableVerticalSwipes?.()
      }
    } catch (_) {}
    try { if (NAME === 'max') { mx.ready?.(); mx.expand?.() } } catch (_) {}
  },

  close() {
    try { if (NAME === 'telegram') return tg.close() } catch (_) {}
    try { if (NAME === 'max') return mx.close?.() } catch (_) {}
  },

  openLink(url) {
    // «Свои» ссылки хоста открываем внутри мессенджера, не во внешнем браузере:
    // Telegram — WebApp.openTelegramLink (t.me, mini-app не закрывается, Bot API 7.0+),
    // MAX — WebApp.openMaxLink (диплинки max.ru). Сверено с docs/telegram
    // 11-webapps-miniapps и docs/max docs/webapps/bridge.
    try {
      if (NAME === 'telegram') {
        if (/^https:\/\/t\.me\//i.test(url)) return tg.openTelegramLink(url)
        return tg.openLink(url)
      }
    } catch (_) {}
    try {
      if (NAME === 'max') {
        if (/^https:\/\/max\.ru\//i.test(url) && mx.openMaxLink) return mx.openMaxLink(url)
        return mx.openLink?.(url)
      }
    } catch (_) {}
    if (typeof window !== 'undefined') window.open(url, '_blank', 'noopener')
  },

  /* Хаптика: 'light'|'medium'|'heavy'|'success'|'warning'|'error'|'selection' */
  haptic(type = 'light') {
    try {
      if (NAME === 'telegram') {
        const h = tg.HapticFeedback
        if (!h) return
        if (type === 'selection') return h.selectionChanged()
        if (['success', 'warning', 'error'].includes(type)) return h.notificationOccurred(type)
        return h.impactOccurred(type === 'heavy' ? 'heavy' : type === 'medium' ? 'medium' : 'light')
      }
      if (NAME === 'max') { mx.haptic?.(type) ?? mx.hapticFeedback?.(type) }
    } catch (_) {}
  },

  /* Нативная кнопка «Назад»: возвращает функцию отписки. */
  backButton(visible, onClick) {
    try {
      if (NAME === 'telegram' && tg.BackButton) {
        if (visible) {
          tg.BackButton.show()
          tg.BackButton.onClick(onClick)
          return () => { try { tg.BackButton.offClick(onClick); tg.BackButton.hide() } catch (_) {} }
        }
        tg.BackButton.hide()
        return () => {}
      }
      if (NAME === 'max' && mx.BackButton) {
        if (visible) { mx.BackButton.show?.(); mx.BackButton.onClick?.(onClick); return () => { try { mx.BackButton.offClick?.(onClick); mx.BackButton.hide?.() } catch (_) {} } }
        mx.BackButton.hide?.()
        return () => {}
      }
    } catch (_) {}
    return () => {}
  },

  /* Нативный запрос контакта/номера. MAX возвращает подписанные данные, Telegram —
   * только маркер успешной отправки self-contact боту. Ошибка MAX отклоняет Promise
   * с безопасным bridgeCode, чтобы экран мог отправить его в диагностику backend-а. */
  async requestContact() {
    if (NAME === 'max') return requestContactMax()
    if (NAME === 'telegram') return requestContactTelegram()
    return null
  },

  /* Данные для авторизации на бэкенде (подпись хоста). */
  getInitData() {
    if (NAME === 'telegram') return { kind: 'telegram-initdata', raw: tg.initData || '', unsafe: tg.initDataUnsafe || {} }
    if (NAME === 'max') return { kind: 'max-initdata', raw: mx.initData || mx.launchParams || '', unsafe: mx.initDataUnsafe || {} }
    return { kind: 'browser', raw: '', unsafe: {} }
  },

  /* Параметр запуска mini-app из диплинка (?startapp=<param>). Telegram и MAX обычно кладут
   * его в initDataUnsafe.start_param; Telegram также передаёт GET-параметр
   * tgWebAppStartParam (docs/telegram 11-webapps-miniapps). Query-fallback нужен и для
   * браузера/дева, и для host-запусков, где SDK не вернул start_param. Используется для
   * роутинга жалоб (startapp=r_<token>). */
  startParam: readStartParam(),

}

function readStartParam() {
  let fromHost = ''
  try {
    if (NAME === 'telegram') fromHost = tg.initDataUnsafe?.start_param || ''
    if (NAME === 'max') fromHost = mx.initDataUnsafe?.start_param || ''
  } catch (_) {}
  if (fromHost) return fromHost
  try {
    const q = new URLSearchParams(window.location.search)
    return q.get('startapp') || q.get('tgWebAppStartParam') || q.get('WebAppStartParam') || ''
  } catch (_) { return '' }
}

/* ---------- requestContact реализации ---------- */
function maxContactFailure(err, fallback = 'client.request_phone.unknown_error') {
  const rawCode = err?.error?.code || err?.code || fallback
  const bridgeCode = String(rawCode || fallback)
  const failure = new Error('MAX requestContact failed')
  failure.bridgeCode = bridgeCode
  if (bridgeCode === 'client.request_phone.user_refused_provide_phone_number') {
    failure.code = 'contact_refused'
  } else if (bridgeCode === 'client.request_phone.not_supported') {
    failure.code = 'contact_unsupported'
  } else {
    failure.code = 'max_contact_error'
  }
  return failure
}

function requestContactMax() {
  return new Promise((resolve, reject) => {
    const accept = (data) => {
      if (data?.error) {
        reject(maxContactFailure(data))
        return
      }
      const contact = normContact(data)
      if (!contact?.phone || contact.authDate == null || !contact.hash) {
        reject(maxContactFailure(null, 'client.request_phone.invalid_response'))
        return
      }
      resolve(contact)
    }
    try {
      if (typeof mx?.requestContact !== 'function') {
        reject(maxContactFailure(null, 'client.request_phone.not_supported'))
        return
      }
      const r = mx.requestContact()
      if (r && typeof r.then === 'function') {
        r.then(accept).catch((err) => reject(maxContactFailure(err)))
        return
      }
      // Колбэк-вариант моста.
      if (!r && typeof mx.onEvent === 'function') {
        mx.onEvent('contactReceived', accept)
        return
      }
      if (r) accept(r)
      else reject(maxContactFailure(null, 'client.request_phone.invalid_response'))
    } catch (err) { reject(maxContactFailure(err)) }
  })
}
function requestContactTelegram() {
  return new Promise((resolve) => {
    try {
      if (typeof tg.requestContact === 'function') {
        tg.requestContact((ok) => {
          if (!ok) return resolve(null)
          // Telegram WebApp API документирует только boolean. Сам Contact приходит
          // отдельным сообщением боту и проверяется backend-ом как self-contact.
          resolve({ shared: true })
        })
        return
      }
      resolve(null)
    } catch (_) { resolve(null) }
  })
}
function normContact(d) {
  if (!d || d.error) return null
  return {
    phone: String(d.phone || d.phone_number || d.phoneNumber || '').replace(/^\+/, ''),
    authDate: d.authDate ?? d.auth_date ?? null,
    hash: d.hash || '',
    firstName: d.first_name || d.firstName,
    raw: d,
  }
}

export default host
