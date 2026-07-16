/* _shared.jsx — общие для экранов хелперы и константы (единые тексты/формат). */
import React from 'react'
import { Avatar, Cell, Icon, TabBar } from '../components/ui.jsx'
import { useScheme } from '../host/useScheme.js'
import { useStore } from '../store/store.js'
import host from '../host/host.js'
import logoLight from '../assets/logo-light.png'
import logoDark from '../assets/logo-dark.png'

const RUNTIME_CONFIG = (typeof window !== 'undefined' && window.__MESYNC_PUBLIC_CONFIG__) || {}
const RUNTIME_SUPPORT = RUNTIME_CONFIG.support || {}
const RUNTIME_LEGAL = RUNTIME_CONFIG.legal || {}
const RUNTIME_LANDING = RUNTIME_CONFIG.landing || {}

export const BOT_NAME = String(RUNTIME_CONFIG.botName || import.meta.env?.VITE_MESYNC_BOT_NAME || 'MeSync')
export const BOT_AVATAR_URL = String(RUNTIME_CONFIG.botAvatarUrl || import.meta.env?.VITE_MESYNC_BOT_AVATAR_URL || '')
export const BOT_LINKS = {
  max: String(RUNTIME_CONFIG.botLinks?.max || import.meta.env?.VITE_MESYNC_MAX_BOT_URL || ''),
  tg: String(RUNTIME_CONFIG.botLinks?.tg || import.meta.env?.VITE_MESYNC_TG_BOT_URL || ''),
}
const handleFromUrl = (value) => {
  try {
    const segment = decodeURIComponent(new URL(value).pathname.split('/').filter(Boolean).at(-1) || '')
    return segment ? `@${segment.replace(/^@/, '')}` : ''
  } catch (_) { return '' }
}
export const BOT_HANDLES = Object.fromEntries(Object.entries(BOT_LINKS).map(
  ([messenger, url]) => [messenger, String(RUNTIME_CONFIG.botHandles?.[messenger] || handleFromUrl(url))],
))
/* Контакты поддержки (хаб «Настройки» и S14 «Частые вопросы»). */
export const SUPPORT_TG_URL = String(RUNTIME_SUPPORT.telegramUrl || import.meta.env?.VITE_MESYNC_SUPPORT_TG_URL || '')
export const SUPPORT_TG_HANDLE = String(RUNTIME_SUPPORT.telegramHandle || handleFromUrl(SUPPORT_TG_URL))
export const SUPPORT_EMAIL = String(RUNTIME_SUPPORT.email || import.meta.env?.VITE_MESYNC_SUPPORT_EMAIL || '')
export const HAS_SUPPORT = !!(SUPPORT_TG_URL || SUPPORT_EMAIL)
/* Юридические документы (публичная оферта и политика конфиденциальности). */
const APP_URL = String(RUNTIME_CONFIG.appUrl || import.meta.env?.VITE_MESYNC_APP_URL || '').replace(/\/$/, '')
export const LEGAL_TERMS_URL = `${APP_URL}/legal/terms/?lang=ru`
export const LEGAL_PRIVACY_URL = `${APP_URL}/legal/privacy/?lang=ru`
export const LEGAL_TERMS_VERSION = String(RUNTIME_LEGAL.termsVersion || import.meta.env?.VITE_MESYNC_LEGAL_TERMS_VERSION || '2026-07-08')
export const LEGAL_PRIVACY_VERSION = String(RUNTIME_LEGAL.privacyVersion || import.meta.env?.VITE_MESYNC_LEGAL_PRIVACY_VERSION || '2026-07-11')
export const LANDING_DESCRIPTION = String(RUNTIME_LANDING.description || import.meta.env?.VITE_MESYNC_LANDING_DESCRIPTION || `${BOT_NAME} синхронизирует сообщения и посты между групповыми чатами и каналами MAX и Telegram, сохраняя форматирование, фото, видео и файлы.`)
export const LANDING_OFFER_TITLE = String(RUNTIME_LANDING.offerTitle ?? import.meta.env?.VITE_MESYNC_LANDING_OFFER_TITLE ?? '7 дней бесплатно')
export const LANDING_OFFER_TEXT = String(RUNTIME_LANDING.offerText ?? import.meta.env?.VITE_MESYNC_LANDING_OFFER_TEXT ?? 'Новым пользователям после входа и подключения автопродления. Сейчас 0 ₽.')
export const LANDING_ANALYTICS_NOTICE = String(RUNTIME_LANDING.analyticsNotice ?? import.meta.env?.VITE_MESYNC_LANDING_ANALYTICS_NOTICE ?? 'Находясь на этом сайте, вы соглашаетесь на сбор аналитических данных.')

