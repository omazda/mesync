/* store.js — глобальное состояние mini-app (zustand).
 *
 * Держит: фазу загрузки/гейтинга, сессию и аккаунт, ресурсы (подписка, источники,
 * правила, трафик, уведомления), статус сети и состояние навигации (вкладка, стек
 * экранов, нижний лист, тост). Экраны читают срезы и вызывают действия отсюда.
 */
import { create } from 'zustand'
import api, { setToken, clearToken, isLoggedOut, setLoggedOut } from '../api/client.js'
import host from '../host/host.js'

const empty = () => ({ items: [], loading: false, error: null })
const CURRENT_TERMS_VERSION = '2026-07-08'
const CURRENT_PRIVACY_VERSION = '2026-07-11'

function hasCurrentLegal(account) {
  return Boolean(account?.legal?.accepted)
}

// Коллатор для сортировки названий источников по алфавиту — корректно сразу для всех
// языков, символов и цифр: локаль среды + Unicode-правила для прочих письменностей
// (латиница, кириллица, CJK, арабский, эмодзи и т.д.). numeric:true — числа в названиях
// сравниваются по значению («чат 2» < «чат 10»); полный (variant) уровень сравнения даёт
// детерминированный порядок с учётом регистра и диакритики (Ё рядом с Е).
const titleCollator = new Intl.Collator(undefined, { numeric: true, usage: 'sort' })

