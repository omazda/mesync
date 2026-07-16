import React, { useEffect, useState } from 'react'
import { api } from '../api.js'
import { Play, Pause, Trash2, BellOff, Bell, ShieldAlert, ShieldCheck, EyeOff } from 'lucide-react'

const PAGE = 100
const ST = { active: 'ok', paused: 'na', broken: 'violation' }
const ST_RU = { active: 'активно', paused: 'пауза', broken: 'сбой' }
const DIR = { both: 'A ⇄ B', to: 'A → B', from: 'A ← B' }

function Chip({ ep }) {
  return <span className={`mchip ${ep?.messenger === 'max' ? 'max' : 'tg'}`}>{ep?.messenger === 'max' ? 'MAX' : 'TG'} · {ep?.title || ep?.sourceId}</span>
}

export default function Rules() {
  const [q, setQ] = useState('')
  const [status, setStatus] = useState('')
  const [data, setData] = useState(null)
  const [offset, setOffset] = useState(0)
  const [tick, setTick] = useState(0)
  const [sel, setSel] = useState(null)
  useEffect(() => {
    let alive = true
    const t = setTimeout(() => {
      api.rules({ q, status, limit: PAGE, offset })
        .then((r) => { if (!alive) return; setData((prev) => (offset && prev) ? { ...r, items: [...prev.items, ...r.items] } : r) })
        .catch(() => { if (alive) setData((prev) => (offset && prev) ? prev : { items: [], total: 0, stats: {} }) })
    }, offset ? 0 : 250)
    return () => { alive = false; clearTimeout(t) }
  }, [q, status, offset, tick])
  const pick = (v) => { setStatus(v); setOffset(0) }
  const onSearch = (e) => { setQ(e.target.value); setOffset(0) }
  const reload = () => { setOffset(0); setTick((t) => t + 1) }

  const st = data?.stats || {}
  const filters = [['', 'Все'], ['active', 'Активные'], ['paused', 'На паузе'], ['broken', 'Сбойные']]
  return (
    <>
      <div className="view-head">
        <div><div className="lbl eyebrow">Правила синхронизации всех аккаунтов</div><h1>Правила</h1></div>
      </div>

      <div className="chips" style={{ marginBottom: 12 }}>
        <span className="mchip plain">всего {st.total ?? '—'}</span>
        <span className="pill ok dot">активных {st.active ?? 0}</span>
        <span className="pill na dot">на паузе {st.paused ?? 0}</span>
        <span className="pill violation dot">сбойных {st.broken ?? 0}</span>
      </div>

      <div className="spread" style={{ marginBottom: 12, gap: 10, flexWrap: 'wrap' }}>
        <input className="search-inp" style={{ flex: 1, minWidth: 220 }} placeholder="Поиск: id правила, телефон аккаунта…"
          value={q} onChange={onSearch} />
        <div className="seg">
          {filters.map(([v, l]) => <button key={v} className={status === v ? 'on' : ''} onClick={() => pick(v)}>{l}</button>)}
        </div>
      </div>

      <div className="card"><div className="twrap"><table className="t">
        <thead><tr><th>Правило</th><th>Аккаунт</th><th>Направление</th><th>Статус</th></tr></thead>
        <tbody>
          {(data?.items || []).map((r) => (
            <tr key={r.id} className="clickable" onClick={() => setSel(r.id)}>
              <td><div className="chips"><Chip ep={r.a} /><Chip ep={r.b} /></div></td>
              <td><span className="id">{r.account_id}</span>{r.phone ? <div className="muted mono" style={{ fontSize: 11.5 }}>+{r.phone}</div> : null}</td>
              <td className="mono muted">{DIR[r.dir] || r.dir}</td>
              <td>
                <span className={`pill ${ST[r.status] || 'na'} dot`}>{ST_RU[r.status] || r.status}</span>
                {r.moderationHold ? <span className="pill unsure dot" style={{ marginLeft: 6 }}>hold</span> : null}
                {r.reportMuted ? <span className="pill na dot" style={{ marginLeft: 6 }}>mute</span> : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table></div></div>
      {data && data.items.length === 0 && <div className="card pad muted" style={{ marginTop: 12 }}>Правил не найдено.</div>}
      {data && data.total > data.items.length && (
        <div className="row-flex" style={{ marginTop: 10, gap: 10 }}>
          <button className="btn sm" onClick={() => setOffset(data.items.length)}>Показать ещё</button>
          <span className="muted" style={{ fontSize: 12.5 }}>Показаны {data.items.length} из {data.total}.</span>
        </div>
      )}
      {sel && <RuleDrawer id={sel} onClose={() => setSel(null)} onChanged={reload} />}
    </>
  )
}

function RuleDrawer({ id, onClose, onChanged }) {
  const [d, setD] = useState(null)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState(null)
  const load = () => api.rule(id).then(setD).catch(() => onClose())
  useEffect(() => { load() }, [id])
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const act = async (action, close) => {
    setBusy(true); setMsg(null)
    try {
      await api.ruleAction(id, { action })
      onChanged && onChanged()
      if (close) { onClose(); return }
      await load()
      setMsg({ text: 'Готово.', ok: true })
    } catch (e) { setMsg({ text: e.message || 'Не удалось', ok: false }) }
    setBusy(false)
  }

  if (!d) return null
  const r = d.rule || {}
  return (
    <div>
      <div className="scrim" onClick={onClose} />
      <aside className="drawer" role="dialog" aria-label="Правило">
        <div className="drawer-head">
          <span className={`pill ${ST[r.status] || 'na'} dot`}>{ST_RU[r.status] || r.status}</span>
          <span className="id">{r.id}</span>
          <button className="iconbtn" style={{ marginLeft: 'auto' }} onClick={onClose} title="Закрыть">✕</button>
        </div>
        <div className="drawer-body">
          <div className="chips" style={{ marginBottom: 10 }}><Chip ep={r.a} /><Chip ep={r.b} /></div>
          {r.status === 'broken' && r.brokenReason && (
            <div className="note"><span>⚠</span><span>{r.brokenReason}</span></div>
          )}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginTop: 8 }}>
            <div className="kv"><span className="k">Направление</span><span className="v">{DIR[r.dir] || r.dir}</span></div>
            <div className="kv"><span className="k">Аккаунт</span><span className="v mono" style={{ fontSize: 12.5 }}>{r.account_id}{r.phone ? ` · +${r.phone}` : ''}</span></div>
            <div className="kv"><span className="k">Модерация</span><span className="v">{r.moderationHold ? 'на паузе (hold)' : 'обычная'}</span></div>
            <div className="kv"><span className="k">Жалобы</span><span className="v">{r.reportMuted ? 'заглушены' : 'принимаются'}</span></div>
          </div>
          {r.deliveryWarn && <div className="note" style={{ marginTop: 10 }}><span>ℹ</span><span>Есть предупреждение о сбое доставки.</span></div>}
          {msg && <div className={`form-note ${msg.ok ? 'ok' : 'err'}`} style={{ marginTop: 10 }}>{msg.text}</div>}
        </div>
        <div className="drawer-foot">
          {r.status === 'paused'
            ? <button className="btn" disabled={busy} onClick={() => act('resume')}><Play size={15} />Возобновить</button>
            : <button className="btn" disabled={busy} onClick={() => act('pause')}><Pause size={15} />Поставить на паузу</button>}
          {r.moderationHold
            ? <button className="btn" disabled={busy} onClick={() => act('unhold_rule')}><ShieldCheck size={15} />Снять hold</button>
            : <button className="btn" disabled={busy} onClick={() => act('hold_rule')}><ShieldAlert size={15} />Hold (модерация)</button>}
          {r.reportMuted
            ? <button className="btn" disabled={busy} onClick={() => act('unmute_rule')}><Bell size={15} />Вернуть жалобы</button>
            : <button className="btn" disabled={busy} onClick={() => act('mute_rule')}><BellOff size={15} />Заглушить жалобы</button>}
          {r.deliveryWarn && <button className="btn" disabled={busy} onClick={() => act('dismiss_warning')}><EyeOff size={15} />Скрыть предупреждение</button>}
          <button className="btn danger" style={{ gridColumn: '1 / -1' }} disabled={busy} onClick={() => act('delete', true)}><Trash2 size={15} />Удалить правило</button>
        </div>
      </aside>
    </div>
  )
}
