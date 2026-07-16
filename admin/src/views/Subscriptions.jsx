import React, { useEffect, useState } from 'react'
import { api } from '../api.js'
import { PowerOff, CircleOff } from 'lucide-react'

function fmtDate(iso) { return iso || '—' }
const CLS = { active: 'ok', trial: 'unsure', inactive: 'na', retry: 'unsure' }

const PAGE = 100

export default function Subscriptions() {
  const [filter, setFilter] = useState('')
  const [data, setData] = useState(null)
  const [offset, setOffset] = useState(0)
  const [tick, setTick] = useState(0)
  const [busyId, setBusyId] = useState('')
  const [msg, setMsg] = useState(null)
  useEffect(() => {
    let alive = true
    api.subscriptions({ status: filter, limit: PAGE, offset })
      .then((r) => { if (!alive) return; setData((prev) => (offset && prev) ? { ...r, items: [...prev.items, ...r.items] } : r) })
      .catch(() => { if (alive) setData({ items: [], total: 0 }) })
    return () => { alive = false }
  }, [filter, offset, tick])
  const pick = (v) => { setFilter(v); setOffset(0) }
  const reload = () => { setOffset(0); setTick((t) => t + 1) }
  const canDisableAutopay = (s) => !!s.autopay || !!s.payment_method_title || !!s.pending
  const canDisableSub = (s) => s.status === 'active' || !!s.autopay || !!s.payment_method_title || !!s.pending || !!s.paid_until || !!s.renew_at
  const disableAutopay = async (s) => {
    if (!canDisableAutopay(s) || busyId) return
    const ok = window.confirm('Отключить автопродление? Оплаченная подписка останется активной до даты окончания. Для триала пробный период завершится.')
    if (!ok) return
    setBusyId(s.account_id); setMsg(null)
    try {
      const r = await api.accountAction(s.account_id, { action: 'disable_autopay' })
      setMsg({ ok: true, text: r.annulled ? 'Автопродление отключено, триал завершён.' : 'Автопродление отключено.' })
      reload()
    } catch (e) {
      setMsg({ ok: false, text: e.message || 'Не удалось отключить автопродление.' })
    }
    setBusyId('')
  }
  const disableSubscription = async (s) => {
    if (!canDisableSub(s) || busyId) return
    const ok = window.confirm('Отключить подписку? Статус станет inactive, автопродление и привязка оплаты будут сняты.')
    if (!ok) return
    setBusyId(s.account_id); setMsg(null)
    try {
      await api.accountAction(s.account_id, { action: 'disable_subscription' })
      setMsg({ ok: true, text: 'Подписка отключена.' })
      reload()
    } catch (e) {
      setMsg({ ok: false, text: e.message || 'Не удалось отключить подписку.' })
    }
    setBusyId('')
  }

  const filters = [['', 'Все'], ['active', 'Активные'], ['trial', 'Триал'], ['inactive', 'Истёкшие']]
  return (
    <>
      <div className="view-head">
        <div><div className="lbl eyebrow">Биллинг</div><h1>Подписки</h1><p>Выдача и продление — в карточке аккаунта. Возврат средств делается в личном кабинете ЮKassa.</p></div>
      </div>

      <div className="spread" style={{ marginBottom: 14 }}>
        <div className="seg">
          {filters.map(([v, l]) => <button key={v} className={filter === v ? 'on' : ''} onClick={() => pick(v)}>{l}</button>)}
        </div>
        <button className="btn sm" onClick={reload}>Обновить</button>
      </div>
      {msg && <div className={`form-note ${msg.ok ? 'ok' : 'err'}`} style={{ marginBottom: 12 }}>{msg.text}</div>}

      <div className="card"><div className="twrap"><table className="t">
        <thead><tr><th>Аккаунт</th><th>Статус</th><th>Тариф</th><th>Действует до</th><th>Автопродление</th><th>Действия</th></tr></thead>
        <tbody>
          {(data?.items || []).map((s) => (
            <tr key={s.account_id}>
              <td><span className="id">{s.account_id}</span> {s.phone ? <span className="muted mono" style={{ fontSize: 12 }}>+{s.phone}</span> : ''}</td>
              <td><span className={`pill ${CLS[s.status] || 'na'} dot`}>{s.status || '—'}</span></td>
              <td>{s.planName || (s.plan === 'individual' ? 'Индивидуальный' : (s.plan || '—'))}</td>
              <td className="mono muted">{fmtDate(s.renew_at)}</td>
              <td>{s.autopay ? 'Вкл' : 'Выкл'}</td>
              <td>
                <div className="row-flex" style={{ gap: 6, flexWrap: 'wrap' }}>
                  <button className="btn sm" disabled={!!busyId || !canDisableAutopay(s)} onClick={() => disableAutopay(s)}><CircleOff size={15} />Автопродление</button>
                  <button className="btn sm danger" disabled={!!busyId || !canDisableSub(s)} onClick={() => disableSubscription(s)}><PowerOff size={15} />Подписку</button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table></div></div>
      {data && data.items.length === 0 && <div className="card pad muted" style={{ marginTop: 12 }}>Подписок нет.</div>}
      {data && data.total > data.items.length && (
        <div className="row-flex" style={{ marginTop: 10, gap: 10 }}>
          <button className="btn sm" onClick={() => setOffset(data.items.length)}>Показать ещё</button>
          <span className="muted" style={{ fontSize: 12.5 }}>Показаны {data.items.length} из {data.total}.</span>
        </div>
      )}
    </>
  )
}
