/* registry.js — карта имён экранов/листов на компоненты (для Navigator). */
import { BrowserEntry, S1, S2, S3, S4 } from './auth.jsx'
import { S5 } from './paywall.jsx'
import { SLegal } from './legal.jsx'
import { S7, S8 } from './sources.jsx'
import { S6, S9, S10 } from './rules.jsx'
import { SH, S11, S12, S13 } from './settings.jsx'
import { S14 } from './faq.jsx'
import { SReport } from './report.jsx'
import { MarketActivation } from './marketActivation.jsx'
import {
  SheetWhatIsSource, SheetBindHowTo, SheetActivationCode, SheetSourceDetail,
  SheetDeleteSource, SheetPickSource, SheetDeleteRule, SheetPayStub, HostNotRecognized,
} from './sheets.jsx'

export const SCREENS = {
  S1, S2, S3, S4, S5, S6, S7, S8, S9, S10, S11, S12, S13, S14, SH,
  SLegal, SReport, BrowserEntry, MarketActivation, HostNotRecognized,
}

export const SHEETS = {
  whatIsSource: SheetWhatIsSource,
  bindHowTo: SheetBindHowTo,
  activationCode: SheetActivationCode,
  sourceDetail: SheetSourceDetail,
  deleteSource: SheetDeleteSource,
  pickSource: SheetPickSource,
  deleteRule: SheetDeleteRule,
  payStub: SheetPayStub,
}

export function getScreen(name) { return SCREENS[name] || null }
export function getSheet(name) { return SHEETS[name] || null }
