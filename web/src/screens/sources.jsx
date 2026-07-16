/* sources.jsx — список и добавление источников: данные из стора/API,
 * состояния загрузка/пусто/ошибка/оффлайн,
 * живой опрос привязки источника. Тело — обычный screen-body (без pull-to-refresh):
 * жест тянул верх экрана вниз и выглядел как случайная прокрутка. */
import React, { useEffect, useMemo, useRef, useState } from 'react'
import {
  Screen, HostHeader, Btn, BtnLink, PillButton, Avatar, MBadge, TBadge, StatusChip,
  Cell, SkeletonCell, Icon,
} from '../components/ui.jsx'
import { useStore } from '../store/store.js'
import host from '../host/host.js'
import api from '../api/client.js'
import { LargeTitle, TabFooter, BOT_HANDLES, BotHandleTap, BotLink, CodeTap } from './_shared.jsx'
import { MaxMark, TgMark } from './paywall.jsx'
import { baseTitle, buildTopicGroups, forumChoices, topicTitle } from '../utils/sourceTopics.js'

/* ---------- ячейка источника ---------- */
function SourceCell({ source, onClick }) {
  const { messenger, type, title, status, code, tone, rightsOk } = source
  const badgeType = type === 'topic' ? 'topic' : source.isForum ? 'supergroup' : type
  return (
    <Cell inset tap
      before={<Avatar size={40} tone={tone} src={source.avatar}
        icon={type === 'channel' ? <Icon.megaphone /> : <Icon.people />} />}
      title={title}
      subtitle={<><MBadge m={messenger} /><TBadge type={badgeType} />{rightsOk === false && <span className="dng" style={{ fontSize: 12 }}>· нет прав</span>}</>}
      after={<StatusChip status={status} code={code} />}
      chevron
      onClick={onClick}
    />
  )
}

function ForumSourceGroup({ group, all, expanded, onToggle, onOpen }) {
  const title = group.base?.title || baseTitle(group.topics[0], all)
  const choices = forumChoices(group)
  const topicsCount = group.topics.length
  const rightsOk = [group.base, ...group.topics].filter(Boolean).every((s) => s.rightsOk !== false)
  const status = group.base?.status || group.topics[0]?.status
  return (
    <>
      <Cell
        tap
        before={<Avatar size={40} tone={group.base?.tone || group.topics[0]?.tone}
          src={group.base?.avatar || group.topics[0]?.avatar} icon={<Icon.people />} />}
        title={title}
        subtitle={<><MBadge m="tg" /><TBadge type="supergroup" /><span>{topicsCount} {plural(topicsCount, 'тема', 'темы', 'тем')}</span>{!rightsOk && <span className="dng" style={{ fontSize: 12 }}>· нет прав</span>}</>}
        after={<>
          <StatusChip status={status} />
          <span
            style={{ color: 'var(--text-tertiary)', transform: expanded ? 'rotate(90deg)' : undefined, display: 'inline-flex', padding: 8, margin: -8 }}
            onClick={(e) => {
              e.stopPropagation()
              onToggle()
            }}
          >
            <Icon.chevron size={18} />
          </span>
        </>}
        onClick={group.base ? () => onOpen(group.base) : onToggle}
      />
      {expanded && choices.map(({ source, label }) => (
        <Cell
          key={source.id}
          tap
          compact
          before={<span style={{ width: 40, display: 'flex', justifyContent: 'center', color: 'var(--text-tertiary)' }}>
            <Icon.chevron size={16} />
          </span>}
          title={label || topicTitle(source, all)}
          subtitle={<><TBadge type={source.type} />{source.rightsOk === false && <span className="dng" style={{ fontSize: 12 }}>· нет прав</span>}</>}
          after={<StatusChip status={source.status} code={source.code} />}
          onClick={() => onOpen(source)}
        />
      ))}
    </>
  )
}

