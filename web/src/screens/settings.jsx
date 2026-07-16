/* settings.jsx — «Настройки» и вложенные экраны подписки, трафика и уведомлений.
 * Экраны используют общую дизайн-систему и данные из стора/API,
 * состояния загрузка/пусто/ошибка/оффлайн, хаптика при действиях. Pull-to-refresh
 * убран: жест двигал верх экрана и выглядел как случайная прокрутка. */
import React, { useEffect, useState } from 'react'
import {
  Screen, HostHeader, Btn, BtnLink, PillButton, Avatar, MBadge, TBadge, Counter, Dot, Switch,
  Cell, Banner, Spinner, Skeleton, SkeletonCell, TrafficRing, Icon,
} from '../components/ui.jsx'
import { useStore } from '../store/store.js'
import host from '../host/host.js'
import { errorMessage } from '../api/client.js'
import {
  LargeTitle, TabFooter, SupportIsland, LegalLinks, BOT_HANDLES, BOT_LINKS, BOT_NAME,
  HAS_SUPPORT,
  fmtTB, fmtBytes, relTime,
} from './_shared.jsx'
import { usePayFlow, ConfirmSheet } from './pay.jsx'
import { SyncBridge, PwPlan, PwFeatures, buildTrialRows, MaxMark, TgMark, planName } from './paywall.jsx'

/* Дата вида «2026-07-14» → «14 июля 2026». */
function fmtDate(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (isNaN(d)) return iso
  return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' })
}

function CrossBotAvatar({ platform }) {
  const isMax = platform === 'max'
  return (
    <span
      className={`pw-node ${isMax ? 'max' : 'tg'}`}
      style={{ width: 38, height: 38, borderRadius: 11, boxShadow: '0 4px 12px rgba(0,0,0,0.14)' }}
    >
      {isMax ? <MaxMark size={22} /> : <TgMark size={28} />}
    </span>
  )
}

