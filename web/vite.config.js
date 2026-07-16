import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function safeHttpUrl(value) {
  try {
    const url = new URL(String(value || '').trim())
    return ['http:', 'https:'].includes(url.protocol) ? url.toString().replace(/\/$/, '') : ''
  } catch (_) {
    return ''
  }
}

function safeAssetUrl(value) {
  const asset = String(value || '').trim()
  if (asset.startsWith('/') && !asset.startsWith('//')) return asset
  return safeHttpUrl(asset)
}

function safeEmail(value) {
  const email = String(value || '').trim()
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) ? email : ''
}

function handleFromUrl(value) {
  try {
    const segment = decodeURIComponent(new URL(value).pathname.split('/').filter(Boolean).at(-1) || '')
    return segment ? `@${segment.replace(/^@/, '')}` : ''
  } catch (_) {
    return ''
  }
}

function withQuery(value, key, queryValue) {
  const url = new URL(value)
  url.searchParams.set(key, queryValue)
  return url.toString()
}

function jsonForScript(value) {
  return JSON.stringify(value)
    .replace(/&/g, '\\u0026')
    .replace(/</g, '\\u003c')
    .replace(/>/g, '\\u003e')
    .replace(/\u2028/g, '\\u2028')
    .replace(/\u2029/g, '\\u2029')
}

function browserBotLinks(config) {
  const links = []
  if (config.botLinks.max) {
    links.push(`<a class="static-entry-action max" href="${escapeHtml(withQuery(config.botLinks.max, 'start', 'web'))}">Открыть ${escapeHtml(config.botName)} в MAX</a>`)
  }
  if (config.botLinks.tg) {
    links.push(`<a class="static-entry-action telegram" href="${escapeHtml(withQuery(config.botLinks.tg, 'start', 'web'))}">Открыть ${escapeHtml(config.botName)} в Telegram</a>`)
  }
  return links.length ? links.join('\n          ') : '<p class="static-entry-note">Ссылки на ботов не настроены.</p>'
}

function replaceIndexTokens(html, config) {
  const avatar = config.botAvatarUrl
    ? `<img class="static-entry-logo" src="${escapeHtml(config.botAvatarUrl)}" width="88" height="88" alt="Логотип ${escapeHtml(config.botName)}" />`
    : ''
  const favicons = config.botAvatarUrl
    ? `<link rel="icon" href="${escapeHtml(config.botAvatarUrl)}" />\n  <link rel="apple-touch-icon" href="${escapeHtml(config.botAvatarUrl)}" />`
    : ''
  const offer = config.landing.offerTitle || config.landing.offerText
    ? `<p class="static-entry-offer">${config.landing.offerTitle ? `<strong>${escapeHtml(config.landing.offerTitle)}</strong>` : ''}${escapeHtml(config.landing.offerText)}</p>`
    : ''
  const analyticsNotice = config.trackers.vkAds.enabled && config.landing.analyticsNotice
    ? `<p class="static-entry-analytics">${escapeHtml(config.landing.analyticsNotice)}</p>`
    : ''
  const appUrl = `${config.appUrl.replace(/\/$/, '')}/`
  const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'WebApplication',
    name: config.botName,
    url: appUrl,
    description: config.landing.description,
    applicationCategory: 'BusinessApplication',
  }
  const sameAs = Object.values(config.botLinks).filter(Boolean)
  if (sameAs.length) jsonLd.sameAs = sameAs
  const replacements = {
    '__MESYNC_BOT_NAME__': escapeHtml(config.botName),
    '__MESYNC_APP_URL__': escapeHtml(appUrl),
    '__MESYNC_LANDING_DESCRIPTION__': escapeHtml(config.landing.description),
    '__MESYNC_LANDING_OFFER__': offer,
    '__MESYNC_LANDING_ANALYTICS_NOTICE__': analyticsNotice,
    '__MESYNC_LANDING_JSON_LD__': jsonForScript(jsonLd),
    '__MESYNC_BROWSER_BOT_LINKS__': browserBotLinks(config),
    '__MESYNC_BROWSER_AVATAR__': avatar,
    '__MESYNC_FAVICON_LINKS__': favicons,
  }
  return Object.entries(replacements).reduce(
    (result, [token, value]) => result.replaceAll(token, value),
    html,
  )
}

