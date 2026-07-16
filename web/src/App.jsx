/* App.jsx — корень приложения: тема, гейтинг/бутстрап, нативная «Назад»,
 * глобальные тост и оффлайн-баннер. */
import React, { useEffect } from 'react'
import { AppRoot } from '@telegram-apps/telegram-ui'
import Navigator from './nav/Navigator.jsx'
import { useStore } from './store/store.js'
import { useScheme } from './host/useScheme.js'
import host from './host/host.js'
import { Toast, Icon } from './components/ui.jsx'

/* Заглушка на случай краха рендера: пользователь видит дружелюбный экран с кнопкой
 * перезапуска вместо белого экрана/сырого текста ошибки. Детали — только в console. */
class ErrorBoundary extends React.Component {
  constructor(props) { super(props); this.state = { crashed: false } }
  static getDerivedStateFromError() { return { crashed: true } }
  componentDidCatch(err, info) { try { console.error('UI crash:', err, info) } catch (_) {} }
  render() {
    if (!this.state.crashed) return this.props.children
    return (
      <div style={{ minHeight: '100%', display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center', gap: 12, padding: 24, textAlign: 'center' }}>
        <div style={{ fontSize: 44 }}>😔</div>
        <div style={{ fontSize: 17, fontWeight: 600 }}>Что-то пошло не так</div>
        <div style={{ fontSize: 14, opacity: 0.65 }}>
          Мы уже знаем о проблеме. Перезапустите приложение — это обычно помогает.
        </div>
        <button
          onClick={() => { try { window.location.reload() } catch (_) {} }}
          style={{ marginTop: 8, padding: '10px 20px', borderRadius: 10, border: 'none',
            background: '#2990ff', color: '#fff', fontSize: 15, fontWeight: 600 }}>
          Перезапустить
        </button>
      </div>
    )
  }
}

export default function App() {
  const scheme = useScheme()
  const bootstrap = useStore((s) => s.bootstrap)
  const nav = useStore((s) => s.nav)
  const back = useStore((s) => s.back)
  const toast = useStore((s) => s.toast)
  const online = useStore((s) => s.online)
  const isExternalBrowser = host.name === 'browser'
  const isMarketActivation = typeof window !== 'undefined'
    && window.location.pathname.replace(/\/+$/, '') === '/ya_market'
  const isPublicStandalone = isExternalBrowser || isMarketActivation

  useEffect(() => {
    host.ready()
    // Публичная веб-страница — только переходник. Сессию для неё
    // не загружаем: вход всегда начинается после запуска mini-app в мессенджере.
    if (!isPublicStandalone) bootstrap()
  }, [bootstrap, isPublicStandalone])

  // Нативная кнопка «Назад» хоста ↔ навигация приложения.
  const canBack = !!nav.sheet || nav.stack.length > 0
  useEffect(() => host.backButton(canBack, () => back()), [canBack])

  // Цвет фона страницы под тему (для статус-бара хоста/safe-area).
  useEffect(() => {
    const bg = scheme === 'dark' ? '#000000' : '#FFFFFF'
    document.body.style.background = bg
    const meta = document.querySelector('meta[name="theme-color"]')
    if (meta) meta.setAttribute('content', bg)
  }, [scheme])

  const ToastIcon = (toast && Icon[toast.icon]) || Icon.check
  const platform = host.platform === 'android' ? 'base' : 'ios'

  return (
    <AppRoot appearance={scheme} platform={platform} style={{ height: '100%' }}>
      <div className={`app ${scheme}${isPublicStandalone ? ' browser-public' : ''}`}>
        {!online && (
          <div className="offline-bar"><Icon.wifiOff size={14} />Нет соединения</div>
        )}
        <ErrorBoundary>
          <Navigator />
        </ErrorBoundary>
        {toast && <Toast icon={<ToastIcon size={18} />}>{toast.text}</Toast>}
      </div>
    </AppRoot>
  )
}
