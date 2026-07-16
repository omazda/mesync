/* paywall.jsx — S5 Пейволл Smart (жёсткий гейт, без таб-бара).
 *
 * Продажная структура: hero «живой мост» (MAX и Telegram, соединённые встречными
 * потоками сообщений — продукт в одном кадре) → честный таймлайн триала
 * «Сегодня 0 ₽ → 7 дней → дальше 299 ₽/мес» (снимает страх привязки карты) →
 * преимущества рядами → тумблер автопродления → принятие условий со ссылками
 * на документы. В футере — только CTA и строка «Безопасная оплата с партнёром
 * ЮКасса» под ней (без подписи над кнопкой).
 *
 * Реальная оплата через ЮKassa (см. pay.jsx):
 *   - новый пользователь + автоплатёж ВКЛ → 7 дней бесплатно за привязку
 *     автоплатежа (карта/СБП, без списания);
 *   - автоплатёж ВЫКЛ → разовая оплата 299 ₽ без привязки, пробный период
 *     недоступен (отключение автоплатежа = полная стоимость);
 *   - триал уже использован → оплата 299 ₽ (с привязкой при включённом автоплатеже).
 *
 * Обязательные раскрытия для автоплатежей (docs/yookassa, recurring-payments):
 * сумма и периодичность списаний, момент списания, самостоятельное отключение,
 * ссылки на оферту и политику — на экране при любом состоянии тумблера.
 */
import React, { useState } from 'react'
import { Screen, HostHeader, Btn, BtnLink, Switch, Icon } from '../components/ui.jsx'
import { useStore } from '../store/store.js'
import host from '../host/host.js'
import { BrandMark, BOT_NAME, LegalLinks } from './_shared.jsx'
import { usePayFlow } from './pay.jsx'

export function planName(sub) {
  return sub?.planName || (sub?.plan === 'individual' ? 'Индивидуальный' : 'Smart')
}

function featureRows(sub) {
  const perks = Array.isArray(sub?.perks) ? sub.perks : []
  return [
    { tone: 'i1', icon: Icon.arrowBoth, title: 'MAX ⇄ Telegram', text: 'Пересылка в обе стороны или в одну' },
    { tone: 'i2', icon: Icon.copy, title: 'Чистая копия', text: 'Без пометки «переслано»' },
    { tone: 'i3', icon: Icon.rules, title: perks[0] || 'До 10 правил пересылки', text: 'Чаты, каналы и темы — в любых связках' },
    { tone: 'i4', icon: Icon.traffic, title: perks[1] || '0,5 ТБ медиа в месяц', text: 'Фото, видео и файлы до 2 ГБ' },
  ]
}

/* Официальные знаки мессенджеров (белым по фирменному фону узла):
 * MAX — знак из шапки dev.max.ru (docs/max/html/index.html, path с currentColor);
 * Telegram — самолётик из официального telegram.org/img/t_logo.svg. */
