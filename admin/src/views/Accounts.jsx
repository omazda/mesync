import React, { useEffect, useState } from 'react'
import { api } from '../api.js'
import { AlertTriangle, CalendarPlus, RotateCcw, KeyRound, Ban, ShieldCheck, PowerOff, CircleOff, PackagePlus } from 'lucide-react'

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
    return { cls: 'violation', icon: CircleOff, label: 'медиа закрыто', note: 'нет месячного или add-on остатка' }
  }
  if ((r.overageBytes || 0) > 0) {
    return { cls: 'unsure', icon: PackagePlus, label: 'расходует пакет', note: 'сверх месячного лимита' }
  }
  if ((r.percent || 0) >= 80) {
    return { cls: 'unsure', icon: AlertTriangle, label: 'близко к лимиту', note: 'месячный пакет' }
  }
  return { cls: 'ok', icon: ShieldCheck, label: 'в норме', note: 'месячный пакет' }
}
function fmtDate(ms) {
  if (!ms) return '—'
  try { return new Date(ms).toLocaleDateString('ru-RU') } catch (_) { return '—' }
}
const SUB_CLS = { active: 'ok', trial: 'unsure', inactive: 'na', retry: 'unsure', expired: 'na' }

function initials(text) {
  const clean = String(text || '').trim()
  return (clean[0] || 'A').toUpperCase()
}

function AccountAvatar({ profile, fallback, size = 'sm' }) {
  const [failed, setFailed] = useState(false)
  const src = profile?.avatar && !failed ? profile.avatar : ''
  return (
    <span className={`account-avatar ${size}`}>
      {src
        ? <img src={src} alt="" onError={() => setFailed(true)} />
        : <span>{initials(profile?.name || fallback)}</span>}
    </span>
  )
}

function AccountTitle({ account, profile }) {
  const name = profile?.name || (account?.phone ? '+' + account.phone : account?.id)
  return (
    <div className="account-title">
      <div className="account-name">{name || 'Аккаунт'}</div>
      <div className="account-subline">
        {profile?.messenger && <span className={`mchip ${profile.messenger === 'max' ? 'max' : 'tg'}`}>{profile.messenger === 'max' ? 'MAX' : 'TG'}</span>}
        <span className="id">{account?.id}</span>
      </div>
    </div>
  )
}

export default function Accounts() {
  const [sel, setSel] = useState(null)
  return sel
    ? <AccountDetail id={sel} onBack={() => setSel(null)} />
    : <AccountList onOpen={setSel} />
}

const PAGE = 100

function AccountList({ onOpen }) {
  const [q, setQ] = useState('')
  const [data, setData] = useState(null)
  const [offset, setOffset] = useState(0)
  useEffect(() => {
    let alive = true   // защита от гонки: ответ устаревшего запроса не перетирает свежий
    const t = setTimeout(() => {
      api.accounts({ q, limit: PAGE, offset })
        .then((r) => { if (!alive) return; setData((prev) => (offset && prev) ? { ...r, items: [...prev.items, ...r.items] } : r) })
        .catch(() => { if (alive) setData({ items: [], total: 0 }) })
    }, offset ? 0 : 250)
    return () => { alive = false; clearTimeout(t) }
  }, [q, offset])
  const onSearch = (e) => { setQ(e.target.value); setOffset(0) }
  return (
    <>
      <div className="view-head">
        <div><div className="lbl eyebrow">Пользователи сервиса</div><h1>Аккаунты</h1></div>
      </div>
      <input className="search-inp" style={{ marginBottom: 14 }} placeholder="Поиск: id аккаунта, телефон, user_id…"
        value={q} onChange={onSearch} />
      <div className="card"><div className="twrap"><table className="t">
        <thead><tr><th>Аккаунт</th><th>Телефон</th><th>Подписка</th><th>Правил</th><th>Статус</th></tr></thead>
        <tbody>
          {(data?.items || []).map((a) => (
            <tr key={a.id} className="clickable" onClick={() => onOpen(a.id)}>
              <td>
                <div className="account-cell">
                  <AccountAvatar profile={a.profile} fallback={a.phone || a.id} />
                  <AccountTitle account={a} profile={a.profile} />
                </div>
              </td>
              <td className="mono muted">{a.phone ? '+' + a.phone : '—'}</td>
              <td><span className={`pill ${SUB_CLS[a.subscription] || 'na'} dot`}>{a.subscription || '—'}</span></td>
              <td className="mono">{a.rulesCount}</td>
              <td>{a.blocked ? <span className="pill violation dot">заблокирован</span> : <span className="muted" style={{ fontSize: 12 }}>—</span>}</td>
            </tr>
          ))}
        </tbody>
      </table></div></div>
      {data && data.items.length === 0 && <div className="card pad muted" style={{ marginTop: 12 }}>Аккаунтов не найдено.</div>}
      {data && data.total > data.items.length && (
        <div className="row-flex" style={{ marginTop: 10, gap: 10 }}>
          <button className="btn sm" onClick={() => setOffset(data.items.length)}>Показать ещё</button>
          <span className="muted" style={{ fontSize: 12.5 }}>Показаны {data.items.length} из {data.total}.</span>
        </div>
      )}
    </>
  )
}

