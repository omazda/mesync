import React, { useEffect, useState } from 'react'
import { api } from '../api.js'
import { Trash2, Pause, Ban, BellOff, Check, RefreshCw } from 'lucide-react'
import ModerationSettingsPanel from '../components/ModerationSettingsPanel.jsx'

function fmt(ts) {
  try { return new Date(ts).toLocaleString('ru-RU', { hour12: false }) } catch (_) { return String(ts) }
}
const CLS = { violation: 'violation', unsure: 'unsure', ok: 'ok' }
function pillCls(v) { return CLS[v] || 'na' }
function Pill({ v }) { return <span className={`pill ${pillCls(v)} dot`}>{v || '—'}</span> }

export default function Moderation() {
  const [tab, setTab] = useState('queue')
  const tabs = { queue: 'Очередь', modes: 'Режимы', stoplist: 'Стоп-словарь' }
  return (
    <>
      <div className="view-head">
        <div><div className="lbl eyebrow">Жалобы и стоп-словарь</div><h1>Модерация</h1></div>
        <div className="seg">
          {Object.entries(tabs).map(([t, l]) => (
            <button key={t} className={tab === t ? 'on' : ''} onClick={() => setTab(t)}>{l}</button>
          ))}
        </div>
      </div>
      {tab === 'queue' && <Queue />}
      {tab === 'modes' && <Modes />}
      {tab === 'stoplist' && <Stoplist />}
    </>
  )
}

/* ---------------- очередь жалоб ---------------- */
function Queue() {
  const [filter, setFilter] = useState('')
  const [data, setData] = useState(null)
  const [sel, setSel] = useState(null)
  const load = () => api.modReports({ verdict: filter, limit: 100 })
    .then(setData).catch(() => setData({ items: [], total: 0 }))
  useEffect(() => { load() }, [filter])

  const filters = [['', 'Все'], ['violation', 'Нарушения'], ['unsure', 'Не ясно'], ['ok', 'Ок']]
  return (
    <>
      <div className="spread" style={{ marginBottom: 14 }}>
        <div className="seg">
          {filters.map(([v, l]) => (
            <button key={v} className={filter === v ? 'on' : ''} onClick={() => setFilter(v)}>{l}</button>
          ))}
        </div>
        <button className="btn sm" onClick={load}>Обновить</button>
      </div>
      <div className="card"><div className="twrap"><table className="t">
        <thead><tr><th>Жалоба</th><th>Вердикт</th><th>Категория</th><th>Правило</th><th>Аккаунт</th><th>Когда</th></tr></thead>
        <tbody>
          {(data?.items || []).map((r) => (
            <tr key={r.id} className="clickable" onClick={() => setSel(r.id)}>
              <td>
                <span className="id">{r.id}</span>
                <div className="faint" style={{ fontSize: 11.5 }}>{r.reporter || '—'}</div>
                {r.review_required && <div className="faint" style={{ fontSize: 11.5, color: 'var(--warn)' }}>ручная проверка</div>}
              </td>
              <td><Pill v={r.verdict} /></td>
              <td><span className="cat">{r.category || '—'}</span></td>
              <td className="id">{r.rule_id || '—'}</td>
              <td className="id">{r.account_id || '—'}</td>
              <td className="muted mono" style={{ whiteSpace: 'nowrap' }}>{fmt(r.ts)}</td>
            </tr>
          ))}
        </tbody>
      </table></div></div>
      {data && data.items.length === 0 && <div className="card pad muted" style={{ marginTop: 12 }}>Жалоб нет.</div>}
      {data && data.total > data.items.length && (
        <div className="muted" style={{ marginTop: 10, fontSize: 12.5 }}>Показаны {data.items.length} из {data.total}.</div>
      )}
      {sel && <ReportDrawer id={sel} onClose={() => setSel(null)} onChanged={load} />}
    </>
  )
}

