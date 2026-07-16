import React, { useEffect, useRef, useState } from 'react'
import { AlertTriangle, Check, Download, Upload, X } from 'lucide-react'
import { api } from '../api.js'
import ModerationSettingsPanel from '../components/ModerationSettingsPanel.jsx'

const RESTORE_CONFIRM = 'ВОССТАНОВИТЬ'

function fileSize(bytes) {
  if (bytes < 1024) return `${bytes} Б`
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} КБ`
  return `${(bytes / 1024 ** 2).toFixed(1)} МБ`
}

export default function Settings() {
  const [s, setS] = useState(null)
  const [err, setErr] = useState(null)
  const [busy, setBusy] = useState(false)
  const [backupBusy, setBackupBusy] = useState(false)
  const [backupNotice, setBackupNotice] = useState('')
  const [restoreBusy, setRestoreBusy] = useState(false)
  const [restoreCandidate, setRestoreCandidate] = useState(null)
  const [restoreConfirm, setRestoreConfirm] = useState('')
  const [restoreError, setRestoreError] = useState('')
  const restoreInput = useRef(null)

  const load = () => api.getSettings().then((r) => setS(r.settings)).catch((e) => setErr(e.message))
  useEffect(() => { load() }, [])

  const put = async (patch) => {
    setBusy(true); setErr(null)
    const prev = s
    setS({ ...s, ...patch })                          // оптимистично
    try {
      const r = await api.putSettings(patch)
      setS(r.settings)
    } catch (e) { setS(prev); setErr(e.message) }
    setBusy(false)
  }
  const setPaused = (val) => put({ payments_paused: val })

  const downloadBackup = async () => {
    setBackupBusy(true); setBackupNotice(''); setErr(null)
    try {
      const { blob, filename } = await api.downloadBackup()
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = filename
      document.body.appendChild(link)
      try {
        link.click()
      } finally {
        link.remove()
        window.setTimeout(() => URL.revokeObjectURL(url), 1000)
      }
      setBackupNotice(`Резервная копия ${filename} скачана.`)
    } catch (e) {
      setErr(e.message || 'Не удалось скачать резервную копию.')
    } finally {
      setBackupBusy(false)
    }
  }

  const selectRestore = async (event) => {
    const file = event.target.files && event.target.files[0]
    event.target.value = ''
    if (!file) return
    if (file.size > 50 * 1024 * 1024) {
      setErr('Файл резервной копии превышает допустимые 50 МБ.')
      return
    }
    setRestoreBusy(true); setBackupNotice(''); setErr(null)
    try {
      const result = await api.validateBackup(file)
      setRestoreCandidate({ file, summary: result.summary })
      setRestoreConfirm('')
      setRestoreError('')
    } catch (e) {
      setErr(e.message || 'Не удалось проверить резервную копию.')
    } finally {
      setRestoreBusy(false)
    }
  }

  const installRestore = async () => {
    if (!restoreCandidate || restoreConfirm !== RESTORE_CONFIRM) return
    setRestoreBusy(true); setErr(null); setRestoreError(''); setBackupNotice('')
    try {
      const result = await api.restoreBackup(
        restoreCandidate.file, restoreCandidate.summary.sha256)
      setRestoreCandidate(null)
      setRestoreConfirm('')
      if (result.restartScheduled) {
        setBackupNotice('Бэкап принят. Сервис перезапускается и применяет восстановление…')
        window.setTimeout(() => window.location.reload(), 7000)
      } else {
        setBackupNotice('Бэкап подготовлен. Перезапустите сервис, чтобы применить восстановление.')
      }
    } catch (e) {
      setRestoreError(e.message || 'Не удалось установить резервную копию.')
    } finally {
      setRestoreBusy(false)
    }
  }

  return (
    <>
      <div className="view-head">
        <div>
          <div className="lbl eyebrow">Параметры сервиса</div>
          <h1>Настройки</h1>
          <p>Меняются на лету и применяются мгновенно, без перезапуска. Ключи и пароли задаются на сервере и здесь не показываются.</p>
        </div>
      </div>

      {err && <div className="form-err" style={{ marginBottom: 14 }}>{err}</div>}

      <div className="card pad" style={{ maxWidth: 720 }}>
        <div className="sec-title"><h3>Оплата</h3><span className="lbl">применяется сразу</span></div>
        <div className="set-row">
          <div className="info">
            <div className="t">Приём платежей</div>
            <div className="d">Выключите, чтобы временно приостановить оплату и автопродление (техработы, инцидент у эквайера). Коды активации продолжают работать.</div>
          </div>
          <button className={`toggle${s && !s.payments_paused ? ' on' : ''}`}
                  disabled={!s || busy} aria-pressed={s ? String(!s.payments_paused) : 'false'}
                  onClick={() => setPaused(!s.payments_paused)} title="Приём платежей" />
        </div>
        {s && s.payments_paused && (
          <div className="warnbox" style={{ marginTop: 4 }}>
            <span>⏸</span>
            <span><b>Приём платежей приостановлен.</b> Новые оплаты и автопродления не проводятся; пользователям показывается «оплата временно недоступна».</span>
          </div>
        )}
      </div>

      <div style={{ marginTop: 14 }}>
        <ModerationSettingsPanel settings={s} onPatch={put} busy={busy} />
      </div>

      <div className="card pad" style={{ maxWidth: 720, marginTop: 14 }}>
        <div className="sec-title"><h3>Рассылки</h3><span className="lbl">применяется сразу</span></div>
        <div className="set-row">
          <div className="info">
            <div className="t">Темп рассылки, сообщений/с</div>
            <div className="d">Сколько личных сообщений в секунду отправлять при массовой рассылке. Потолок 30 = лимит MAX API (общий с трафиком моста); меньше — бережнее.</div>
          </div>
          <input className="inp" style={{ width: 64 }} type="number" min={1} max={30}
            disabled={!s || busy}
            defaultValue={s ? s.broadcast_rate_limit : ''} key={s ? s.broadcast_rate_limit : 'x'}
            onBlur={(e) => {
              let v = parseInt(e.target.value, 10)
              if (Number.isNaN(v)) { e.target.value = s.broadcast_rate_limit; return }
              v = Math.max(1, Math.min(30, v)); e.target.value = v
              if (v !== s.broadcast_rate_limit) put({ broadcast_rate_limit: v })
            }} />
        </div>
      </div>

      <div className="card pad" style={{ maxWidth: 720, marginTop: 14 }}>
        <div className="sec-title"><h3>Резервная копия</h3><span className="lbl">хранилище данных</span></div>
        <div className="set-row">
          <div className="info">
            <div className="t">Данные сервиса</div>
            <div className="d">Аккаунты, правила, подписки, коды, трафик и настройки в одном JSON-файле. Секреты из .env и медиа-файлы не включаются.</div>
          </div>
          <div className="row-flex" style={{ flex: 'none', gap: 8 }}>
            <button className="btn sm" disabled={backupBusy || restoreBusy} onClick={downloadBackup}
                    style={{ whiteSpace: 'nowrap' }}>
              <Download size={15} />{backupBusy ? 'Создаём…' : 'Скачать'}
            </button>
            <button className="btn sm danger" disabled={backupBusy || restoreBusy}
                    onClick={() => restoreInput.current?.click()} style={{ whiteSpace: 'nowrap' }}>
              <Upload size={15} />{restoreBusy && !restoreCandidate ? 'Проверяем…' : 'Установить'}
            </button>
            <input ref={restoreInput} type="file" accept="application/json,.json"
                   onChange={selectRestore} style={{ display: 'none' }} />
          </div>
        </div>
        {backupNotice && (
          <div className="form-note ok" style={{ marginTop: 8 }}>
            <Check size={15} /><span>{backupNotice}</span>
          </div>
        )}
      </div>

      {restoreCandidate && (
        <>
          <div className="scrim" onClick={() => !restoreBusy && setRestoreCandidate(null)} />
          <aside className="drawer" role="dialog" aria-modal="true"
                 aria-label="Установка резервной копии">
            <div className="drawer-head">
              <Upload size={18} />
              <b>Установить резервную копию</b>
              <button className="iconbtn" style={{ marginLeft: 'auto' }} title="Закрыть"
                      disabled={restoreBusy} onClick={() => setRestoreCandidate(null)}>
                <X size={16} />
              </button>
            </div>
            <div className="drawer-body">
              <div className="warnbox">
                <AlertTriangle size={17} />
                <span><b>Текущее состояние базы будет заменено.</b> Перед применением сервис сохранит автоматическую копию и штатно перезапустится.</span>
              </div>

              {restoreError && <div className="form-err">{restoreError}</div>}

              <div className="kv">
                <span className="k">Файл</span>
                <span className="v">{restoreCandidate.file.name}</span>
                <span className="muted mono" style={{ fontSize: 11.5 }}>
                  {fileSize(restoreCandidate.summary.bytes)} · SHA-256 {restoreCandidate.summary.sha256.slice(0, 16)}…
                </span>
              </div>

              <div className="grid cols-2" style={{ gap: 10 }}>
                {[
                  ['Аккаунты', 'accounts'],
                  ['Правила', 'rules'],
                  ['Подписки', 'subscriptions'],
                  ['Коды', 'activation_codes'],
                  ['Жалобы', 'reports'],
                  ['Аудит', 'admin_audit'],
                ].map(([label, key]) => (
                  <div className="kv" key={key}>
                    <span className="k">{label}</span>
                    <span className="v mono">{restoreCandidate.summary.counts[key] ?? 0}</span>
                  </div>
                ))}
              </div>

              <div className="field-block">
                <label className="lbl" htmlFor="restore-confirm">Введите {RESTORE_CONFIRM}</label>
                <input id="restore-confirm" className="search-inp" autoComplete="off"
                       value={restoreConfirm} disabled={restoreBusy}
                       onChange={(e) => setRestoreConfirm(e.target.value.toUpperCase())} />
              </div>
            </div>
            <div className="drawer-foot">
              <button className="btn" disabled={restoreBusy}
                      onClick={() => setRestoreCandidate(null)}>Отмена</button>
              <button className="btn danger" disabled={restoreBusy || restoreConfirm !== RESTORE_CONFIRM}
                      onClick={installRestore}>
                <Upload size={15} />{restoreBusy ? 'Подготавливаем…' : 'Установить'}
              </button>
            </div>
          </aside>
        </>
      )}
    </>
  )
}
