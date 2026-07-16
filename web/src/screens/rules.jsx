/* rules.jsx — пустое состояние, список и редактор правил: данные из стора/API,
 * состояния загрузка/пусто/гейт/лимит/ошибка/оффлайн,
 * живая валидация и предпросмотр. Pull-to-refresh убран: жест двигал верх экрана
 * и выглядел как случайная прокрутка; данные обновляются при входе и действиями. */
import React, { useEffect, useMemo, useState } from 'react'
import {
  Screen, HostHeader, MainButton, Btn, BtnLink, PillButton, Avatar, MBadge, TBadge, Banner,
  Switch, DirSegment, DIRS, Spinner, Icon,
} from '../components/ui.jsx'
import { useStore } from '../store/store.js'
import host from '../host/host.js'
import { errorMessage } from '../api/client.js'
import { LargeTitle, TabFooter } from './_shared.jsx'
import { selectionSubtitle, selectionTitle } from '../utils/sourceTopics.js'

/* Иконка типа источника для аватара (по data-shape: "channel"|"group"). */
const typeIcon = (type) => (type === 'channel' ? <Icon.megaphone /> : <Icon.people />)

/* Слот источника на пустом экране: пунктирная заглушка, при добавленном
 * источнике — зелёная отметка «готов»; pulse подсвечивает недостающий слот. */
function Slot({ filled, pulse, label }) {
  return (
    <div className={`slot${filled ? ' filled' : ''}${pulse ? ' pulse-ring' : ''}`}>
      {filled ? <span className="slot-check"><Icon.check size={15} /></span> : <Icon.source size={24} />}
      <span>{label}</span>
    </div>
  )
}