/* ============================ S7 — Источники ============================ */
export function S7() {
  const sources = useStore((s) => s.sources)
  const online = useStore((s) => s.online)
  const loadSources = useStore((s) => s.loadSources)
  const openSheet = useStore((s) => s.openSheet)
  const push = useStore((s) => s.push)
  const account = useStore((s) => s.account)
  const markAccountFlag = useStore((s) => s.markAccountFlag)
  const [query, setQuery] = useState('')
  const [expandedForums, setExpandedForums] = useState({})

  useEffect(() => { loadSources() }, [loadSources])

  // Первый вход на вкладку: один раз показываем «Что такое источник?» (флаг — на
  // сервере, один на аккаунт). Дальше ответ живёт в «Настройки → Частые вопросы».
  const introRef = useRef(false)
  useEffect(() => {
    if (introRef.current || !account || account.uiFlags?.sources_intro_seen) return
    introRef.current = true
    openSheet('whatIsSource')
    markAccountFlag('sources_intro_seen')
  }, [account, openSheet, markAccountFlag])

  const items = sources.items || []
  const loading = sources.loading && items.length === 0
  const offline = !online || sources.error === 'offline'
  const errored = sources.error && sources.error !== 'offline'

  const q = query.trim().toLowerCase()
  const filtered = q ? items.filter((s) => (s.title || '').toLowerCase().includes(q)) : items
  const waiting = filtered.filter((s) => s.status === 'wait')
  const bound = filtered.filter((s) => s.status === 'ok' || s.status === 'err' || s.status === 'dead')
  const boundGroups = useMemo(() => buildTopicGroups(bound), [bound])
  const sourceCount = useMemo(() => {
    const waitingCount = items.filter((s) => s.status === 'wait').length
    const boundItems = items.filter((s) => s.status === 'ok' || s.status === 'err' || s.status === 'dead')
    return waitingCount + buildTopicGroups(boundItems).length
  }, [items])

  const waitOrNoRights = items.some((s) => s.status === 'wait' || s.rightsOk === false)

  const open = (source) => { host.haptic('selection'); openSheet('sourceDetail', { source }) }

  let body
  if (loading) {
    body = <div className="body-pad"><div className="island"><SkeletonCell /><SkeletonCell /><SkeletonCell /></div></div>
  } else if (errored || (offline && items.length === 0)) {
    body = (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', padding: '60px 28px 0', color: 'var(--text-secondary)' }}>
        <span style={{ color: 'var(--text-tertiary)' }}>{offline ? <Icon.wifiOff size={40} /> : <Icon.alert size={40} />}</span>
        <div className="t-headline" style={{ marginTop: 14, color: 'var(--text)' }}>{offline ? 'Нет соединения' : 'Не удалось загрузить'}</div>
        <PillButton icon={<Icon.refresh size={16} />} style={{ marginTop: 14 }} onClick={() => loadSources()}>Обновить</PillButton>
      </div>
    )
  } else if (items.length === 0) {
    // Пустое состояние — без собственной кнопки: единственная CTA «Добавить источник»
    // всегда есть снизу в TabFooter, дубль в центре экрана не нужен. Аврора-hero
    // в языке пейволла: узлы обеих платформ — что именно здесь подключается.
    body = (
      <div className="body-pad" style={{ marginTop: 8 }}>
        <section className="pw-hero pw-in" style={{ paddingBottom: 18 }}>
          <div style={{ display: 'flex', justifyContent: 'center', gap: 12, paddingTop: 4 }}>
            <span className="pw-node max"><MaxMark /></span>
            <span className="pw-node tg"><TgMark /></span>
          </div>
          <h2 className="pw-title" style={{ fontSize: 22, marginTop: 16 }}>Источников ещё нет</h2>
          <p className="pw-lead">
            Добавьте чат или канал из MAX или Telegram, чтобы бот мог переносить сообщения.
          </p>
        </section>
      </div>
    )
  } else {
    body = (
      <>
        <div className="body-pad" style={{ paddingBottom: 8 }}>
          <div className="search">
            <Icon.search size={17} />
            <input placeholder="Поиск по источникам" value={query} onChange={(e) => setQuery(e.target.value)} />
          </div>
        </div>
        {waiting.length > 0 && (
          <>
            <div className="cell-header caps">Ожидают привязки</div>
            <div className="body-pad">
              <div className="island">
                {waiting.map((s) => <SourceCell key={s.id} source={s} onClick={() => open(s)} />)}
              </div>
            </div>
          </>
        )}
        {bound.length > 0 && (
          <>
            <div className="cell-header caps">Привязанные</div>
            <div className="body-pad source-blocks">
              {boundGroups.map((item) => {
                if (item.kind === 'source') {
                  return (
                    <div className="island" key={item.source.id}>
                      <SourceCell source={item.source} onClick={() => open(item.source)} />
                    </div>
                  )
                }
                const openKey = item.id
                return (
                  <div className="island" key={item.id}>
                    <ForumSourceGroup
                      group={item}
                      all={items}
                      expanded={expandedForums[openKey] !== false}
                      onToggle={() => {
                        host.haptic('selection')
                        setExpandedForums((v) => ({ ...v, [openKey]: v[openKey] === false }))
                      }}
                      onOpen={open}
                    />
                  </div>
                )
              })}
            </div>
          </>
        )}
        {filtered.length === 0 && (
          <div className="t-footnote sec text-pretty" style={{ textAlign: 'center', padding: '32px 28px' }}>
            Ничего не найдено.
          </div>
        )}
      </>
    )
  }

  return (
    <Screen grouped>
      <HostHeader title="" onGrouped />
      <div className="screen-body grouped">
        <LargeTitle after={sourceCount > 0 ? <span className="t-title-lg sec" style={{ fontWeight: 600 }}>{sourceCount}</span> : undefined}>Источники</LargeTitle>
        {body}
      </div>
      {/* Ссылки «Что такое источник?» в футере больше нет: лист показывается сам при
        * первом входе, а ответ навсегда доступен в «Настройки → Частые вопросы». */}
      <TabFooter sourcesBadge={waitOrNoRights ? true : undefined}>
        <Btn before={<Icon.plus size={20} />} onClick={() => push('S8')}>Добавить источник</Btn>
      </TabFooter>
    </Screen>
  )
}

