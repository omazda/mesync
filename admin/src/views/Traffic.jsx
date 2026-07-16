import React, { useEffect, useState } from 'react'
import { api } from '../api.js'
import { AlertTriangle, CircleOff, PackagePlus, RotateCcw, ShieldCheck } from 'lucide-react'

const PAGE = 100
const TB = 1024 ** 4
const GB = 1024 ** 3
function fmtBytes(b) {
  b = Number(b) || 0
  if (b >= TB) return (b / TB).toFixed(2) + ' ТБ'
  return (b / GB).toFixed(1) + ' ГБ'
}
function pct(v) {
  return Math.max(0, Math.min(100, Number(v) || 0))
}
function trafficState(r) {
  if (!r.mediaAllowed) {
    return { cls: 'violation', icon: CircleOff, label: 'медиа закрыто', note: 'нет остатка' }
  }
  if ((r.overageBytes || 0) > 0) {
    return { cls: 'unsure', icon: PackagePlus, label: 'расходует пакет', note: 'сверх месяца' }
  }
  if ((r.percent || 0) >= 80) {
    return { cls: 'unsure', icon: AlertTriangle, label: 'близко к лимиту', note: 'месячный пакет' }
  }
  return { cls: 'ok', icon: ShieldCheck, label: 'в норме', note: 'месячный пакет' }
}

export default function Traffic() {
  const [state, setState] = useState('')
  const [sort, setSort] = useState('used')
  const [data, setData] = useState(null)
  const [offset, setOffset] = useState(0)
  const [tick, setTick] = useState(0)
  const [msg, setMsg] = useState(null)
  const [busy, setBusy] = useState(false)
  useEffect(() => {
    let alive = true
    api.traffic({ sort, state, limit: PAGE, offset })
      .then((r) => { if (!alive) return; setData((prev) => (offset && prev) ? { ...r, items: [...prev.items, ...r.items] } : r) })
      .catch(() => { if (alive) setData((prev) => (offset && prev) ? prev : { items: [], total: 0, totals: {} }) })
    return () => { alive = false }
  }, [state, sort, offset, tick])
  const pickState = (v) => { setState(v); setOffset(0) }
  const pickSort = (v) => { setSort(v); setOffset(0) }
  const reload = () => { setOffset(0); setTick((t) => t + 1) }

  const reset = async (r) => {
    const id = r.account_id
    const ok = window.confirm(`Сбросить месячный расход аккаунта ${id}? Добавочный остаток ${fmtBytes(r.topupBytes)} сохранится.`)
    if (!ok) return
    setBusy(true); setMsg(null)
    try {
      await api.trafficAction(id, { action: 'reset_traffic' })
      setMsg({ text: `Месячный расход аккаунта ${id} сброшен, добавочный остаток сохранён.`, ok: true })
      reload()
    } catch (e) { setMsg({ text: e.message || 'Не удалось', ok: false }) }
    setBusy(false)
  }

  const tot = data?.totals || {}
  const states = [['', 'Все'], ['warn', '≥80% месяца'], ['over', 'Сверх месяца'], ['addon', 'Есть пакет'], ['blocked', 'Медиа закрыто']]
  const sorts = [['used', 'расход'], ['percent', '% месяца'], ['overage', 'сверх'], ['topup', 'пакет']]
  return (
    <>
      <div className="view-head">
        <div><div className="lbl eyebrow">Расход медиа-трафика по аккаунтам</div><h1>Трафик</h1></div>
      </div>

      <div className="tiles traffic-tiles" style={{ marginBottom: 12 }}>
        <div className="card stat"><div className="n">{tot.count ?? 0}</div><div className="k">Аккаунтов в учёте</div><div className="sub">расход или add-on</div></div>
        <div className="card stat"><div className="n">{fmtBytes(tot.sumUsed)}</div><div className="k">Месячный расход</div><div className="sub">за текущие периоды</div></div>
        <div className="card stat"><div className="n">{fmtBytes(tot.sumTopup)}</div><div className="k">Add-on остаток</div><div className="sub">без срока действия</div></div>
        <div className="card stat"><div className="n">{tot.mediaBlocked ?? 0}</div><div className="k">Медиа закрыто</div><div className="sub">нет месячного или add-on</div></div>
      </div>

      <div className="spread" style={{ marginBottom: 12, gap: 10, flexWrap: 'wrap' }}>
        <div className="seg">
          {states.map(([v, l]) => <button key={v} className={state === v ? 'on' : ''} onClick={() => pickState(v)}>{l}</button>)}
        </div>
        <div className="seg">
          {sorts.map(([v, l]) => <button key={v} className={sort === v ? 'on' : ''} onClick={() => pickSort(v)}>{l}</button>)}
        </div>
      </div>

      {msg && <div className={`form-note ${msg.ok ? 'ok' : 'err'}`} style={{ marginBottom: 12 }}>{msg.text}</div>}

      <div className="card"><div className="twrap"><table className="t">
        <thead><tr><th>Аккаунт</th><th style={{ width: 250 }}>Месячный период</th><th>Сверх месяца</th><th>Add-on остаток</th><th>Состояние</th><th></th></tr></thead>
        <tbody>
          {(data?.items || []).map((r) => {
            const st = trafficState(r)
            const Icon = st.icon
            return (
              <tr key={r.account_id}>
                <td><span className="id">{r.account_id}</span>{r.phone ? <div className="muted mono" style={{ fontSize: 11.5 }}>+{r.phone}</div> : null}</td>
                <td>
                  <div className="spread traffic-month-line">
                    <span className="mono" style={{ fontWeight: 700 }}>{fmtBytes(r.usedBytes)}</span>
                    <span className="muted mono" style={{ fontSize: 12 }}>из {fmtBytes(r.limitBytes)}</span>
                  </div>
                  <div className={`meter${r.percent >= 80 ? ' warn' : ''}`}><i style={{ width: pct(r.percent) + '%' }} /></div>
                  <div className="traffic-subline">
                    <span className="mono">{r.percent}%</span>
                    <span>осталось {fmtBytes(r.includedRemainingBytes)}</span>
                  </div>
                </td>
                <td className="mono" style={{ fontWeight: (r.overageBytes || 0) ? 700 : 500 }}>
                  {(r.overageBytes || 0) ? fmtBytes(r.overageBytes) : <span className="muted">—</span>}
                </td>
                <td className="mono" style={{ fontWeight: (r.topupBytes || 0) ? 700 : 500 }}>
                  {(r.topupBytes || 0) ? fmtBytes(r.topupBytes) : <span className="muted">—</span>}
                </td>
                <td>
                  <span className={`pill ${st.cls}`}><Icon size={12} />{st.label}</span>
                  <div className="faint" style={{ fontSize: 11.5, marginTop: 4 }}>{st.note}</div>
                </td>
                <td><button className="btn sm" disabled={busy} onClick={() => reset(r)}><RotateCcw size={14} />Сбросить месяц</button></td>
              </tr>
            )
          })}
        </tbody>
      </table></div></div>
      {data && data.items.length === 0 && <div className="card pad muted" style={{ marginTop: 12 }}>Аккаунтов по выбранному фильтру нет.</div>}
      {data && data.total > data.items.length && (
        <div className="row-flex" style={{ marginTop: 10, gap: 10 }}>
          <button className="btn sm" onClick={() => setOffset(data.items.length)}>Показать ещё</button>
          <span className="muted" style={{ fontSize: 12.5 }}>Показаны {data.items.length} из {data.total}.</span>
        </div>
      )}
    </>
  )
}
