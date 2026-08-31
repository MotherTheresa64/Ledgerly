import { useEffect, useState } from 'react'

type ThemeId = 'midnight' | 'emerald' | 'violet' | 'amber' | 'graphite'

const themes: { id: ThemeId; name: string; description: string }[] = [
  { id: 'midnight', name: 'Midnight', description: 'Near-black navy with cool blue accents' },
  { id: 'emerald', name: 'Emerald', description: 'Near-black charcoal with Ledgerly green' },
  { id: 'violet', name: 'Violet', description: 'Near-black plum with violet accents' },
  { id: 'amber', name: 'Amber', description: 'Near-black charcoal with warm gold accents' },
  { id: 'graphite', name: 'Graphite', description: 'Neutral near-black with slate accents' },
]

function getInitialTheme(): ThemeId {
  const saved = localStorage.getItem('ledgerly_theme') as ThemeId | null
  if (saved && themes.some(theme => theme.id === saved)) return saved
  return 'emerald'
}

export default function ThemeSwitcher() {
  const [theme, setTheme] = useState<ThemeId>(getInitialTheme)
  const [open, setOpen] = useState(false)

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    document.documentElement.style.colorScheme = 'dark'
    localStorage.setItem('ledgerly_theme', theme)
  }, [theme])

  return <div className="theme-switcher">
    {open && <div className="theme-popover" role="dialog" aria-label="Choose appearance theme">
      <div className="theme-popover-head">
        <div><strong>Appearance</strong><span>All Ledgerly themes keep the same dark foundation.</span></div>
        <button type="button" className="theme-close" aria-label="Close theme picker" onClick={() => setOpen(false)}>×</button>
      </div>
      <div className="theme-options">
        {themes.map(option => <button type="button" key={option.id} className={`theme-option ${theme === option.id ? 'selected' : ''}`} aria-pressed={theme === option.id} onClick={() => setTheme(option.id)}>
          <span className={`theme-swatch ${option.id}`} aria-hidden="true"><i /><i /><i /></span>
          <span><strong>{option.name}</strong><small>{option.description}</small></span>
          {theme === option.id && <b aria-hidden="true">✓</b>}
        </button>)}
      </div>
    </div>}
    <button type="button" className="theme-trigger" onClick={() => setOpen(value => !value)} aria-expanded={open} aria-label="Change Ledgerly theme"><span aria-hidden="true">◐</span><span>Theme</span></button>
  </div>
}
