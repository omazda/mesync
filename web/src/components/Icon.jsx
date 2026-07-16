/* Icon.jsx — единый набор иконок приложения поверх библиотеки lucide-react
 * (стандартный аутлайн-набор: stroke currentColor, viewBox 24, скруглённые концы).
 * Обёртка сохраняет API прежнего самописного набора: Icon.имя с пропсами
 * size/fill/stroke/style и базовой толщиной 1.7. Vite tree-shaking оставляет
 * в бандле только импортированные ниже иконки. */
import React from 'react'
import {
  ChevronRight, ChevronLeft, X, Plus, Check, Copy, Clock, TriangleAlert, Bell, Search,
  ArrowRight, ArrowLeft, ArrowLeftRight, Workflow, MessageSquare, Settings, Megaphone,
  Users, Signature, Gift, Gauge, RefreshCw, Trash2, Ellipsis, CreditCard,
  ShieldCheck, Link, Sparkles, Pause, Play, Pencil, WifiOff, KeyRound, CircleHelp,
  Send, Mail, LogOut,
} from 'lucide-react'

/* filled — иконки-заливки (play/pause): fill вместо контура. */
const _ic = (C, sw = 1.7, filled = false) =>
  function I({ size = 22, fill = filled, stroke = !filled, style } = {}) {
    return (
      <C size={size} strokeWidth={sw} aria-hidden="true"
        fill={fill ? 'currentColor' : 'none'}
        stroke={stroke ? 'currentColor' : 'none'}
        style={{ display: 'block', ...style }} />
    )
  }

export const Icon = {
  chevron: _ic(ChevronRight),
  back: _ic(ChevronLeft, 2),
  close: _ic(X, 1.8),
  plus: _ic(Plus, 1.9),
  check: _ic(Check, 2),
  copy: _ic(Copy),
  clock: _ic(Clock),
  alert: _ic(TriangleAlert),
  bell: _ic(Bell),
  search: _ic(Search),
  arrowR: _ic(ArrowRight, 1.9),
  arrowL: _ic(ArrowLeft, 1.9),
  arrowBoth: _ic(ArrowLeftRight, 1.9),
  rules: _ic(Workflow),
  source: _ic(MessageSquare),
  settings: _ic(Settings),
  megaphone: _ic(Megaphone),
  people: _ic(Users),
  signature: _ic(Signature),
  gift: _ic(Gift),
  traffic: _ic(Gauge),
  refresh: _ic(RefreshCw),
  trash: _ic(Trash2),
  dots: _ic(Ellipsis),
  card: _ic(CreditCard),
  shield: _ic(ShieldCheck),
  link: _ic(Link),
  spark: _ic(Sparkles),
  pause: _ic(Pause, 1.7, true),
  play: _ic(Play, 1.7, true),
  edit: _ic(Pencil),
  wifiOff: _ic(WifiOff),
  key: _ic(KeyRound),
  help: _ic(CircleHelp),
  send: _ic(Send),
  mail: _ic(Mail),
  logout: _ic(LogOut),
}

export default Icon
