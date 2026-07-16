import React, { useEffect, useState } from 'react'
import { api } from '../api.js'

const TB = 1024 ** 4, GB = 1024 ** 3
function fmtBytes(b) { b = Number(b) || 0; return b >= TB ? (b / TB).toFixed(2) + ' ТБ' : (b / GB).toFixed(1) + ' ГБ' }
function ago(ts) {
  if (!ts) return '—'
  const sec = Math.max(0, Math.floor(Date.now() / 1000 - ts))
  if (sec < 60) return sec + ' с назад'
  if (sec < 3600) return Math.floor(sec / 60) + ' мин назад'
  if (sec < 86400) return Math.floor(sec / 3600) + ' ч назад'
  return Math.floor(sec / 86400) + ' дн назад'
}
const BOT = { online: ['g', 'на связи'], degraded: ['w', 'сбои при опросе'], stalled: ['b', 'нет связи'], offline: ['b', 'не запущен'] }
const EV = { crash: 'violation', quota_pause: 'unsure', autopause: 'unsure', delivery_warn: 'unsure', info: 'na' }
const EV_RU = { crash: 'падение', quota_pause: 'пауза-квота', autopause: 'автопауза', delivery_warn: 'доставка', info: 'инфо' }
function evTime(ts) { try { return new Date(ts * 1000).toLocaleString('ru-RU', { hour12: false }) } catch (_) { return String(ts) } }

function Stat({ n, k, sub, tone }) {
  return (
    <div className="card stat">
      <div className="n" style={tone ? { color: `var(--${tone})` } : null}>{n}</div>
      <div className="k">{k}</div>
      {sub != null && <div className="sub">{sub}</div>}
    </div>
  )
}

function BotTile({ name, b }) {
  const [dot, label] = BOT[b?.state] || ['b', b ? '—' : 'загрузка…']
  return (
    <div className="card op">
      <span className={`dot ${dot}`} />
      <div>
        <div className="t">Бот {name}{b?.username ? <span className="muted mono" style={{ fontWeight: 400 }}> @{b.username}</span> : ''}</div>
        <div className="s">{label}{b?.lastPollTs ? ` · опрос ${ago(b.lastPollTs)}` : ''}{b && b.consecutiveErrors > 0 ? ` · ошибок подряд: ${b.consecutiveErrors}` : ''}</div>
      </div>
    </div>
  )
}

