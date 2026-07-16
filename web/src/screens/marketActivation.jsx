/* Публичная активация кодов, купленных на Яндекс Маркете.
 * Страница не создаёт аккаунт и не выдаёт сессию: телефон выбирает существующий
 * аккаунт, а право на месяц подтверждает одноразовый bearer-код из заказа. */
import React, { useMemo, useState } from 'react'
import { BrandMark, BOT_LINKS, BOT_NAME, LEGAL_PRIVACY_URL, LEGAL_PRIVACY_VERSION,
  LEGAL_TERMS_URL, LEGAL_TERMS_VERSION, botLaunchUrl } from './_shared.jsx'
import { Icon } from '../components/ui.jsx'
import './marketActivation.css'

function phoneDigits(value) {
  let digits = String(value || '').replace(/\D/g, '')
  if (digits.length === 10) digits = `7${digits}`
  if (digits.length === 11 && digits.startsWith('8')) digits = `7${digits.slice(1)}`
  return digits.slice(0, 15)
}

function formatPhone(value) {
  let digits = String(value || '').replace(/\D/g, '')
  if (!digits) return ''
  if (digits.startsWith('8')) digits = `7${digits.slice(1)}`
  digits = digits.slice(0, 15)
  if (!digits.startsWith('7')) return `+${digits}`
  const rest = digits.slice(1, 11)
  let out = '+7'
  if (rest.length) out += ` ${rest.slice(0, 3)}`
  if (rest.length > 3) out += ` ${rest.slice(3, 6)}`
  if (rest.length > 6) out += `-${rest.slice(6, 8)}`
  if (rest.length > 8) out += `-${rest.slice(8, 10)}`
  return out
}

function formatCode(value) {
  const raw = String(value || '').replace(/[^A-Za-z0-9]/g, '').slice(0, 12)
  return raw.replace(/(.{4})(?=.)/g, '$1-')
}

function formatUntil(epoch) {
  const date = new Date(Number(epoch) * 1000)
  if (Number.isNaN(date.getTime())) return null
  return date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' })
}

async function activateMarketCode(payload) {
  let response
  try {
    response = await fetch('/api/market/activate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      cache: 'no-store',
    })
  } catch (_) {
    throw new Error('Нет связи с сервером. Проверьте интернет и попробуйте снова.')
  }
  let data = null
  try { data = await response.json() } catch (_) { /* дружелюбный fallback ниже */ }
  if (!response.ok) {
    throw new Error(data?.detail?.message || 'Не удалось активировать подписку. Попробуйте позже.')
  }
  return data
}

