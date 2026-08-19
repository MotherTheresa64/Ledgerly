import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import ThemeSwitcher from './ThemeSwitcher'
import './styles.css'
import './consumer.css'
import './themes.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
    <ThemeSwitcher />
  </React.StrictMode>,
)