export function botLaunchUrl(messenger, source = 'web') {
  const base = BOT_LINKS[messenger]
  if (!base) return ''
  try {
    const url = new URL(base)
    url.searchParams.set('start', source)
    return url.toString()
  } catch (_) { return '' }
}

/* Строка-футер со ссылками на юридические документы (пейволл, настройки). */
export function LegalLinks({ style }) {
  const link = { color: 'var(--accent)', cursor: 'pointer' }
  const open = (event, url) => {
    event.preventDefault()
    host.openLink(url)
  }
  return (
    <div className="t-footnote sec text-pretty" style={{ textAlign: 'center', ...style }}>
      <a href={LEGAL_TERMS_URL} style={link} onClick={(e) => open(e, LEGAL_TERMS_URL)}>Пользовательское соглашение</a>
      {' · '}
      <a href={LEGAL_PRIVACY_URL} style={link} onClick={(e) => open(e, LEGAL_PRIVACY_URL)}>Политика конфиденциальности</a>
    </div>
  )
}
/* Ссылка на бота внутри текста инструкции: тап открывает бота (в «своём» мессенджере —
 * внутри него, см. host.openLink). Показывает сам URL — его видно и можно переслать. */
export function BotLink({ m }) {
  const url = BOT_LINKS[m]
  if (!url) return <span className="sec">Ссылка на бота не настроена</span>
  return (
    <span role="link" style={{ color: 'var(--accent)', cursor: 'pointer', wordBreak: 'break-all' }}
      onClick={() => { host.haptic('light'); host.openLink(url) }}>
      {url}
    </span>
  )
}

/* Название бота внутри инструкции: тап копирует username/handle бота в буфер. */
export function BotHandleTap({ m }) {
  const showToast = useStore((s) => s.showToast)
  const handle = BOT_HANDLES[m]
  const copy = async () => {
    try { await navigator.clipboard?.writeText(handle) } catch (_) { /* ignore */ }
    host.haptic('light')
    showToast('Username бота скопирован')
  }
  return handle ? (
    <span className="bot-handle-tap" role="button" aria-label={`Скопировать username ${handle}`} onClick={copy}>
      {BOT_NAME}<Icon.copy size={12} />
    </span>
  ) : <span>{BOT_NAME}</span>
}
export const PAY_STUB = 'Оплата пока недоступна. Мы включим её совсем скоро.'
export const WHAT_IS_SOURCE = 'Источник — это ваш групповой чат или канал в MAX или Telegram, куда добавлен наш бот. Из одних источников бот читает, в другие — пишет.'
export const DEAD_TEXT = 'Источник временно не отвечает, мы уже знаем о ситуации и чиним.'

