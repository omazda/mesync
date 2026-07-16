/* useScheme — React-хук текущей цветовой темы хоста (light|dark), реактивный. */
import { useEffect, useState } from 'react'
import host from './host.js'

function normalizeScheme(value) {
  return value === 'dark' ? 'dark' : 'light'
}

export function useScheme() {
  const [scheme, setScheme] = useState(normalizeScheme(host.colorScheme))
  useEffect(() => host.onThemeChanged((value) => setScheme(normalizeScheme(value))), [])
  return scheme
}
