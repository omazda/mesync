/* legal.jsx — interstitial явного принятия актуальной оферты и политики.
 * Показывается после входа, но до оплаты, источников и правил, если backend не видит
 * акцепт текущих редакций документов.
 */
import React, { useState } from 'react'
import { Screen, HostHeader, Avatar, Icon, Btn } from '../components/ui.jsx'
import { useStore } from '../store/store.js'
import host from '../host/host.js'
import { errorMessage } from '../api/client.js'
import {
  LegalLinks, LEGAL_TERMS_VERSION, LEGAL_PRIVACY_VERSION,
} from './_shared.jsx'

export function SLegal() {
  const account = useStore((s) => s.account)
  const acceptLegal = useStore((s) => s.acceptLegal)
  const showToast = useStore((s) => s.showToast)
  const [checked, setChecked] = useState(false)
  const [loading, setLoading] = useState(false)

  const legal = account?.legal || {}
  const termsVersion = legal.requiredTermsVersion || LEGAL_TERMS_VERSION
  const privacyVersion = legal.requiredPrivacyVersion || LEGAL_PRIVACY_VERSION
  const isUpdate = Boolean(legal.termsVersion || legal.privacyVersion)

  const submit = async () => {
    if (!checked || loading) return
    setLoading(true)
    try {
      await acceptLegal()
      host.haptic('success')
      showToast('Условия приняты', 'check')
    } catch (err) {
      host.haptic('error')
      showToast(errorMessage(err, 'Не удалось сохранить согласие'), 'alert')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Screen>
      <HostHeader title="Условия сервиса" />
      <div className="screen-body" style={{ padding: '8px 24px 20px' }}>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', gap: 14 }}>
          <Avatar size={64} tone="av-blue" icon={<Icon.shield />} />
          <div className="t-headline text-pretty">{isUpdate ? 'Обновлены документы' : 'Примите документы'}</div>
          <div className="t-body-sm sec text-pretty" style={{ maxWidth: 340 }}>
            {isUpdate
              ? 'Перед продолжением нужно принять актуальные редакции пользовательского соглашения и политики конфиденциальности.'
              : 'Это требуется перед оплатой, подключением источников и настройкой правил пересылки.'}
          </div>
        </div>
        <div className="note-card" style={{ marginTop: 20 }}>
          <div className="t-footnote sec text-pretty">
            Редакции: соглашение от {termsVersion}, политика от {privacyVersion}. Русская версия документов имеет приоритет.
          </div>
          <LegalLinks style={{ marginTop: 10, textAlign: 'left' }} />
        </div>
      </div>
      <div className="footer-area">
        <label className="legal-check">
          <input type="checkbox" checked={checked} onChange={(e) => setChecked(e.target.checked)} />
          <span>Я прочитал и принимаю документы</span>
        </label>
        <Btn disabled={!checked || loading} loading={loading} onClick={submit}>Продолжить</Btn>
      </div>
    </Screen>
  )
}