export const useStore = create((set, get) => ({
  // --- фаза приложения / гейтинг ---
  phase: 'loading', // loading | auth | legal | paywall | app | report
  online: typeof navigator === 'undefined' ? true : navigator.onLine,

  // --- сессия ---
  account: null,
  subscription: null,
  reportToken: null,   // токен жалобы из диплинка startapp=r_<token> (фаза report)
  preAuthLegalAccepted: false,

  // --- ресурсы ---
  sources: empty(),
  rules: { ...empty(), activeCount: 0, limit: 10 },
  traffic: { data: null, loading: false, error: null },
  notifications: { ...empty(), unread: 0 },

  // --- навигация ---
  nav: { tab: 'rules', stack: [], sheet: null },
  toast: null,

  /* ===================== bootstrap / auth / гейт ===================== */
  async bootstrap() {
    set({ phase: 'loading' })
    // Диплинк жалобы (startapp=r_<token>): отдельная лёгкая фаза БЕЗ входа/пейволла —
    // жалобщик обычно не клиент MeSync. Аутентификация/антиспам — на бэкенде по initData.
    const sp = String(host.startParam || '')
    if (sp.startsWith('r_')) { set({ phase: 'report', reportToken: sp }); return }
    if (isLoggedOut()) {
      clearToken()
      set({ phase: 'auth', account: null })
      return
    }
    let token = api.getToken()
    // В вебвью MAX localStorage не переживает перезагрузку (а порой и недоступен) → токен
    // теряется и сессия «живёт только до перезагрузки». Но при КАЖДОМ запуске есть подписанный
    // initData (MAX/Telegram кладут его в location.hash) → тихо восстанавливаем сессию по нему,
    // не требуя повторного входа. Новый пользователь (аккаунта ещё нет) тихим входом не
    // находится → дальше обычный экран входа S1 (онбординг новых не меняется).
    if (!token) token = await get().silentAuth()
    if (!token) { set({ phase: 'auth' }); return }
    try {
      const account = await api.getAccount()
      set({ account })
      await get().gateBySubscription()
    } catch (err) {
      // Токен есть, но протух/невалиден → ещё раз пробуем тихий вход по initData; и только
      // если и он не помог — на экран входа.
      const fresh = await get().silentAuth()
      if (fresh) {
        try {
          set({ account: await api.getAccount() })
          await get().gateBySubscription()
          return
        } catch (_) { /* провалилось — на экран входа */ }
      }
      clearToken()
      set({ phase: 'auth', account: null })
    }
  },

  // Тихое восстановление сессии по подписанному initData запуска (без телефона). Находит
  // СУЩЕСТВУЮЩИЙ аккаунт (бэкенд новый НЕ создаёт) → сохраняет токен и возвращает его; если
  // launch-данных нет или аккаунт ещё не заведён — null (покажем обычный экран входа).
  async silentAuth() {
    try {
      if (isLoggedOut()) return null
      const init = host.getInitData() || {}
      if (!init.raw) return null
      const res = await api.authSilent({
        messenger: host.name === 'telegram' ? 'tg' : 'max',
        initData: init.raw,
        userId: init.unsafe?.user?.id,
      })
      if (!res || !res.token) return null
      setToken(res.token)
      set({ account: res.account })
      return res.token
    } catch (_) { return null }
  },

  async gateBySubscription() {
    // Смена фазы сбрасывает стек навигации: иначе экраны auth-флоу (S2/S3/S4)
    // остаются в стеке и перекрывают приложение после входа.
    const freshNav = { tab: 'rules', stack: [], sheet: null }
    const account = get().account || await api.getAccount()
    if (!hasCurrentLegal(account)) {
      set({ account, subscription: null, phase: 'legal', nav: freshNav })
      return
    }
    set({ account })
    try {
      const subscription = await api.getSubscription()
      const phase = subscription.status === 'active' ? 'app' : 'paywall'
      set({ subscription, phase, nav: freshNav })
      if (subscription.status === 'active') get().loadAll()
    } catch (err) {
      set({ phase: 'paywall', nav: freshNav })
    }
  },

  async setSession(token, account) {
    setLoggedOut(false)
    setToken(token)
    set({ account: account || get().account })
    if (!account) { try { set({ account: await api.getAccount() }) } catch (_) {} }
    if (get().preAuthLegalAccepted && !hasCurrentLegal(get().account)) {
      const init = host.getInitData() || {}
      const legal = get().account?.legal || {}
      try {
        const accepted = await api.acceptLegal({
          termsVersion: legal.requiredTermsVersion || CURRENT_TERMS_VERSION,
          privacyVersion: legal.requiredPrivacyVersion || CURRENT_PRIVACY_VERSION,
          source: 'start_screen',
          messenger: host.name === 'telegram' ? 'tg' : 'max',
          userId: init.unsafe?.user?.id,
        })
        set({ account: accepted, preAuthLegalAccepted: false })
      } catch (_) { /* покажем legal-interstitial */ }
    }
    await get().gateBySubscription()
  },

  async acceptLegal() {
    const init = host.getInitData() || {}
    const legal = get().account?.legal || {}
    const account = await api.acceptLegal({
      termsVersion: legal.requiredTermsVersion || CURRENT_TERMS_VERSION,
      privacyVersion: legal.requiredPrivacyVersion || CURRENT_PRIVACY_VERSION,
      source: 'miniapp',
      messenger: host.name === 'telegram' ? 'tg' : 'max',
      userId: init.unsafe?.user?.id,
    })
    set({ account })
    set({ preAuthLegalAccepted: false })
    await get().gateBySubscription()
    return account
  },

  setPreAuthLegalAccepted(value) {
    set({ preAuthLegalAccepted: !!value })
  },

  logout() {
    clearToken()
    setLoggedOut(true)
    set({ phase: 'auth', account: null, subscription: null, preAuthLegalAccepted: false, sources: empty(),
      rules: { ...empty(), activeCount: 0, limit: 10 }, traffic: { data: null, loading: false, error: null },
      notifications: { ...empty(), unread: 0 }, nav: { tab: 'rules', stack: [], sheet: null } })
  },

  /* ===================== загрузка ресурсов ===================== */
  loadAll() {
    get().loadSources(); get().loadRules(); get().loadTraffic(); get().loadNotifications()
  },

  async loadSources() {
    set((s) => ({ sources: { ...s.sources, loading: true, error: null } }))
    try {
      const { sources, counts } = await api.getSources()
      // Источники — по алфавиту (см. titleCollator: корректно для всех языков, символов
      // и цифр). Единая точка сортировки: покрывает и список «Источники» (S7), и лист
      // выбора источника в редакторе правила.
      const items = [...sources].sort((a, b) => titleCollator.compare(a.title || '', b.title || ''))
      set({ sources: { items, counts, loading: false, error: null } })
    } catch (err) { set((s) => ({ sources: { ...s.sources, loading: false, error: errText(err) } })) }
  },

  async loadRules() {
    set((s) => ({ rules: { ...s.rules, loading: true, error: null } }))
    try {
      const { rules, activeCount, limit } = await api.getRules()
      set({ rules: { items: rules, activeCount, limit, loading: false, error: null } })
    } catch (err) { set((s) => ({ rules: { ...s.rules, loading: false, error: errText(err) } })) }
  },

  async loadTraffic() {
    set((s) => ({ traffic: { ...s.traffic, loading: true, error: null } }))
    try { set({ traffic: { data: await api.getTraffic(), loading: false, error: null } }) }
    catch (err) { set((s) => ({ traffic: { ...s.traffic, loading: false, error: errText(err) } })) }
  },

  async loadNotifications() {
    set((s) => ({ notifications: { ...s.notifications, loading: true, error: null } }))
    try {
      const { items, unread } = await api.getNotifications()
      set({ notifications: { items, unread, loading: false, error: null } })
    } catch (err) { set((s) => ({ notifications: { ...s.notifications, loading: false, error: errText(err) } })) }
  },

  async markNotificationsRead() {
    try { await api.readNotifications(); set((s) => ({ notifications: { ...s.notifications, items: s.notifications.items.map((n) => ({ ...n, read: true })), unread: 0 } })) } catch (_) {}
  },

  // Скрыть (отметить прочитанными) конкретные уведомления — для кнопки «Скрыть» на баннере.
  async dismissNotifications(ids) {
    if (!ids || !ids.length) return
    const idset = new Set(ids)
    set((s) => {
      const items = s.notifications.items.map((n) => (idset.has(n.id) ? { ...n, read: true } : n))
      return { notifications: { ...s.notifications, items, unread: items.filter((n) => !n.read).length } }
    })
    try { await api.readNotifications(ids) } catch (_) {}
  },

  /* ===================== источники ===================== */
  async deleteSource(id) {
    await api.deleteSource(id)
    await Promise.all([get().loadSources(), get().loadRules()])
  },

  // Одноразовый UI-флаг аккаунта (показанные подсказки): оптимистично в сторе,
  // запрос фоном. Не вышло — не страшно: подсказка покажется ещё раз позже.
  async markAccountFlag(flag) {
    const acc = get().account
    if (!acc || acc.uiFlags?.[flag]) return
    set({ account: { ...acc, uiFlags: { ...(acc.uiFlags || {}), [flag]: true } } })
    try { await api.setAccountFlag(flag) } catch (_) {}
  },

  /* ===================== правила ===================== */
  async createRule(payload) { const { rule } = await api.createRule(payload); await get().loadRules(); return rule },
  async updateRule(id, patch) { const { rule } = await api.updateRule(id, patch); await get().loadRules(); return rule },
  async setRuleStatus(id, status) { await api.setRuleStatus(id, status); await get().loadRules() },
  async deleteRule(id) { await api.deleteRule(id); await Promise.all([get().loadRules(), get().loadSources()]) },
  // «Скрыть» баннер предупреждения о сбое доставки: прячем сразу (оптимистично), запрос
  // фоном. Баннер вернётся сам при следующем сбое (бэкенд снова поднимет флаг).
  async dismissRuleWarning(id) {
    set((s) => ({ rules: { ...s.rules, items: (s.rules.items || []).map((r) => (r.id === id ? { ...r, deliveryWarn: false } : r)) } }))
    try { await api.dismissRuleWarning(id) } catch (_) { /* оставляем скрытым; loadRules ресинхронизирует при необходимости */ }
  },

  /* ===================== подписка / оплата / трафик ===================== */
  // Оплата ЮKassa: оформление (payCheckout) возвращает либо confirmationUrl
  // (привязка на странице ЮKassa), либо confirmationToken (виджет). Результат
  // дожимается поллингом payStatus — бэкенд применяет платёж идемпотентно.
  async payCheckout(payload) {
    const res = await api.payCheckout(payload)
    if (res.subscription) set({ subscription: res.subscription })
    return res
  },
  async payStatus() {
    const res = await api.payStatus()
    if (res.subscription) set({ subscription: res.subscription })
    if (res.traffic) set({ traffic: { data: res.traffic, loading: false, error: null } })
    // Успех с пейволла — переключаем фазу на приложение; внутри приложения (S11)
    // фазу не трогаем, чтобы не сбрасывать навигацию.
    if (res.state === 'succeeded' && get().phase !== 'app') await get().gateBySubscription()
    return res
  },
  async payCancel() {
    const res = await api.payCancel()
    if (res.subscription) set({ subscription: res.subscription })
    return res
  },
  async payAutopay(enabled) {
    const res = await api.payAutopay(enabled)
    if (res.subscription) set({ subscription: res.subscription })
    // Аннулирование триала гасит подписку → возвращаемся на пейволл.
    if (res.annulled) await get().gateBySubscription()
    return res
  },
  // Код активации: месяц подписки без привязки карты. Успех с пейволла — в приложение.
  async activateCode(code) {
    const res = await api.activateCode(code)
    if (res.subscription) set({ subscription: res.subscription })
    if (get().phase !== 'app') await get().gateBySubscription()
    return res
  },
  async topupTraffic() {
    const res = await api.topupTraffic()
    if (res.traffic) set({ traffic: { data: res.traffic, loading: false, error: null } })
    return res
  },

  /* ===================== жалоба (модерация, этап 3) ===================== */
  async checkReport() {
    return api.reportCheck({ token: get().reportToken })
  },
  // Отправить жалобу на пересланное сообщение. Аутентификация — по подписанному initData
  // запуска (бэкенд валидирует подпись + антиспам); токен из диплинка адресует сообщение.
  async submitReport(text) {
    const init = host.getInitData() || {}
    return api.report({
      messenger: host.name === 'telegram' ? 'tg' : 'max',
      initData: init.raw,
      userId: init.unsafe?.user?.id,
      token: get().reportToken,
      text,
    })
  },

  /* ===================== навигация ===================== */
  setTab(tab) { host.haptic('selection'); set((s) => ({ nav: { ...s.nav, tab, stack: [] } })) },
  push(name, props = {}) { set((s) => ({ nav: { ...s.nav, stack: [...s.nav.stack, { name, props }] } })) },
  pop() { set((s) => ({ nav: { ...s.nav, stack: s.nav.stack.slice(0, -1) } })) },
  resetStack() { set((s) => ({ nav: { ...s.nav, stack: [] } })) },
  openSheet(name, props = {}) { set((s) => ({ nav: { ...s.nav, sheet: { name, props } } })) },
  closeSheet() { set((s) => ({ nav: { ...s.nav, sheet: null } })) },

  /** Единая реакция на «Назад» (нативная кнопка/жест/чип в шапке). */
  back() {
    const { nav, phase } = get()
    if (nav.sheet) { get().closeSheet(); return true }
    if (nav.stack.length) { get().pop(); return true }
    if (phase === 'auth' && get()._authPop) return get()._authPop()
    return false
  },
  _authPop: null,
  setAuthPop(fn) { set({ _authPop: fn }) },

  /* ===================== тосты ===================== */
  showToast(text, icon = 'check') {
    set({ toast: { text, icon } })
    clearTimeout(get()._toastT)
    const t = setTimeout(() => set({ toast: null }), 1900)
    set({ _toastT: t })
  },
  _toastT: null,

  setOnline(online) { set({ online }) },
}))

function errText(err) {
  if (!err) return 'Что-то пошло не так'
  if (err.code === 'network' || err.status === 0) return 'offline'
  if (err.code === 'unauthorized') return 'Требуется вход'
  // Ошибка без status — не ApiError, а внутренний сбой JS: его текст техничен (и по-английски),
  // пользователю показываем заглушку. ApiError.message уже дружелюбный (client.js).
  if (err.status == null) return 'Что-то пошло не так'
  return err.message || 'Что-то пошло не так'
}

/* Сетевой статус → стор. */
if (typeof window !== 'undefined') {
  window.addEventListener('online', () => useStore.getState().setOnline(true))
  window.addEventListener('offline', () => useStore.getState().setOnline(false))
}
