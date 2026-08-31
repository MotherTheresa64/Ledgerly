import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import ThemeSwitcher from './ThemeSwitcher'
import { installTransactionTextLimits } from './inputGuardrails'
import { installTransactionPagination } from './transactionPagination'
import { installMobileNavigation } from './mobileNavigation'
import './styles.css'
import './consumer.css'
import './themes.css'
import './guardrails.css'
import './pagination.css'
import './mobileNavigation.css'

installTransactionTextLimits()
installTransactionPagination()
installMobileNavigation()

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
    <ThemeSwitcher />
  </React.StrictMode>,
)
