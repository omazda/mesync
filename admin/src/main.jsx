import React from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'
import './styles.css'
import botAvatar from '../../web/src/assets/logo-light.png'

const PUBLIC_CONFIG = window.__MESYNC_PUBLIC_CONFIG__ || {}
const BOT_NAME = String(PUBLIC_CONFIG.botName || import.meta.env?.VITE_MESYNC_BOT_NAME || 'MeSync')
const BOT_AVATAR_URL = String(PUBLIC_CONFIG.botAvatarUrl || import.meta.env?.VITE_MESYNC_BOT_AVATAR_URL || '') || botAvatar

document.title = `${BOT_NAME} — панель управления`

function setPageIcon(rel) {
  let link = document.head.querySelector(`link[rel="${rel}"]`)
  if (!link) {
    link = document.createElement('link')
    link.rel = rel
    document.head.appendChild(link)
  }
  link.href = BOT_AVATAR_URL
  if (rel === 'icon') {
    const clean = BOT_AVATAR_URL.split('?')[0].toLowerCase()
    link.type = clean.endsWith('.svg') ? 'image/svg+xml'
      : clean.endsWith('.ico') ? 'image/x-icon'
        : 'image/png'
  }
}

setPageIcon('icon')
setPageIcon('apple-touch-icon')

createRoot(document.getElementById('root')).render(<App />)
