/* main.jsx — точка входа Vite. */
import React from 'react'
import { createRoot } from 'react-dom/client'
import '@telegram-apps/telegram-ui/dist/styles.css'  // дизайн-система библиотеки (до наших токенов)
import './styles/theme.css'                          // наши токены/мост к --tgui--* поверх
import App from './App.jsx'

createRoot(document.getElementById('root')).render(<App />)