/* Крупный заголовок раздела (large title). */
export function LargeTitle({ children, after, sub }) {
  return (
    <div style={{ padding: '4px 16px 6px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span className="t-title-lg">{children}</span>
        {after}
      </div>
      {sub && <div className="t-footnote sec" style={{ marginTop: 2 }}>{sub}</div>}
    </div>
  )
}

/* Футер вкладки: контент над таб-баром + таб-бар. */
export function TabFooter({ sourcesBadge, children }) {
  return (
    <div style={{ flex: '0 0 auto', background: 'var(--bg-grouped)' }}>
      {children && <div style={{ padding: '6px 16px 10px' }}>{children}</div>}
      <TabBar sourcesBadge={sourcesBadge} />
    </div>
  )
}

/* Остров «Поддержка»: чат в Telegram + почта. Почту копируем в буфер с тостом —
 * mailto: в webview мессенджера может быть никем не обработан, а копирование
 * работает всегда; попутно best-effort пробуем открыть почтовый клиент. */
export function SupportIsland() {
  const showToast = useStore((s) => s.showToast)
  const openTg = () => { host.haptic('light'); host.openLink(SUPPORT_TG_URL) }
  const openMail = async () => {
    host.haptic('light')
    try { await navigator.clipboard?.writeText(SUPPORT_EMAIL) } catch (_) { /* ignore */ }
    showToast('Почта скопирована')
    try { window.location.href = `mailto:${SUPPORT_EMAIL}` } catch (_) { /* ignore */ }
  }
  if (!HAS_SUPPORT) return null
  return (
    <div className="island">
      {SUPPORT_TG_URL && (
        <Cell inset tap
          before={<Avatar size={38} tone="av-blue" icon={<Icon.send />} />}
          title="Написать в Telegram" subtitle={SUPPORT_TG_HANDLE || SUPPORT_TG_URL}
          after={<span style={{ color: 'var(--text-tertiary)' }}><Icon.link size={16} /></span>}
          onClick={openTg} />
      )}
      {SUPPORT_EMAIL && (
        <Cell inset tap
          before={<Avatar size={38} tone="av-green" icon={<Icon.mail />} />}
          title="Написать на почту" subtitle={SUPPORT_EMAIL}
          after={<span style={{ color: 'var(--text-tertiary)' }}><Icon.copy size={16} /></span>}
          onClick={openMail} />
      )}
    </div>
  )
}

/* Логотип бренда (тема-зависимый). */
export function BrandMark({ size = 72 }) {
  const scheme = useScheme()
  const src = BOT_AVATAR_URL || (scheme === 'dark' ? logoDark : logoLight)
  return (
    <img src={src} alt=""
      style={{ width: size, height: size, borderRadius: size * 0.28, objectFit: 'cover', boxShadow: '0 8px 22px rgba(0,0,0,0.18)' }} />
  )
}

/* Код привязки внутри текста: тап копирует его в буфер (тост + хаптика).
 * Пока код не выпущен («····») — обычное выделение без копирования. */
export function CodeTap({ code }) {
  const showToast = useStore((s) => s.showToast)
  const ready = /^\d{4}$/.test(String(code))
  const copy = async () => {
    if (!ready) return
    try { await navigator.clipboard?.writeText(String(code)) } catch (_) { /* ignore */ }
    host.haptic('light')
    showToast('Код скопирован')
  }
  if (!ready) return <b>{code}</b>
  return (
    <span className="code-tap" role="button" aria-label={`Скопировать код ${code}`} onClick={copy}>
      {code}<Icon.copy size={12} />
    </span>
  )
}

/* Строка-галочка (списки преимуществ). */
export function CheckRow({ children }) {
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10, padding: '7px 0' }}>
      <span style={{ flex: '0 0 auto', marginTop: 1, color: 'var(--success)' }}><Icon.check size={19} /></span>
      <span className="t-body-sm">{children}</span>
    </div>
  )
}

/* ---- форматирование ---- */
const KB = 1024
const MB = 1024 ** 2
const GB = 1024 ** 3
const TB = 1024 ** 4
export function fmtTB(bytes) {
  const v = bytes / TB
  return `${v.toFixed(2).replace('.', ',')} ТБ`
}
/* Адаптивный размер (КБ/МБ/ГБ/ТБ) — для ЗНАЧЕНИЙ РАСХОДА: небольшой расход в МБ должен
 * быть виден, а не округляться в «0,00 ТБ» (иначе кажется, что трафик не считается). Лимит
 * по-прежнему показываем в ТБ (fmtTB), чтобы сохранить формулировку тарифа «0,5 ТБ». */
export function fmtBytes(bytes) {
  const b = Math.max(0, Number(bytes) || 0)
  if (b >= TB) return `${(b / TB).toFixed(2).replace('.', ',')} ТБ`
  if (b >= GB) return `${(b / GB).toFixed(1).replace('.', ',')} ГБ`
  if (b >= MB) return `${Math.round(b / MB)} МБ`
  if (b >= KB) return `${Math.round(b / KB)} КБ`
  return `${Math.round(b)} Б`
}
export function relTime(ts) {
  const diff = Date.now() - ts
  const h = Math.floor(diff / 3600e3)
  if (h < 1) return `${Math.max(1, Math.floor(diff / 60e3))} мин назад`
  if (h < 24) return `${h} ч назад`
  const d = new Date(ts)
  return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' })
}