function AccountDetail({ id, onBack }) {
  const [d, setD] = useState(null)
  const [msg, setMsg] = useState(null)
  const [busy, setBusy] = useState(false)
  const load = () => api.account(id).then(setD).catch(() => onBack())
  useEffect(() => { load() }, [id])

  const act = async (body, done) => {
    setBusy(true); setMsg(null)
    try {
      const r = await api.accountAction(id, body)
      if (done) done(r)
      await load()
    } catch (e) { setMsg({ text: e.message || 'Не удалось', ok: false }) }
    setBusy(false)
  }

  if (!d) return <div className="muted">Загрузка…</div>
  const sub = d.subscription || {}
  const ov = d.overrides || {}
  const eff = ov.effective || {}
  const tr = d.traffic || {}
  const trState = trafficState(tr)
  const TrStateIcon = trState.icon
  const idents = d.identities || []
  const profile = d.profile || {}
  const canDisableAutopay = !!sub.autopay || !!sub.methodTitle || !!sub.pendingKind
  const canDisableSub = sub.status === 'active' || !!sub.autopay || !!sub.methodTitle || !!sub.pendingKind || !!sub.paidUntil
  const disableAutopay = () => {
    if (!canDisableAutopay || busy) return
    const ok = window.confirm('Отключить автопродление? Оплаченная подписка останется активной до даты окончания. Для триала пробный период завершится.')
    if (!ok) return
    act({ action: 'disable_autopay' }, (r) => setMsg({
      text: r.annulled ? 'Автопродление отключено, триал завершён.' : 'Автопродление отключено.',
      ok: true,
    }))
  }
  const disableSubscription = () => {
    if (!canDisableSub || busy) return
    const ok = window.confirm('Отключить подписку? Статус станет inactive, автопродление и привязка оплаты будут сняты.')
    if (!ok) return
    act({ action: 'disable_subscription' }, () => setMsg({ text: 'Подписка отключена.', ok: true }))
  }
  const resetTraffic = () => {
    if (busy) return
    const ok = window.confirm('Сбросить месячный расход трафика? Добавочный остаток сохранится.')
    if (!ok) return
    act({ action: 'reset_traffic' }, () => setMsg({ text: 'Месячный расход трафика сброшен, добавочный остаток сохранён.', ok: true }))
  }

  return (
    <>
      <div className="view-head">
        <div><div className="lbl eyebrow">Аккаунт · карточка</div><h1 className="mono" style={{ fontSize: 18 }}>{id}</h1></div>
        <div className="head-actions"><button className="btn sm" onClick={onBack}>← К списку</button></div>
      </div>
      {msg && (
        <div className={`form-note ${msg.ok ? 'ok' : 'err'}`} style={{ marginBottom: 12 }}>
          <span>{msg.text}</span>
          {msg.code && <span className="code-line">{msg.code}</span>}
        </div>
      )}

      <div className="grid cols-2" style={{ alignItems: 'start' }}>
        <div className="stack">
          <div className="card pad">
            <div className="acct-head">
              <AccountAvatar profile={profile} fallback={d.account?.phone || id} size="lg" />
              <div style={{ flex: 1 }}>
                <div className="spread">
                  <div>
                    <div style={{ fontSize: 15, fontWeight: 720 }}>{profile.name || (d.account?.phone ? '+' + d.account.phone : 'без телефона')}</div>
                    <div className="mono muted" style={{ fontSize: 12 }}>{id}</div>
                  </div>
                  {d.blocked
                    ? <span className="pill violation dot">заблокирован</span>
                    : <span className={`pill ${SUB_CLS[sub.status] || 'na'} dot`}>{sub.status || '—'}</span>}
                </div>
                <div className="chips">
                  {idents.map(([m, uid]) => <span key={m + uid} className={`mchip ${m === 'max' ? 'max' : 'tg'}`}>{m === 'max' ? 'MAX' : 'TG'} · {uid}</span>)}
                  <span className="mchip plain">создан {fmtDate((d.account?.created_at || 0) * 1000)}</span>
                </div>
              </div>
            </div>
          </div>

          <div className="card pad">
            <div className="sec-title"><h3>Подписка</h3><span className="lbl">{sub.planName || (sub.plan === 'individual' ? 'Индивидуальный' : 'Smart')}</span></div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 14 }}>
              <div className="kv"><span className="k">Статус</span><span className="v">{sub.status || '—'}</span></div>
              <div className="kv"><span className="k">Действует до</span><span className="v mono">{fmtDate(sub.paidUntil)}</span></div>
              <div className="kv"><span className="k">Автопродление</span><span className="v">{sub.autopay ? 'Вкл' : 'Выкл'}</span></div>
            </div>
            <div className="row-flex" style={{ marginTop: 14, flexWrap: 'wrap', gap: 8 }}>
              <button className="btn sm primary" disabled={busy} onClick={() => act({ action: 'grant_month' }, () => setMsg({ text: 'Месяц выдан.', ok: true }))}><CalendarPlus size={15} />Продлить месяц</button>
              <button className="btn sm" disabled={busy} onClick={() => act({ action: 'issue_code' }, (r) => setMsg({ text: 'Код активации выдан:', ok: true, code: r.code || '—' }))}><KeyRound size={15} />Выдать код</button>
              <button className="btn sm" disabled={busy || !canDisableAutopay} onClick={disableAutopay}><CircleOff size={15} />Отключить автопродление</button>
              <button className="btn sm danger" disabled={busy || !canDisableSub} onClick={disableSubscription}><PowerOff size={15} />Отключить подписку</button>
              {d.blocked
                ? <button className="btn sm" disabled={busy} onClick={() => act({ action: 'unblock' })}><ShieldCheck size={15} />Разблокировать</button>
                : <button className="btn sm danger" disabled={busy} onClick={() => act({ action: 'block' })}><Ban size={15} />Заблокировать</button>}
            </div>
          </div>

          <Overrides id={id} ov={ov} eff={eff} onSaved={(m, ok) => { setMsg({ text: m, ok }); load() }} />
        </div>

        <div className="stack">
          <div className="card pad">
            <div className="sec-title">
              <h3>Трафик</h3>
              <button className="btn sm" disabled={busy} onClick={resetTraffic}><RotateCcw size={14} />Сбросить месяц</button>
            </div>
            <div className="spread" style={{ marginBottom: 6 }}>
              <span className="mono" style={{ fontWeight: 700 }}>{fmtBytes(tr.usedBytes)}</span>
              <span className="muted mono" style={{ fontSize: 12.5 }}>из {fmtBytes(tr.limitBytes)}</span>
            </div>
            <div className={`meter${(tr.percent || 0) >= 80 ? ' warn' : ''}`}><i style={{ width: pct(tr.percent) + '%' }} /></div>
            <div className="traffic-subline">
              <span className="mono">{tr.percent || 0}% месяца</span>
              <span>осталось {fmtBytes(tr.includedRemainingBytes)}</span>
            </div>
            <div className="traffic-mini-grid">
              <div className="kv"><span className="k">Сверх месяца</span><span className="v mono">{fmtBytes(tr.overageBytes)}</span></div>
              <div className="kv"><span className="k">Add-on остаток</span><span className="v mono">{fmtBytes(tr.topupBytes)}</span></div>
            </div>
            <div className="row-flex" style={{ marginTop: 12, justifyContent: 'space-between' }}>
              <span className={`pill ${trState.cls}`}><TrStateIcon size={12} />{trState.label}</span>
              <span className="faint" style={{ fontSize: 12 }}>{trState.note}</span>
            </div>
          </div>
          <div className="card pad">
            <div className="sec-title"><h3>Правила · {d.rules?.activeCount ?? 0} из {d.rules?.limit ?? '—'}</h3></div>
            {(d.rules?.rules || []).slice(0, 6).map((r) => (
              <div key={r.id} className="list-line">
                <span style={{ flex: 1 }}>{r.a?.title} ⇄ {r.b?.title}</span>
                <span className={`pill ${r.status === 'active' ? 'ok' : 'na'} dot`}>{r.status}</span>
              </div>
            ))}
            {(!d.rules?.rules || d.rules.rules.length === 0) && <div className="muted" style={{ fontSize: 13 }}>Правил нет.</div>}
          </div>
          <div className="card pad">
            <div className="sec-title"><h3>Модерация</h3></div>
            <div className="spread"><span className="muted">Подтверждённых нарушений / 24 ч</span><span className="mono" style={{ fontWeight: 700, color: d.strikes24h ? 'var(--bad)' : 'var(--ink)' }}>{d.strikes24h ?? 0}</span></div>
          </div>
        </div>
      </div>
    </>
  )
}

