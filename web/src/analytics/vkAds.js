/* VK Ads использует Счётчик Mail (Top.Mail.Ru). Конфигурация приходит из runtime
 * .env через /api/public-config.js; пустой ID не загружает внешний скрипт. */

const tracker = ((typeof window !== 'undefined' && window.__MESYNC_PUBLIC_CONFIG__) || {})
  .trackers?.vkAds || {}
const rawPixelId = String(tracker.pixelId || '').trim()
const configuredSource = String(tracker.utmSource || '').trim().toLowerCase()

export const VK_ADS_PIXEL_ID = /^\d+$/.test(rawPixelId) ? rawPixelId : ''
export const VK_ADS_ENABLED = tracker.enabled === true && Boolean(VK_ADS_PIXEL_ID)
export const VISIT_GOAL = 'visit'
export const VK_ADS_GOALS = Object.freeze({ max: 'exitmax', telegram: 'exittelegram' })
export const VK_ADS_VISIT_GOAL = 'vkvisit'
export const VK_ADS_BOT_EXIT_GOAL = 'vkexitbot'
export const VK_ADS_SOURCE_GOALS = Object.freeze({
  max: 'vkexitmax',
  telegram: 'vkexittelegram',
})

const SCRIPT_ID = 'tmr-code'
let pageViewQueued = false
let visitGoalQueued = false
let vkVisitGoalQueued = false
let scriptRequested = false

function queue() {
  if (typeof window === 'undefined') return null
  return window._tmr || (window._tmr = [])
}

function isVkAdsVisit() {
  if (typeof window === 'undefined') return false
  try {
    const params = new URLSearchParams(window.location.search)
    const source = String(params.get('utm_source') || '').trim().toLowerCase()
    return [configuredSource, 'vk', 'vkads', 'vk_ads', 'vkontakte'].filter(Boolean).includes(source)
      || Boolean(params.get('rb_clickid'))
  } catch (_) {
    return false
  }
}

export function initVkAds() {
  if (!VK_ADS_ENABLED || typeof document === 'undefined') return false
  const events = queue()
  if (!events) return false

  if (!pageViewQueued) {
    events.push({ id: VK_ADS_PIXEL_ID, type: 'pageView', start: Date.now() })
    pageViewQueued = true
  }
  if (!visitGoalQueued) {
    events.push({ id: VK_ADS_PIXEL_ID, type: 'reachGoal', goal: VISIT_GOAL })
    visitGoalQueued = true
  }
  if (!vkVisitGoalQueued && isVkAdsVisit()) {
    events.push({ id: VK_ADS_PIXEL_ID, type: 'reachGoal', goal: VK_ADS_VISIT_GOAL })
    vkVisitGoalQueued = true
  }

  if (!scriptRequested && !document.getElementById(SCRIPT_ID)) {
    const script = document.createElement('script')
    script.id = SCRIPT_ID
    script.async = true
    script.src = 'https://top-fwz1.mail.ru/js/code.js'
    document.head.appendChild(script)
    scriptRequested = true
  }
  return true
}

export function trackMessengerExit(destination) {
  const goal = VK_ADS_GOALS[destination]
  if (!goal || !initVkAds()) return false

  const events = queue()
  events.push({ id: VK_ADS_PIXEL_ID, type: 'reachGoal', goal })
  if (isVkAdsVisit()) {
    events.push({ id: VK_ADS_PIXEL_ID, type: 'reachGoal', goal: VK_ADS_BOT_EXIT_GOAL })
    const sourceGoal = VK_ADS_SOURCE_GOALS[destination]
    if (sourceGoal) events.push({ id: VK_ADS_PIXEL_ID, type: 'reachGoal', goal: sourceGoal })
  }
  return true
}
