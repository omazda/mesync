import React, { useEffect, useMemo, useState } from 'react'
import { api } from '../api.js'
import { Copy, RefreshCcw, Plus, Check, AlertCircle, Ban } from 'lucide-react'

function fmtTs(sec) {
  if (!sec) return '—'
  try { return new Date(Number(sec) * 1000).toLocaleString('ru-RU') } catch (_) { return '—' }
}

function sortCodes(codes) {
  return [...(codes || [])].sort((a, b) => String(a).localeCompare(String(b)))
}

function textForCodes(codes) {
  return sortCodes(codes).join('\n')
}

async function copyText(text) {
  if (!text) return false
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch (_) {
    return false
  }
}

export default function ActivationCodes() {
  const [count, setCount] = useState(10)
  const [generated, setGenerated] = useState([])
  const [stats, setStats] = useState(null)
  const [filter, setFilter] = useState('unused')
  const [busy, setBusy] = useState(false)
  const [revoking, setRevoking] = useState('')
  const [err, setErr] = useState('')
  const [copied, setCopied] = useState('')
  const [notice, setNotice] = useState('')
  const [tick, setTick] = useState(0)

  const load = () => api.listCodes()
    .then((r) => { setStats(r); setErr('') })
    .catch((e) => setErr(e.message || 'Не удалось загрузить коды.'))

  useEffect(() => { load() }, [tick])

  const gen = async () => {
    setBusy(true); setErr(''); setGenerated([]); setCopied(''); setNotice('')
    try {
      const n = Math.max(1, Math.min(1000, parseInt(count, 10) || 1))
      const r = await api.genCodes(n)
      setGenerated(r.codes || [])
      setCount(n)
      setTick((t) => t + 1)
    } catch (e) {
      setErr(e.message || 'Не удалось сгенерировать коды.')
    }
    setBusy(false)
  }

  const unused = useMemo(() => sortCodes(stats?.unused), [stats])
  const used = stats?.used || []
  const expired = stats?.expired || []
  const revoked = stats?.revoked || []
  const shown = filter === 'used' ? used : filter === 'expired' ? expired : filter === 'revoked' ? revoked : unused
  const totals = {
    unused: unused.length,
    used: used.length,
    expired: expired.length,
    revoked: revoked.length,
    total: stats?.total ?? 0,
  }

  const doCopy = async (kind, text) => {
    const ok = await copyText(text)
    setNotice('')
    setCopied(ok ? kind : 'fail')
    window.setTimeout(() => setCopied(''), 1800)
  }

  const revoke = async (code) => {
    if (!window.confirm(`Аннулировать код ${code}? Активировать его после этого будет нельзя.`)) return
    setRevoking(code); setErr(''); setCopied(''); setNotice('')
    try {
      await api.revokeCode(code)
      setGenerated((prev) => prev.filter((c) => c !== code))
      setNotice(`Код ${code} аннулирован.`)
      setTick((t) => t + 1)
    } catch (e) {
      setErr(e.message || 'Не удалось аннулировать код.')
    }
    setRevoking('')
  }

  return (
    <>
      <div className="view-head">
        <div>
          <div className="lbl eyebrow">Активация Smart</div>
          <h1>Коды активации</h1>
          <p>Одноразовые коды действуют 30 дней с генерации и добавляют календарный месяц Smart без привязки карты.</p>
        </div>
        <div className="head-actions row-flex" style={{ gap: 8 }}>
          <button className="btn sm" onClick={() => setTick((t) => t + 1)}><RefreshCcw size={15} />Обновить</button>
        </div>
      </div>

      {err && <div className="form-note err" style={{ marginBottom: 12 }}><AlertCircle size={15} /><span>{err}</span></div>}
      {copied === 'fail' && <div className="form-note err" style={{ marginBottom: 12 }}><span>Не удалось скопировать в буфер обмена.</span></div>}
      {copied && copied !== 'fail' && <div className="form-note ok" style={{ marginBottom: 12 }}><Check size={15} /><span>Скопировано.</span></div>}
      {notice && <div className="form-note ok" style={{ marginBottom: 12 }}><Check size={15} /><span>{notice}</span></div>}

      <div className="grid cols-2" style={{ alignItems: 'start' }}>
        <div className="stack">
          <div className="card pad">
            <div className="sec-title"><h3>Генерация</h3><span className="lbl">до 1000 за раз</span></div>
            <div className="row-flex" style={{ gap: 8, flexWrap: 'wrap' }}>
              <input className="inp" style={{ width: 88 }} type="number" min={1} max={1000}
                value={count} onChange={(e) => setCount(e.target.value)} />
              <button className="btn sm primary" disabled={busy} onClick={gen}><Plus size={15} />{busy ? 'Генерируем…' : 'Сгенерировать'}</button>
              <button className="btn sm" disabled={!generated.length}
                onClick={() => doCopy('generated', textForCodes(generated))}><Copy size={15} />Скопировать новые</button>
            </div>
            {generated.length > 0 && (
              <div className="code-scroll code-scroll-generated" style={{ marginTop: 14 }}>
                <div className="code-grid">
                {sortCodes(generated).map((c) => (
                  <button key={c} className="code-chip" onClick={() => doCopy(c, c)} title="Скопировать код">
                    <span>{c}</span><Copy size={13} />
                  </button>
                ))}
                </div>
              </div>
            )}
          </div>

          <div className="tiles">
            <div className="stat card"><div className="n">{totals.unused}</div><div className="k">Свободные</div></div>
            <div className="stat card"><div className="n">{totals.used}</div><div className="k">Использованные</div></div>
            <div className="stat card"><div className="n">{totals.expired}</div><div className="k">Истёкшие</div></div>
            <div className="stat card"><div className="n">{totals.revoked}</div><div className="k">Аннулированные</div></div>
            <div className="stat card"><div className="n">{totals.total}</div><div className="k">Всего</div></div>
          </div>
        </div>

        <div className="card pad">
          <div className="sec-title">
            <h3>Реестр</h3>
            <button className="btn sm" disabled={!unused.length} onClick={() => doCopy('unused', textForCodes(unused))}>
              <Copy size={15} />Свободные
            </button>
          </div>
          <div className="seg" style={{ marginBottom: 12 }}>
            <button className={filter === 'unused' ? 'on' : ''} onClick={() => setFilter('unused')}>Свободные · {totals.unused}</button>
            <button className={filter === 'used' ? 'on' : ''} onClick={() => setFilter('used')}>Использованные · {totals.used}</button>
            <button className={filter === 'expired' ? 'on' : ''} onClick={() => setFilter('expired')}>Истёкшие · {totals.expired}</button>
            <button className={filter === 'revoked' ? 'on' : ''} onClick={() => setFilter('revoked')}>Аннулированные · {totals.revoked}</button>
          </div>
          <div className="code-scroll code-scroll-registry">
            {filter === 'unused'
              ? <UnusedTable codes={shown} onCopy={doCopy} onRevoke={revoke} revoking={revoking} />
              : <EventTable rows={shown} kind={filter} onCopy={doCopy} />}
          </div>
        </div>
      </div>
    </>
  )
}