/* ============================ S8 — Новый источник ============================ */
function StepRow({ n, title, text }) {
  return (
    <div className="cell" style={{ alignItems: 'flex-start', minHeight: 0, padding: '13px 16px' }}>
      <div className="cell-before" style={{ marginTop: 1 }}>
        <span style={{ width: 24, height: 24, borderRadius: 12, background: 'var(--accent)', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, fontWeight: 700 }}>{n}</span>
      </div>
      <div className="cell-main" style={{ padding: 0, gap: 3 }}>
        <div className="t-headline" style={{ fontSize: 15 }}>{title}</div>
        <div className="t-footnote sec text-pretty">{text}</div>
      </div>
    </div>
  )
}

export function S8({ messenger }) {
  const loadSources = useStore((s) => s.loadSources)
  const showToast = useStore((s) => s.showToast)
  const openSheet = useStore((s) => s.openSheet)

  // Сегмент мессенджера: по умолчанию — текущий хост.
  const initial = messenger === 'tg' ? 'Telegram' : messenger === 'max' ? 'MAX'
    : host.name === 'telegram' ? 'Telegram' : 'MAX'
  const [seg, setSeg] = useState(initial)
  const [code, setCode] = useState('····')
  const [expired, setExpired] = useState(false)
  const [refreshNonce, setRefreshNonce] = useState(0)

  const mkey = seg === 'MAX' ? 'max' : 'tg'
  const hostName = seg === 'MAX' ? 'MAX' : 'Telegram'
  const botHandle = BOT_HANDLES[mkey]

  // Права бота зависят от мессенджера: в Telegram группе особые права не нужны, каналу —
  // админ с публикацией; в MAX боту нужны админ-права обязательно — в группе читать
  // и удалять сообщения, в канале писать, редактировать и удалять чужие посты.
  const step2 = mkey === 'tg'
    ? { title: 'Выдайте права (для канала)', text: 'Для канала назначьте бота администратором с правами публикации, а также правки и удаления постов. Для группы особые права не нужны — бот читает и пишет как участник.' }
    : {
        title: 'Назначьте бота администратором',
        text: (
          <>
            Бот работает в MAX только как администратор — выдайте права:
            <div style={{ marginTop: 6, color: 'var(--text)' }}>
              <b>В группе:</b> Читать сообщения, Удалять сообщения
            </div>
            <div style={{ marginTop: 2, color: 'var(--text)' }}>
              <b>В канале:</b> Писать посты, Редактировать чужие посты, Удалять чужие посты
            </div>
          </>
        ),
      }

  const pollRef = useRef(null)
  const prevLenRef = useRef(0)

  // Получение кода при монтировании и при ручном обновлении истёкшего кода.
  useEffect(() => {
    let alive = true
    setExpired(false); setCode('····'); prevLenRef.current = 0
    ;(async () => {
      try {
        const r = await api.createSourceCode(mkey)
        if (alive) setCode(r?.code || String(Math.floor(1000 + Math.random() * 9000)))
      } catch (_) {
        if (alive) setCode(String(Math.floor(1000 + Math.random() * 9000)))
      }
    })()
    return () => { alive = false }
    // Код — общий для аккаунта (1 на 10 минут, независимо от мессенджера): НЕ
    // перевыпускаем при смене сегмента, только при монтировании и «Обновить код».
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshNonce])

  const refresh = () => { host.haptic('light'); setRefreshNonce((n) => n + 1) }

  // Опрос статуса привязки каждые ~2с. Код многоразовый (можно добавить несколько
  // чатов за 10 минут). Постоянной плашки статуса и кнопки «Готово» нет: о каждой
  // привязке сообщает исчезающий тост (+ бот шлёт уведомление в мессенджеры, а
  // запись остаётся в «Настройки → Уведомления» — это делает backend).
  useEffect(() => {
    const tick = async () => {
      try {
        const r = await api.getPendingSource()
        if (r?.status === 'listening') {
          setExpired(false)
          const next = r.bound || []
          if (next.length > prevLenRef.current) {
            const fresh = next.slice(prevLenRef.current)
            prevLenRef.current = next.length
            host.haptic('success')
            const t = fresh[0]?.title
            showToast(fresh.length === 1
              ? (t ? `Источник «${t}» привязан` : 'Источник привязан')
              : `Привязано источников: ${fresh.length}`, 'check')
            loadSources()
          }
        } else if (r?.status === 'idle' && code !== '····') {
          setExpired(true)  // код истёк (TTL вышел)
        }
      } catch (_) { /* мягкая деградация — продолжаем опрос */ }
    }
    pollRef.current = setInterval(tick, 2000)
    return () => clearInterval(pollRef.current)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [code])

  const copy = async () => {
    try { await navigator.clipboard?.writeText(code) } catch (_) {}
    host.haptic('light')
    showToast('Код скопирован')
  }

  return (
    <Screen grouped>
      <HostHeader title="Новый источник" back onGrouped />
      <div className="screen-body grouped">
        {/* карточка кода — аврора и фирменный градиент кода (язык пейволла) */}
        <div className="body-pad" style={{ paddingTop: 8 }}>
          <div className="note-card code-card">
            <div className="t-footnote sec">Ваш код привязки</div>
            <div className="code-value">{code}</div>
            <PillButton icon={<Icon.copy size={16} />} style={{ margin: '10px auto 0' }} onClick={copy}>Скопировать код</PillButton>
            <div className="t-caption sec" style={{ marginTop: 10 }}>Код действует 10 минут. Им можно привязать несколько чатов и каналов — в любом мессенджере.</div>
          </div>
        </div>

        {/* шаги */}
        <div className="cell-header caps">Как привязать</div>
        <div className="body-pad">
          <div className="t-footnote sec" style={{ margin: '0 0 8px 2px' }}>В каком мессенджере чат или канал?</div>
          <div className="dir-seg" style={{ gridTemplateColumns: '1fr 1fr', marginBottom: 12 }}>
            {['MAX', 'Telegram'].map((h) => (
              <div key={h} className={`dir-opt ${h === 'MAX' ? 'seg-max' : 'seg-tg'}${seg === h ? ' active' : ''}`} style={{ padding: '9px 4px', flexDirection: 'row', justifyContent: 'center', gap: 6 }} onClick={() => setSeg(h)}>
                <span className="dir-label" style={{ fontSize: 14, fontWeight: 600 }}>{h}</span>
              </div>
            ))}
          </div>
          <div className="island">
            <StepRow n="1" title="Добавьте бота в чат или канал" text={<>Откройте нужный чат или канал в {hostName} и добавьте бота <BotHandleTap m={mkey} />{botHandle && <> ({botHandle})</>}. Ссылка на бота: <BotLink m={mkey} />. Если бот уже в этом чате — переходите к следующему шагу.</>} />
            <StepRow n="2" title={step2.title} text={step2.text} />
            <StepRow n="3" title="Отправьте код привязки в этот чат" text={<>Напишите в чат код привязки <CodeTap code={code} /> одним сообщением — он должен быть последним сообщением в чате. Как только бот увидит последний код — источник привяжется автоматически, а вам придёт уведомление.</>} />
          </div>
          <BtnLink style={{ display: 'block', margin: '10px auto 0' }}
            onClick={() => {
              host.haptic('selection')
              // Мессенджер в листе переключается сегментом; выбор синхронизируется
              // обратно в S8, чтобы шаги на экране совпадали с инструкцией.
              openSheet('bindHowTo', {
                messenger: mkey, code,
                onSwitch: (m) => setSeg(m === 'tg' ? 'Telegram' : 'MAX'),
              })
            }}>
            Подробная инструкция для новичков
          </BtnLink>
        </div>

        {/* карточка истёкшего кода (единственный постоянный статус на экране) */}
        {expired && (
          <div className="body-pad" style={{ marginTop: 4 }}>
            <div className="note-card" style={{ display: 'flex', alignItems: 'center', gap: 12, borderColor: 'var(--muted-red)', background: 'var(--muted-red-weak)' }}>
              <span style={{ color: 'var(--muted-red)' }}><Icon.clock size={24} /></span>
              <div style={{ flex: 1 }}>
                <div className="t-headline" style={{ fontSize: 15 }}>Код истёк</div>
                <div className="t-footnote sec">Обновите код, чтобы продолжить привязку.</div>
              </div>
              <PillButton icon={<Icon.refresh size={16} />} onClick={refresh}>Обновить</PillButton>
            </div>
          </div>
        )}
        <div style={{ height: 12 }} />
      </div>
    </Screen>
  )
}

function plural(n, one, few, many) {
  const m10 = n % 10
  const m100 = n % 100
  if (m10 === 1 && m100 !== 11) return one
  if (m10 >= 2 && m10 <= 4 && (m100 < 10 || m100 >= 20)) return few
  return many
}