/* ============================ SH — Настройки (хаб) ============================ */
export function SH() {
  const subscription = useStore((s) => s.subscription)
  const traffic = useStore((s) => s.traffic)
  const notifications = useStore((s) => s.notifications)
  const loadTraffic = useStore((s) => s.loadTraffic)
  const loadNotifications = useStore((s) => s.loadNotifications)
  const gateBySubscription = useStore((s) => s.gateBySubscription)
  const push = useStore((s) => s.push)
  const logout = useStore((s) => s.logout)
  const showToast = useStore((s) => s.showToast)

  useEffect(() => {
    if (!subscription) gateBySubscription()
    if (!traffic.data) loadTraffic()
    loadNotifications()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const subActive = subscription?.status === 'active'
  const subSub = subActive ? `Активна до ${fmtDate(subscription?.renewAt)}` : 'Не активна'

  const t = traffic.data
  const trafficSub = t
    ? `Использовано ${fmtBytes(t.usedBytes)} из ${fmtTB(t.limitBytes)}${t.topupBytes ? ` · добавочно ${fmtBytes(t.topupBytes)}` : ''}`
    : `Использовано — из ${subscription?.trafficLimitText || '0,5 ТБ'}`

  const unread = notifications.unread || 0
  const doLogout = () => {
    host.haptic('warning')
    logout()
    showToast('Вы вышли из аккаунта')
  }
  const crossBot = host.name === 'max' && BOT_LINKS.tg ? {
    title: 'Наш бот в ТГ',
    subtitle: `${BOT_HANDLES.tg || BOT_NAME} · вход с тем же номером объединит аккаунт`,
    url: BOT_LINKS.tg,
    platform: 'tg',
  } : host.name === 'telegram' && BOT_LINKS.max ? {
    title: 'Наш бот в MAX',
    subtitle: `${BOT_HANDLES.max || BOT_NAME} · вход с тем же номером объединит аккаунт`,
    url: BOT_LINKS.max,
    platform: 'max',
  } : null
  const openCrossBot = () => {
    if (!crossBot) return
    host.haptic('light')
    host.openLink(crossBot.url)
  }

  return (
    <Screen grouped>
      <HostHeader title="" onGrouped />
      <div className="screen-body grouped">
        <LargeTitle>Настройки</LargeTitle>
        <div className="body-pad" style={{ marginTop: 10 }}>
          <div className="island">
            <Cell inset tap
              before={<Avatar size={38} tone="av-accent" icon={<Icon.gift />} />}
              title="Подписка" subtitle={subSub}
              after={subActive
                ? <span className="chip ok"><Icon.check size={13} />Активна</span>
                : <span className="chip dead"><Icon.alert size={13} />Не активна</span>}
              chevron onClick={() => push('S11')} />
            <Cell inset tap
              before={<Avatar size={38} tone="av-green" icon={<Icon.traffic />} />}
              title="Управление трафиком" subtitle={trafficSub}
              chevron onClick={() => push('S12')} />
            <Cell inset tap
              before={<Avatar size={38} tone="av-orange" icon={<Icon.bell />} />}
              title="Уведомления" subtitle="История событий по источникам, правилам, трафику и подписке"
              after={unread > 0 ? <Counter value={unread} negative /> : undefined}
              chevron onClick={() => push('S13')} />
            <Cell inset tap
              before={<Avatar size={38} tone="av-blue" icon={<Icon.help />} />}
              title="Частые вопросы" subtitle="Ответы про источники, правила, трафик, аккаунт и сбои"
              chevron onClick={() => push('S14')} />
            <Cell inset tap
              before={<Avatar size={38} tone="av-red" icon={<Icon.logout />} />}
              title="Выйти из аккаунта" subtitle="Сессия будет сброшена на этом устройстве"
              onClick={doLogout} />
          </div>
        </div>
        {crossBot && (
          <>
            <div className="cell-header caps">Другой мессенджер</div>
            <div className="body-pad">
              <div className="island">
                <Cell inset tap
                  before={<CrossBotAvatar platform={crossBot.platform} />}
                  title={crossBot.title} subtitle={crossBot.subtitle}
                  after={<span style={{ color: 'var(--text-tertiary)' }}><Icon.link size={16} /></span>}
                  onClick={openCrossBot} />
              </div>
            </div>
          </>
        )}
        {HAS_SUPPORT && (
          <>
            <div className="cell-header caps">Поддержка</div>
            <div className="body-pad"><SupportIsland /></div>
          </>
        )}
        <div className="cell-footer" style={{ paddingTop: 10 }}>Один аккаунт объединяет ваши логины в MAX и Telegram.</div>
        <LegalLinks style={{ padding: '4px 16px 12px' }} />
      </div>
      <TabFooter />
    </Screen>
  )
}

/* ============================ S11 — Подписка ============================ */
/* Экран управления в языке пейволла (S5): аврора-hero с «живым мостом»
 * (потоки бегут, пока подписка активна, и замирают на паузе), таймлайн
 * «сейчас → что дальше» вместо баннеров и сводок. Управление автопродлением
 * и способом оплаты — самостоятельное, без поддержки; сумма, дата списания
 * и способ отключения всегда на экране (требование ЮKassa к автоплатежам). */
export function S11() {
  const subscription = useStore((s) => s.subscription)
  const payAutopay = useStore((s) => s.payAutopay)
  const showToast = useStore((s) => s.showToast)
  const openSheet = useStore((s) => s.openSheet)
  const [confirm, setConfirm] = useState(null)   // подтверждение отключения автоплатежа
  const pay = usePayFlow()

  const sub = subscription || {}
  const active = sub.status === 'active'
  const trial = active && sub.trial
  const price = sub.price ?? 299
  const currency = sub.currency ?? '₽'
  const trialDays = sub.trialDays ?? 7
  const renewDate = fmtDate(sub.renewAt) || '—'
  const priceText = `${price} ${currency}`
  const planTitle = planName(sub)
  const trafficLimitText = sub.trafficLimitText || '0,5 ТБ'
  const payEnabled = sub.payEnabled !== false
  const trialAvailable = !sub.trialUsed
  // Ранняя ручная оплата: активная подписка без автопродления в последние дни
  // (окно считает бэкенд). Привязка автопродления гасит флаг — кнопка исчезает.
  const canRenewEarly = active && !!sub.canRenewEarly
  const canActivateCode = active && !!(sub.canActivateCode || sub.canRenewEarly)
  const showManualRenewActions = !active || canRenewEarly
  const showActivationCode = !active || canActivateCode
  const showBillingBlock = active || sub.autopay || sub.methodTitle

  // Hero: состояние — заголовком, «что будет дальше» — таймлайном.
  const title = trial ? 'Пробный период' : active ? 'Всё работает' : 'Доступ на паузе'
  const planRows = trial
    ? [
        { title: `Сегодня — 0 ${currency}`, text: 'Все условия тарифа открыты, деньги не списаны.' },
        { title: `${renewDate} — первое списание ${priceText}`, text: 'Автоматически, с привязанной карты или СБП.' },
      ]
    : active
      ? sub.autopay
        ? [
            { title: 'Подписка активна', text: 'Правила пересылают сообщения, медиа — в полном качестве.' },
            { title: `${renewDate} — списание ${priceText}`, text: `Продление на месяц. Медиа-трафик обновится до ${trafficLimitText}.` },
          ]
        : [
            { title: 'Подписка активна', text: `Оплачено до ${renewDate}.` },
            canRenewEarly
              ? { title: `${renewDate} — подписка истечёт`, warn: true, text: 'Продлите заранее — пересылка продолжится без паузы. Месяц добавится к текущей дате. Или включите автопродление ниже.' }
              : { title: `${renewDate} — оплата вручную`, warn: true, text: 'Автопродление отключено. Без оплаты правила встанут на паузу.' },
          ]
      : trialAvailable ? buildTrialRows(price, currency, trialDays) : null

  const autopayText = !active
    ? 'Списаний нет, пока подписка не оформлена.'
    : trial
      ? 'Пробный период держится на привязке: отключение сразу его завершит.'
      : sub.autopay
        ? 'Подписка продлевается сама. Отключить можно в любой момент.'
        : `Продления не будет — ${renewDate} подписку нужно оплатить вручную.`

  // Тумблер автопродления. Выключение — через подтверждение (у триала оно
  // аннулирует пробный период); включение требует привязанного способа оплаты —
  // если его нет, запускаем нулевую привязку (карта/СБП).
  const onAutopayToggle = async () => {
    host.haptic('selection')
    if (sub.autopay) { setConfirm({ trial, active }); return }
    try {
      await payAutopay(true)
      host.haptic('success')
      showToast('Автопродление включено', 'check')
    } catch (err) {
      if (err && err.code === 'need_bind' && active) pay.beginBind()
      else showToast(errorMessage(err, 'Не удалось включить автопродление.'), 'alert')
    }
  }

  const doDisable = async () => {
    try {
      const res = await payAutopay(false)
      setConfirm(null)
      host.haptic('success')
      showToast(res.annulled ? 'Пробный период завершён' : 'Автопродление отключено', 'check')
    } catch (err) {
      setConfirm(null)
      showToast(errorMessage(err, 'Не получилось. Попробуйте ещё раз.'), 'alert')
    }
  }

  const ctaLabel = !payEnabled ? 'Оплата временно недоступна'
    : pay.busy ? 'Открываем оплату…'
      : canRenewEarly ? `Продлить за ${priceText}`
        : trialAvailable ? `Попробовать ${trialDays} дней бесплатно`
          : `Оплатить ${priceText}`
  const onCta = () => {
    if (!payEnabled || pay.busy) return
    if (canRenewEarly) pay.beginPay(false)   // ранняя ручная оплата — без привязки
    else if (trialAvailable) pay.beginTrial()
    else pay.beginPay(true)
  }

  return (
    <Screen grouped>
      <HostHeader title="Подписка" back onGrouped />
      <div className="screen-body grouped pw-body">
        <div className="pw-wrap">
          <section className="pw-hero pw-in">
            <SyncBridge paused={!active} />
            <div className="pw-kicker">{BOT_NAME} {planTitle}</div>
            <h1 className="pw-title">{title}</h1>
            {!active && (
              <p className="pw-lead">
                Правила и источники сохранены. После оплаты пересылка продолжится сама.
              </p>
            )}
            {planRows ? (
              <PwPlan rows={planRows} />
            ) : (
              <div className="pw-price">
                <div className="pw-price-value">{price} {currency}<span>/ месяц</span></div>
              </div>
            )}
          </section>

          {sub.lastError && (
            <Banner tone="crit" icon={<Icon.alert size={20} />} title="Последняя ошибка">
              {sub.lastError}
            </Banner>
          )}

          {/* Блок виден всегда, когда есть активная подписка, привязка или автоплатёж:
              пользователь обязан иметь возможность отвязать способ оплаты самостоятельно,
              без поддержки — требование ЮKassa к рекуррентным платежам. */}
          {showBillingBlock && (
            <section className="pw-stack pw-in d1">
              <div className="pw-sec-head">Оплата и автопродление</div>
              <div className={`pw-autopay${sub.autopay ? ' on' : ''}`} onClick={onAutopayToggle}>
                <div className="pw-autopay-main">
                  <div className="pw-autopay-title">Автопродление</div>
                  <div className="pw-autopay-text">{autopayText}</div>
                </div>
                <div className="pw-autopay-switch" onClick={(e) => e.stopPropagation()}>
                  <Switch on={!!sub.autopay} onClick={onAutopayToggle} />
                </div>
              </div>
              {sub.methodTitle && (
                <div className="pw-list">
                  <div className="pw-row">
                    <span className="pw-row-icon i2"><Icon.card size={17} /></span>
                    <span className="pw-row-main">
                      <span className="pw-row-title">Способ оплаты</span>
                      <span className="pw-row-text">{sub.methodTitle}</span>
                    </span>
                    <span className="sub-danger-link"
                      onClick={() => { host.haptic('selection'); setConfirm({ trial, active }) }}>
                      Отвязать
                    </span>
                  </div>
                </div>
              )}
              {active && !sub.methodTitle && (
                <div className="pw-list">
                  <div className="pw-row" role="button" style={{ cursor: 'pointer' }}
                    onClick={() => { host.haptic('selection'); pay.beginBind() }}>
                    <span className="pw-row-icon i2"><Icon.card size={17} /></span>
                    <span className="pw-row-main">
                      <span className="pw-row-title">Привязать способ оплаты</span>
                      <span className="pw-row-text">Карта или СБП для автопродления</span>
                    </span>
                    <span className="sub-action-link">Привязать</span>
                  </div>
                </div>
              )}
              <div className="t-footnote sec text-pretty" style={{ padding: '0 2px' }}>
                Отвязать способ оплаты можно в любой момент — без обращения в поддержку.
              </div>
            </section>
          )}

          <section className="pw-stack pw-in d2">
            <div className="pw-sec-head">Что входит</div>
            <div className="pw-list" aria-label="Что входит в тариф">
              <PwFeatures subscription={sub} />
            </div>
          </section>

          <div className="pw-in d3">
            {showActivationCode && (
              <BtnLink style={{ display: 'block', margin: '0 auto 12px' }}
                onClick={() => { host.haptic('selection'); openSheet('activationCode') }}>
                У меня есть код активации
              </BtnLink>
            )}
            <LegalLinks />
          </div>
        </div>
      </div>
      {showManualRenewActions && (
        <div className="footer-area grouped">
          <Btn kind={!payEnabled ? 'gray' : 'primary'} loading={pay.busy} disabled={!payEnabled} onClick={onCta}>
            {ctaLabel}
          </Btn>
          <div className="pw-trust">
            <Icon.shield size={15} />
            <span>Безопасная оплата с партнёром ЮКасса.</span>
          </div>
        </div>
      )}
      {confirm && (
        <ConfirmSheet
          title={confirm.trial ? 'Завершить пробный период?' : 'Отвязать способ оплаты?'}
          text={confirm.trial
            ? `Отвязка сразу аннулирует пробный период: подписка станет неактивной, правила встанут на паузу. Вернуться можно разовой оплатой ${price} ${currency} — уже без привязки.`
            : confirm.active
              ? `Способ оплаты будет отвязан, автопродление отключится. Подписка останется активной до ${renewDate}, дальше продления не будет.`
              : 'Способ оплаты будет отвязан, автоматические списания прекратятся.'}
          confirmLabel={confirm.trial ? 'Отвязать и завершить' : 'Отвязать'}
          onConfirm={doDisable}
          onClose={() => setConfirm(null)}
        />
      )}
      {pay.ui}
      <TabFooter />
    </Screen>
  )
}

/* ============================ S12 — Управление трафиком ============================ */
const TRAFFIC_BANNER = {
  norm: { tone: 'norm', icon: <Icon.check size={20} />, title: 'Трафика достаточно', text: 'Сообщения пересылаются с медиа в полном качестве.' },
  warn: { tone: 'warn', icon: <Icon.alert size={20} />, title: 'Трафик заканчивается', text: 'Использовано больше 80%. Когда трафик закончится, сообщения продолжат пересылаться, но без медиа — со ссылкой на оригинал. Стоит докупить заранее.' },
  extra: { tone: 'warn', icon: <Icon.alert size={20} />, title: 'Используется добавочный трафик', text: 'Месячный лимит исчерпан, но медиа продолжает пересылаться за счёт добавочного остатка. Он не сгорает и расходуется только сверх месячного лимита.' },
  crit: { tone: 'crit', icon: <Icon.alert size={20} />, title: 'Медиа-трафик исчерпан', text: 'Сообщения и посты продолжают пересылаться — но без фото, видео и файлов. Вместо медиа добавляется ссылка на оригинал с подписью «полное сообщение/пост можно посмотреть здесь». Докупите трафик, чтобы вернуть пересылку с медиа.' },
}

export function S12() {
  const traffic = useStore((s) => s.traffic)
  const online = useStore((s) => s.online)
  const loadTraffic = useStore((s) => s.loadTraffic)
  const pay = usePayFlow({ onDone: loadTraffic })

  useEffect(() => { loadTraffic() }, [loadTraffic])

  const t = traffic.data
  const loading = traffic.loading && !t
  const offline = !online || traffic.error === 'offline'
  const errored = traffic.error && traffic.error !== 'offline'

  const onTopup = async () => {
    pay.beginTopup()
  }

  let body
  if (loading) {
    body = (
      <>
        <div style={{ display: 'flex', justifyContent: 'center', padding: '24px 0 18px' }}>
          <Skeleton w={168} h={168} r={84} />
        </div>
        <div className="body-pad"><div className="island" style={{ padding: 16 }}><Skeleton w="70%" h={14} /><Skeleton w="50%" h={12} style={{ marginTop: 10 }} /></div></div>
        <div className="body-pad"><Skeleton w="100%" h={72} r={12} /></div>
      </>
    )
  } else if (errored || (offline && !t)) {
    body = (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', padding: '60px 28px 0', color: 'var(--text-secondary)' }}>
        <span style={{ color: 'var(--text-tertiary)' }}>{offline ? <Icon.wifiOff size={40} /> : <Icon.alert size={40} />}</span>
        <div className="t-headline" style={{ marginTop: 14, color: 'var(--text)' }}>{offline ? 'Нет соединения' : 'Не удалось загрузить'}</div>
        <PillButton icon={<Icon.refresh size={16} />} style={{ marginTop: 14 }} onClick={() => loadTraffic()}>Обновить</PillButton>
      </div>
    )
  } else if (t) {
    const baseLimit = Math.max(0, t.limitBytes || 0)
    const percent = t.percent ?? (baseLimit ? Math.min(100, Math.round((t.usedBytes / baseLimit) * 100)) : (t.usedBytes ? 100 : 0))
    const extraRemaining = t.topupBytes || 0
    const packageBytes = t.topupPackageBytes || 100 * 1024 ** 3
    const packagePrice = t.topupPackagePrice ?? 100
    const packageText = fmtBytes(packageBytes).replace(',0 ГБ', ' ГБ').replace(',00 ТБ', ' ТБ')
    const topupPayEnabled = t.topupPayEnabled !== false
    const mediaAllowed = t.mediaAllowed ?? (t.usedBytes < baseLimit || extraRemaining > 0)
    const tone = percent >= 100 && !mediaAllowed ? 'crit' : percent >= 100 ? 'extra' : percent >= 80 ? 'warn' : 'norm'
    const remaining = t.includedRemainingBytes ?? Math.max(0, t.limitBytes - t.usedBytes)
    const banner = TRAFFIC_BANNER[tone]

    body = (
      <>
        {/* кольцо */}
        <div style={{ display: 'flex', justifyContent: 'center', padding: '20px 0 14px' }}>
          <TrafficRing percent={percent} tone={tone}
            center={percent === 0 && t.usedBytes > 0 ? '<1%' : `${percent}%`} />
        </div>
        <div className="t-body-sm sec" style={{ textAlign: 'center' }}>
          Использовано {fmtBytes(t.usedBytes)} из {fmtTB(t.limitBytes)}
        </div>
        <div className="t-footnote sec text-pretty" style={{ textAlign: 'center', marginTop: 6, padding: '0 28px' }}>
          Учитывается только медиа: фото, видео, файлы, голосовые.
        </div>

        {/* остаток / сброс */}
        <div className="body-pad" style={{ marginTop: 14 }}>
          <div className="cell" style={{ borderRadius: 12, alignItems: 'flex-start', minHeight: 0, padding: '13px 16px' }}>
            <div className="cell-before" style={{ marginTop: 1, color: 'var(--text-secondary)' }}><Icon.clock size={22} /></div>
            <div className="cell-main" style={{ padding: 0, gap: 3 }}>
              <div className="t-headline" style={{ fontSize: 15 }}>Осталось {fmtTB(remaining)}</div>
              <div className="t-footnote sec text-pretty">Обнулится {fmtDate(t.resetAt) || '14 июля 2026'} (в дату продления подписки)</div>
              {extraRemaining > 0 && <div className="t-footnote sec text-pretty">Добавочный остаток: {fmtBytes(extraRemaining)} без срока действия</div>}
            </div>
          </div>
        </div>

        {/* баннер-объяснение */}
        <div className="body-pad" style={{ marginTop: 4 }}>
          <Banner tone={banner.tone} icon={banner.icon} title={banner.title}>{banner.text}</Banner>
          {tone === 'crit' && (
            <div className="note-card" style={{ marginTop: 8, padding: '12px 14px' }}>
              <div className="t-body-sm">Текст сообщения сохраняется полностью.</div>
              <div className="t-footnote acc" style={{ marginTop: 6, display: 'flex', alignItems: 'center', gap: 6 }}>
                <span>🔗</span><span>полное сообщение/пост можно посмотреть здесь</span>
              </div>
            </div>
          )}
        </div>

        {/* докупка */}
        <div className="cell-header caps">Докупить трафик</div>
        <div className="body-pad">
          <div className="note-card" style={tone !== 'norm' ? { borderColor: 'var(--accent)', borderWidth: 1.5 } : undefined}>
            <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
              <span className="t-headline" style={{ fontSize: 16 }}>{packageText} — {packagePrice} ₽</span>
            </div>
            <div className="t-footnote sec text-pretty" style={{ marginTop: 4 }}>Бессрочный пакет: расходуется только после месячного лимита.</div>
            <Btn style={{ marginTop: 12 }} disabled={!topupPayEnabled || pay.busy} onClick={onTopup}>
              Докупить {packageText} за {packagePrice} ₽
            </Btn>
            {!topupPayEnabled && (
              <div className="t-footnote sec text-pretty" style={{ textAlign: 'center', marginTop: 10 }}>
                Оплата пакетов временно недоступна.
              </div>
            )}
          </div>
        </div>
      </>
    )
  }

  return (
    <Screen grouped>
      <HostHeader title="Управление трафиком" back onGrouped />
      <div className="screen-body grouped">
        {body}
      </div>
      {pay.ui}
      <TabFooter />
    </Screen>
  )
}

/* ============================ S13 — Уведомления ============================ */
const NOTIF_ICON = {
  rights: { tone: 'av-orange', icon: <Icon.shield /> },
  dead: { tone: 'av-red', icon: <Icon.alert /> },
  bound: { tone: 'av-green', icon: <Icon.check /> },
  code: { tone: 'av-blue', icon: <Icon.key /> },
  traffic: { tone: 'av-green', icon: <Icon.traffic /> },
  sub: { tone: 'av-accent', icon: <Icon.gift /> },
  rules: { tone: 'av-orange', icon: <Icon.shield /> },
}
function notifIcon(type) { return NOTIF_ICON[type] || { tone: 'av-blue', icon: <Icon.bell /> } }

function NotifCell({ n, onClick }) {
  const ic = notifIcon(n.type)
  return (
    <Cell inset tap
      before={
        <div style={{ position: 'relative' }}>
          <Avatar size={38} tone={ic.tone} icon={ic.icon} />
          {!n.read && <span style={{ position: 'absolute', top: -2, left: -2 }}><Dot tone="accent" /></span>}
        </div>
      }
      title={n.title}
      subtitle={n.subtitle ? <NotifSub text={n.subtitle} /> : undefined}
      after={<span className="t-caption sec" style={{ whiteSpace: 'nowrap' }}>{relTime(n.ts)}</span>}
      onClick={onClick}
    />
  )
}

/* Подзаголовок уведомления: «MAX · Канал» → бейдж MAX/TG + текст. */
function NotifSub({ text }) {
  const m = /^(MAX|TG)\s*·\s*(.*)$/.exec(text)
  if (m) return <><MBadge m={m[1]} /><span className="t-caption sec">· {m[2]}</span></>
  return <span className="t-caption sec">{text}</span>
}

export function S13() {
  const notifications = useStore((s) => s.notifications)
  const online = useStore((s) => s.online)
  const loadNotifications = useStore((s) => s.loadNotifications)
  const markNotificationsRead = useStore((s) => s.markNotificationsRead)
  const push = useStore((s) => s.push)
  const setTab = useStore((s) => s.setTab)

  useEffect(() => {
    (async () => { await loadNotifications(); await markNotificationsRead() })()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const items = notifications.items || []
  const loading = notifications.loading && items.length === 0
  const offline = !online || notifications.error === 'offline'
  const errored = notifications.error && notifications.error !== 'offline'

  const goto = (link) => {
    if (!link) return
    host.haptic('selection')
    if (link.screen === 'sources') setTab('sources')
    else if (link.screen === 'rules') setTab('rules')
    else if (link.screen === 'traffic') push('S12')
    else if (link.screen === 'subscription') push('S11')
  }

  let body
  if (loading) {
    body = <div className="body-pad" style={{ marginTop: 10 }}><div className="island"><SkeletonCell /><SkeletonCell /><SkeletonCell /></div></div>
  } else if (errored || (offline && items.length === 0)) {
    body = (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', padding: '60px 28px 0', color: 'var(--text-secondary)' }}>
        <span style={{ color: 'var(--text-tertiary)' }}>{offline ? <Icon.wifiOff size={40} /> : <Icon.alert size={40} />}</span>
        <div className="t-headline" style={{ marginTop: 14, color: 'var(--text)' }}>{offline ? 'Нет соединения' : 'Не удалось загрузить'}</div>
        <PillButton icon={<Icon.refresh size={16} />} style={{ marginTop: 14 }} onClick={() => loadNotifications()}>Обновить</PillButton>
      </div>
    )
  } else if (items.length === 0) {
    body = (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', padding: '48px 28px 0' }}>
        <span style={{ color: 'var(--text-tertiary)' }}><Icon.bell size={44} /></span>
        <div className="t-title-sm" style={{ marginTop: 16, fontSize: 20, fontWeight: 700 }}>Уведомлений пока нет</div>
        <div className="t-body-sm sec text-pretty" style={{ marginTop: 8, maxWidth: 290 }}>
          Здесь появятся события по источникам, правилам, трафику и подписке.
        </div>
      </div>
    )
  } else {
    body = (
      <div className="body-pad" style={{ marginTop: 10 }}>
        <div className="island">
          {items.map((n) => <NotifCell key={n.id} n={n} onClick={() => goto(n.link)} />)}
        </div>
      </div>
    )
  }

  return (
    <Screen grouped>
      <HostHeader title="Уведомления" back onGrouped />
      <div className="screen-body grouped">
        {body}
      </div>
      <TabFooter />
    </Screen>
  )
}