/* ============================ S6 — Правила (пусто) ============================ */
export function S6() {
  const sources = useStore((s) => s.sources)
  const loadSources = useStore((s) => s.loadSources)
  const setTab = useStore((s) => s.setTab)
  const push = useStore((s) => s.push)
  const openSheet = useStore((s) => s.openSheet)

  useEffect(() => { loadSources() }, [loadSources])

  // Привязанные источники (готовые к использованию в правилах).
  const bound = (sources.items || []).filter((s) => s.status === 'ok').length
  const need = 2
  const have = Math.min(bound, need)
  const oneMore = have === 1

  const heading = oneMore ? 'Остался один шаг' : 'Здесь пока пусто'
  const subText = oneMore
    ? 'Добавьте ещё один источник — и можно будет создать первое правило пересылки между ними.'
    : 'Чтобы создать первое правило, добавьте минимум два источника — чаты или каналы, между которыми бот будет переносить сообщения.'

  const addSource = () => { host.haptic('selection'); setTab('sources'); push('S8') }

  return (
    <Screen grouped>
      <HostHeader title="" onGrouped />
      <div className="screen-body grouped">
        <LargeTitle>Правила</LargeTitle>
        {/* Аврора-hero в языке пейволла: слоты источников соединены «мостом»
            на паузе — поток оживёт, когда появится первое правило. */}
        <div className="body-pad" style={{ marginTop: 8 }}>
          <section className="pw-hero pw-in" style={{ paddingBottom: 18 }}>
            <div className="pw-bridge paused" style={{ maxWidth: 300, margin: '0 auto' }}>
              <Slot filled={have >= 1} label="Источник A" />
              <span className="pw-wires" style={{ color: 'var(--accent)', maxWidth: 44 }}>
                <i className="pw-wire" /><i className="pw-wire" />
              </span>
              <Slot filled={false} pulse={oneMore} label="Источник B" />
            </div>
            <h2 className="pw-title" style={{ fontSize: 22, marginTop: 16 }}>{heading}</h2>
            <p className="pw-lead">{subText}</p>
          </section>
        </div>
      </div>
      <TabFooter sourcesBadge>
        {/* Прогресс — в футере НАД кнопкой: в теле экрана на невысоких окнах
            (неразвёрнутый webview MAX) он уезжал за футер и казался «под кнопкой». */}
        <div style={{ padding: '0 2px 12px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 7 }}>
            <span className="t-footnote sec">Добавлено источников</span>
            <span className="t-footnote" style={{ fontWeight: 600 }}>{have} из {need}</span>
          </div>
          <div className="progress-track"><div className="progress-fill" style={{ width: `${Math.max(4, (have / need) * 100)}%` }} /></div>
        </div>
        <Btn before={<Icon.plus size={20} />} style={{ marginBottom: 6 }} onClick={addSource}>Добавить источник</Btn>
        <BtnLink style={{ display: 'block', margin: '0 auto' }} onClick={() => openSheet('whatIsSource')}>Что такое источник?</BtnLink>
      </TabFooter>
    </Screen>
  )
}

/* ============================ S9 — Правила (список) ============================ */
/* Эндпоинт правила: аватар + название в строку, под ними — бейджи мессенджера/типа
 * этого же источника, выровненные по левому краю аватарки. Значок — если включена подпись. */
function Endpoint({ ep, signOn }) {
  const { messenger, type, title, tone, avatar } = ep
  const badgeType = type === 'topic' ? 'topic' : ep.isForum ? 'supergroup' : type
  return (
    <div style={{ minWidth: 0, flex: 1, display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 9, minWidth: 0 }}>
        <Avatar size={38} tone={tone} icon={typeIcon(type)} src={avatar} />
        <span className="t-headline truncate" style={{ fontSize: 16, flex: '1 1 auto' }}>{title}</span>
        {signOn && (
          <span className="sec" title="Подпись отправителя включена" style={{ flex: '0 0 auto', display: 'inline-flex' }}>
            <Icon.signature size={15} />
          </span>
        )}
      </div>
      <div className="cell-sub rule-badges" style={{ display: 'flex', alignItems: 'center' }}>
        <MBadge m={messenger} /><TBadge type={badgeType} compact />
      </div>
    </div>
  )
}

/* Поток правила — язык «живого моста» с пейволла: пунктир бежит по направлению
 * переноса; у правила на паузе или со сбоем поток замирает. Стрелка дублирует
 * направление, когда анимация выключена (reduced-motion, пауза). */
function RuleFlow({ dir, active }) {
  const d = DIRS[dir] || DIRS.both
  const Arrow = dir === 'to' ? Icon.arrowR : dir === 'from' ? Icon.arrowL : Icon.arrowBoth
  return (
    <span className={`rule-flow${active ? '' : ' off'}`} title={d.word} aria-label={d.word}>
      {dir !== 'from' && <i className="pw-wire fwd" />}
      <span className="rule-flow-arrow"><Arrow size={15} /></span>
      {dir !== 'to' && <i className="pw-wire rev" />}
    </span>
  )
}

function RuleCard({ rule, onOpen, onToggle, onDelete, onFix, onDismissWarn }) {
  const [menuOpen, setMenuOpen] = useState(false)
  const { a, b, dir, signAB, signBA, status } = rule
  // «подпись вкл.» у эндпоинта-ИСТОЧНИКА: A подписывается в потоке A→B (signAB),
  // B — в потоке B→A (signBA); только когда направление этот поток включает.
  const aSignOn = signAB && (dir === 'to' || dir === 'both')
  const bSignOn = signBA && (dir === 'from' || dir === 'both')
  const paused = status === 'paused'
  const broken = status === 'broken'
  const held = !!rule.moderationHold
  // Жёлтый баннер-продолжение снизу карточки — сбой доставки. У «сломанного» правила
  // не показываем: там свой баннер «Исправить» сверху.
  const showWarn = rule.deliveryWarn && !broken && !held
  return (
    <div className="note-card" style={{ padding: 0, marginBottom: 10 }}>
      {held && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px', background: 'var(--amber-weak)', borderRadius: '12px 12px 0 0' }}>
          <span style={{ color: 'var(--amber)' }}><Icon.shield size={16} /></span>
          <span className="t-footnote" style={{ flex: 1, fontWeight: 500 }}>
            Пересылка остановлена модерацией.
          </span>
        </div>
      )}
      {!held && broken && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px', background: 'var(--danger-weak)', borderRadius: '12px 12px 0 0' }}>
          <span className="dng"><Icon.alert size={16} /></span>
          <span className="t-footnote dng" style={{ flex: 1, fontWeight: 500 }}>{rule.brokenReason || 'Источник недоступен — правило не работает'}</span>
          <PillButton onClick={onFix}>Исправить</PillButton>
        </div>
      )}
      {/* Шапка: №N + статус слева; ⋯ справа открывает меню действий. Приглушение для
          paused применяем ТОЛЬКО к инфо-части (и телу ниже), а НЕ к ⋯/меню — иначе
          opacity родителя ложится и на выпадающее меню (потомок не бывает непрозрачнее). */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 8px 0 14px' }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1, minWidth: 0, opacity: paused || held ? 0.62 : 1 }}>
          {rule.number != null && <span className="sec" style={{ fontSize: 15, fontWeight: 700 }}>№{rule.number}</span>}
          <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span className={`dot ${held ? 'orange' : broken ? 'red' : paused ? 'gray' : 'green'}`} />
            <span style={{ fontSize: 15, fontWeight: 500, color: paused || broken || held ? 'var(--text-secondary)' : 'var(--text)' }}>
              {held ? 'Остановлено' : broken ? 'Не работает' : paused ? 'Пауза' : 'Активно'}
            </span>
          </span>
        </span>
        {/* ⋯ — меню действий. Для moderation hold оставляем только безопасное действие. */}
        <span style={{ position: 'relative', flex: '0 0 auto' }}>
          <span className="card-corner-btn" aria-label="Действия с правилом"
            onClick={(e) => { e.stopPropagation(); setMenuOpen((v) => !v) }}>
            <Icon.dots size={20} />
          </span>
          {menuOpen && (
            <>
              <div onClick={(e) => { e.stopPropagation(); setMenuOpen(false) }}
                style={{ position: 'fixed', inset: 0, zIndex: 40 }} />
              <div className="rule-menu" onClick={(e) => e.stopPropagation()}>
                {!held && (
                  <button className="rule-menu-item" onClick={() => { setMenuOpen(false); onToggle() }}>
                    {paused ? <Icon.play size={18} /> : <Icon.pause size={18} />}
                    {paused ? 'Активировать' : 'Отключить'}
                  </button>
                )}
                {!held && (
                  <button className="rule-menu-item" onClick={() => { setMenuOpen(false); onOpen() }}>
                    <Icon.edit size={18} /> Редактировать
                  </button>
                )}
                <button className="rule-menu-item danger" onClick={() => { setMenuOpen(false); onDelete() }}>
                  <Icon.trash size={18} /> Удалить
                </button>
              </div>
            </>
          )}
        </span>
      </div>
      {/* Тело (тап → редактор): два источника в строку, бейджи каждого — под ним
          (по левому краю своей аватарки); направление стрелкой между блоками. */}
      <div onClick={held ? undefined : onOpen} style={{ cursor: held ? 'default' : 'pointer', padding: '8px 14px 14px', opacity: paused || held ? 0.62 : 1 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <Endpoint ep={a} signOn={aSignOn} />
          <RuleFlow dir={dir} active={!paused && !broken && !held} />
          <Endpoint ep={b} signOn={bSignOn} />
        </div>
      </div>
      {/* Предупреждение о сбое доставки — жёлтая полоса, продолжающая карточку снизу
          (скруглена под нижние углы). «Скрыть» прячет до следующего сбоя. */}
      {showWarn && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px', background: 'var(--amber-weak)', borderTop: '1px solid var(--separator)', borderRadius: '0 0 12px 12px' }}>
          <span style={{ flex: '0 0 auto', fontSize: 15, lineHeight: 1 }}>⚠️</span>
          <span className="t-footnote" style={{ flex: 1, fontWeight: 500, color: 'var(--text)' }}>
            Не удалось отправить сообщение — возможно, на принимающей стороне неполадки. Проверьте права бота на отправку сообщений.
          </span>
          <button onClick={(e) => { e.stopPropagation(); onDismissWarn && onDismissWarn() }}
            style={{ flex: '0 0 auto', background: 'none', border: 'none', color: 'var(--text-secondary)', fontSize: 13, fontWeight: 600, cursor: 'pointer', padding: '4px 2px' }}>
            Скрыть
          </button>
        </div>
      )}
    </div>
  )
}

export function S9() {
  const rules = useStore((s) => s.rules)
  const online = useStore((s) => s.online)
  const subscription = useStore((s) => s.subscription)
  const loadRules = useStore((s) => s.loadRules)
  const setRuleStatus = useStore((s) => s.setRuleStatus)
  const showToast = useStore((s) => s.showToast)
  const push = useStore((s) => s.push)
  const openSheet = useStore((s) => s.openSheet)
  const dismissRuleWarning = useStore((s) => s.dismissRuleWarning)

  useEffect(() => { loadRules() }, [loadRules])

  const items = rules.items || []
  const activeCount = rules.activeCount || 0
  const limit = rules.limit || 10
  const limitText = `Достигнут лимит ${limit} активных правил по вашему тарифу. Удалите одно, чтобы создать новое.`
  const atLimit = activeCount >= limit
  const subActive = !subscription || subscription.status === 'active'

  const loading = rules.loading && items.length === 0
  const offline = !online || rules.error === 'offline'
  const errored = rules.error && rules.error !== 'offline'

  // Переключение паузы/возобновления кнопкой включить/выключить в подвале карточки.
  const toggle = async (rule) => {
    const next = rule.status === 'paused' ? 'active' : 'paused'
    host.haptic('selection')
    try {
      await setRuleStatus(rule.id, next)
      showToast(next === 'paused' ? 'Правило на паузе' : 'Правило возобновлено', next === 'paused' ? 'pause' : 'play')
    } catch (_) { showToast('Не удалось изменить правило', 'alert') }
  }

  const create = () => { if (atLimit || !subActive) return; host.haptic('selection'); push('S10') }

  let body
  if (loading) {
    body = (
      <div className="body-pad" style={{ marginTop: 8 }}>
        {[0, 1, 2].map((i) => (
          <div key={i} className="note-card" style={{ marginBottom: 10, height: 156 }}>
            <div className="skeleton" style={{ width: '55%', height: 14, borderRadius: 7 }} />
            <div className="skeleton" style={{ width: '40%', height: 11, borderRadius: 6, marginTop: 30 }} />
            <div className="skeleton" style={{ width: '55%', height: 14, borderRadius: 7, marginTop: 30 }} />
          </div>
        ))}
      </div>
    )
  } else if (errored || (offline && items.length === 0)) {
    body = (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', padding: '60px 28px 0', color: 'var(--text-secondary)' }}>
        <span style={{ color: 'var(--text-tertiary)' }}>{offline ? <Icon.wifiOff size={40} /> : <Icon.alert size={40} />}</span>
        <div className="t-headline" style={{ marginTop: 14, color: 'var(--text)' }}>{offline ? 'Нет соединения' : 'Не удалось загрузить'}</div>
        <PillButton icon={<Icon.refresh size={16} />} style={{ marginTop: 14 }} onClick={() => loadRules()}>Обновить</PillButton>
      </div>
    )
  } else if (items.length === 0) {
    // Источники готовы (есть правила = нет, но раздел вызван) — приглашение создать.
    body = (
      <div className="body-pad" style={{ marginTop: 8 }}>
        <Banner tone="norm" icon={<Icon.check size={20} />}>Источники готовы. Создайте первое правило.</Banner>
      </div>
    )
  } else {
    body = (
      <div className="body-pad" style={{ marginTop: 8 }}>
        {!subActive && (
          <Banner tone="warn" icon={<Icon.alert size={20} />} title="Пересылка приостановлена">
            Правила приостановлены. Возобновите подписку, чтобы продолжить пересылку.
          </Banner>
        )}
        {subActive && atLimit && (
          <div style={{ marginBottom: 10 }}>
            <Banner tone="info" icon={<Icon.alert size={20} />}>{limitText}</Banner>
          </div>
        )}
        {items.map((rule) => (
          <RuleCard
            key={rule.id}
            rule={rule}
            onOpen={() => push('S10', { ruleId: rule.id })}
            onToggle={() => toggle(rule)}
            onDelete={() => openSheet('deleteRule', { ruleId: rule.id })}
            onFix={(e) => { e.stopPropagation(); push('S10', { ruleId: rule.id }) }}
            onDismissWarn={() => dismissRuleWarning(rule.id)}
          />
        ))}
      </div>
    )
  }

  return (
    <Screen grouped>
      <HostHeader title="" onGrouped />
      <div className="screen-body grouped">
        <LargeTitle after={<span className="t-title-lg sec" style={{ fontWeight: 600, color: atLimit ? 'var(--danger)' : undefined }}>{activeCount}/{limit}</span>}>Правила</LargeTitle>
        {body}
      </div>
      <TabFooter sourcesBadge>
        <Btn
          kind={atLimit || !subActive ? 'gray' : 'primary'}
          disabled={atLimit || !subActive}
          before={<Icon.plus size={20} />}
          onClick={create}
        >Создать правило</Btn>
      </TabFooter>
    </Screen>
  )
}

/* ============================ S10 — Редактор правила ============================ */

/* Справка «Что переносится»: список материалов, поддерживаемых движком пересылки.
 * Набор взят из реального диспетчера (src/control/integration.py) и нормализаторов
 * (telegram_sync/content.py, max_sync/content.py) — он одинаков для всех направлений
 * и пар мессенджеров (различается лишь способ доставки, см. сноску). Чисто
 * информационный блок, бэкенд не затрагивает. */
const FORWARD_SUPPORTED = [
  'Текст и форматирование',
  'Ссылки и упоминания',
  'Фото и изображения',
  'Видео, GIF и видеосообщения',
  'Аудио и голосовые',
  'Документы и файлы',
  'Стикеры',
  'Альбомы из нескольких файлов',
]
const FORWARD_UNSUPPORTED = [
  'Опросы и викторины',
  'Геолокация и контакты',
  'Платное медиа, розыгрыши, счёт на оплату',
]
const FORWARD_NOTE = 'Крупные файлы переносятся целиком, но расходуют медиа-трафик. Когда трафик закончится, вместо файла придёт ссылка на оригинал.'
// Примечание к тексту для направления MAX→Telegram: цитаты (блок-цитаты) внутри поста
// MAX не отдаёт через свой Bot API (проверено), поэтому в Telegram их оформление
// воссоздать нельзя — сам текст цитаты переносится, но без оформления цитатой.
const FORWARD_NOTE_MAX_TG = 'Цитаты внутри текста при переносе из MAX в Telegram не сохраняются: MAX не передаёт их оформление. Сам текст цитаты переносится.'

/* Строка справки: зелёная галочка (переносится) либо приглушённый крестик (нет). */
function MaterialRow({ ok, children }) {
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10, padding: '5px 0' }}>
      <span style={{ flex: '0 0 auto', marginTop: 1, color: ok ? 'var(--success)' : 'var(--text-tertiary)' }}>
        {ok ? <Icon.check size={18} /> : <Icon.close size={15} />}
      </span>
      <span className="t-body-sm" style={{ color: ok ? 'var(--text)' : 'var(--text-secondary)' }}>{children}</span>
    </div>
  )
}