function Overrides({ id, ov, eff, onSaved }) {
  const TBB = 1024 ** 4
  const init = () => ({
    rule_limit: ov.rule_limit ?? '',
    price: ov.price ?? '',
    // байты→ТБ: сохранённый 0 — это оверрайд (не «пусто»); округляем, чтобы не показывать
    // длинный хвост float для недвоичных значений (0.3 ТБ и т.п.).
    traffic_limit: ov.traffic_limit != null ? +(ov.traffic_limit / TBB).toFixed(3) : '',
  })
  const [v, setV] = useState(init)
  const [busy, setBusy] = useState(false)
  useEffect(() => { setV(init()) }, [ov.rule_limit, ov.price, ov.traffic_limit])
  const set = (k) => (e) => setV({ ...v, [k]: e.target.value })

  const save = async () => {
    setBusy(true)
    const body = { action: 'set_overrides' }
    body.rule_limit = v.rule_limit === '' ? null : parseInt(v.rule_limit, 10)
    body.price = v.price === '' ? null : parseInt(v.price, 10)
    body.traffic_limit = v.traffic_limit === '' ? null : Math.round(parseFloat(v.traffic_limit) * TBB)
    try { await api.accountAction(id, body); onSaved('Индивидуальные условия сохранены.', true) }
    catch (e) { onSaved(e.message || 'Не удалось', false) }
    setBusy(false)
  }

  return (
    <div className="card pad">
      <div className="sec-title"><h3>Индивидуальные условия</h3><span className="pill dot" style={{ background: 'var(--accent-soft)', color: 'var(--accent)' }}>персональный план</span></div>
      <p className="muted" style={{ fontSize: 12, margin: '-2px 0 4px' }}>Пусто — общий тариф. Применяется к следующей оплате/доставке.</p>
      <div className="set-row">
        <div className="info"><div className="t">Лимит правил</div><div className="d">По умолчанию {eff.rule_limit}.</div></div>
        <input className="inp" style={{ width: 70 }} type="number" min={1} value={v.rule_limit} onChange={set('rule_limit')} placeholder={String(eff.rule_limit ?? '')} />
      </div>
      <div className="set-row">
        <div className="info"><div className="t">Персональная цена, ₽/мес</div><div className="d">По умолчанию {eff.price}. Идёт в оплату и автопродление.</div></div>
        <input className="inp" style={{ width: 80 }} type="number" min={0} value={v.price} onChange={set('price')} placeholder={String(eff.price ?? '')} />
      </div>
      <div className="set-row">
        <div className="info"><div className="t">Лимит трафика, ТБ</div><div className="d">По умолчанию {(eff.traffic_limit / TBB || 0).toFixed(2)}. Пакеты — сверх.</div></div>
        <input className="inp" style={{ width: 80 }} type="number" min={0} step="0.1" value={v.traffic_limit} onChange={set('traffic_limit')} placeholder={(eff.traffic_limit / TBB || 0).toFixed(1)} />
      </div>
      <div style={{ marginTop: 12, display: 'flex', justifyContent: 'flex-end' }}>
        <button className="btn sm primary" disabled={busy} onClick={save}>{busy ? 'Сохраняем…' : 'Сохранить условия'}</button>
      </div>
    </div>
  )
}