export function MaxMark({ size = 26 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 25 24" fill="none" aria-hidden="true" style={{ display: 'block' }}>
      <path fillRule="evenodd" clipRule="evenodd" fill="#fff" d="M12.3405 23.9342C9.97568 23.9342 8.87728 23.5899 6.97252 22.2125C5.76041 23.762 1.94518 24.9672 1.77774 22.9012C1.77774 21.3535 1.42788 20.0492 1.04269 18.6132C0.570922 16.8544 0.0461426 14.898 0.0461426 12.0546C0.0461426 5.27426 5.6424 0.175079 12.2777 0.175079C18.913 0.175079 24.1153 5.52322 24.1153 12.1205C24.1153 18.7178 18.7474 23.9342 12.3405 23.9342ZM12.4368 6.03673C9.20791 5.86848 6.68817 8.0948 6.13253 11.5794C5.6724 14.465 6.48821 17.9812 7.18602 18.1582C7.51488 18.2416 8.35763 17.564 8.87711 17.0475C9.73154 17.5981 10.712 18.0245 11.8019 18.0813C15.1168 18.254 18.0544 15.6761 18.228 12.382C18.4016 9.08792 15.7517 6.20946 12.4368 6.03673Z" />
    </svg>
  )
}
export function TgMark({ size = 44 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 128 128" fill="none" aria-hidden="true" style={{ display: 'block' }}>
      <path fill="#fff" d="M28.9700376,63.3244248 C47.6273373,55.1957357 60.0684594,49.8368063 66.2934036,47.2476366 C84.0668845,39.855031 87.7600616,38.5708563 90.1672227,38.528 C90.6966555,38.5191258 91.8804274,38.6503351 92.6472251,39.2725385 C93.294694,39.7979149 93.4728387,40.5076237 93.5580865,41.0057381 C93.6433345,41.5038525 93.7494885,42.63857 93.6651041,43.5252052 C92.7019529,53.6451182 88.5344133,78.2034783 86.4142057,89.5379542 C85.5170662,94.3339958 83.750571,95.9420841 82.0403991,96.0994568 C78.3237996,96.4414641 75.5015827,93.6432685 71.9018743,91.2836143 C66.2690414,87.5912212 63.0868492,85.2926952 57.6192095,81.6896017 C51.3004058,77.5256038 55.3966232,75.2369981 58.9976911,71.4967761 C59.9401076,70.5179421 76.3155302,55.6232293 76.6324771,54.2720454 C76.6721165,54.1030573 76.7089039,53.4731496 76.3346867,53.1405352 C75.9604695,52.8079208 75.4081573,52.921662 75.0095933,53.0121213 C74.444641,53.1403447 65.4461175,59.0880351 48.0140228,70.8551922 C45.4598218,72.6091037 43.1463059,73.4636682 41.0734751,73.4188859 C38.7883453,73.3695169 34.3926725,72.1268388 31.1249416,71.0646282 C27.1169366,69.7617838 23.931454,69.0729605 24.208838,66.8603276 C24.3533167,65.7078514 25.9403832,64.5292172 28.9700376,63.3244248 Z" />
    </svg>
  )
}

/* «Живой мост»: MAX ⇄ MeSync ⇄ Telegram, потоки бегут навстречу друг другу.
 * paused (S11, подписка не активна) — потоки замирают и гаснут: состояние
 * продукта видно без слов. */
export function SyncBridge({ paused = false }) {
  return (
    <div className={`pw-bridge${paused ? ' paused' : ''}`} aria-hidden="true">
      <span className="pw-node max"><MaxMark /></span>
      <span className="pw-wires left"><i className="pw-wire fwd" /><i className="pw-wire rev" /></span>
      <BrandMark size={54} />
      <span className="pw-wires right"><i className="pw-wire fwd" /><i className="pw-wire rev" /></span>
      <span className="pw-node tg"><TgMark /></span>
    </div>
  )
}

/* Таймлайн в языке точек: первая — «сейчас» (градиентная), warn — шаг,
 * требующий действия пользователя. Общий для S5 (триал) и S11 (состояние). */
export function PwPlan({ rows }) {
  return (
    <div className="pw-plan">
      {rows.map((row, i) => (
        <div className={`pw-plan-row${i === 0 ? ' first' : ''}${row.warn ? ' warn' : ''}`} key={row.title}>
          <span className="pw-plan-rail">
            <i className="pw-plan-dot" />
            {i < rows.length - 1 && <i className="pw-plan-line" />}
          </span>
          <span className="pw-plan-main">
            <span className="pw-plan-title">{row.title}</span>
            <span className="pw-plan-text">{row.text}</span>
          </span>
        </div>
      ))}
    </div>
  )
}

/* Таймлайн триала: отвечает на главный вопрос «почему карта, если бесплатно».
 * Единые формулировки для S5 и S11 (неактивная подписка с доступным триалом). */
export function buildTrialRows(price, currency, trialDays) {
  return [
    { title: `Сегодня — 0 ${currency}`, text: 'Привязываете карту или СБП. Деньги не списываются.' },
    { title: `${trialDays} дней бесплатно`, text: 'Все условия тарифа доступны полностью.' },
    { title: `Дальше — ${price} ${currency}/мес`, text: 'Списание автоматическое, в дату окончания периода. Отключить можно в любой момент в настройках.' },
  ]
}

/* Преимущества тарифа — ряды с цветными чипами (внутри .pw-list). */
export function PwFeatures({ subscription } = {}) {
  return featureRows(subscription).map((f) => {
    const I = f.icon
    return (
      <div className="pw-row" key={f.title}>
        <span className={`pw-row-icon ${f.tone}`}><I size={17} /></span>
        <span className="pw-row-main">
          <span className="pw-row-title">{f.title}</span>
          <span className="pw-row-text">{f.text}</span>
        </span>
      </div>
    )
  })
}

