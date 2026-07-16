/* ui.jsx — общие компоненты mini-app: Sheet, Banner, Field, OtpInput,
 * TrafficRing, Skeleton и базовые элементы интерфейса. */
import React, { useEffect, useRef, useState } from 'react'
import {
  Button as TgButton, Switch as TgSwitch, Input as TgInput, Spinner as TgSpinner,
} from '@telegram-apps/telegram-ui'
import { Icon } from './Icon.jsx'
import host from '../host/host.js'
import { useStore } from '../store/store.js'

/* ---------- Каркас экрана ---------- */
export function Screen({ grouped, children }) {
  return <div className={`screen${grouped ? ' grouped' : ''}`}>{children}</div>
}

/* ---------- Под-шапка (заголовок/назад/действия) ----------
 * Нативные BackButton/закрытие даёт хост; здесь — внутренняя шапка экрана. */
export function HostHeader({ title, back = false, onBack, close = false, onClose,
  onGrouped = false, bell = false, bellBadge = 0, right = null }) {
  const storeBack = useStore((s) => s.back)
  const openNotifications = useStore((s) => s.push)
  const actionCount = (bell ? 1 : 0) + (close ? 1 : 0) + (right ? 1 : 0)
  const sideWidth = Math.max(44, actionCount * 32)
  return (
    <div className={`host-header${onGrouped ? ' on-grouped' : ''}`}>
      <div style={{ minWidth: sideWidth, display: 'flex', alignItems: 'center' }}>
        {back && <div className="host-back" onClick={onBack || storeBack}><Icon.back size={22} /></div>}
      </div>
      <div className="host-title">{title}</div>
      <div className="host-actions" style={{ minWidth: sideWidth }}>
        {right}
        {bell && (
          <div className="host-icon-btn" onClick={() => openNotifications('S13')}>
            <Icon.bell size={17} />
            {bellBadge > 0 && <span className="badge-dot">{bellBadge > 9 ? '9+' : bellBadge}</span>}
          </div>
        )}
        {close && <div className="host-icon-btn" onClick={onClose || (() => host.close())}><Icon.close size={16} /></div>}
      </div>
    </div>
  )
}

/* ---------- Кнопки (элементы библиотеки @telegram-apps/telegram-ui) ---------- */
const _danger = { '--tgui--button_color': 'var(--danger)' }

/* Универсальная кнопка поверх Button из telegram-ui. */
export function Btn({ children, kind = 'primary', size = 'l', stretched = true, loading = false,
  disabled = false, onClick, before, style }) {
  const mode = kind === 'secondary' ? 'bezeled' : kind === 'plain' ? 'plain'
    : kind === 'gray' ? 'gray' : 'filled'
  const st = kind === 'destructive' ? { ..._danger, ...style } : style
  return (
    <TgButton mode={mode} size={size} stretched={stretched} loading={loading} disabled={disabled}
      before={before} onClick={(disabled || loading) ? undefined : onClick} style={st}>
      {children}
    </TgButton>
  )
}

/* Главная кнопка действия экрана (футер, на всю ширину). */
export function MainButton({ label, kind = 'primary', icon, grouped = false, loading = false, sub, onClick, disabled }) {
  const isDisabled = kind === 'disabled' || disabled
  return (
    <div className={`footer-area${grouped ? ' grouped' : ''}`}>
      {sub && <div className="t-footnote sec text-pretty" style={{ textAlign: 'center', padding: '0 4px 8px' }}>{sub}</div>}
      <Btn kind={isDisabled ? 'gray' : kind} loading={loading} disabled={isDisabled}
        before={icon} onClick={onClick}>{label}</Btn>
    </div>
  )
}

/* ---------- Таб-бар ---------- */
export function TabBar({ sourcesBadge }) {
  const tab = useStore((s) => s.nav.tab)
  const setTab = useStore((s) => s.setTab)
  const tabs = [
    { id: 'rules', label: 'Правила', ic: Icon.rules },
    { id: 'sources', label: 'Источники', ic: Icon.source },
    { id: 'settings', label: 'Настройки', ic: Icon.settings },
  ]
  return (
    <div className="tabbar">
      {tabs.map((t) => (
        <div key={t.id} className={`tab${tab === t.id ? ' active' : ''}`} onClick={() => setTab(t.id)}>
          <t.ic size={26} />
          <span>{t.label}</span>
          {t.id === 'sources' && sourcesBadge && (sourcesBadge === true ? <span className="tab-dot" /> : <span className="tab-badge">{sourcesBadge}</span>)}
        </div>
      ))}
    </div>
  )
}

/* ---------- Аватар ----------
 * src — фото чата/канала (реальная аватарка). Если не задан или не загрузился —
 * показываем запасной вариант: иконку типа (icon) или текст (text) на цветном фоне. */
export function Avatar({ size = 40, form = 'squircle', tone = 'av-blue', text, icon, src, style }) {
  const [failed, setFailed] = useState(false)
  useEffect(() => { setFailed(false) }, [src])
  const showImg = src && !failed
  return (
    <div className={`avatar ${form} ${tone}`} style={{ width: size, height: size, fontSize: size * 0.4, ...style }}>
      {showImg
        ? <img src={src} alt="" loading="lazy" decoding="async" onError={() => setFailed(true)}
            style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }} />
        : (icon ? React.cloneElement(icon, { size: size * 0.52 }) : text)}
    </div>
  )
}

