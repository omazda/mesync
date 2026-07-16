/* pay.jsx — общий флоу оплаты ЮKassa для пейволла (S5) и управления подпиской (S11).
 *
 * Три сценария (бэкенд: /api/pay/*, сверено с docs/yookassa):
 *   - триал: привязка автоплатежа на нулевую сумму (карта/СБП) → готовая страница
 *     ЮKassa во внешнем браузере (confirmationUrl) → поллинг статуса;
 *   - оплата: платёж виджетом ЮKassa прямо в mini-app (confirmation_token,
 *     confirmation.type=embedded) → события success/fail + поллинг;
 *   - bind: привязка способа оплаты к уже активной подписке (включение автопродления).
 *
 * Скрипт виджета грузится внутри изолированного iframe, чтобы CSS mini-app не влиял
 * на поля формы (https://yookassa.ru/checkout-widget/…).
 */
import React, { useEffect, useMemo, useRef, useState } from 'react'
import { Sheet, Btn, Cell, Avatar, Spinner, Icon } from '../components/ui.jsx'
import { useStore } from '../store/store.js'
import host from '../host/host.js'
import { errorMessage } from '../api/client.js'

const WIDGET_SRC = 'https://yookassa.ru/checkout-widget/v1/checkout-widget.js'

/* ---------- платёжная форма виджета в контейнере ---------- */
function WidgetBox({ token, onSuccess, onFail }) {
  const frameRef = useRef(null)

  useEffect(() => {
    const onMessage = (event) => {
      if (event.source !== frameRef.current?.contentWindow) return
      const data = event.data || {}
      if (data.source !== 'mesync-yookassa-widget') return
      if (data.type === 'success') onSuccess?.()
      if (data.type === 'fail') onFail?.()
    }
    window.addEventListener('message', onMessage)
    return () => window.removeEventListener('message', onMessage)
  }, [onFail, onSuccess])

  const srcDoc = useMemo(() => {
    const widgetSrc = JSON.stringify(WIDGET_SRC)
    const confirmationToken = JSON.stringify(token)
    return `<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, viewport-fit=cover, interactive-widget=resizes-content" />
  <style>
    html, body {
      width: 100%;
      min-width: 0;
      margin: 0;
      padding: 0;
      overflow-x: hidden;
      background: #fff;
      color: #000;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
    }
    *, *::before, *::after { box-sizing: border-box; }
    #yk-pay-form {
      width: 100%;
      max-width: 430px;
      min-width: 0;
      margin: 0 auto;
      padding: 0;
      overflow-x: hidden;
      background: #fff;
    }
    #yk-pay-form > * {
      max-width: 100% !important;
    }
  </style>
</head>
<body>
  <div id="yk-pay-form"></div>
  <script src=${widgetSrc}><\/script>
  <script>
    (function () {
      function send(type, extra) {
        window.parent.postMessage(Object.assign({ source: 'mesync-yookassa-widget', type: type }, extra || {}), '*');
      }
      function fail(error) {
        send('fail', { error: String(error && (error.message || error.code) || error || 'widget_error') });
      }
      try {
        var checkout = new window.YooMoneyCheckoutWidget({
          confirmation_token: ${confirmationToken},
          customization: {
            colors: {
              control_primary: '#2B7CF6',
              background: '#FFFFFF'
            }
          },
          error_callback: fail
        });
        checkout.on('success', function () { send('success'); });
        checkout.on('fail', function () { send('fail'); });
        var rendered = checkout.render('yk-pay-form');
        if (rendered && rendered.catch) rendered.catch(fail);
        window.addEventListener('pagehide', function () {
          try { checkout.destroy(); } catch (_) {}
        });
      } catch (error) {
        fail(error);
      }
    })();
  <\/script>
</body>
</html>`
  }, [token])

  return (
    <div className="yk-widget-wrap">
      <iframe
        ref={frameRef}
        title="Оплата ЮKassa"
        className="yk-widget-frame"
        srcDoc={srcDoc}
        allow="payment"
      />
    </div>
  )
}

