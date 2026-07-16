import React from 'react'

export default function Placeholder({ title }) {
  return (
    <>
      <div className="view-head">
        <div>
          <div className="lbl eyebrow">Раздел</div>
          <h1>{title}</h1>
        </div>
      </div>
      <div className="card pad" style={{ textAlign: 'center', padding: '48px 24px' }}>
        <div style={{ fontSize: 34, marginBottom: 8 }}>🚧</div>
        <div style={{ fontSize: 15, fontWeight: 600 }}>Раздел появится на следующем этапе</div>
        <p className="muted" style={{ fontSize: 13, marginTop: 6 }}>
          Сейчас готов фундамент панели (вход, настройки, аудит). «{title}» — в одном из этапов 4.2–4.6.
        </p>
      </div>
    </>
  )
}
