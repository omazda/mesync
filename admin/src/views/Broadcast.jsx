import React, { useEffect, useState } from 'react'
import { api } from '../api.js'
import { Send, Ban } from 'lucide-react'

const AUD = [['all', 'Все пользователи'], ['active', 'С активной подпиской'], ['trial', 'На триале']]
const MSG = [['both', 'MAX и Telegram'], ['max', 'Только MAX'], ['tg', 'Только Telegram']]
const ST = { pending: ['unsure', 'в очереди'], running: ['unsure', 'идёт'], done: ['ok', 'завершена'], canceled: ['na', 'отменена'], failed: ['violation', 'сбой'] }
function fmt(ts) { if (!ts) return '—'; try { return new Date(ts * 1000).toLocaleString('ru-RU', { hour12: false }) } catch (_) { return String(ts) } }
const ACTIVE = (b) => b && (b.status === 'pending' || b.status === 'running')

export default function Broadcast() {
  const [text, setText] = useState('')
  const [audience, setAudience] = useState('all')
  const [messenger, setMessenger] = useState('both')
  const [count, setCount] = useState(null)
  const [confirm, setConfirm] = useState(false)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState(null)
  const [list, setList] = useState(null)

  // Живой счётчик адресатов (дебаунс) при смене аудитории/мессенджера.
  useEffect(() => {
    let alive = true
    setCount(null)
    const t = setTimeout(() => {
      api.broadcastPreview({ audience, messenger }).then((r) => { if (alive) setCount(r.count) }).catch(() => {})
    }, 250)
    return () => { alive = false; clearTimeout(t) }
  }, [audience, messenger])

  // История + поллинг прогресса, пока есть активная рассылка.
  const loadList = () => api.broadcasts({ limit: 50 }).then((r) => setList(r.items || [])).catch(() => setList([]))
  useEffect(() => { loadList() }, [])
  useEffect(() => {
    const running = (list || []).some(ACTIVE)
    if (!running) return
    const id = setInterval(loadList, 3000)
    return () => clearInterval(id)
  }, [list])

  const active = (list || []).find(ACTIVE)

  const send = async () => {
    setBusy(true); setMsg(null)
    try {
      await api.createBroadcast({ text: text.trim(), audience, messenger, confirm: true })
      setConfirm(false); setText(''); setMsg({ text: 'Рассылка запущена.', ok: true })
      loadList()
    } catch (e) { setConfirm(false); setMsg({ text: e.message || 'Не удалось', ok: false }) }
    setBusy(false)
  }
  const cancel = async (id) => { try { await api.cancelBroadcast(id) } catch (_) {} loadList() }

  const canSend = text.trim() && count > 0 && !active
  return (
    <>
      <div className="view-head">
        <div><div className="lbl eyebrow">Управление</div><h1>Рассылки</h1>
          <p>Сообщение уходит в <b>личный чат с ботом</b> каждому пользователю. В источники, каналы и группы — не отправляется. Отменить уже отправленное нельзя.</p>
        </div>
      </div>

      {msg && <div className={`form-note ${msg.ok ? 'ok' : 'err'}`} style={{ marginBottom: 12 }}>{msg.text}</div>}
      {active && <ProgressCard b={active} onCancel={cancel} />}

      <div className="card pad" style={{ maxWidth: 760 }}>
        <div className="sec-title"><h3>Новая рассылка</h3>
          <span className="lbl">{count == null ? 'считаем…' : `${count} адресатов`}</span>
        </div>
        <textarea className="ta" rows={5} placeholder="Текст сообщения пользователям…"
          value={text} onChange={(e) => setText(e.target.value)} />
        <div className="set-row" style={{ marginTop: 12 }}>
          <div className="info"><div className="t">Аудитория</div><div className="d">Заблокированные аккаунты исключаются автоматически.</div></div>
          <div className="seg">{AUD.map(([v, l]) => <button key={v} className={audience === v ? 'on' : ''} onClick={() => setAudience(v)}>{l}</button>)}</div>
        </div>
        <div className="set-row">
          <div className="info"><div className="t">Куда доставлять</div><div className="d">Личный чат пользователя в выбранных мессенджерах.</div></div>
          <div className="seg">{MSG.map(([v, l]) => <button key={v} className={messenger === v ? 'on' : ''} onClick={() => setMessenger(v)}>{l}</button>)}</div>
        </div>
        {active && <div className="note" style={{ marginTop: 10 }}><span>⏳</span><span>Дождитесь завершения текущей рассылки.</span></div>}
        <div style={{ marginTop: 14, display: 'flex', justifyContent: 'flex-end' }}>
          <button className="btn primary" disabled={!canSend || busy} onClick={() => setConfirm(true)}><Send size={15} />Отправить</button>
        </div>
      </div>

      <History items={(list || []).filter((b) => !ACTIVE(b))} />

      {confirm && (
        <div>
          <div className="scrim" onClick={() => setConfirm(false)} />
          <aside className="drawer" role="dialog" aria-label="Подтверждение рассылки">
            <div className="drawer-head"><b>Подтвердите рассылку</b>
              <button className="iconbtn" style={{ marginLeft: 'auto' }} onClick={() => setConfirm(false)} title="Закрыть">✕</button>
            </div>
            <div className="drawer-body">
              <div className="warnbox"><span>⚠</span><span>Сообщение уйдёт <b>{count} адресатам</b> в личные чаты с ботом. Действие <b>необратимо</b> — отправленное вернуть нельзя.</span></div>
              <div className="field-block" style={{ marginTop: 12 }}><span className="lbl">Текст</span>
                <div style={{ fontSize: 13, whiteSpace: 'pre-wrap' }}>{text.trim()}</div>
              </div>
            </div>
            <div className="drawer-foot">
              <button className="btn" disabled={busy} onClick={() => setConfirm(false)}>Отмена</button>
              <button className="btn danger" disabled={busy} onClick={send}><Send size={15} />Отправить {count} адресатам</button>
            </div>
          </aside>
        </div>
      )}
    </>
  )
}

