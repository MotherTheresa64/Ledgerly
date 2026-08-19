import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import ThemeSwitcher from './ThemeSwitcher'
import { installTransactionTextLimits } from './inputGuardrails'
import './styles.css'
import './consumer.css'
import './themes.css'
import './guardrails.css'

installTransactionTextLimits()

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
    <ThemeSwitcher />
  </React.StrictMode>,
)