function ReportDrawer({ id, onClose, onChanged }) {
  const [rec, setRec] = useState(null)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState(null)
  const load = () => api.modReport(id).then((r) => setRec(r.report)).catch(() => onClose())
  useEffect(() => { load() }, [id])
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const act = async (action, extra) => {
    setBusy(true); setMsg(null)
    try {
      const r = await api.modAction(id, { action, ...(extra || {}) })
      if (r.report) setRec(r.report)
      if ('hidden' in r) setMsg(`Скрыто копий: ${r.hidden}`)
      else if ('deleted' in r) setMsg(`Скрыто копий: ${r.deleted}`)
      else if (r.verdict) setMsg('Переклассифицировано')
      else setMsg('Готово')
      onChanged && onChanged()
    } catch (e) { setMsg(e.message || 'Не удалось') }
    setBusy(false)
  }

  if (!rec) return null
  return (
    <div>
      <div className="scrim" onClick={onClose} />
      <aside className="drawer" role="dialog" aria-label="Жалоба">
        <div className="drawer-head">
          <Pill v={rec.verdict} />
          <span className="id">{rec.id}</span>
          <button className="iconbtn" style={{ marginLeft: 'auto' }} onClick={onClose} title="Закрыть">✕</button>
        </div>
        <div className="drawer-body">
          <div className={`verdict-box ${pillCls(rec.verdict)}`}>
            <div>
              <div className="lbl">Вердикт ИИ</div>
              <div style={{ fontSize: 15, fontWeight: 700 }}>{rec.verdict || '—'}{rec.category ? ` · ${rec.category}` : ''}</div>
            </div>
          </div>
          {rec.reason && <div className="field-block"><span className="lbl">Причина</span><div style={{ fontSize: 13 }}>{rec.reason}</div></div>}
          {rec.review_required && (
            <div className="note">
              <span>!</span>
              <span>Нужна ручная проверка{rec.review_reason ? `: ${rec.review_reason}` : ''}</span>
            </div>
          )}
          {rec.has_media && <div className="note"><span>↗</span><span>В сообщении есть медиа или вложения.</span></div>}
          {rec.description && <div className="field-block"><span className="lbl">Комментарий жалобщика</span><div style={{ fontSize: 13 }} className="muted">{rec.description}</div></div>}
          <div className="divider" />
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
            <div className="kv"><span className="k">Источник</span><span className="v mono" style={{ fontSize: 12.5 }}>{rec.src_messenger}:{rec.src_chat}</span></div>
            <div className="kv"><span className="k">Правило</span><span className="v mono" style={{ fontSize: 12.5 }}>{rec.rule_id || '—'}</span></div>
            <div className="kv"><span className="k">Аккаунт</span><span className="v mono" style={{ fontSize: 12.5 }}>{rec.account_id || '—'}</span></div>
            <div className="kv"><span className="k">Повторов</span><span className="v mono">{rec.repeat_count || 0}</span></div>
          </div>
          {rec.reviewed && <div className="note"><span>✓</span><span>Жалоба просмотрена оператором.</span></div>}
          {msg && <div className="note"><span>ℹ</span><span>{msg}</span></div>}
        </div>
        <div className="drawer-foot">
          <button className="btn danger" disabled={busy} onClick={() => act('hide_copies')}><Trash2 size={15} />Скрыть копии</button>
          <button className="btn" disabled={busy} onClick={() => act('hold_rule')}><Pause size={15} />Пауза правила</button>
          <button className="btn danger" disabled={busy} onClick={() => act('block_account')}><Ban size={15} />Блок аккаунта</button>
          <button className="btn" disabled={busy} onClick={() => act('mute_rule')}><BellOff size={15} />Мьют жалоб</button>
          <button className="btn" disabled={busy} onClick={() => act('reclassify')}><RefreshCw size={15} />Переклассифицировать</button>
          <button className="btn" disabled={busy} onClick={() => act('override', { verdict: 'violation' })}>Пометить нарушением</button>
          <button className="btn ghost" style={{ gridColumn: '1 / -1' }} disabled={busy}
            onClick={() => act('override', { verdict: 'ok' })}><Check size={15} />Отклонить — контент допустим</button>
        </div>
      </aside>
    </div>
  )
}

