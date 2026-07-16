export function parseSourceId(id) {
  const parts = String(id || '').split(':')
  if (parts.length !== 2 && parts.length !== 3) return null
  if (parts[0] !== 'tg' && parts[0] !== 'max') return null
  if (parts.length === 3 && parts[0] !== 'tg') return null
  return { messenger: parts[0], chatId: parts[1], threadId: parts[2] || null }
}

export function isTopicSource(source) {
  if (!source) return false
  if (source.type === 'topic') return true
  return !!parseSourceId(source.id)?.threadId
}

export function baseSourceId(source) {
  if (!source) return null
  if (source.baseSourceId) return source.baseSourceId
  const p = parseSourceId(source.id)
  if (p?.messenger === 'tg' && p.threadId) return `tg:${p.chatId}`
  return source.id
}

export function topicThreadId(source) {
  return source?.threadId || parseSourceId(source?.id)?.threadId || null
}

export function baseTitle(source, all = []) {
  if (!source) return ''
  if (source.baseTitle) return source.baseTitle
  const base = source.baseSourceId ? all.find((s) => s.id === source.baseSourceId) : null
  if (base?.title) return base.title
  const title = source.title || ''
  const marker = ' · тема '
  const idx = title.lastIndexOf(marker)
  return idx > 0 ? title.slice(0, idx) : title
}

export function topicTitle(source, all = []) {
  if (!source) return ''
  if (source.topicTitle) return source.topicTitle
  const base = baseTitle(source, all)
  const title = source.title || ''
  const prefix = base ? `${base} · ` : ''
  if (prefix && title.startsWith(prefix) && title.length > prefix.length) {
    return title.slice(prefix.length)
  }
  const tid = topicThreadId(source)
  if (tid === '1') return 'General'
  return tid ? `Тема ${tid}` : title
}

export function sourceShortTitle(source, all = []) {
  return isTopicSource(source) ? topicTitle(source, all) : (source?.title || '')
}

export function selectionTitle(sources, all = []) {
  const list = (sources || []).filter(Boolean)
  if (list.length === 0) return ''
  if (list.length === 1) return list[0].title || sourceShortTitle(list[0], all)
  const firstBase = baseSourceId(list[0])
  const sameForum = firstBase && list.every((s) => isTopicSource(s) && baseSourceId(s) === firstBase)
  return sameForum ? `${baseTitle(list[0], all)} · ${list.length} тем` : `${list.length} источника`
}

export function selectionSubtitle(sources, all = []) {
  const list = (sources || []).filter(Boolean)
  if (list.length <= 1) return ''
  return list.map((s) => sourceShortTitle(s, all)).join(', ')
}

export function buildTopicGroups(items) {
  const all = items || []
  const byId = new Map(all.map((s) => [s.id, s]))
  const groups = new Map()
  const singles = []

  for (const source of all) {
    if (!isTopicSource(source)) {
      continue
    }
    const key = baseSourceId(source)
    if (!key) continue
    if (!groups.has(key)) groups.set(key, { id: key, base: byId.get(key) || null, topics: [] })
    groups.get(key).topics.push(source)
  }

  const topicBaseIds = new Set(groups.keys())
  for (const source of all) {
    if (isTopicSource(source)) continue
    if (topicBaseIds.has(source.id)) continue
    singles.push({ kind: 'source', source })
  }

  const out = [...singles]
  for (const group of groups.values()) {
    group.topics.sort((a, b) => sourceShortTitle(a, all).localeCompare(sourceShortTitle(b, all), undefined, { numeric: true }))
    out.push({ kind: 'forum', ...group })
  }
  out.sort((a, b) => {
    const at = a.kind === 'forum' ? (a.base?.title || baseTitle(a.topics[0], all)) : a.source.title
    const bt = b.kind === 'forum' ? (b.base?.title || baseTitle(b.topics[0], all)) : b.source.title
    return String(at || '').localeCompare(String(bt || ''), undefined, { numeric: true })
  })
  return out
}

export function forumChoices(group) {
  return (group?.topics || []).map((topic) => ({ source: topic, label: topicTitle(topic, group.topics) }))
}