// Production HTML keeps neutral placeholders: FastAPI fills them from the runtime .env.
// The development server renders the same fields from the repository-level env file.
export default defineConfig(({ mode, command }) => {
  const rootEnv = loadEnv(mode, '..', '')
  const env = (name, fallback = '', preserveEmpty = false) => {
    if (command !== 'serve') return String(fallback)
    const value = Object.prototype.hasOwnProperty.call(process.env, name)
      ? process.env[name]
      : rootEnv[name]
    return String(value == null || (!preserveEmpty && value === '') ? fallback : value).trim()
  }

  const botName = env('MESYNC_BOT_NAME', 'MeSync') || 'MeSync'
  const botAvatarUrl = safeAssetUrl(env('MESYNC_BOT_AVATAR_URL'))
  const appUrl = safeHttpUrl(env('MESYNC_APP_URL', 'http://localhost:8090')) || 'http://localhost:8090'
  const botLinks = {
    max: safeHttpUrl(env('MESYNC_MAX_BOT_URL')),
    tg: safeHttpUrl(env('MESYNC_TG_BOT_URL')),
  }
  const landingDescription = env(
    'MESYNC_LANDING_DESCRIPTION',
    `${botName} синхронизирует сообщения и посты между групповыми чатами и каналами MAX и Telegram, сохраняя форматирование, фото, видео и файлы.`,
  )
  const vkAdsPixelId = env('MESYNC_VK_ADS_PIXEL_ID')
  const publicConfig = {
    botName,
    botAvatarUrl,
    appUrl,
    botLinks,
    botHandles: Object.fromEntries(
      Object.entries(botLinks).map(([messenger, url]) => [messenger, handleFromUrl(url)]),
    ),
    support: {
      telegramUrl: safeHttpUrl(env('MESYNC_SUPPORT_TG_URL')),
      email: safeEmail(env('MESYNC_SUPPORT_EMAIL')),
    },
    legal: {
      termsVersion: env('MESYNC_LEGAL_TERMS_VERSION', '2026-07-08'),
      privacyVersion: env('MESYNC_LEGAL_PRIVACY_VERSION', '2026-07-11'),
    },
    landing: {
      description: landingDescription,
      offerTitle: env('MESYNC_LANDING_OFFER_TITLE', '7 дней бесплатно', true),
      offerText: env('MESYNC_LANDING_OFFER_TEXT', 'Новым пользователям после входа и подключения автопродления. Сейчас 0 ₽.', true),
      analyticsNotice: env('MESYNC_LANDING_ANALYTICS_NOTICE', 'Находясь на этом сайте, вы соглашаетесь на сбор аналитических данных.', true),
    },
    trackers: {
      vkAds: {
        enabled: /^\d+$/.test(vkAdsPixelId),
        pixelId: /^\d+$/.test(vkAdsPixelId) ? vkAdsPixelId : '',
        utmSource: env('MESYNC_VK_ADS_UTM_SOURCE', 'vkads'),
      },
    },
  }

  const plugins = [react()]
  if (command === 'serve') {
    plugins.push({
      name: 'mesync-dev-html-config',
      transformIndexHtml: {
        order: 'pre',
        handler: (html) => replaceIndexTokens(html, publicConfig),
      },
    })
  }

  return {
    plugins,
    base: './',
    define: {
      'import.meta.env.VITE_MESYNC_BOT_NAME': JSON.stringify(botName),
      'import.meta.env.VITE_MESYNC_BOT_AVATAR_URL': JSON.stringify(botAvatarUrl),
      'import.meta.env.VITE_MESYNC_APP_URL': JSON.stringify(appUrl),
      'import.meta.env.VITE_MESYNC_MAX_BOT_URL': JSON.stringify(botLinks.max),
      'import.meta.env.VITE_MESYNC_TG_BOT_URL': JSON.stringify(botLinks.tg),
      'import.meta.env.VITE_MESYNC_SUPPORT_TG_URL': JSON.stringify(publicConfig.support.telegramUrl),
      'import.meta.env.VITE_MESYNC_SUPPORT_EMAIL': JSON.stringify(publicConfig.support.email),
      'import.meta.env.VITE_MESYNC_LEGAL_TERMS_VERSION': JSON.stringify(publicConfig.legal.termsVersion),
      'import.meta.env.VITE_MESYNC_LEGAL_PRIVACY_VERSION': JSON.stringify(publicConfig.legal.privacyVersion),
      'import.meta.env.VITE_MESYNC_LANDING_DESCRIPTION': JSON.stringify(publicConfig.landing.description),
      'import.meta.env.VITE_MESYNC_LANDING_OFFER_TITLE': JSON.stringify(publicConfig.landing.offerTitle),
      'import.meta.env.VITE_MESYNC_LANDING_OFFER_TEXT': JSON.stringify(publicConfig.landing.offerText),
      'import.meta.env.VITE_MESYNC_LANDING_ANALYTICS_NOTICE': JSON.stringify(publicConfig.landing.analyticsNotice),
    },
    server: {
      host: true,
      port: 5174,
      proxy: {
        '/api': { target: 'http://127.0.0.1:8090', changeOrigin: true },
      },
    },
    build: {
      outDir: 'dist',
      sourcemap: true,
    },
  }
})
