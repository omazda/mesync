/* sheets.jsx — нижние листы (bottom sheets) и шторки-заглушки mini-app.
 *
 * Все листы рендерят <Sheet> (он сам рисует оверлей, грабер, заголовок и закрытие).
 * Пропсы приходят через openSheet(name, props). Тексты — дословно из раздела 5
 * дизайн-спецификации (единые формулировки из блока «Унификация дублей»).
 * HostNotRecognized — НЕ лист, а полноэкранная заглушка для неизвестного хоста.
 */
import React, { useMemo, useState } from 'react'
import {
  Sheet, Btn, MBadge, TBadge, StatusChip, Avatar, Cell, Icon,
} from '../components/ui.jsx'
import { useStore } from '../store/store.js'
import host from '../host/host.js'
import { errorMessage } from '../api/client.js'
import { WHAT_IS_SOURCE, PAY_STUB, BOT_HANDLES, BotHandleTap, BotLink, BrandMark, CodeTap } from './_shared.jsx'
import { baseSourceId, baseTitle, buildTopicGroups, forumChoices, isTopicSource, topicTitle } from '../utils/sourceTopics.js'

/* ============================ Что такое источник ============================ */
export function SheetWhatIsSource() {
  const closeSheet = useStore((s) => s.closeSheet)
  return (
    <Sheet
      title="Что такое источник?"
      footer={<Btn onClick={closeSheet}>Понятно</Btn>}
    >
      <div className="t-body-sm text-pretty" style={{ padding: '4px 0 8px', color: 'var(--text-secondary)' }}>
        {WHAT_IS_SOURCE}
      </div>
    </Sheet>
  )
}

/* ============================ Пошаговая инструкция привязки ============================ */
/* «Для чайников»: каждый шаг — одно конкретное действие с названиями кнопок.
 * Механика сверена с бэкендом: код сообщением в чат — мгновенная привязка
 * (ownership.on_chat_message; в теме супергруппы TG привязывается именно тема),
 * запасной путь — код в конец ОПИСАНИЯ чата (свипер, до ~минуты). Для канала
 * Telegram бот обязан сначала стать администратором — до этого посты канала
 * (в т.ч. код) до него не доходят. Путь назначения администратора канала MAX —
 * из официальной справки (docs/max/markdown/docs/channels/manage.md). */
const HOWTO_STEPS = {
  max: {
    group: (m, code) => [
      ['Добавьте бота в группу', <>Название группы → участники → добавить <BotHandleTap m={m} />{BOT_HANDLES[m] && <> ({BOT_HANDLES[m]})</>}.</>],
      ['Назначьте бота администратором', <>Нажмите на бота в списке участников → назначить администратором. Права: <b>«Читать сообщения»</b> и <b>«Удалять сообщения»</b>.</>],
      ['Отправьте код в группу', <>Обычным сообщением, только код: <CodeTap code={code} />.</>],
      ['Готово', 'Придёт уведомление, группа появится в источниках. Сообщение с кодом можно удалить.'],
    ],
    channel: (m, code) => [
      ['Назначьте бота администратором', <>Название канала → <b>«Администраторы»</b> → <b>«Добавить администратора»</b> → <BotHandleTap m={m} />{BOT_HANDLES[m] && <> ({BOT_HANDLES[m]})</>}. Права: <b>«Писать посты»</b>, <b>«Редактировать чужие посты»</b>, <b>«Удалять чужие посты»</b>.</>],
      ['Опубликуйте код в канале', <>Постом, только код: <CodeTap code={code} />.</>],
      ['Готово', 'Придёт уведомление, канал появится в источниках. Пост с кодом можно удалить.'],
    ],
  },
  tg: {
    group: (m, code) => [
      ['Добавьте бота в группу', <>Название группы → <b>«Добавить»</b> → <BotHandleTap m={m} />{BOT_HANDLES[m] && <> ({BOT_HANDLES[m]})</>}. Права администратора не нужны.</>],
      ['Отправьте код в группу', <>Обычным сообщением, только код: <CodeTap code={code} />. Если в группе есть темы — отправьте код в нужную тему: привяжется именно она.</>],
      ['Готово', 'Придёт уведомление, группа появится в источниках. Сообщение с кодом можно удалить.'],
    ],
    channel: (m, code) => [
      ['Назначьте бота администратором', <>Название канала → <b>«Управление каналом»</b> → <b>«Администраторы»</b> → <b>«Добавить администратора»</b> → <BotHandleTap m={m} />{BOT_HANDLES[m] && <> ({BOT_HANDLES[m]})</>}. Включите <b>«Публикация сообщений»</b>. Без прав бот не видит постов — сначала права, потом код.</>],
      ['Опубликуйте код в канале', <>Постом, только код: <CodeTap code={code} />.</>],
      ['Готово', 'Придёт уведомление, канал появится в источниках. Пост с кодом можно удалить.'],
    ],
  },
}