/* ---------------- режимы + тест-классификатор ---------------- */
function Modes() {
  const [s, setS] = useState(null)
  const [loadErr, setLoadErr] = useState(null)
  const [putErr, setPutErr] = useState(null)
  useEffect(() => { api.getSettings().then((r) => setS(r.settings)).catch((e) => setLoadErr(e.message)) }, [])
  const put = async (patch) => {
    const prev = s
    setS({ ...s, ...patch }); setPutErr(null)   // оптимистично; ошибка PUT — инлайн-баннер, панель не падает
    try { const r = await api.putSettings(patch); setS(r.settings) } catch (e) { setS(prev); setPutErr(e.message) }
  }
  if (loadErr) return <div className="form-err">{loadErr}</div>
  if (!s) return <div className="muted">Загрузка…</div>
  return (
    <>
      {putErr && <div className="form-err" style={{ marginBottom: 12 }}>{putErr}</div>}
      <ModerationSettingsPanel settings={s} onPatch={put} />
      <div className="card pad" style={{ maxWidth: 760, marginTop: 14 }}>
        <div className="sec-title"><h3>Автодействия</h3><span className="lbl">применяется сразу</span></div>
        <div className="set-row">
          <div className="info"><div className="t">Автопауза правила по страйкам</div><div className="d">Порог подтверждённых нарушений за 24 ч, после которого правило встаёт на паузу.</div></div>
          <input className="inp" style={{ width: 64 }} type="number" min={1} max={100}
            defaultValue={s.moderation_autopause_strikes}
            onBlur={(e) => {
              let v = parseInt(e.target.value, 10)
              if (Number.isNaN(v)) { e.target.value = s.moderation_autopause_strikes; return }
              v = Math.max(1, Math.min(100, v)); e.target.value = v
              if (v !== s.moderation_autopause_strikes) put({ moderation_autopause_strikes: v })
            }} />
        </div>
      </div>
      <ClassifyTest />
    </>
  )
}

function ClassifyTest() {
  const [text, setText] = useState('')
  const [res, setRes] = useState(null)
  const [busy, setBusy] = useState(false)
  const run = async () => {
    setBusy(true); setRes(null)
    try { setRes(await api.modClassify(text)) } catch (e) { setRes({ error: e.message }) }
    setBusy(false)
  }
  const v = res && res.verdict
  return (
    <div className="card pad" style={{ maxWidth: 760, marginTop: 14 }}>
      <div className="sec-title"><h3>Проверить классификатор</h3><span className="lbl">MiniMax · тест</span></div>
      <textarea className="ta" rows={3} placeholder="Вставьте текст — увидите стоп-хиты и вердикт ИИ…"
        value={text} onChange={(e) => setText(e.target.value)} />
      <div className="spread" style={{ marginTop: 10, flexWrap: 'wrap', gap: 8 }}>
        <div className="row-flex" style={{ flexWrap: 'wrap', gap: 6 }}>
          {res && res.hits && res.hits.length > 0 && res.hits.map((h) => <span key={h} className="pill violation dot">{h}</span>)}
          {res && res.hits && res.hits.length === 0 && <span className="muted" style={{ fontSize: 12.5 }}>стоп-хитов нет</span>}
          {v && <span className={`pill ${pillCls(v.verdict)} dot`}>вердикт: {v.verdict}{v.category ? ` · ${v.category}` : ''}</span>}
          {res && res.error && <span className="form-err">{res.error}</span>}
          {res && res.verdict === null && !res.error && <span className="muted" style={{ fontSize: 12.5 }}>ИИ не вызывался (пусто/выключен)</span>}
        </div>
        <button className="btn sm primary" disabled={busy || !text.trim()} onClick={run}>{busy ? 'Проверяем…' : 'Проверить'}</button>
      </div>
    </div>
  )
}

/* ---------------- редактор стоп-словаря ---------------- */
function Stoplist() {
  const [text, setText] = useState(null)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState(null)
  const [err, setErr] = useState(null)
  useEffect(() => { api.getStoplist().then((r) => setText(r.text || '')).catch((e) => setErr(e.message)) }, [])
  const save = async () => {
    setBusy(true); setMsg(null); setErr(null)
    try { await api.putStoplist(text); setMsg('Сохранено. Матчер перечитает словарь автоматически.') }
    catch (e) { setErr(e.message) }
    setBusy(false)
  }
  if (text === null && !err) return <div className="muted">Загрузка…</div>
  return (
    <div className="card pad" style={{ maxWidth: 900 }}>
      <div className="sec-title"><h3>Стоп-словарь</h3><span className="lbl">YAML · горячая перезагрузка</span></div>
      <p className="muted" style={{ fontSize: 12.5, marginBottom: 10 }}>
        Категории drugs/weapons/extremism/violence/fraud/war/profanity · terms/words/spaced/phrases.
        Словарь — триггер для ИИ, не блок-лист.
      </p>
      <textarea className="ta code" rows={20} value={text || ''} onChange={(e) => setText(e.target.value)} spellCheck={false} />
      {err && <div className="form-err">{err}</div>}
      {msg && <div className="note" style={{ marginTop: 10 }}><span>✓</span><span>{msg}</span></div>}
      <div style={{ marginTop: 12, display: 'flex', justifyContent: 'flex-end' }}>
        <button className="btn primary" disabled={busy || !text || !text.trim()} onClick={save}>{busy ? 'Сохраняем…' : 'Сохранить словарь'}</button>
      </div>
    </div>
  )
}