function SourceSelect({ label, ep, eps, all, onClick }) {
  const list = eps || (ep ? [ep] : [])
  if (list.length === 0) {
    return (
      <div className="cell tap" style={{ borderRadius: 12, minHeight: 60 }} onClick={onClick}>
        <div className="cell-before">
          <span style={{ width: 36, height: 36, borderRadius: 9, background: 'var(--fill)', color: 'var(--accent)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><Icon.plus size={20} /></span>
        </div>
        <div className="cell-main"><div className="cell-title sec">{label}</div></div>
        <span className="chevron"><Icon.chevron size={18} /></span>
      </div>
    )
  }
  if (list.length > 1) {
    const first = list[0]
    const title = selectionTitle(list, all)
    const sub = selectionSubtitle(list, all)
    return (
      <div className="cell tap" style={{ borderRadius: 12, minHeight: 64 }} onClick={onClick}>
        <div className="cell-before"><Avatar size={38} tone={first.tone} icon={typeIcon(first.type)} src={first.avatar} /></div>
        <div className="cell-main">
          <div className="cell-title">{title}</div>
          <div className="cell-sub truncate" style={{ marginTop: 3 }}>{sub || `${list.length} выбрано`}</div>
        </div>
        <span className="chevron"><Icon.chevron size={18} /></span>
      </div>
    )
  }
  ep = list[0]
  return (
    <div className="cell tap" style={{ borderRadius: 12, minHeight: 64 }} onClick={onClick}>
      <div className="cell-before"><Avatar size={38} tone={ep.tone} icon={typeIcon(ep.type)} src={ep.avatar} /></div>
      <div className="cell-main">
        <div className="cell-title">{ep.title}</div>
        <div className="cell-sub rule-badges" style={{ marginTop: 3 }}><MBadge m={ep.messenger} /><TBadge type={ep.type === 'topic' ? 'topic' : ep.isForum ? 'supergroup' : ep.type} compact /></div>
      </div>
      <span className="chevron"><Icon.chevron size={18} /></span>
    </div>
  )
}

/* Строка раздельной подписи: «Подпись для «получатель»» + тумблер. */
function SignatureRow({ recipient, source, on, onToggle }) {
  return (
    <div className="cell" style={{ borderRadius: 12, alignItems: 'flex-start', minHeight: 0, padding: '12px 16px' }}>
      <div className="cell-before" style={{ marginTop: 1, color: 'var(--text-secondary)' }}><Icon.signature size={22} /></div>
      <div className="cell-main" style={{ padding: 0, gap: 3 }}>
        <div className="t-headline truncate" title={`Подпись для «${recipient}»`} style={{ fontSize: 16 }}>Подпись для «{recipient}»</div>
        <div className="t-footnote sec text-pretty">В сообщениях, уходящих в «{recipient}», помечать отправителя из «{source}» — имя участника группы или название канала.</div>
      </div>
      <div className="cell-after" onClick={onToggle} style={{ cursor: 'pointer' }}><Switch on={on} /></div>
    </div>
  )
}

export function S10({ ruleId }) {
  const rules = useStore((s) => s.rules)
  const sources = useStore((s) => s.sources)
  const loadSources = useStore((s) => s.loadSources)
  const createRule = useStore((s) => s.createRule)
  const updateRule = useStore((s) => s.updateRule)
  const openSheet = useStore((s) => s.openSheet)
  const pop = useStore((s) => s.pop)
  const showToast = useStore((s) => s.showToast)

  const editing = useMemo(() => (ruleId ? (rules.items || []).find((r) => r.id === ruleId) : null), [ruleId, rules.items])

  // Локальное состояние выбора (id источников → endpoint берём из стора источников).
  // При создании можно выбрать несколько тем/источников; при редактировании — ровно одно правило.
  const [aIds, setAIds] = useState(editing?.a.sourceId ? [editing.a.sourceId] : [])
  const [bIds, setBIds] = useState(editing?.b.sourceId ? [editing.b.sourceId] : [])
  const [dir, setDir] = useState(editing?.dir || 'both')
  // Подпись раздельно по направлениям: sigAB — поток A→B (для получателя B), sigBA — B→A (для A).
  const [sigAB, setSigAB] = useState(editing ? editing.signAB !== false : true)
  const [sigBA, setSigBA] = useState(editing ? editing.signBA !== false : true)
  const [saving, setSaving] = useState(false)

  useEffect(() => { loadSources() }, [loadSources])

  const items = sources.items || []
  // Endpoint по выбранному id (предпочитаем актуальные данные источника, иначе — из правила).
  const epOf = (id, fallback) => {
    const s = items.find((x) => x.id === id)
    if (s) return { sourceId: s.id, messenger: s.messenger, type: s.type, title: s.title, tone: s.tone, avatar: s.avatar }
    return fallback || null
  }
  const epsA = aIds.map((id) => epOf(id, editing?.a)).filter(Boolean)
  const epsB = bIds.map((id) => epOf(id, editing?.b)).filter(Boolean)
  const epA = epsA[0] || null
  const epB = epsB[0] || null

  // Подпись по направлениям — работает и для групп, и для каналов (для канала подпись = имя
  // автора поста или название канала). Поток A→B (получатель B) активен при dir to/both,
  // B→A (получатель A) — при from/both; показываем, когда выбраны оба источника.
  // Одностороннее → один тумблер, двустороннее → по одному на каждого получателя.
  const a2bOn = !!(epA && epB) && (dir === 'to' || dir === 'both')
  const b2aOn = !!(epA && epB) && (dir === 'from' || dir === 'both')
  const showSig = a2bOn || b2aOn

  // Есть ли в правиле поток MAX→Telegram (источник MAX, получатель Telegram) — для примечания
  // о цитатах, которые MAX не отдаёт через API (см. FORWARD_NOTE_MAX_TG).
  const maxToTg =
    (epA?.messenger === 'max' && epB?.messenger === 'tg' && a2bOn) ||
    (epB?.messenger === 'max' && epA?.messenger === 'tg' && b2aOn)

  // Валидация: оба набора выбраны, пары разные, без дублей.
  const selectedPairs = []
  for (const a of aIds) for (const b of bIds) selectedPairs.push([a, b])
  const pairCount = selectedPairs.length
  const sameSel = selectedPairs.some(([a, b]) => a && b && a === b)
  // Дубль — по НАПРАВЛЕННОМУ потоку (src→dst): A→B и B→A разные и сосуществуют; конфликт =
  // пересечение потоков (как на бэкенде, rules._conflict). Чужие правила здесь не видны —
  // их дубль ловит бэкенд при сохранении («…у другого пользователя», см. catch в save).
  const flowsOf = (x, y, d) => (d === 'to' ? [`${x}>${y}`] : d === 'from' ? [`${y}>${x}`] : [`${x}>${y}`, `${y}>${x}`])
  const selectedFlows = selectedPairs.flatMap(([a, b]) => flowsOf(a, b, dir))
  const dupInside = new Set(selectedFlows).size !== selectedFlows.length
  const dup = selectedPairs.length > 0 && (
    dupInside || (rules.items || []).some((r) => {
      if (r.id === ruleId) return false
      const theirs = flowsOf(r.a.sourceId, r.b.sourceId, r.dir)
      return selectedFlows.some((f) => theirs.includes(f))
    })
  )
  const overLimit = !editing && pairCount > 0 && (rules.activeCount || 0) + pairCount > (rules.limit || 10)
  const valid = pairCount > 0 && !sameSel && !dup && !overLimit

  const pick = (slot) => {
    host.haptic('selection')
    openSheet('pickSource', {
      slot,
      multi: !editing,
      selectedIds: slot === 'a' ? aIds : bIds,
      selectedId: slot === 'a' ? aIds[0] : bIds[0],
      excludeIds: slot === 'a' ? bIds : aIds,
      onPick: (ids) => {
        const next = Array.isArray(ids) ? ids : [ids]
        ;(slot === 'a' ? setAIds : setBIds)(next.filter(Boolean))
      },
    })
  }

  const aName = selectionTitle(epsA, items) || epA?.title || 'A'
  const bName = selectionTitle(epsB, items) || epB?.title || 'B'
  const d = DIRS[dir] || DIRS.both
  const caption = dir === 'both'
    ? `Сообщения будут переноситься между „${aName}“ и „${bName}“ в обе стороны.`
    : dir === 'to'
      ? `Сообщения будут переноситься из „${aName}“ в „${bName}“.`
      : `Сообщения будут переноситься из „${bName}“ в „${aName}“.`

  const save = async () => {
    if (!valid || saving) return
    host.haptic('medium')
    setSaving(true)
    try {
      // Сохраняем подпись только для применимых потоков; неприменимые обнуляем.
      const sign = { signAB: a2bOn ? sigAB : false, signBA: b2aOn ? sigBA : false }
      if (editing) {
        // ВАЖНО: при редактировании передаём и источники (a_id/b_id) — иначе смена
        // источника в редакторе молча терялась (бэкенд update_rule ждёт snake_case
        // a_id/b_id, см. rules.update_rule). id здесь всегда заданы (valid-гейт).
        await updateRule(editing.id, { a_id: aIds[0], b_id: bIds[0], dir, ...sign })
      } else {
        for (const [aId, bId] of selectedPairs) {
          await createRule({ aId, bId, dir, ...sign })
        }
      }
      host.haptic('success')
      pop()
      showToast(editing || pairCount === 1 ? 'Правило сохранено' : `Создано правил: ${pairCount}`)
    } catch (err) {
      host.haptic('error')
      showToast(errorMessage(err, 'Не удалось сохранить'), 'alert')
    } finally {
      setSaving(false)
    }
  }

  const hint = pairCount === 0 ? 'Выберите оба источника.'
    : sameSel ? 'Источники должны быть разными.'
      : dup ? 'Такое правило уже существует.'
        : overLimit ? `Лимит ${rules.limit || 10} активных правил. Выбрано: ${pairCount}.`
        : undefined

  return (
    <Screen grouped>
      <HostHeader title={editing ? (editing.number != null ? `Правило №${editing.number}` : 'Редактирование правила') : 'Новое правило'} back onGrouped />
      <div className="screen-body grouped">
        <div className="cell-header caps">Источник A</div>
        <div className="body-pad"><SourceSelect label="Выберите источник A" eps={epsA} all={items} onClick={() => pick('a')} /></div>

        <div className="cell-header caps">Направление</div>
        <div className="body-pad"><DirSegment value={dir} onChange={(k) => { host.haptic('selection'); setDir(k) }} /></div>

        <div className="cell-header caps">Источник B</div>
        <div className="body-pad">
          <SourceSelect label="Выберите источник B" eps={epsB} all={items} onClick={() => pick('b')} />
          {!editing && pairCount > 1 && valid && (
            <div className="t-footnote sec" style={{ padding: '7px 2px 0' }}>
              Будет создано {pairCount} {pairCount === 1 ? 'правило' : pairCount < 5 ? 'правила' : 'правил'}.
            </div>
          )}
        </div>

        {/* Подпись отправителя — по направлениям (только для потоков, чей источник — группа).
            Одностороннее правило → одна строка (подпись для получателя); двустороннее → по
            строке на каждого получателя, чей источник — группа. */}
        {showSig && (
          <>
            <div className="cell-header caps">Подпись отправителя</div>
            <div className="body-pad" style={{ marginTop: 0 }}>
              {a2bOn && (
                <SignatureRow recipient={bName} source={aName} on={sigAB}
                  onToggle={() => { host.haptic('selection'); setSigAB((v) => !v) }} />
              )}
              {a2bOn && b2aOn && <div style={{ height: 8 }} />}
              {b2aOn && (
                <SignatureRow recipient={aName} source={bName} on={sigBA}
                  onToggle={() => { host.haptic('selection'); setSigBA((v) => !v) }} />
              )}
            </div>
          </>
        )}

        {/* Предпросмотр. */}
        <div className="cell-header caps">Предпросмотр</div>
        <div className="body-pad" style={{ paddingBottom: 12 }}>
          <div className="note-card" style={{ background: 'var(--accent-weak)', border: 'none', padding: '16px 14px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10 }}>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
                {epA && <MBadge m={epA.messenger} />}
                <span className="t-headline" style={{ fontSize: 14 }}>{aName}</span>
              </span>
              <span className="acc" style={{ fontSize: 24, fontWeight: 700, minWidth: 26, textAlign: 'center' }}>{d.arrow}</span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
                {epB && <MBadge m={epB.messenger} />}
                <span className="t-headline" style={{ fontSize: 14 }}>{bName}</span>
              </span>
            </div>
            <div className="t-footnote sec text-pretty" style={{ textAlign: 'center', marginTop: 10 }}>{caption}</div>
          </div>
        </div>

        {/* Что переносится — справка о поддерживаемых материалах (когда выбраны оба источника). */}
        {epA && epB && (
          <>
            <div className="cell-header caps">Что переносится</div>
            <div className="body-pad" style={{ paddingBottom: 12 }}>
              <div className="note-card" style={{ padding: '8px 16px' }}>
                {FORWARD_SUPPORTED.map((label) => <MaterialRow key={label} ok>{label}</MaterialRow>)}
                <div style={{ height: 1, background: 'var(--separator)', margin: '9px 0' }} />
                {FORWARD_UNSUPPORTED.map((label) => <MaterialRow key={label}>{label}</MaterialRow>)}
                <div className="t-caption sec text-pretty" style={{ marginTop: 11 }}>{FORWARD_NOTE}</div>
                {maxToTg && (
                  <div className="t-caption sec text-pretty" style={{ marginTop: 8 }}>{FORWARD_NOTE_MAX_TG}</div>
                )}
              </div>
            </div>
          </>
        )}

        {/* Удаление (только при редактировании). */}
        {editing && (
          <div className="body-pad" style={{ paddingBottom: 16 }}>
            <Btn
              kind="destructive"
              before={<Icon.trash size={19} />}
              onClick={() => { host.haptic('warning'); openSheet('deleteRule', { ruleId: editing.id }) }}
            >Удалить правило</Btn>
          </div>
        )}
      </div>
      <MainButton
        label={editing ? 'Сохранить изменения' : 'Сохранить правило'}
        kind={valid ? 'primary' : 'disabled'}
        disabled={!valid}
        loading={saving}
        sub={hint}
        grouped
        onClick={save}
      />
    </Screen>
  )
}