/* ---------- хук платёжного флоу ---------- */
/* Возвращает { flow, busy, beginTrial, beginBind, beginPay, ui }.
 * ui — готовый JSX (шиты флоу), рендерить в конце экрана. */
export function usePayFlow({ onDone } = {}) {
  const payCheckout = useStore((s) => s.payCheckout)
  const topupTraffic = useStore((s) => s.topupTraffic)
  const payStatus = useStore((s) => s.payStatus)
  const payCancel = useStore((s) => s.payCancel)
  const showToast = useStore((s) => s.showToast)
  const [flow, setFlow] = useState(null)   // {step:'method'|'widget'|'wait', ...}
  const [busy, setBusy] = useState(false)
  const pollRef = useRef(null)
  const doneRef = useRef(onDone)
  doneRef.current = onDone

  const stopPoll = () => { if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null } }
  useEffect(() => stopPoll, [])

  const finishFail = (text) => {
    stopPoll()
    setFlow(null)
    host.haptic('error')
    showToast(text || 'Оплата не прошла. Попробуйте ещё раз.', 'alert')
  }

  const startPoll = (mode) => {
    stopPoll()
    const startedAt = Date.now()
    const finishOk = () => {
      stopPoll()
      setFlow(null)
      host.haptic('success')
      showToast(mode === 'bind'
        ? 'Автопродление включено'
        : mode === 'traffic_topup'
          ? 'Пакет трафика начислен'
          : 'Подписка активирована', 'check')
      doneRef.current?.()
    }
    pollRef.current = setInterval(async () => {
      // Привязку/оплату применяет бэкенд (идемпотентно) — мы только опрашиваем.
      try {
        const res = await payStatus()
        if (res.state === 'succeeded') {
          finishOk()
        } else if (res.state === 'failed') {
          finishFail(res.subscription?.lastError)
        } else if (res.state === 'none') {
          // Оформления на бэкенде уже нет. Обычно это гонка с вебхуком ЮKassa:
          // он применил результат раньше нашего опроса и снял pending — исход
          // виден по подписке из этого же ответа. lastError ставится при провале
          // и очищается при новом оформлении/успехе, поэтому он надёжнее статуса:
          // при РАННЕМ продлении подписка активна ещё ДО платежа, и «активна»
          // сама по себе успех не доказывает. Иначе — лист тихо закрываем.
          const sub = res.subscription || {}
          if (sub.lastError) {
            finishFail(sub.lastError)
          } else if (mode === 'traffic_topup' || (mode === 'pay' ? sub.status === 'active' : !!sub.autopay)) {
            finishOk()
          } else {
            stopPoll()
            setFlow(null)
          }
        } else if (Date.now() - startedAt > 15 * 60e3) {
          stopPoll()          // страница привязки ЮKassa живёт 1 час, но ждать вечно незачем
          setFlow(null)
        }
      } catch (_) { /* сеть мигнула — продолжаем опрос */ }
    }, 2500)
  }

  const checkout = async (payload) => {
    if (busy) return
    host.haptic('medium')
    setBusy(true)
    try {
      const res = payload.mode === 'traffic_topup' ? await topupTraffic() : await payCheckout(payload)
      if (res.kind === 'binding' && res.confirmationUrl) {
        host.openLink(res.confirmationUrl)  // готовая страница привязки ЮKassa
        setFlow({ step: 'wait', mode: payload.mode })
        startPoll(payload.mode)
      } else if (res.kind === 'payment' && res.confirmationToken) {
        setFlow({ step: 'widget', token: res.confirmationToken, mode: payload.mode })
      } else {
        finishFail()
      }
    } catch (err) {
      host.haptic('error')
      showToast(errorMessage(err, 'Не удалось начать оплату. Попробуйте ещё раз.'), 'alert')
    } finally {
      setBusy(false)
    }
  }

  const cancelFlow = async () => {
    stopPoll()
    setFlow(null)
    try { await payCancel() } catch (_) {}
  }

  const api = {
    flow, busy,
    beginTrial: () => setFlow({ step: 'method', mode: 'trial' }),
    beginBind: () => setFlow({ step: 'method', mode: 'bind' }),
    beginPay: (autopay) => checkout({ mode: 'pay', autopay: !!autopay }),
    beginTopup: () => checkout({ mode: 'traffic_topup' }),
  }

  const onWidgetSuccess = (mode = 'pay') => {
    // Пользователь оплатил на форме — дожимаем статус платежа поллингом.
    setFlow({ step: 'wait', mode })
    startPoll(mode)
  }

  api.ui = (
    <>
      {flow?.step === 'method' && (
        <Sheet title={flow.mode === 'trial' ? 'Привязка автоплатежа' : 'Способ оплаты'} onClose={() => setFlow(null)}>
          <div className="t-footnote sec text-pretty" style={{ padding: '2px 16px 10px' }}>
            {flow.mode === 'trial'
              ? 'Деньги сейчас не списываются: способ оплаты проверяется и привязывается. Откроется страница ЮKassa.'
              : 'Привязка без списания — откроется страница ЮKassa.'}
          </div>
          <div className="island" style={{ margin: '0 16px 16px' }}>
            <Cell inset tap
              before={<Avatar size={38} tone="av-blue" icon={<Icon.card />} />}
              title="Банковская карта" subtitle="Visa, Mastercard, «Мир»"
              chevron onClick={() => { setFlow(null); checkout({ mode: flow.mode, method: 'bank_card' }) }} />
            <Cell inset tap
              before={<Avatar size={38} tone="av-green" icon={<Icon.spark />} />}
              title="СБП" subtitle="Счёт в банке через Систему быстрых платежей"
              chevron onClick={() => { setFlow(null); checkout({ mode: flow.mode, method: 'sbp' }) }} />
          </div>
        </Sheet>
      )}
      {flow?.step === 'widget' && (
        <Sheet title="Оплата" onClose={cancelFlow} className="yk-pay-sheet" bodyClassName="yk-pay-sheet-body">
          <WidgetBox token={flow.token} onSuccess={() => onWidgetSuccess(flow.mode || 'pay')}
            onFail={() => finishFail('Оплата не прошла. Попробуйте ещё раз.')} />
        </Sheet>
      )}
      {flow?.step === 'wait' && (
        <Sheet title="Почти готово" onClose={cancelFlow}>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', padding: '10px 24px 20px', gap: 12 }}>
            <Spinner size={26} />
            <div className="t-body-sm sec text-pretty">
              {flow.mode === 'pay'
                ? 'Проверяем оплату — обычно это пара секунд.'
                : flow.mode === 'traffic_topup'
                  ? 'Проверяем оплату пакета — обычно это пара секунд.'
                : 'Подтвердите привязку на открывшейся странице и вернитесь сюда — статус обновится автоматически.'}
            </div>
            <Btn kind="secondary" onClick={cancelFlow} style={{ marginTop: 6 }}>Отмена</Btn>
          </div>
        </Sheet>
      )}
    </>
  )
  return api
}

/* ---------- подтверждение (отключение автоплатежа и т.п.) ---------- */
export function ConfirmSheet({ title, text, confirmLabel, onConfirm, onClose, danger = true }) {
  const [busy, setBusy] = useState(false)
  return (
    <Sheet title={title} onClose={onClose}>
      <div className="t-body-sm sec text-pretty" style={{ padding: '2px 16px 14px' }}>{text}</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, padding: '0 16px 16px' }}>
        <Btn kind={danger ? 'destructive' : 'primary'} loading={busy}
          onClick={async () => { if (busy) return; setBusy(true); try { await onConfirm() } finally { setBusy(false) } }}>
          {confirmLabel}
        </Btn>
        <Btn kind="secondary" onClick={onClose}>Отмена</Btn>
      </div>
    </Sheet>
  )
}
