/* auth.jsx — приветствие, вход по контакту, вход по другому номеру и OTP. */
import React, { useEffect, useState } from 'react'
import { Screen, HostHeader, MainButton, Field, OtpInput, Avatar, Icon, Btn, BtnLink } from '../components/ui.jsx'
import { BOT_NAME, BrandMark, LANDING_ANALYTICS_NOTICE, LANDING_DESCRIPTION,
  LANDING_OFFER_TEXT, LANDING_OFFER_TITLE, LegalLinks, botLaunchUrl } from './_shared.jsx'
import { MaxMark, TgMark } from './paywall.jsx'
import { useStore } from '../store/store.js'
import host from '../host/host.js'
import api from '../api/client.js'
import { VK_ADS_ENABLED, initVkAds, trackMessengerExit } from '../analytics/vkAds.js'

/* Публичный переходник: обычный браузер не может безопасно подтвердить личность
 * пользователя, поэтому вход продолжается через личный чат бота в выбранном хосте.
 * Форматы ?start=<payload> сверены с локальной документацией обеих платформ. */
export function BrowserEntry() {
  const links = {
    max: botLaunchUrl('max'),
    tg: botLaunchUrl('tg'),
  }

  useEffect(() => {
    initVkAds()
  }, [])

  return (
    <Screen>
      <main className="screen-body browser-entry-body">
        <div className="browser-entry-shell">
          <div className="browser-entry-card">
            <section className="browser-entry-intro">
              <BrandMark size={88} />
              <div className="browser-entry-heading">
                <h1 className="t-title-lg text-pretty">{BOT_NAME}</h1>
                <p className="t-body-sm sec text-pretty">
                  {LANDING_DESCRIPTION}
                </p>
              </div>
              {(LANDING_OFFER_TITLE || LANDING_OFFER_TEXT) && (
                <div className="auth-trial-offer browser-entry-offer">
                  <span className="auth-trial-icon"><Icon.gift size={18} /></span>
                  <span className="auth-trial-copy">
                    {LANDING_OFFER_TITLE && <span className="auth-trial-title">{LANDING_OFFER_TITLE}</span>}
                    {LANDING_OFFER_TEXT && <span className="auth-trial-text">{LANDING_OFFER_TEXT}</span>}
                  </span>
                </div>
              )}
            </section>

            <section className="browser-entry-panel">
              <div className="browser-entry-panel-heading">
                <div className="t-headline">Продолжить в мессенджере</div>
                <div className="t-footnote sec text-pretty">Выберите, где войти в аккаунт {BOT_NAME}.</div>
              </div>

              <div className="browser-entry-actions" aria-label="Выберите мессенджер для входа">
                {links.max && (
                  <a className="browser-entry-button max" href={links.max}
                    onClick={() => trackMessengerExit('max')}>
                    <span className="browser-entry-platform max"><MaxMark size={22} /></span>
                    <span>Войти через MAX</span>
                    <Icon.arrowR size={20} />
                  </a>
                )}
                {links.tg && (
                  <a className="browser-entry-button telegram" href={links.tg}
                    onClick={() => trackMessengerExit('telegram')}>
                    <span className="browser-entry-platform telegram"><TgMark size={28} /></span>
                    <span>Войти через Telegram</span>
                    <Icon.arrowR size={20} />
                  </a>
                )}
                {!links.max && !links.tg && <div className="t-footnote sec">Ссылки на ботов не настроены.</div>}
              </div>

              <div className="t-footnote sec text-pretty browser-entry-note">
                Откроется чат с ботом в выбранном мессенджере.
              </div>
            </section>
          </div>

          <footer className="browser-entry-footer t-footnote sec text-pretty">
            {VK_ADS_ENABLED && LANDING_ANALYTICS_NOTICE && <div>{LANDING_ANALYTICS_NOTICE}</div>}
            <LegalLinks style={{ marginTop: VK_ADS_ENABLED && LANDING_ANALYTICS_NOTICE ? 8 : 0 }} />
          </footer>
        </div>
      </main>
    </Screen>
  )
}