function UnusedTable({ codes, onCopy, onRevoke, revoking }) {
  if (!codes.length) return <div className="muted" style={{ fontSize: 13 }}>Свободных кодов нет.</div>
  return (
    <div className="twrap"><table className="t">
      <thead><tr><th>Код</th><th style={{ width: 1 }}>Действия</th></tr></thead>
      <tbody>
        {codes.map((code) => (
          <tr key={code}>
            <td><span className="code-line">{code}</span></td>
            <td>
              <div className="row-flex" style={{ gap: 6 }}>
                <button className="iconbtn" onClick={() => onCopy(code, code)} title="Скопировать"><Copy size={14} /></button>
                <button className="iconbtn danger-icon" disabled={revoking === code} onClick={() => onRevoke(code)} title="Аннулировать"><Ban size={14} /></button>
              </div>
            </td>
          </tr>
        ))}
      </tbody>
    </table></div>
  )
}

function EventTable({ rows, kind, onCopy }) {
  if (!rows.length) return <div className="muted" style={{ fontSize: 13 }}>{kind === 'used' ? 'Использованных кодов нет.' : kind === 'revoked' ? 'Аннулированных кодов нет.' : 'Истёкших кодов нет.'}</div>
  return (
    <div className="twrap"><table className="t">
      <thead>
        <tr><th>Код</th><th>{kind === 'used' ? 'Аккаунт' : 'Создан'}</th><th>{kind === 'used' ? 'Активирован' : kind === 'revoked' ? 'Аннулирован' : 'Истёк'}</th><th style={{ width: 1 }}>Действие</th></tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.code}>
            <td><span className="code-line">{r.code}</span></td>
            <td className="mono muted">{kind === 'used' ? (r.used_by || '—') : fmtTs(r.created_at)}</td>
            <td className="mono muted">{fmtTs(kind === 'used' ? r.used_at : kind === 'revoked' ? r.revoked_at : r.expires_at)}</td>
            <td><button className="iconbtn" onClick={() => onCopy(r.code, r.code)} title="Скопировать"><Copy size={14} /></button></td>
          </tr>
        ))}
      </tbody>
    </table></div>
  )
}
