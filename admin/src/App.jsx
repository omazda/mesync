import React, { useEffect, useState } from 'react'
import { api } from './api.js'
import Login from './Login.jsx'
import Shell from './Shell.jsx'

export default function App() {
  const [phase, setPhase] = useState('loading') // loading | login | app

  useEffect(() => {
    api.me().then(() => setPhase('app')).catch(() => setPhase('login'))
    // Любой 401 в середине сессии (истёк cookie) → назад на экран входа.
    const onUnauth = () => setPhase('login')
    window.addEventListener('admin-unauth', onUnauth)
    return () => window.removeEventListener('admin-unauth', onUnauth)
  }, [])

  return (
    <div id="app" className={phase === 'app' ? 'booted' : ''}>
      {phase === 'loading' && (
        <div className="login"><div className="login-card" style={{ textAlign: 'center' }}>Загрузка…</div></div>
      )}
      {phase === 'login' && <Login onDone={() => setPhase('app')} />}
      {phase === 'app' && <Shell onLogout={() => setPhase('login')} />}
    </div>
  )
}