/* ============================ S1 — Приветствие ============================ */
export function S1() {
  const push = useStore((s) => s.push)
  const legalAccepted = useStore((s) => s.preAuthLegalAccepted)
  const setLegalAccepted = useStore((s) => s.setPreAuthLegalAccepted)
  const [legalDialog, setLegalDialog] = useState(null)
  const [legalChecked, setLegalChecked] = useState(false)

  const bullets = [
    [Icon.arrowBoth, 'Синхронизация чатов и каналов в обе стороны'],
    [Icon.signature, 'Полное форматирование, фото, видео и файлы'],
    [Icon.rules, 'Гибкие правила: куда и в какую сторону переносить'],
  ]
  const proceed = (screen) => {
    if (!legalAccepted) {
      setLegalDialog(screen)
      setLegalChecked(false)
      host.haptic('selection')
      return
    }
    host.haptic('light')
    push(screen)
  }
  const closeLegalDialog = () => setLegalDialog(null)
  const acceptAndProceed = () => {
    if (!legalChecked || !legalDialog) return
    const screen = legalDialog
    setLegalAccepted(true)
    setLegalDialog(null)
    host.haptic('light')
    push(screen)
  }

  return (
    <Screen>
      <div className="screen-body" style={{ display: 'flex', flexDirection: 'column', padding: 'max(env(safe-area-inset-top, 0px), 16px) 24px 16px' }}>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', gap: 16, marginTop: 'auto' }}>
          <BrandMark size={76} />
          <div className="t-title-lg text-pretty" style={{ marginTop: 4 }}>Перенос сообщений между MAX и Telegram</div>
          <div className="t-body-sm sec text-pretty" style={{ maxWidth: 320 }}>
            Бот делает чистую копию ваших постов и сообщений из одного мессенджера в другой — с форматированием и медиа, без пометки «переслано».
          </div>
          <div className="auth-trial-offer">
            <span className="auth-trial-icon"><Icon.gift size={18} /></span>
            <span className="auth-trial-copy">
              <span className="auth-trial-title">7 дней бесплатно</span>
              <span className="auth-trial-text">Новым пользователям при подключении автопродления. Сейчас ничего не списывается.</span>
            </span>
          </div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 26, marginBottom: 'auto' }}>
          {bullets.map(([I, t], i) => (
            <div key={i} className="bullet" style={{ padding: '8px 0' }}>
              <span className="bx"><I size={17} /></span>
              <span className="t-body-sm" style={{ alignSelf: 'center' }}>{t}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="footer-area">
        <Btn
          onClick={() => proceed('S2')}>Войти / Создать аккаунт</Btn>
      </div>
      {legalDialog && (
        <div className="modal-overlay" onClick={closeLegalDialog}>
          <div className="legal-dialog" role="dialog" aria-modal="true" aria-labelledby="legal-dialog-title"
            onClick={(e) => e.stopPropagation()}>
            <div className="legal-dialog-head">
              <div style={{ width: 30 }} />
              <div id="legal-dialog-title" className="legal-dialog-title">Условия сервиса</div>
              <button type="button" className="host-icon-btn" aria-label="Закрыть" onClick={closeLegalDialog}>
                <Icon.close size={16} />
              </button>
            </div>
            <div className="legal-dialog-body">
              <div className="t-body-sm sec text-pretty">
                Перед входом нужно принять пользовательское соглашение и политику конфиденциальности.
              </div>
              <label className="legal-check modal">
                <input type="checkbox" checked={legalChecked} onChange={(e) => setLegalChecked(e.target.checked)} />
                <span>Я принимаю условия сервиса</span>
              </label>
              <LegalLinks style={{ padding: '0', marginTop: 8, textAlign: 'left' }} />
            </div>
            <div className="legal-dialog-footer">
              <Btn disabled={!legalChecked} onClick={acceptAndProceed}>Продолжить</Btn>
            </div>
          </div>
        </div>
      )}
    </Screen>
  )
}

/* ============================ S2 — Вход по номеру ============================ */
const S2_ERR = {
  refusal: 'Без номера телефона войти не получится. Нажмите «Поделиться номером телефона» и подтвердите доступ. Если у вас аккаунт на другом номере — войдите по другому номеру.',
  request: 'Не удалось получить номер. Проверьте интернет и попробуйте снова.',
  hash: 'Не удалось подтвердить номер. Перезапустите приложение из бота и попробуйте снова.',
  old: 'Ваша версия мессенджера не поддерживает быстрый вход. Обновите приложение или войдите по другому номеру.',
}

function hostAuthPayload() {
  const init = host.getInitData() || {}
  return {
    messenger: host.name === 'telegram' ? 'tg' : 'max',
    initData: init.raw,
    userId: init.unsafe?.user?.id,
  }
}

function reportMaxContactError(err) {
  if (host.name !== 'max' || !err?.bridgeCode) return
  // Только технический код Bridge и версия среды. Номер, hash и ответ контакта
  // в этот временный диагностический запрос не попадают.
  void api.authContactDiagnostic({
    ...hostAuthPayload(),
    errorCode: err.bridgeCode,
    platform: host.platform,
    bridgeVersion: host.bridgeVersion,
  }).catch(() => {})
}

export function S2() {
  const push = useStore((s) => s.push)
  const setSession = useStore((s) => s.setSession)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const onShare = async () => {
    setError(null)
    setLoading(true)
    try {
      // Без успешного requestContact запрос авторизации не отправляем. MAX отдаёт
      // подписанную тройку, Telegram — boolean-маркер (сам self-contact придёт боту).
      const contact = await host.requestContact()
      if (!contact) {
        const e = new Error('contact refused')
        e.code = 'contact_refused'
        throw e
      }
      if (host.name !== 'telegram'
          && (!contact.phone || contact.authDate == null || !contact.hash)) {
        const e = new Error('bad contact')
        e.code = 'bad_contact'
        throw e
      }
      const res = await api.authContact({
        ...hostAuthPayload(),
        phone: contact?.phone,
        authDate: contact?.authDate,
        hash: contact?.hash,
        contactShared: contact?.shared === true,
      })
      host.haptic('success')
      await setSession(res.token, res.account)
      // Гейтинг по подписке (paywall/app) выполняет setSession → gateBySubscription.
    } catch (err) {
      reportMaxContactError(err)
      host.haptic('error')
      if (err && err.code === 'contact_refused') setError(S2_ERR.refusal)
      else if (err && err.code === 'contact_unsupported') setError(S2_ERR.old)
      else if (err && err.code === 'max_contact_error') setError(S2_ERR.request)
      else if (err && (err.code === 'network' || err.code === 'contact_required')) setError(S2_ERR.request)
      else if (err && (err.code === 'bad_contact' || err.code === 'bad_signature' || err.code === 'no_user')) setError(S2_ERR.hash)
      else setError(S2_ERR.request)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Screen>
      <HostHeader title="" back />
      <div className="screen-body" style={{ padding: '8px 24px 20px' }}>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', gap: 14 }}>
          <Avatar size={64} tone="av-blue" icon={<Icon.shield />} />
          <div className="t-headline text-pretty">Вход по номеру телефона</div>
          <div className="t-body-sm sec text-pretty" style={{ maxWidth: 330 }}>
            Чтобы создать аккаунт или войти, подтвердите номер телефона текущего аккаунта. Это безопасно — номер подтянется автоматически, вводить его вручную не нужно.
          </div>
        </div>
        <div className="note-card" style={{ marginTop: 20, display: 'flex', gap: 10, alignItems: 'flex-start' }}>
          <span style={{ flex: '0 0 auto', color: 'var(--text-secondary)', marginTop: 1 }}><Icon.shield size={18} /></span>
          <span className="t-footnote sec text-pretty">
            Мы используем номер только для входа в это приложение. Мы не звоним и не пишем на него.
          </span>
        </div>
        {error && (
          <div className="t-footnote dng text-pretty" style={{ marginTop: 16, color: 'var(--danger)' }}>{error}</div>
        )}
        <div style={{ textAlign: 'center', marginTop: 14 }}>
          <BtnLink onClick={() => push('S3')}>Войти по другому номеру</BtnLink>
        </div>
      </div>
      <MainButton
        label={loading ? 'Проверяем…' : 'Поделиться номером телефона'}
        loading={loading}
        onClick={onShare}
      />
    </Screen>
  )
}

/* ============================ S3 — Вход по другому номеру ============================ */
const S3_ERR = {
  format: 'Введите номер в международном формате, например +7 900 000-00-00.',
  notfound: 'Аккаунт с таким номером не найден. Проверьте номер или создайте новый аккаунт через вход по текущему номеру.',
  rate: 'Слишком много попыток. Попробуйте снова через несколько минут.',
  network: 'Нет связи. Проверьте интернет и попробуйте снова.',
}

/* Нормализация в +7XXXXXXXXXX и проверка «похоже на валидный». */
function digitsOf(s) { return String(s || '').replace(/\D/g, '') }
function looksValid(phone) {
  const d = digitsOf(phone)
  return d.length >= 11 && d.length <= 15
}

export function S3() {
  const push = useStore((s) => s.push)
  const [phone, setPhone] = useState('+7 ')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [notFound, setNotFound] = useState(false)

  const valid = looksValid(phone)

  const onSubmit = async () => {
    if (!valid || loading) return
    setError(null)
    setNotFound(false)
    if (!valid) { setError(S3_ERR.format); return }
    setLoading(true)
    const e164 = '+' + digitsOf(phone)
    try {
      await api.authOtpRequest({ ...hostAuthPayload(), phone: e164 })
      host.haptic('light')
      push('S4', { phone: e164 })
    } catch (err) {
      if (err && err.code === 'network') setError(S3_ERR.network)
      else if (err && (err.code === 'not_found' || err.status === 404)) { setError(S3_ERR.notfound); setNotFound(true) }
      else if (err && (err.code === 'rate_limited' || err.status === 429)) setError(S3_ERR.rate)
      else setError(S3_ERR.format)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Screen>
      <HostHeader title="" back />
      <div className="screen-body" style={{ padding: '8px 24px 20px' }}>
        <div className="t-headline text-pretty">Вход по другому номеру</div>
        <div className="t-body-sm sec text-pretty" style={{ marginTop: 8 }}>
          Введите номер телефона аккаунта, в который хотите войти. Мы отправим код подтверждения в мессенджер/аккаунт, где этот номер уже авторизован (есть активная сессия).
        </div>
        <div className="t-label sec" style={{ margin: '20px 0 8px' }}>Номер телефона</div>
        <Field
          value={phone}
          onChange={(v) => { setPhone(v); if (error) { setError(null); setNotFound(false) } }}
          placeholder="+7 900 000-00-00"
          inputMode="tel"
          type="tel"
          autoFocus
          error={!!error}
        />
        {error ? (
          <div className="t-footnote text-pretty" style={{ marginTop: 8, color: 'var(--danger)' }}>{error}</div>
        ) : (
          <div className="t-footnote sec text-pretty" style={{ marginTop: 8 }}>
            Код придёт сообщением от бота в MAX или Telegram.
          </div>
        )}
        {notFound && (
          <div style={{ marginTop: 6 }}>
            <BtnLink onClick={() => push('S2')} style={{ padding: '4px 0' }}>Войти / Создать аккаунт</BtnLink>
          </div>
        )}
      </div>
      <MainButton
        label={loading ? 'Отправляем код…' : 'Получить код'}
        loading={loading}
        disabled={!valid}
        onClick={onSubmit}
      />
    </Screen>
  )
}

/* ============================ S4 — Код авторизации (OTP) ============================ */
const S4_ERR = {
  wrong: 'Неверный код. Проверьте сообщение и введите код ещё раз.',
  tooMany: 'Слишком много попыток. Запросите новый код.',
  expired: 'Срок действия кода истёк. Запросите новый код.',
  network: 'Нет связи. Проверьте интернет и попробуйте снова.',
}

export function S4({ phone }) {
  const pop = useStore((s) => s.pop)
  const setSession = useStore((s) => s.setSession)
  const showToast = useStore((s) => s.showToast)
  const [code, setCode] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [left, setLeft] = useState(59)

  /* Обратный отсчёт до повторной отправки. */
  useEffect(() => {
    if (left <= 0) return
    const t = setInterval(() => setLeft((v) => (v <= 1 ? 0 : v - 1)), 1000)
    return () => clearInterval(t)
  }, [left])

  const verify = async (value) => {
    const c = value ?? code
    if (c.length !== 4 || loading) return
    setError(null)
    setLoading(true)
    try {
      const res = await api.authOtpVerify({ ...hostAuthPayload(), phone, code: c })
      host.haptic('success')
      await setSession(res.token, res.account)
      // Гейтинг (paywall/app) выполняет setSession → gateBySubscription.
    } catch (err) {
      host.haptic('error')
      if (err && err.code === 'network') setError(S4_ERR.network)
      else if (err && (err.code === 'too_many' || err.status === 429)) setError(S4_ERR.tooMany)
      else if (err && (err.code === 'expired' || err.code === 'code_expired')) setError(S4_ERR.expired)
      else setError(S4_ERR.wrong)
      setCode('')
      setLoading(false)
    }
  }

  const resend = async () => {
    try {
      await api.authOtpRequest({ ...hostAuthPayload(), phone })
      setLeft(59)
      setError(null)
      setCode('')
      showToast('Код отправлен повторно')
    } catch (_) {
      setError(S4_ERR.network)
    }
  }

  const mm = Math.floor(left / 60)
  const ss = String(left % 60).padStart(2, '0')

  return (
    <Screen>
      <HostHeader title="" back />
      <div className="screen-body" style={{ padding: '8px 24px 20px' }}>
        <div className="t-headline text-pretty">Введите код подтверждения</div>
        <div className="t-body-sm sec text-pretty" style={{ marginTop: 8 }}>
          Мы отправили код для входа в мессенджер/аккаунт, где номер {phone || 'вашего аккаунта'} уже авторизован. Введите его ниже.
        </div>

        <div style={{ marginTop: 24 }}>
          <OtpInput
            length={4}
            value={code}
            error={!!error}
            onChange={(v) => { setCode(v); if (error) setError(null) }}
            onComplete={(v) => verify(v)}
          />
        </div>

        {error && (
          <div className="t-footnote text-pretty" style={{ marginTop: 14, textAlign: 'center', color: 'var(--danger)' }}>{error}</div>
        )}

        <div style={{ marginTop: 18, textAlign: 'center' }}>
          {left > 0 ? (
            <span className="t-footnote sec">Отправить код снова можно через {mm}:{ss}</span>
          ) : (
            <BtnLink onClick={resend}>Отправить код снова</BtnLink>
          )}
        </div>

        <div style={{ marginTop: 6, textAlign: 'center' }}>
          <BtnLink onClick={() => pop()}>Изменить номер</BtnLink>
        </div>

        <div className="t-footnote sec text-pretty" style={{ marginTop: 18, textAlign: 'center', maxWidth: 340, marginLeft: 'auto', marginRight: 'auto' }}>
          Не пришёл код? Проверьте, что мессенджер с этим номером открыт, и запросите код снова.
        </div>
      </div>
      <MainButton
        label={loading ? 'Проверяем код…' : 'Войти'}
        loading={loading}
        disabled={code.length !== 4}
        onClick={() => verify()}
      />
    </Screen>
  )
}
