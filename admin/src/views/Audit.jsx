import React, { useEffect, useState } from 'react'
import { api } from '../api.js'

function fmt(ts) {
  try { return new Date(ts).toLocaleString('ru-RU', { hour12: false }) } catch (_) { return String(ts) }
}
function describe(rec) {
  const d = rec.details
  if (rec.action === 'settings' && d && typeof d === 'object') {
    return Object.entries(d).map(([k, v]) => `${k}: ${JSON.stringify(v.from)} → ${JSON.stringify(v.to)}`).join('; ')
  }
  return d ? (typeof d === 'string' ? d : JSON.stringify(d)) : '—'
}
const ACTION = {
  settings: 'Изменены настройки',
  'database:backup': 'Скачана резервная копия',
  'database:restore': 'Установлена резервная копия',
}

export default function Audit() {
  const [items, setItems] = useState(null)
  const [err, setErr] = useState(null)

  useEffect(() => {
    api.getAudit().then((r) => setItems(r.items || [])).catch((e) => setErr(e.message))
  }, [])

  return (
    <>
      <div className="view-head">
        <div>
          <div className="lbl eyebrow">Журнал действий</div>
          <h1>Аудит</h1>
          <p>Каждое действие администратора фиксируется: что, когда, детали и адрес.</p>
        </div>
      </div>

      {err && <div className="form-err">{err}</div>}
      {items === null && !err && <div className="muted">Загрузка…</div>}
      {items && items.length === 0 && <div className="card pad muted">Пока нет записей.</div>}

      {items && items.length > 0 && (
        <div className="card"><div className="twrap"><table className="t">
          <thead><tr><th>Время</th><th>Действие</th><th>Детали</th><th>IP</th></tr></thead>
          <tbody>
            {items.map((r) => (
              <tr key={r.id}>
                <td className="mono muted" style={{ whiteSpace: 'nowrap' }}>{fmt(r.ts)}</td>
                <td><b>{ACTION[r.action] || r.action}</b></td>
                <td className="muted">{describe(r)}</td>
                <td className="mono muted">{r.ip || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table></div></div>
      )}
    </>
  )
}