export function MarketActivation() {
  const [phone, setPhone] = useState('+7 ')
  const [code, setCode] = useState('')
  const [accepted, setAccepted] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)

  const phoneReady = useMemo(() => {
    const digits = phoneDigits(phone)
    return digits.length >= 11 && digits.length <= 15
  }, [phone])
  const codeReady = code.replace(/-/g, '').length === 12
  const ready = phoneReady && codeReady && accepted && !busy

  const submit = async (event) => {
    event.preventDefault()
    if (!ready) return
    setBusy(true)
    setError('')
    try {
      const data = await activateMarketCode({
        phone: phoneDigits(phone),
        code,
        legalAccepted: true,
        termsVersion: LEGAL_TERMS_VERSION,
        privacyVersion: LEGAL_PRIVACY_VERSION,
      })
      const sub = data.subscription || {}
      const planTitle = sub.planName || (sub.plan === 'individual' ? 'Индивидуальный' : 'Smart')
      setResult({ until: formatUntil(data.until), phone: formatPhone(phone), planTitle })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось активировать подписку.')
    } finally {
      setBusy(false)
    }
  }

  if (result) {
    return (
      <main className="yam-page">
        <section className="yam-card yam-success" aria-live="polite">
          <div className="yam-success-icon"><Icon.check size={34} /></div>
          <div className="yam-eyebrow">{BOT_NAME} {result.planTitle}</div>
          <h1>Подписка активирована</h1>
          <p className="yam-lead">
            Месяц тарифа {result.planTitle} добавлен аккаунту <strong>{result.phone}</strong>.
          </p>
          {result.until && <div className="yam-until">Доступ активен до {result.until}</div>}
          {(BOT_LINKS.max || BOT_LINKS.tg) && (
            <div className="yam-success-actions">
              {BOT_LINKS.max && <a className="yam-button yam-button-primary" href={botLaunchUrl('max', 'market')}>Открыть в MAX</a>}
              {BOT_LINKS.tg && <a className="yam-button yam-button-secondary" href={botLaunchUrl('tg', 'market')}>Открыть в Telegram</a>}
            </div>
          )}
          <button className="yam-link-button" type="button" onClick={() => {
            setResult(null); setCode(''); setAccepted(false)
          }}>
            Активировать ещё один код
          </button>
        </section>
      </main>
    )
  }

  return (
    <main className="yam-page">
      <section className="yam-card">
        <header className="yam-header">
          <BrandMark size={72} />
          <div className="yam-market-badge"><Icon.key size={15} /> Код из заказа Яндекс Маркета</div>
          <h1>Активация {BOT_NAME} Smart</h1>
          <p className="yam-lead">
            Введите номер, привязанный к аккаунту {BOT_NAME}, и код активации из заказа.
          </p>
        </header>

        <form className="yam-form" onSubmit={submit} noValidate>
          <label className="yam-field">
            <span>Номер телефона</span>
            <input
              type="tel"
              inputMode="tel"
              autoComplete="tel"
              value={phone}
              onFocus={() => { if (!phone) setPhone('+7 ') }}
              onChange={(event) => { setPhone(formatPhone(event.target.value)); setError('') }}
              placeholder="+7 900 000-00-00"
              aria-invalid={!!phone && !phoneReady}
            />
            <small>Укажите номер, с которым вы входили в {BOT_NAME}.</small>
          </label>

          <label className="yam-field">
            <span>Код активации</span>
            <input
              className="yam-code-input"
              type="text"
              inputMode="text"
              autoComplete="off"
              autoCorrect="off"
              autoCapitalize="off"
              spellCheck={false}
              value={code}
              onChange={(event) => { setCode(formatCode(event.target.value)); setError('') }}
              placeholder="XXXX-XXXX-XXXX"
              maxLength={14}
              aria-invalid={!!code && !codeReady}
            />
            <small>Код действует 30 дней с генерации. Скопируйте его точно: регистр букв имеет значение.</small>
          </label>

          <label className="yam-consent">
            <input type="checkbox" checked={accepted} onChange={(event) => {
              setAccepted(event.target.checked); setError('')
            }} />
            <span>
              Я принимаю <a href={LEGAL_TERMS_URL} target="_blank" rel="noreferrer">условия использования</a>
              {' '}и <a href={LEGAL_PRIVACY_URL} target="_blank" rel="noreferrer">политику конфиденциальности</a>.
            </span>
          </label>

          {error && <div className="yam-error" role="alert"><Icon.alert size={18} />{error}</div>}

          <button className="yam-button yam-button-primary" type="submit" disabled={!ready}>
            {busy ? <><span className="yam-spinner" />Активируем…</> : 'Активировать подписку'}
          </button>
        </form>

        <div className="yam-note">
          <Icon.spark size={18} />
          <span>Код применяется сразу. Если подписка уже активна, месяц добавится к текущей дате окончания.</span>
        </div>

        {(BOT_LINKS.max || BOT_LINKS.tg) && (
          <footer className="yam-footer">
            <span>Ещё нет аккаунта?</span>
            {BOT_LINKS.max && <a href={botLaunchUrl('max', 'market')}>Открыть {BOT_NAME} в MAX</a>}
            {BOT_LINKS.max && BOT_LINKS.tg && <span aria-hidden="true">·</span>}
            {BOT_LINKS.tg && <a href={botLaunchUrl('tg', 'market')}>в Telegram</a>}
          </footer>
        )}
      </section>
    </main>
  )
}

export default MarketActivation
