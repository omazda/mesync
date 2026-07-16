/* report.jsx — экран жалобы на пересланное сообщение (модерация, этап 3).
 *
 * Открывается по диплинку startapp=r_<token> из подписи копии («Пожаловаться»).
 * Отдельная лёгкая фаза (см. store.bootstrap / Navigator): БЕЗ онбординга, пейволла и
 * создания аккаунта — жалобщик обычно не клиент MeSync. Аутентификация и антиспам — на
 * бэкенде по подписанному initData; сам текст сообщения бот перечитывает и проверяет сам. */
import React, { useEffect, useState } from 'react'
import { Screen, HostHeader, MainButton, Avatar, Icon, Spinner } from '../components/ui.jsx'
import { useStore } from '../store/store.js'
import host from '../host/host.js'
import { errorMessage } from '../api/client.js'
import { BOT_NAME } from './_shared.jsx'

export function SReport() {
  const checkReport = useStore((s) => s.checkReport)
  const submitReport = useStore((s) => s.submitReport)
  const [text, setText] = useState('')
  const [checking, setChecking] = useState(true)
  const [blocked, setBlocked] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [done, setDone] = useState(false)

  useEffect(() => {
    let alive = true
    ;(async () => {
      try {
        await checkReport()
        if (alive) setChecking(false)
      } catch (err) {
        if (!alive) return
        host.haptic('error')
        setBlocked(errorMessage(err, 'Жалобы временно недоступны. Попробуйте позже.'))
        setChecking(false)
      }
    })()
    return () => { alive = false }
  }, [checkReport])

  const onSubmit = async () => {
    setError(null)
    setLoading(true)
    try {
      await submitReport(text)
      host.haptic('success')
      setDone(true)
    } catch (err) {
      host.haptic('error')
      setError(errorMessage(err, 'Не удалось отправить жалобу. Попробуйте ещё раз позже.'))
      setLoading(false)
    }
  }

  if (done) {
    return (
      <Screen>
        <HostHeader title="Жалоба отправлена" close />
        <div className="screen-body" style={{ padding: '8px 24px 20px' }}>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center',
            textAlign: 'center', gap: 14, marginTop: 24 }}>
            <Avatar size={64} tone="av-green" icon={<Icon.check />} />
            <div className="t-headline text-pretty">Спасибо за бдительность</div>
            <div className="t-body-sm sec text-pretty" style={{ maxWidth: 330 }}>
              Мы проверим это сообщение автоматически. Если оно нарушает правила — копия будет
              удалена. Повторно жаловаться на него не нужно.
            </div>
          </div>
        </div>
        <MainButton label="Закрыть" onClick={() => host.close()} />
      </Screen>
    )
  }

  if (checking) {
    return (
      <Screen>
        <HostHeader title="Пожаловаться" close />
        <div className="screen-body" style={{ padding: '8px 24px 20px' }}>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center',
            textAlign: 'center', gap: 14, marginTop: 30 }}>
            <Spinner size={36} />
            <div className="t-headline text-pretty">Проверяем группу</div>
            <div className="t-body-sm sec text-pretty" style={{ maxWidth: 330 }}>
              Проверяем, что бот всё ещё обслуживает чат с этим сообщением.
            </div>
          </div>
        </div>
      </Screen>
    )
  }

  if (blocked) {
    return (
      <Screen>
        <HostHeader title="Пожаловаться" close />
        <div className="screen-body" style={{ padding: '8px 24px 20px' }}>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center',
            textAlign: 'center', gap: 14, marginTop: 24 }}>
            <Avatar size={64} tone="av-orange" icon={<Icon.alert />} />
            <div className="t-headline text-pretty">Жалоба недоступна</div>
            <div className="t-body-sm sec text-pretty" style={{ maxWidth: 330 }}>
              {blocked}
            </div>
          </div>
        </div>
        <MainButton label="Закрыть" onClick={() => host.close()} />
      </Screen>
    )
  }

  return (
    <Screen>
      <HostHeader title="Пожаловаться" close />
      <div className="screen-body" style={{ padding: '8px 24px 20px' }}>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center',
          textAlign: 'center', gap: 14 }}>
          <Avatar size={64} tone="av-red" icon={<Icon.shield />} />
          <div className="t-headline text-pretty">Пожаловаться на сообщение</div>
          <div className="t-body-sm sec text-pretty" style={{ maxWidth: 330 }}>
            Сообщение переслал бот {BOT_NAME}. Мы проверим его автоматически и удалим копию, если
            оно нарушает закон или правила. По желанию опишите, что не так.
          </div>
        </div>
        <div style={{ marginTop: 22 }}>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Что не так с этим сообщением? (необязательно)"
            rows={4}
            maxLength={1000}
            style={{ width: '100%', resize: 'none', borderRadius: 12, padding: '12px 14px',
              border: '1px solid var(--separator, rgba(128,128,128,0.28))',
              background: 'var(--fill-strong, rgba(128,128,128,0.10))', color: 'inherit',
              fontSize: 15, lineHeight: 1.4, fontFamily: 'inherit', outline: 'none',
              boxSizing: 'border-box' }} />
          {error && (
            <div className="t-footnote text-pretty" style={{ color: 'var(--danger)', marginTop: 10 }}>
              {error}
            </div>
          )}
        </div>
      </div>
      <MainButton label="Отправить жалобу" kind="destructive" loading={loading}
        onClick={onSubmit} />
    </Screen>
  )
}
