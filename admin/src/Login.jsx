import React, { useState } from 'react'
import { api } from './api.js'
import botAvatar from '../../web/src/assets/logo-light.png'

const PUBLIC_CONFIG = window.__MESYNC_PUBLIC_CONFIG__ || {}
const BOT_NAME = String(PUBLIC_CONFIG.botName || import.meta.env?.VITE_MESYNC_BOT_NAME || 'MeSync')
const BOT_AVATAR_URL = String(PUBLIC_CONFIG.botAvatarUrl || import.meta.env?.VITE_MESYNC_BOT_AVATAR_URL || '') || botAvatar

export default function Login({ onDone }) {
  const [pw, setPw] = useState('')
  const [err, setErr] = useState(null)
  const [loading, setLoading] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setErr(null)
    setLoading(true)
    try {
      await api.login(pw)
      onDone()
    } catch (x) {
      if (x.code === 'too_many_attempts') setErr('Слишком много попыток. Попробуйте позже.')
      else if (x.code === 'admin_disabled') setErr('Панель управления сейчас недоступна.')
      else if (x.code === 'network') setErr('Нет соединения с сервером.')
      else setErr('Неверный пароль.')
      setLoading(false)
    }
  }

  return (
    <div className="login">
      <form className="login-card" onSubmit={submit}>
        <div className="login-brand">
          <span className="mark"><img className="bot-avatar" src={BOT_AVATAR_URL} alt="" /></span>
          <span className="wordmark">{BOT_NAME}</span>
        </div>
        <div className="lbl" style={{ marginBottom: 8 }}>Панель управления</div>
        <h1>Вход для администратора</h1>
        <p className="sub">Введите пароль, чтобы продолжить.</p>
        <div className="field">
          <label className="lbl" htmlFor="pw">Пароль</label>
          <input id="pw" type="password" value={pw} autoFocus autoComplete="current-password"
                 placeholder="••••••••••••" onChange={(e) => setPw(e.target.value)} />
        </div>
        {err && <div className="form-err">{err}</div>}
        <button className="btn primary block" type="submit" style={{ marginTop: 18 }}
                disabled={loading}>{loading ? 'Проверяем…' : 'Войти'}</button>
      </form>
    </div>
  )
}