/* ---------- Бейджи / чипы ---------- */
export function MBadge({ m }) { return <span className={`mbadge ${m === 'MAX' || m === 'max' ? 'max' : 'tg'}`}>{m === 'max' ? 'MAX' : m === 'tg' ? 'TG' : m}</span> }
export function TBadge({ type, compact = false }) {
  const label = type === 'channel' ? 'Канал' : type === 'topic' ? 'Тема'
    : type === 'supergroup' ? 'Супергруппа' : type === 'group' ? 'Группа' : type
  const displayLabel = compact && type === 'supergroup' ? 'SuperGroup' : label
  const I = label === 'Канал' ? Icon.megaphone : Icon.people
  return <span className={`tbadge${compact ? ' compact' : ''}`}>{!compact && <I size={12} />}{displayLabel}</span>
}
export function StatusChip({ status, code }) {
  if (status === 'ok') return null   // «Привязан» не показываем — источник и так в разделе «Привязанные»
  if (status === 'wait') return <span className="chip wait"><Icon.clock size={13} />{code ? `Ожидаю код · ${code}` : 'Ожидаю код'}</span>
  if (status === 'err') return <span className="chip err"><Icon.alert size={13} />Бот не админ</span>
  if (status === 'dead') return <span className="chip dead"><Icon.alert size={13} />Не отвечает</span>
  return null
}

/* ---------- Переключатель / спиннер / счётчик / точка ---------- */
/* Switch — элемент telegram-ui. on→checked; если есть onClick на самом тумблере —
 * вешаем onChange, иначе делаем readOnly (клик обрабатывает обёртка). */
export function Switch({ on, disabled, onClick }) {
  return <TgSwitch checked={!!on} disabled={disabled}
    onChange={onClick ? () => onClick() : undefined} readOnly={!onClick} />
}
export function Counter({ value, themed, negative, style }) { return <span className={`counter${themed ? ' themed' : ''}${negative ? ' negative' : ''}`} style={style}>{value}</span> }
export function Dot({ tone = 'green' }) { return <span className={`dot ${tone}`} /> }
/* Spinner: цветной — из telegram-ui; «light» (белый на акценте) оставлен своим. */
export function Spinner({ size = 18, light = false }) {
  if (light) {
    return (
      <svg className="spin" width={size} height={size} viewBox="0 0 24 24" fill="none">
        <circle cx="12" cy="12" r="9" stroke="rgba(255,255,255,0.35)" strokeWidth="3" />
        <path d="M12 3a9 9 0 0 1 9 9" stroke="#fff" strokeWidth="3" strokeLinecap="round" />
      </svg>
    )
  }
  return <TgSpinner size={size <= 18 ? 's' : size <= 30 ? 'm' : 'l'} />
}

/* ---------- Ячейка ---------- */
export function Cell({ before, title, subtitle, overline, after, chevron, inset, compact, tall, onClick, tap = true, titleStyle, style, className = '' }) {
  return (
    <div className={`cell${inset ? ' inset' : ''}${compact ? ' compact' : ''}${tall ? ' tall' : ''}${tap ? ' tap' : ''} ${className}`} onClick={onClick} style={style}>
      {before && <div className="cell-before">{before}</div>}
      <div className="cell-main">
        {overline && <div className="cell-overline">{overline}</div>}
        {title && <div className="cell-title" style={titleStyle}>{title}</div>}
        {subtitle && <div className="cell-sub">{subtitle}</div>}
      </div>
      {after && <div className="cell-after">{after}</div>}
      {chevron && <span className="chevron"><Icon.chevron size={18} /></span>}
    </div>
  )
}

/* ---------- Тост ---------- */
export function Toast({ icon, children }) { return <div className="toast">{icon}<span>{children}</span></div> }

/* ---------- Баннер ---------- */
export function Banner({ tone = 'info', icon, title, children, action }) {
  return (
    <div className={`banner ${tone}`}>
      {icon && <span className="b-ic">{icon}</span>}
      <div style={{ flex: 1 }}>
        {title && <div className="b-title">{title}</div>}
        {children && <div className="text-pretty" style={{ marginTop: title ? 3 : 0 }}>{children}</div>}
      </div>
      {action}
    </div>
  )
}

/* ---------- Нижний лист (bottom sheet) ---------- */
export function Sheet({ title, onClose, children, footer, grabber = true,
  className = '', bodyClassName = '', footerClassName = '' }) {
  const closeSheet = useStore((s) => s.closeSheet)
  const close = onClose || closeSheet
  return (
    <div className="overlay" onClick={close}>
      <div className={`sheet${className ? ` ${className}` : ''}`} onClick={(e) => e.stopPropagation()}>
        {grabber && <div className="sheet-grabber" />}
        {title && (
          <div className="sheet-header">
            <div style={{ width: 30 }} />
            <div className="sheet-title">{title}</div>
            <div className="host-icon-btn" onClick={close}><Icon.close size={16} /></div>
          </div>
        )}
        <div className={`sheet-body${bodyClassName ? ` ${bodyClassName}` : ''}`}>{children}</div>
        {footer && <div className={`sheet-footer${footerClassName ? ` ${footerClassName}` : ''}`}>{footer}</div>}
      </div>
    </div>
  )
}