export function S5() {
  const subscription = useStore((s) => s.subscription)
  const openSheet = useStore((s) => s.openSheet)
  const logout = useStore((s) => s.logout)
  const showToast = useStore((s) => s.showToast)
  const [autopay, setAutopay] = useState(true)
  const pay = usePayFlow()

  const sub = subscription || {}
  const price = sub.price ?? 299
  const currency = sub.currency ?? '₽'
  const trialDays = sub.trialDays ?? 7
  const payEnabled = sub.payEnabled !== false
  const trialMode = autopay && !sub.trialUsed
  const planTitle = planName(sub)
  const perMonth = `${price} ${currency}/мес`

  const toggleAutopay = () => { host.haptic('selection'); setAutopay((v) => !v) }

  const planRows = buildTrialRows(price, currency, trialDays)

  const label = !payEnabled ? 'Оплата временно недоступна'
    : pay.busy ? 'Открываем оплату…'
      : trialMode ? `Попробовать ${trialDays} дней бесплатно`
        : `Оплатить ${price} ${currency}`
  const onAction = () => {
    if (!payEnabled || pay.busy) return
    if (trialMode) pay.beginTrial()
    else pay.beginPay(autopay)
  }
  const switchAccount = () => {
    host.haptic('warning')
    logout()
    showToast('Вы вышли из аккаунта')
  }

  return (
    <Screen grouped>
      <HostHeader
        title="Подписка"
        onGrouped
        right={(
          <button
            type="button"
            className="host-icon-btn pw-logout-btn"
            aria-label="Выйти и войти с другим номером"
            title="Выйти"
            onClick={switchAccount}
          >
            <Icon.logout size={18} />
          </button>
        )}
      />
      <div className="screen-body grouped pw-body">
        <div className="pw-wrap">
          <section className="pw-hero pw-in">
            <SyncBridge />
            <div className="pw-kicker">{BOT_NAME} {planTitle}</div>
            <h1 className="pw-title">Полный доступ</h1>
            <p className="pw-lead">
              Настрой свои правила переноса сообщений между Telegram и Max.
            </p>
            {trialMode ? (
              <PwPlan rows={planRows} />
            ) : (
              <div className="pw-price">
                <div className="pw-price-value">{price} {currency}<span>/ месяц</span></div>
              </div>
            )}
          </section>

          <section className="pw-list pw-in d1" aria-label="Что входит в тариф">
            <PwFeatures subscription={sub} />
          </section>

          <section className={`pw-autopay pw-in d2${autopay ? ' on' : ''}`} onClick={toggleAutopay}>
            <div className="pw-autopay-main">
              <div className="pw-autopay-title">Автопродление</div>
              <div className="pw-autopay-text">
                {autopay
                  ? (sub.trialUsed
                      ? `Способ оплаты будет привязан. Списание ${perMonth} — в дату окончания периода.`
                      : `Нужно для ${trialDays} дней бесплатно. При привязке деньги не списываются.`)
                  : sub.trialUsed
                    ? 'Оплата вручную раз в месяц — продлевать нужно самостоятельно.'
                    : `Без автопродления пробный период недоступен: оплата сразу, ${price} ${currency} за месяц.`}
              </div>
            </div>
            <div className="pw-autopay-switch" onClick={(e) => e.stopPropagation()}>
              <Switch on={autopay} onClick={toggleAutopay} />
            </div>
          </section>

          {!payEnabled && (
            <div className="pw-unavailable pw-in d2">
              <Icon.alert size={18} />
              <span>Оплата временно недоступна. Попробуйте позже.</span>
            </div>
          )}

          <div className="pw-in d3">
            <BtnLink style={{ display: 'block', margin: '0 auto 12px' }}
              onClick={() => { host.haptic('selection'); openSheet('activationCode') }}>
              У меня есть код активации
            </BtnLink>
            <div className="pw-accept">Оформляя подписку, вы принимаете условия:</div>
            <LegalLinks style={{ marginTop: 3 }} />
          </div>
        </div>
      </div>
      <div className="footer-area grouped">
        <Btn kind={!payEnabled ? 'gray' : 'primary'} loading={pay.busy} disabled={!payEnabled} onClick={onAction}>
          {label}
        </Btn>
        <div className="pw-trust">
          <Icon.shield size={15} />
          <span>Безопасная оплата с партнёром ЮКасса.</span>
        </div>
      </div>
      {pay.ui}
    </Screen>
  )
}
