import React, { useState, useEffect } from 'react'
import { api } from './api.js'
import botAvatar from '../../web/src/assets/logo-light.png'
import {
  LayoutDashboard, ShieldCheck, Users, CreditCard, ArrowLeftRight, Activity,
  Radio, Send, SlidersHorizontal, List, LogOut, Moon, Menu, KeyRound, Database,
} from 'lucide-react'
import Dashboard from './views/Dashboard.jsx'
import Moderation from './views/Moderation.jsx'
import Accounts from './views/Accounts.jsx'
import Subscriptions from './views/Subscriptions.jsx'
import ActivationCodes from './views/ActivationCodes.jsx'
import Rules from './views/Rules.jsx'
import Sources from './views/Sources.jsx'
import Traffic from './views/Traffic.jsx'
import Broadcast from './views/Broadcast.jsx'
import Settings from './views/Settings.jsx'
import Audit from './views/Audit.jsx'
import Placeholder from './views/Placeholder.jsx'

const NAV = [
  { id: 'dashboard', label: 'Сводка', Icon: LayoutDashboard, group: 'Работа' },
  { id: 'moderation', label: 'Модерация', Icon: ShieldCheck, group: 'Работа' },
  { id: 'accounts', label: 'Аккаунты', Icon: Users, group: 'Работа' },
  { id: 'subs', label: 'Подписки', Icon: CreditCard, group: 'Работа' },
  { id: 'codes', label: 'Коды', Icon: KeyRound, group: 'Работа' },
  { id: 'rules', label: 'Правила', Icon: ArrowLeftRight, group: 'Работа' },
  { id: 'sources', label: 'Источники', Icon: Radio, group: 'Работа' },
  { id: 'traffic', label: 'Трафик', Icon: Activity, group: 'Работа' },
  { id: 'broadcast', label: 'Рассылки', Icon: Send, group: 'Управление' },
  { id: 'settings', label: 'Настройки', Icon: SlidersHorizontal, group: 'Управление' },
  { id: 'postgres', label: 'PostgreSQL', Icon: Database, group: 'Управление', href: '/admin/psql/' },
  { id: 'audit', label: 'Аудит', Icon: List, group: 'Управление' },
]

const TITLE = Object.fromEntries(NAV.map((n) => [n.id, [n.group, n.label]]))
const PUBLIC_CONFIG = window.__MESYNC_PUBLIC_CONFIG__ || {}
const BOT_NAME = String(PUBLIC_CONFIG.botName || import.meta.env?.VITE_MESYNC_BOT_NAME || 'MeSync')
const BOT_AVATAR_URL = String(PUBLIC_CONFIG.botAvatarUrl || import.meta.env?.VITE_MESYNC_BOT_AVATAR_URL || '') || botAvatar

function toggleTheme() {
  const root = document.documentElement
  const cur = root.getAttribute('data-theme')
    || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
  root.setAttribute('data-theme', cur === 'dark' ? 'light' : 'dark')
}

const BOT_STATE = { online: ['ONLINE', ''], degraded: ['СБОИ', 'stalled'], stalled: ['НЕТ СВЯЗИ', 'stalled'], offline: ['OFFLINE', 'offline'] }
function botLabel(b) { return BOT_STATE[b?.state] || (b ? ['—', 'stalled'] : ['…', '']) }

