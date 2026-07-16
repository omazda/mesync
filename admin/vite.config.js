import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function iconType(url) {
  const clean = String(url || '').split('?')[0].toLowerCase()
  if (clean.endsWith('.svg')) return 'image/svg+xml'
  if (clean.endsWith('.ico')) return 'image/x-icon'
  return 'image/png'
}

// Панель раздаётся FastAPI на /admin (см. src/control/api.py) — базовый путь ассетов /admin/.
export default defineConfig(({ mode, command }) => {
  const rootEnv = loadEnv(mode, '..', '')
  const runtimeBuild = command === 'serve'
  const botName = runtimeBuild
    ? String(process.env.MESYNC_BOT_NAME || rootEnv.MESYNC_BOT_NAME || 'MeSync').trim() || 'MeSync'
    : 'MeSync'
  const botAvatarUrl = runtimeBuild
    ? String(process.env.MESYNC_BOT_AVATAR_URL || rootEnv.MESYNC_BOT_AVATAR_URL || '').trim()
    : ''

  return {
    base: '/admin/',
    plugins: [
      react(),
      {
        name: 'mesync-bot-name-html',
        transformIndexHtml: (html) => {
          const out = html.replaceAll('%MESYNC_BOT_NAME%', escapeHtml(botName))
          if (!botAvatarUrl) return out
          const avatar = escapeHtml(botAvatarUrl)
          const type = escapeHtml(iconType(botAvatarUrl))
          return out.replace('</head>', `    <link rel="icon" type="${type}" href="${avatar}" />\n    <link rel="apple-touch-icon" href="${avatar}" />\n  </head>`)
        },
      },
    ],
    define: {
      'import.meta.env.VITE_MESYNC_BOT_NAME': JSON.stringify(botName),
      'import.meta.env.VITE_MESYNC_BOT_AVATAR_URL': JSON.stringify(botAvatarUrl),
    },
    server: {
      // dev-прокси на control-API (для локальной разработки панели вне процесса mesync-app).
      proxy: { '/api': { target: 'http://127.0.0.1:8090', changeOrigin: true } },
    },
  }
})