function HowtoStep({ n, title, text }) {
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12, padding: '9px 0' }}>
      <span style={{ flex: '0 0 auto', width: 24, height: 24, borderRadius: 12, background: 'var(--accent)', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, fontWeight: 700 }}>{n}</span>
      <span style={{ minWidth: 0 }}>
        <span className="t-headline" style={{ display: 'block', fontSize: 15 }}>{title}</span>
        <span className="t-footnote sec text-pretty" style={{ display: 'block', marginTop: 3 }}>{text}</span>
      </span>
    </div>
  )
}

/* Лист не привязан к мессенджеру запуска mini-app: пользователь из Telegram может
 * добавлять источник в MAX и наоборот. Мессенджер выбирается сегментом прямо в листе
 * (стартовое значение — сегмент экрана S8); onSwitch синхронизирует выбор обратно
 * в S8, чтобы шаги на экране и код-подсказки совпадали с инструкцией. */
export function SheetBindHowTo({ messenger = 'max', code = '····', onSwitch }) {
  const closeSheet = useStore((s) => s.closeSheet)
  const [m, setM] = useState(messenger === 'tg' ? 'tg' : 'max')
  const [kind, setKind] = useState('group')
  const bot = BOT_HANDLES[m]
  const steps = HOWTO_STEPS[m][kind](m, code)
  const pickM = (next) => {
    host.haptic('selection')
    setM(next)
    if (onSwitch) onSwitch(next)
  }
  return (
    <Sheet
      title="Пошаговая инструкция"
      footer={<Btn onClick={closeSheet}>Понятно</Btn>}
    >
      <div className="t-footnote sec" style={{ margin: '0 2px 6px' }}>Где чат или канал?</div>
      <div className="dir-seg" style={{ gridTemplateColumns: '1fr 1fr', margin: '0 0 8px' }}>
        {[['max', 'MAX'], ['tg', 'Telegram']].map(([k, label]) => (
          <div key={k} className={`dir-opt ${k === 'max' ? 'seg-max' : 'seg-tg'}${m === k ? ' active' : ''}`}
            style={{ padding: '9px 4px', flexDirection: 'row', justifyContent: 'center', gap: 6 }}
            onClick={() => pickM(k)}>
            <span className="dir-label" style={{ fontSize: 14, fontWeight: 600 }}>{label}</span>
          </div>
        ))}
      </div>
      <div className="dir-seg" style={{ gridTemplateColumns: '1fr 1fr', margin: '0 0 8px' }}>
        {[['group', 'Группа'], ['channel', 'Канал']].map(([k, label]) => (
          <div key={k} className={`dir-opt${kind === k ? ' active' : ''}`}
            style={{ padding: '9px 4px', flexDirection: 'row', justifyContent: 'center', gap: 6 }}
            onClick={() => { host.haptic('selection'); setKind(k) }}>
            <span className="dir-label" style={{ fontSize: 14, fontWeight: 600 }}>{label}</span>
          </div>
        ))}
      </div>
      <div className="t-footnote sec text-pretty" style={{ margin: '0 2px 8px' }}>
        Бот: <BotHandleTap m={m} />{bot && <> ({bot})</>} · <BotLink m={m} />
      </div>
      {steps.map(([title, text], i) => <HowtoStep key={`${m}-${kind}-${i}`} n={i + 1} title={title} text={text} />)}
      <div className="t-footnote sec text-pretty" style={{ margin: '8px 0 8px', padding: '10px 12px', background: 'var(--fill)', borderRadius: 10 }}>
        Код действует 10 минут. Не сработало — впишите код в конец <b>описания</b> чата:
        привяжется в течение минуты, потом код можно убрать.
      </div>
    </Sheet>
  )
}

