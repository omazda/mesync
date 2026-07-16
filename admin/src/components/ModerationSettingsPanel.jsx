import React from 'react'

export default function ModerationSettingsPanel({ settings, onPatch, busy = false }) {
  const s = settings
  const reportsOn = !!s?.moderation_reports_enabled
  const aiEnabled = !!s?.moderation_ai_enabled
  const gateMode = s?.moderation_gate_mode || 'off'
  const gateOn = gateMode !== 'off'
  const moderationOn = reportsOn || gateOn
  const aiOn = moderationOn && aiEnabled

  const summary = !moderationOn
    ? 'Выключена'
    : reportsOn && aiOn && gateOn
      ? 'Жалобы, ИИ и проверка перед отправкой'
      : reportsOn && aiOn
        ? 'Жалобы с ИИ-классификацией'
        : reportsOn
          ? 'Только ручные жалобы'
          : 'Проверка перед отправкой'

  const disabled = !s || busy
  const setModerationOn = (val) => {
    if (val) {
      onPatch({
        moderation_reports_enabled: true,
        moderation_ai_enabled: true,
        moderation_gate_mode: gateOn ? gateMode : 'shadow',
      })
    } else {
      onPatch({
        moderation_reports_enabled: false,
        moderation_ai_enabled: false,
        moderation_gate_mode: 'off',
      })
    }
  }
  const setReportsOn = (val) => onPatch({
    moderation_reports_enabled: val,
    moderation_gate_mode: !val && !gateOn ? 'off' : gateMode,
  })
  const setAiOn = (val) => onPatch({
    moderation_ai_enabled: val,
    moderation_gate_mode: val ? gateMode : 'off',
  })
  const setGateMode = (mode) => onPatch({
    moderation_ai_enabled: mode === 'off' ? aiEnabled : true,
    moderation_gate_mode: mode,
  })

  return (
    <div className="card pad" style={{ maxWidth: 760 }}>
      <div className="sec-title">
        <h3>Модерация</h3>
        <span className="lbl">{summary}</span>
      </div>

      <div className="set-row">
        <div className="info">
          <div className="t">Модерация доступна</div>
          <div className="d">Главный выключатель. При отключении новые ссылки «Пожаловаться» не добавляются, старые ссылки показывают сообщение о недоступности, а проверка перед отправкой выключается.</div>
        </div>
        <button className={`toggle${moderationOn ? ' on' : ''}`}
                disabled={disabled} aria-pressed={String(moderationOn)}
                onClick={() => setModerationOn(!moderationOn)}
                title="Модерация доступна" />
      </div>

      {!moderationOn && (
        <div className="warnbox" style={{ marginTop: 4 }}>
          <span>⏸</span>
          <span><b>Модерация отключена.</b> Пользователь со старой ссылкой «Пожаловаться» увидит, что модерация временно недоступна.</span>
        </div>
      )}

      <div className="set-row">
        <div className="info">
          <div className="t">Жалобы читателей</div>
          <div className="d">Добавляет ссылку «Пожаловаться» под новыми копиями и принимает обращения по уже выданным ссылкам.</div>
        </div>
        <button className={`toggle${reportsOn ? ' on' : ''}`}
                disabled={disabled} aria-pressed={String(reportsOn)}
                onClick={() => setReportsOn(!reportsOn)}
                title="Жалобы читателей" />
      </div>

      <div className="set-row">
        <div className="info">
          <div className="t">ИИ-классификация</div>
          <div className="d">Классифицирует жалобы автоматически. Также нужна для проверки перед отправкой; при отключении gate переводится в Off.</div>
        </div>
        <button className={`toggle${aiOn ? ' on' : ''}`}
                disabled={disabled || !moderationOn} aria-pressed={String(aiOn)}
                onClick={() => setAiOn(!aiOn)}
                title="ИИ-классификация" />
      </div>

      <div className="set-row">
        <div className="info">
          <div className="t">Проверка перед отправкой</div>
          <div className="d">Off не проверяет сообщения до пересылки. Shadow только логирует нарушения. Enforce блокирует доставку подтверждённых нарушений.</div>
        </div>
        <div className="seg">
          {[
            ['off', 'Off'],
            ['shadow', 'Shadow'],
            ['enforce', 'Enforce'],
          ].map(([value, label]) => (
            <button key={value}
                    className={gateMode === value ? `on${value === 'enforce' ? ' enforce' : ''}` : ''}
                    disabled={disabled || (!aiOn && value !== 'off')}
                    onClick={() => setGateMode(value)}>{label}</button>
          ))}
        </div>
      </div>
    </div>
  )
}
