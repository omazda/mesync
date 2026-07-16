import React, { useEffect, useState } from 'react'
import { api } from '../api.js'

const PAGE = 100
const ST = { ok: 'ok', err: 'violation', dead: 'na' }
const ST_RU = { ok: 'ok', err: 'нет прав', dead: 'недоступен' }
const TYPE_RU = { channel: 'канал', group: 'группа', topic: 'тема' }

export default function Sources() {
  const [q, setQ] = useState('')
  const [status, setStatus] = useState('')
  const [data, setData] = useState(null)
  const [offset, setOffset] = useState(0)
  useEffect(() => {
    let alive = true
    const t = setTimeout(() => {
      api.sources({ q, status, limit: PAGE, offset })
        .then((r) => { if (!alive) return; setData((prev) => (offset && prev) ? { ...r, items: [...prev.items, ...r.items] } : r) })
        .catch(() => { if (alive) setData((prev) => (offset && prev) ? prev : { items: [], total: 0, counts: {} }) })
    }, offset ? 0 : 250)
    return () => { alive = false; clearTimeout(t) }
  }, [q, status, offset])
  const pick = (v) => { setStatus(v); setOffset(0) }
  const onSearch = (e) => { setQ(e.target.value); setOffset(0) }

  const c = data?.counts || {}
  const filters = [['', 'Все'], ['ok', 'OK'], ['err', 'Нет прав'], ['dead', 'Недоступны']]
  return (
    <>
      <div className="view-head">
        <div><div className="lbl eyebrow">Каналы и группы, подключённые к боту</div><h1>Источники</h1></div>
      </div>

      <div className="chips" style={{ marginBottom: 12 }}>
        <span className="mchip plain">всего {c.total ?? '—'}</span>
        <span className="pill ok dot">ok {c.ok ?? 0}</span>
        <span className="pill violation dot">нет прав {c.err ?? 0}</span>
        <span className="pill na dot">недоступны {c.dead ?? 0}</span>
      </div>

      <div className="spread" style={{ marginBottom: 12, gap: 10, flexWrap: 'wrap' }}>
        <input className="search-inp" style={{ flex: 1, minWidth: 220 }} placeholder="Поиск: название, id источника…"
          value={q} onChange={onSearch} />
        <div className="seg">
          {filters.map(([v, l]) => <button key={v} className={status === v ? 'on' : ''} onClick={() => pick(v)}>{l}</button>)}
        </div>
      </div>

      <div className="card"><div className="twrap"><table className="t">
        <thead><tr><th>Источник</th><th>Тип</th><th>Статус</th><th>Правил</th><th>Аккаунты</th></tr></thead>
        <tbody>
          {(data?.items || []).map((s) => (
            <tr key={s.id}>
              <td>
                <span className={`mchip ${s.messenger === 'max' ? 'max' : 'tg'}`}>{s.messenger === 'max' ? 'MAX' : 'TG'}</span>
                <span style={{ marginLeft: 8 }}>{s.title}</span>
                <div className="faint mono" style={{ fontSize: 11 }}>{s.id}</div>
              </td>
              <td className="muted">{TYPE_RU[s.type] || s.type}{s.isForum ? ' · форум' : ''}</td>
              <td><span className={`pill ${ST[s.status] || 'na'} dot`}>{ST_RU[s.status] || s.status}</span></td>
              <td className="mono">{s.usedInRules}</td>
              <td>
                {(s.accounts || []).length === 0 ? <span className="muted" style={{ fontSize: 12 }}>—</span> : (
                  <div className="chips">
                    {s.accounts.slice(0, 4).map((a) => <span key={a.id} className="mchip plain">{a.phone ? '+' + a.phone : a.id}</span>)}
                    {s.accounts.length > 4 ? <span className="muted" style={{ fontSize: 12 }}>+{s.accounts.length - 4}</span> : null}
                  </div>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table></div></div>
      {data && data.items.length === 0 && <div className="card pad muted" style={{ marginTop: 12 }}>Источников не найдено.</div>}
      {data && data.total > data.items.length && (
        <div className="row-flex" style={{ marginTop: 10, gap: 10 }}>
          <button className="btn sm" onClick={() => setOffset(data.items.length)}>Показать ещё</button>
          <span className="muted" style={{ fontSize: 12.5 }}>Показаны {data.items.length} из {data.total}.</span>
        </div>
      )}
    </>
  )
}
