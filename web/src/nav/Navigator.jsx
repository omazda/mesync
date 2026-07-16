/* Navigator.jsx — что рендерить по фазе/вкладке/стеку/листу.
 *
 * Фазы: loading → auth (S1…) → legal → paywall (S5, жёсткий гейт) → app (вкладки).
 * Корень вкладки «Правила» — S6 (пусто) или S9 (список) по данным. Pushed-экраны
 * (S8/S10/S11/S12/S13) рисуются поверх корня вкладки; листы (sheet) — поверх всего.
 */
import React from 'react'
import { useStore } from '../store/store.js'
import { getScreen, getSheet } from '../screens/registry.js'
import { Spinner } from '../components/ui.jsx'
import host from '../host/host.js'

function rulesRoot(rules, sources) {
  const bound = (sources.items || []).filter((s) => s.status !== 'wait').length
  return (rules.items && rules.items.length > 0) || bound >= 2 ? 'S9' : 'S6'
}

function tabRoot(tab, rules, sources) {
  if (tab === 'sources') return 'S7'
  if (tab === 'settings') return 'SH'
  return rulesRoot(rules, sources)
}

export default function Navigator() {
  const phase = useStore((s) => s.phase)
  const nav = useStore((s) => s.nav)
  const rules = useStore((s) => s.rules)
  const sources = useStore((s) => s.sources)

  // Публичная активация кодов Яндекс Маркета — отдельный маршрут без сессии,
  // mini-app bootstrap и браузерного переходника.
  const publicPath = typeof window !== 'undefined'
    ? window.location.pathname.replace(/\/+$/, '') || '/'
    : '/'
  if (publicPath === '/ya_market') {
    const MarketActivation = getScreen('MarketActivation')
    return MarketActivation ? <MarketActivation /> : null
  }

  // Вне MAX/Telegram приложение не авторизует пользователя: показываем публичный
  // переходник независимо от старого browser-localStorage.
  if (host.name === 'browser') {
    const BrowserEntry = getScreen('BrowserEntry')
    return BrowserEntry ? <BrowserEntry /> : null
  }

  if (phase === 'loading') {
    return <div className="fullscreen-msg"><Spinner size={28} /></div>
  }

  // Фаза жалобы (открыта по диплинку startapp=r_<token>): отдельный экран без вкладок,
  // онбординга и пейволла — жалобщик обычно не клиент MeSync.
  if (phase === 'report') {
    const Report = getScreen('SReport')
    return Report ? <Report /> : null
  }

  let rootName
  if (phase === 'auth') rootName = 'S1'
  else if (phase === 'legal') rootName = 'SLegal'
  else if (phase === 'paywall') rootName = 'S5'
  else rootName = tabRoot(nav.tab, rules, sources)

  const top = nav.stack.length ? nav.stack[nav.stack.length - 1] : { name: rootName, props: {} }
  const Screen = getScreen(top.name) || getScreen(rootName)
  const Sheet = nav.sheet ? getSheet(nav.sheet.name) : null

  return (
    <>
      {Screen ? <Screen {...(top.props || {})} /> : null}
      {Sheet ? <Sheet {...(nav.sheet.props || {})} /> : null}
    </>
  )
}