/* ============================ Код активации подписки ============================ */
/* Ввод кода XXXX-XXXX-XXXX (регистрозависимый): даёт месяц текущего тарифа без привязки
 * карты. Бэкенд ограничивает ввод 3 попытками за 10 минут (429 too_many_attempts) —
 * текст ошибки показываем под полем как есть. */
function activationDate(iso) {
  if (!iso) return null
  const d = new Date(iso)
  if (isNaN(d)) return null
  return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' })
}

export function SheetActivationCode() {
  const closeSheet = useStore((s) => s.closeSheet)
  const activateCode = useStore((s) => s.activateCode)
  const showToast = useStore((s) => s.showToast)
  const subscription = useStore((s) => s.subscription)
  const [code, setCode] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const planTitle = subscription?.planName || (subscription?.plan === 'individual' ? 'Индивидуальный' : 'Smart')

  // Авто-формат: оставляем только [A-Za-z0-9] (регистр ВАЖЕН — не приводим),
  // дефис после каждой четвёрки. Вставка из буфера тоже нормализуется.
  const onChange = (e) => {
    const raw = String(e.target.value || '').replace(/[^A-Za-z0-9]/g, '').slice(0, 12)
    setCode(raw.replace(/(.{4})(?=.)/g, '$1-'))
    setError(null)
  }
  const ready = code.replace(/-/g, '').length === 12

  const submit = async () => {
    if (!ready || busy) return
    host.haptic('medium')
    setBusy(true)
    try {
      const res = await activateCode(code)
      host.haptic('success')
      closeSheet()
      const until = activationDate(res.subscription?.renewAt)
      showToast(until ? `Подписка активна до ${until}` : 'Код активирован', 'check')
    } catch (err) {
      host.haptic('error')
      setError(errorMessage(err, 'Не удалось активировать код.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Sheet
      title="Код активации"
      onClose={closeSheet}
      footer={
        <Btn loading={busy} disabled={!ready} kind={ready ? 'primary' : 'gray'} onClick={submit}>
          Активировать
        </Btn>
      }
    >
      <div className="t-body-sm sec text-pretty" style={{ padding: '2px 0 12px' }}>
        Введите код — тариф {planTitle} активируется на 1 месяц. Привязка карты не нужна.
      </div>
      <div className={`field${error ? ' error' : ''}`}>
        <input
          value={code}
          onChange={onChange}
          onKeyDown={(e) => { if (e.key === 'Enter') submit() }}
          placeholder="XXXX-XXXX-XXXX"
          autoComplete="off" autoCorrect="off" autoCapitalize="off" spellCheck={false}
          style={{ textAlign: 'center', fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace', fontSize: 19, letterSpacing: 1 }}
        />
      </div>
      {error
        ? <div className="t-footnote text-pretty" style={{ color: 'var(--danger)', margin: '8px 2px 4px' }}>{error}</div>
        : <div className="t-footnote sec text-pretty" style={{ margin: '8px 2px 4px' }}>
            Код действует 30 дней с момента генерации, различает заглавные и строчные буквы. Не более 3 попыток за 10 минут.
          </div>}
      <div style={{ height: 8 }} />
    </Sheet>
  )
}

/* ============================ Детальный лист источника ============================ */
export function SheetSourceDetail({ source }) {
  const openSheet = useStore((s) => s.openSheet)
  if (!source) return null

  const isTopic = isTopicSource(source)
  const parentSourceId = isTopic ? baseSourceId(source) : null
  const deleteTarget = isTopic && parentSourceId
    ? {
        ...source,
        id: parentSourceId,
        title: source.baseTitle || baseTitle(source) || source.title,
        deleteFromTopic: true,
        topicTitle: topicTitle(source),
      }
    : source
  const used = source.usedInRules || 0
  const usedText = `Используется в ${used} ${plural(used, 'правиле', 'правилах', 'правилах')}`
  const canDelete = isTopic ? !!parentSourceId : source.deletable !== false && !source.observedTopic
  const badgeType = source.type === 'topic' ? 'topic' : source.isForum ? 'supergroup' : source.type

  const remove = () => {
    host.haptic('warning')
    openSheet('deleteSource', { source: deleteTarget })
  }

  return (
    <Sheet title={source.title}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', padding: '2px 0 4px' }}>
        <MBadge m={source.messenger} />
        <TBadge type={badgeType} />
        <StatusChip status={source.status} code={source.code} />
      </div>

      <div className="t-footnote sec" style={{ marginTop: 10 }}>{usedText}</div>
      <div className="t-footnote sec text-pretty" style={{ marginTop: 4 }}>
        Название синхронизируется из чата автоматически.
      </div>

      {canDelete && (
        <div className="island" style={{ marginTop: 14 }}>
          <Cell
            before={<span style={{ color: 'var(--danger)' }}><Icon.trash size={20} /></span>}
            title="Удалить источник"
            titleStyle={{ color: 'var(--danger)' }}
            onClick={remove}
          />
        </div>
      )}
    </Sheet>
  )
}

/* ============================ Удаление источника ============================ */
export function SheetDeleteSource({ source }) {
  const closeSheet = useStore((s) => s.closeSheet)
  const deleteSource = useStore((s) => s.deleteSource)
  const showToast = useStore((s) => s.showToast)
  if (!source) return null

  const del = async () => {
    host.haptic('warning')
    try {
      await deleteSource(source.id)
      closeSheet()
      showToast('Источник удалён')
    } catch (err) {
      showToast(errorMessage(err, 'Не удалось удалить'), 'alert')
    }
  }

  return (
    <Sheet
      title="Удалить источник"
      footer={
        <>
          <Btn kind="destructive" onClick={del}>Удалить</Btn>
          <Btn kind="secondary" onClick={closeSheet}>Отмена</Btn>
        </>
      }
    >
      <div className="t-body-sm text-pretty" style={{ padding: '4px 0 8px', color: 'var(--text-secondary)' }}>
        {source.deleteFromTopic
          ? `Удалить источник «${source.title}» полностью? Тема «${source.topicTitle}» является его подразделом. Правила с этим источником и его темами тоже будут удалены.`
          : `Удалить источник «${source.title}»? Правила с этим источником тоже будут удалены.`}
      </div>
    </Sheet>
  )
}

/* ============================ Выбор источника (S10) ============================ */
export function SheetPickSource({ slot, exclude, excludeId, excludeIds, selectedId, selectedIds, multi = false, onPick }) {
  const sources = useStore((s) => s.sources)
  const closeSheet = useStore((s) => s.closeSheet)
  const items = sources.items || []
  const excluded = new Set([exclude, excludeId, ...(excludeIds || [])].filter(Boolean))
  const initialIds = selectedIds || (selectedId ? [selectedId] : [])
  const [picked, setPicked] = useState(() => new Set(initialIds))
  const groups = useMemo(() => buildTopicGroups(items.filter((s) => s.status === 'ok')), [items])
  const [expanded, setExpanded] = useState(() => {
    const out = {}
    for (const g of groups) {
      if (g.kind === 'forum') out[g.id] = forumChoices(g).some((c) => picked.has(c.source.id))
    }
    return out
  })

  // Привязанные (доступные) — статус ok. Остальные показываем неактивными.
  const available = items.filter((s) => s.status === 'ok')
  const unavailable = items.filter((s) => s.status !== 'ok')

  // Существующий вызывающий код (S10) ждёт id первым аргументом; полный объект
  // отдаём вторым — на случай, если потребителю нужен сам источник.
  const choose = (source) => {
    host.haptic('selection')
    if (multi) {
      if (excluded.has(source.id)) return
      setPicked((prev) => {
        if (!isTopicSource(source)) {
          return prev.has(source.id) ? new Set() : new Set([source.id])
        }
        const forumId = baseSourceId(source)
        const next = new Set(prev)
        for (const id of [...next]) {
          const old = items.find((s) => s.id === id)
          if (!isTopicSource(old) || baseSourceId(old) !== forumId) next.delete(id)
        }
        if (next.has(source.id)) next.delete(source.id)
        else next.add(source.id)
        return next
      })
      return
    }
    onPick?.(source.id, source)
    closeSheet()
  }

  const done = () => {
    host.haptic('selection')
    onPick?.([...picked])
    closeSheet()
  }

  const selectedCount = picked.size
  const check = (source) => picked.has(source.id)

  const sourceRow = (s, title = s.title, extra = null) => {
    const isExcluded = excluded.has(s.id)
    const isSelected = check(s)
    return (
      <Cell
        key={s.id}
        tap={!isExcluded}
        before={<Avatar size={40} tone={s.tone} icon={s.type === 'channel' ? <Icon.megaphone /> : <Icon.people />} src={s.avatar} />}
        title={title}
        subtitle={<><MBadge m={s.messenger} /><TBadge type={s.type === 'topic' ? 'topic' : s.isForum ? 'supergroup' : s.type} />{extra}</>}
        after={isSelected ? <span style={{ color: 'var(--accent)' }}><Icon.check size={20} /></span> : undefined}
        onClick={isExcluded ? undefined : () => choose(s)}
        style={isExcluded ? { opacity: 0.45, pointerEvents: 'none' } : undefined}
      />
    )
  }

  const topicRow = (s, title = s.title) => {
    const isExcluded = excluded.has(s.id)
    const isSelected = check(s)
    return (
      <Cell
        key={s.id}
        tap={!isExcluded}
        compact
        before={<span style={{ width: 40, display: 'flex', justifyContent: 'center', color: 'var(--text-tertiary)' }}>
          <Icon.chevron size={16} />
        </span>}
        title={title}
        subtitle={<><TBadge type={s.type} />{s.rightsOk === false && <span className="dng" style={{ fontSize: 12 }}>· нет прав</span>}</>}
        after={isSelected ? <span style={{ color: 'var(--accent)' }}><Icon.check size={20} /></span> : undefined}
        onClick={isExcluded ? undefined : () => choose(s)}
        style={isExcluded ? { opacity: 0.45, pointerEvents: 'none' } : undefined}
      />
    )
  }

  return (
    <Sheet
      title={multi ? 'Выберите источники' : 'Выберите источник'}
      footer={multi ? <Btn disabled={selectedCount === 0} kind={selectedCount === 0 ? 'gray' : 'primary'} onClick={done}>
        {selectedCount ? `Выбрать: ${selectedCount}` : 'Выберите хотя бы один'}
      </Btn> : undefined}
    >
      {available.length === 0 && unavailable.length === 0 && (
        <div className="t-footnote sec text-pretty" style={{ textAlign: 'center', padding: '24px 8px' }}>
          Источников ещё нет.
        </div>
      )}

      {available.length > 0 && (
        <div className="island">
          {groups.map((item) => {
            if (item.kind === 'source') return sourceRow(item.source)
            const title = item.base?.title || baseTitle(item.topics[0], items)
            const choices = forumChoices(item)
            const selectedInGroup = choices.filter((c) => picked.has(c.source.id)).length
            const open = expanded[item.id] !== false
            return (
              <React.Fragment key={item.id}>
                <Cell
                  tap
                  before={<Avatar size={40} tone={item.base?.tone || item.topics[0]?.tone}
                    icon={<Icon.people />} src={item.base?.avatar || item.topics[0]?.avatar} />}
                  title={title}
                  subtitle={<><MBadge m="tg" /><TBadge type="supergroup" /><span>{item.topics.length} тем</span>{selectedInGroup > 0 && <span>· выбрано {selectedInGroup}</span>}</>}
                  after={<span style={{ color: 'var(--text-tertiary)', transform: open ? 'rotate(90deg)' : undefined, display: 'inline-flex' }}><Icon.chevron size={18} /></span>}
                  onClick={() => {
                    host.haptic('selection')
                    setExpanded((v) => ({ ...v, [item.id]: v[item.id] === false }))
                  }}
                />
                {open && choices.map(({ source, label }) => topicRow(
                  source,
                  label || topicTitle(source, items),
                ))}
              </React.Fragment>
            )
          })}
        </div>
      )}

      {unavailable.length > 0 && (
        <>
          <div className="cell-header caps">Недоступны</div>
          <div className="island">
            {unavailable.map((s) => (
              <Cell
                key={s.id}
                tap={false}
                before={<Avatar size={40} tone={s.tone} icon={s.type === 'channel' ? <Icon.megaphone /> : <Icon.people />} src={s.avatar} />}
                title={s.title}
                subtitle={<><MBadge m={s.messenger} /><TBadge type={s.type === 'topic' ? 'topic' : s.isForum ? 'supergroup' : s.type} /><span className="dng" style={{ fontSize: 12 }}>· не привязан</span></>}
                style={{ opacity: 0.5, pointerEvents: 'none' }}
              />
            ))}
          </div>
        </>
      )}
    </Sheet>
  )
}

/* ============================ Удаление правила (S9 и S10) ============================ */
export function SheetDeleteRule({ ruleId, fromEditor }) {
  const closeSheet = useStore((s) => s.closeSheet)
  const deleteRule = useStore((s) => s.deleteRule)
  const pop = useStore((s) => s.pop)
  const showToast = useStore((s) => s.showToast)
  const stack = useStore((s) => s.nav.stack)

  const del = async () => {
    host.haptic('warning')
    try {
      await deleteRule(ruleId)
      closeSheet()
      // Если открыт редактор правила (S10) — закрываем и его.
      const editorOpen = fromEditor ?? (stack.length > 0 && stack[stack.length - 1].name === 'S10')
      if (editorOpen) pop()
      showToast('Правило удалено')
    } catch (err) {
      showToast(errorMessage(err, 'Не удалось удалить'), 'alert')
    }
  }

  return (
    <Sheet
      title="Удалить правило"
      footer={
        <>
          <Btn kind="destructive" onClick={del}>Удалить</Btn>
          <Btn kind="secondary" onClick={closeSheet}>Отмена</Btn>
        </>
      }
    >
      <div className="t-body-sm text-pretty" style={{ padding: '4px 0 8px', color: 'var(--text-secondary)' }}>
        Удалить правило? Пересылка между этими источниками прекратится.
      </div>
    </Sheet>
  )
}

/* ============================ Шторка-заглушка оплаты ============================ */
export function SheetPayStub() {
  const closeSheet = useStore((s) => s.closeSheet)
  return (
    <Sheet
      footer={<Btn onClick={closeSheet}>Понятно</Btn>}
    >
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', padding: '14px 8px 8px', gap: 14 }}>
        <span style={{ color: 'var(--accent)' }}><Icon.spark size={44} /></span>
        <div className="t-body-sm text-pretty" style={{ maxWidth: 300, color: 'var(--text-secondary)' }}>{PAY_STUB}</div>
      </div>
    </Sheet>
  )
}

/* ============================ Хост не распознан (полноэкранная заглушка) ============================ */
export function HostNotRecognized() {
  return (
    <div className="screen">
      <div className="fullscreen-msg">
        <BrandMark size={72} />
        <div className="t-body-sm text-pretty" style={{ maxWidth: 300, color: 'var(--text-secondary)' }}>
          Приложение работает внутри MAX или Telegram. Откройте его из бота.
        </div>
      </div>
    </div>
  )
}

/* ---- хелпер склонения ---- */
function plural(n, one, few, many) {
  const m10 = n % 10
  const m100 = n % 100
  if (m10 === 1 && m100 !== 11) return one
  if (m10 >= 2 && m10 <= 4 && (m100 < 10 || m100 >= 20)) return few
  return many
}