function ProgressCard({ b, onCancel }) {
  const done = (b.sent || 0) + (b.failed || 0)
  const pct = b.total ? Math.round(done / b.total * 100) : 0
  return (
    <div className="card pad" style={{ marginBottom: 14, maxWidth: 760 }}>
      <div className="sec-title"><h3>Идёт рассылка</h3>
        <button className="btn sm danger" onClick={() => onCancel(b.id)}><Ban size={14} />Остановить</button>
      </div>
      <div className="spread" style={{ marginBottom: 6 }}>
        <span className="mono" style={{ fontWeight: 700 }}>{done} / {b.total}</span>
        <span className="muted mono" style={{ fontSize: 12.5 }}>доставлено {b.sent || 0} · ошибок {b.failed || 0}</span>
      </div>
      <div className={`meter${pct >= 100 ? '' : ' warn'}`}><i style={{ width: pct + '%' }} /></div>
    </div>
  )
}

function History({ items }) {
  if (!items || items.length === 0) return null
  return (
    <div className="card" style={{ marginTop: 16 }}><div className="twrap"><table className="t">
      <thead><tr><th>Когда</th><th>Аудитория</th><th>Доставлено</th><th>Статус</th></tr></thead>
      <tbody>
        {items.map((b) => {
          const [cls, label] = ST[b.status] || ['na', b.status]
          return (
            <tr key={b.id}>
              <td className="muted mono" style={{ fontSize: 12 }}>{fmt(b.created_at)}</td>
              <td>{(AUD.find((a) => a[0] === b.audience) || [null, b.audience])[1]} · {(MSG.find((m) => m[0] === b.messenger) || [null, b.messenger])[1]}</td>
              <td className="mono">{b.sent || 0}<span className="faint"> / {b.total || 0}</span>{b.failed ? <span style={{ color: 'var(--bad)' }}> ({b.failed} ош.)</span> : null}</td>
              <td><span className={`pill ${cls} dot`}>{label}</span></td>
            </tr>
          )
        })}
      </tbody>
    </table></div></div>
  )
}