export default function Shell({ onLogout }) {
  const [view, setView] = useState('dashboard')
  const [navOpen, setNavOpen] = useState(false)
  const [ops, setOps] = useState(null)
  const current = NAV.find((n) => n.id === view) || NAV[0]

  // Один опрос ops на всю панель (полоса статуса + «Сводка» используют одни данные).
  useEffect(() => {
    let alive = true
    // При первом же провале (нет прежних данных) отдаём false — Dashboard покажет FailShell,
    // а не вечную «Загрузку»; после успеха транзиентный сбой сохраняет последний снимок.
    const tick = () => api.ops()
      .then((r) => { if (alive) setOps(r) })
      .catch(() => { if (alive) setOps((prev) => (prev && prev !== true ? prev : false)) })
    tick()
    const id = setInterval(tick, 15000)
    return () => { alive = false; clearInterval(id) }
  }, [])

  const doLogout = async () => { try { await api.logout() } catch (_) {} onLogout() }
  const go = (id) => { setView(id); setNavOpen(false) }
  const [maxLbl, maxCls] = botLabel(ops?.bots?.max)
  const [tgLbl, tgCls] = botLabel(ops?.bots?.tg)

  let groupSeen = null
  return (
    <div className={`console${navOpen ? ' nav-open' : ''}`}>
      <aside className="side">
        <div className="side-head">
          <div className="row">
            <span className="mark"><img className="bot-avatar" src={BOT_AVATAR_URL} alt="" /></span>
            <span className="wordmark">{BOT_NAME}</span>
          </div>
          <div className="status-strip" title="Статус ботов">
            <div className="ends">
              <span className="node max" style={{ width: 9, height: 9, borderRadius: '50%', background: 'var(--max)' }} />
              <div className="end"><span className="lbl">MAX</span><span className={`v ${maxCls}`}>{maxLbl}</span></div>
            </div>
            <span className="bridge" style={{ opacity: 0.8 }}><span className="span" /></span>
            <div className="ends">
              <div className="end" style={{ alignItems: 'flex-end' }}><span className="lbl">TG</span><span className={`v ${tgCls}`}>{tgLbl}</span></div>
              <span className="node tg" style={{ width: 9, height: 9, borderRadius: '50%', background: 'var(--tg)' }} />
            </div>
          </div>
        </div>
        <nav className="side-nav">
          {NAV.map((n) => {
            const head = n.group !== groupSeen ? (groupSeen = n.group) : null
            return (
              <React.Fragment key={n.id}>
                {head && <div className="nav-group"><div className="lbl">{head}</div></div>}
                {n.href ? (
                  <a className="nav-item" href={n.href} title="Открыть pgAdmin" onClick={() => setNavOpen(false)}>
                    <n.Icon size={17} />
                    {n.label}
                  </a>
                ) : (
                  <button className={`nav-item${view === n.id ? ' active' : ''}`} onClick={() => go(n.id)}>
                    <n.Icon size={17} />
                    {n.label}
                    {n.soon && <span className="count soft">скоро</span>}
                  </button>
                )}
              </React.Fragment>
            )
          })}
        </nav>
        <div className="side-foot">
          <span className="avatar ava">A</span>
          <div className="who"><div className="n">Администратор</div><div className="r mono">сессия активна</div></div>
          <button className="iconbtn" onClick={doLogout} title="Выйти"><LogOut size={15} /></button>
        </div>
      </aside>

      <div className="main">
        <header className="topbar">
          <button className="iconbtn menu-btn" onClick={() => setNavOpen((v) => !v)} title="Меню"><Menu size={16} /></button>
          <span className="topbar-page-icon"><current.Icon size={16} /></span>
          <span className="crumb">{TITLE[view][0]}</span>
          <span className="env" style={{ marginLeft: 'auto' }}>PROD</span>
          <button className="iconbtn" onClick={toggleTheme} title="Сменить тему"><Moon size={15} /></button>
        </header>
        <div className="content">
          {view === 'dashboard' && <Dashboard onGo={go} ops={ops} />}
          {view === 'moderation' && <Moderation />}
          {view === 'accounts' && <Accounts />}
          {view === 'subs' && <Subscriptions />}
          {view === 'codes' && <ActivationCodes />}
          {view === 'rules' && <Rules />}
          {view === 'sources' && <Sources />}
          {view === 'traffic' && <Traffic />}
          {view === 'broadcast' && <Broadcast />}
          {view === 'settings' && <Settings />}
          {view === 'audit' && <Audit />}
          {current.soon && <Placeholder title={current.label} />}
        </div>
      </div>
    </div>
  )
}