export default function Dashboard({ onGo, ops: opsProp }) {
  const [own, setOwn] = useState(null)
  // Обычно данные приходят пропом из Shell (единый опрос); если открыли напрямую — грузим сами.
  useEffect(() => {
    if (opsProp !== undefined) return
    let alive = true
    const t = () => api.ops().then((r) => { if (alive) setOwn(r) }).catch(() => { if (alive) setOwn(false) })
    t(); const id = setInterval(t, 15000)
    return () => { alive = false; clearInterval(id) }
  }, [opsProp])
  const ops = opsProp !== undefined ? opsProp : own

  if (ops === false) return <FailShell onGo={onGo} />
  if (!ops) return <div className="muted">Загрузка состояния…</div>

  const bots = ops.bots || {}
  const q = ops.queues?.reports
  const m = ops.metrics || {}
  const paused = ops.paymentsPaused
  const payDot = paused == null ? 'b' : (paused ? 'w' : 'g')
  const qDot = !q ? 'b' : (q.paused ? 'w' : (q.depth > 0 ? 'w' : 'g'))

  return (
    <>
      <div className="view-head">
        <div>
          <div className="lbl eyebrow">Состояние сервиса</div>
          <h1>Сводка</h1>
          <p>Живой статус ботов, очередь модерации, ключевые метрики и лента событий. Обновляется автоматически.</p>
        </div>
      </div>

      <div className="ops">
        <BotTile name="MAX" b={bots.max} />
        <BotTile name="TG" b={bots.tg} />
        <div className="card op"><span className={`dot ${payDot}`} /><div><div className="t">Приём платежей</div><div className="s">{paused == null ? 'состояние неизвестно' : (paused ? 'приостановлен' : 'включён')}</div></div></div>
        <div className="card op"><span className={`dot ${qDot}`} /><div><div className="t">Очередь жалоб</div><div className="s">{!q ? 'воркер недоступен' : (q.paused ? 'пауза (квота ИИ)' : `${q.depth} в очереди`)}</div></div></div>
      </div>

      <div className="tiles" style={{ marginTop: 16 }}>
        <Stat n={m.accounts ?? '—'} k="Аккаунты" sub={m.accounts24h ? `+${m.accounts24h} за сутки` : 'за сутки без новых'} />
        <Stat n={m.subs?.active ?? '—'} k="Активные подписки" sub={`истёкших ${m.subs?.inactive ?? 0}`} />
        <Stat n={m.rules ?? '—'} k="Правила синхронизации" />
        <Stat n={fmtBytes(m.traffic?.sumUsed)} k="Трафик за период" sub={`превышений ${m.traffic?.over100 ?? 0}`} tone={m.traffic?.over100 ? 'bad' : null} />
        <Stat n={m.reports?.last24h ?? 0} k="Жалоб за сутки" sub={`нарушений всего ${m.reports?.violation ?? 0}`} />
        <Stat n={m.codes?.unused ?? 0} k="Свободные коды" sub={`выдано ${m.codes?.used ?? 0} · истекло ${m.codes?.expired ?? 0} · аннулировано ${m.codes?.revoked ?? 0}`} />
      </div>

      <div className="grid cols-2" style={{ marginTop: 16, alignItems: 'start' }}>
        <div className="card pad">
          <div className="sec-title"><h3>Очередь модерации</h3>
            <button className="btn sm" onClick={() => onGo('moderation')}>Открыть</button>
          </div>
          {!q ? <div className="note"><span>⚠</span><span>Воркер жалоб недоступен.</span></div> : (
            <>
              <div className="spread" style={{ marginBottom: 8 }}>
                <span className="mono" style={{ fontWeight: 700, fontSize: 20 }}>{q.depth}</span>
                <span className="chips">
                  {q.inflight ? <span className="pill unsure dot">обработка</span> : <span className="pill ok dot">простаивает</span>}
                  {q.paused ? <span className="pill violation dot">пауза (квота)</span> : null}
                  {q.persistedDepth !== q.depth ? <span className="mchip plain">в сторе {q.persistedDepth}</span> : null}
                </span>
              </div>
              <div className="stack" style={{ gap: 6, fontSize: 12.5 }}>
                <div className="spread"><span className="muted">Обработано с запуска</span><span className="mono">{q.processedTotal}</span></div>
                <div className="spread"><span className="muted">Ошибок с запуска</span><span className="mono" style={{ color: q.errorTotal ? 'var(--bad)' : 'var(--ink)' }}>{q.errorTotal}</span></div>
                <div className="spread"><span className="muted">Последняя обработка</span><span className="mono">{ago(q.lastProcessedTs)}</span></div>
              </div>
            </>
          )}
        </div>

        <div className="card pad">
          <div className="sec-title"><h3>События сервиса</h3><span className="lbl">последние {ops.events?.length ?? 0}</span></div>
          {(!ops.events || ops.events.length === 0) ? (
            <div className="muted" style={{ fontSize: 13 }}>Событий нет — сервис работает штатно.</div>
          ) : (
            <div className="twrap"><table className="t">
              <tbody>
                {ops.events.map((e) => (
                  <tr key={e.id}>
                    <td style={{ width: 108 }}><span className={`pill ${EV[e.kind] || 'na'} dot`}>{EV_RU[e.kind] || e.kind}</span></td>
                    <td>{e.title}</td>
                    <td className="muted mono" style={{ whiteSpace: 'nowrap', fontSize: 11.5 }}>{evTime(e.ts)}</td>
                  </tr>
                ))}
              </tbody>
            </table></div>
          )}
        </div>
      </div>
    </>
  )
}

function FailShell({ onGo }) {
  return (
    <>
      <div className="view-head"><div><div className="lbl eyebrow">Состояние сервиса</div><h1>Сводка</h1></div></div>
      <div className="card pad"><div className="note"><span>⚠</span><span>Не удалось загрузить состояние сервиса. Обновите страницу или проверьте, запущен ли процесс.</span></div></div>
    </>
  )
}