/* ---------- Поле ввода (Input из telegram-ui) ---------- */
export function Field({ value, onChange, placeholder, before, type = 'text', inputMode, error, autoFocus, header }) {
  return (
    <TgInput value={value} onChange={(e) => onChange?.(e.target.value)} placeholder={placeholder}
      type={type} inputMode={inputMode} autoFocus={autoFocus} before={before} header={header}
      status={error ? 'error' : 'default'} />
  )
}

/* ---------- Ввод кода (OTP, 4 ячейки) ---------- */
export function OtpInput({ length = 4, value = '', onChange, onComplete, error, autoFocus = true }) {
  const ref = useRef(null)
  useEffect(() => { if (autoFocus) setTimeout(() => ref.current?.focus(), 120) }, [autoFocus])
  const set = (raw) => {
    const v = raw.replace(/\D/g, '').slice(0, length)
    onChange?.(v)
    if (v.length === length) onComplete?.(v)
  }
  const cells = Array.from({ length })
  return (
    <div style={{ position: 'relative' }}>
      <input ref={ref} value={value} onChange={(e) => set(e.target.value)} inputMode="numeric"
        autoComplete="one-time-code" maxLength={length}
        style={{ position: 'absolute', inset: 0, opacity: 0, width: '100%', height: '100%', border: 'none', fontSize: 1, caretColor: 'transparent' }} />
      <div className="otp-grid">
        {cells.map((_, i) => (
          <div key={i} className={`otp-cell${error ? ' error' : (i === value.length ? ' active' : '')}`}>{value[i] || ''}</div>
        ))}
      </div>
    </div>
  )
}

/* ---------- Тройной переключатель направления (S10) ---------- */
export const DIRS = {
  to: { arrow: '⇒', icon: Icon.arrowR, word: 'Только из A в B' },
  both: { arrow: '⇔', icon: Icon.arrowBoth, word: 'В обе стороны' },
  from: { arrow: '⇐', icon: Icon.arrowL, word: 'Только из B в A' },
}
export function DirSegment({ value, onChange }) {
  return (
    <div className="dir-seg">
      {['to', 'both', 'from'].map((k) => (
        <div key={k} className={`dir-opt${value === k ? ' active' : ''}`} onClick={() => onChange(k)}>
          <span className="dir-arrow">{DIRS[k].arrow}</span>
          <span className="dir-label">{DIRS[k].word}</span>
        </div>
      ))}
    </div>
  )
}

/* ---------- Кольцевой индикатор трафика (S12) ---------- */
export function TrafficRing({ percent = 0, size = 168, stroke = 14, tone, center, sub }) {
  const r = (size - stroke) / 2
  const c = 2 * Math.PI * r
  const pct = Math.max(0, Math.min(100, percent))
  const color = tone === 'crit' ? 'var(--danger)' : tone === 'warn' ? 'var(--amber)' : 'var(--success)'
  return (
    <div className="ring-wrap" style={{ width: size, height: size }}>
      <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--fill-strong)" strokeWidth={stroke} />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={stroke}
          strokeLinecap="round" strokeDasharray={c} strokeDashoffset={c * (1 - pct / 100)}
          style={{ transition: 'stroke-dashoffset 0.6s ease, stroke 0.3s ease' }} />
      </svg>
      <div className="ring-center">
        <span className="t-display" style={{ fontSize: 40, color }}>{center}</span>
        {sub && <span className="t-footnote sec">{sub}</span>}
      </div>
    </div>
  )
}

/* ---------- Скелетоны ---------- */
export function Skeleton({ w = '100%', h = 14, r = 7, style }) { return <div className="skeleton" style={{ width: w, height: h, borderRadius: r, ...style }} /> }
export function SkeletonCell({ avatar = true }) {
  return (
    <div className="cell" style={{ cursor: 'default' }}>
      {avatar && <div className="cell-before"><Skeleton w={40} h={40} r={11} /></div>}
      <div className="cell-main" style={{ gap: 7 }}>
        <Skeleton w="55%" h={14} />
        <Skeleton w="35%" h={11} />
      </div>
    </div>
  )
}

/* ---------- Буллет (иконка в плашке + текст) ---------- */
export function Bullet({ icon, children }) {
  return <div className="bullet" style={{ padding: '8px 0' }}><span className="bx">{icon}</span><span className="t-body-sm" style={{ alignSelf: 'center' }}>{children}</span></div>
}

export function PillButton({ icon, children, onClick, style }) {
  return <Btn kind="secondary" size="s" stretched={false} before={icon} onClick={onClick} style={style}>{children}</Btn>
}
export function BtnLink({ children, onClick, style }) {
  return <Btn kind="plain" size="s" stretched={false} onClick={onClick} style={style}>{children}</Btn>
}

export { Icon }
