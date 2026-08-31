const MOBILE_NAV_BREAKPOINT = 600

function closeMenu(sidebar: HTMLElement, toggle: HTMLButtonElement) {
  sidebar.classList.remove('mobile-menu-open')
  toggle.setAttribute('aria-expanded', 'false')
}

function setupSidebar(sidebar: HTMLElement) {
  if (sidebar.dataset.mobileNavReady === 'true') return

  const nav = sidebar.querySelector<HTMLElement>('nav[aria-label="Primary navigation"]')
  if (!nav) return

  sidebar.dataset.mobileNavReady = 'true'

  if (!nav.id) nav.id = 'ledgerly-primary-navigation'

  const toggle = document.createElement('button')
  toggle.type = 'button'
  toggle.className = 'mobile-nav-toggle'
  toggle.setAttribute('aria-label', 'Open Ledgerly navigation')
  toggle.setAttribute('aria-controls', nav.id)
  toggle.setAttribute('aria-expanded', 'false')
  toggle.innerHTML = `
    <span class="mobile-nav-icon" aria-hidden="true"><i></i><i></i><i></i></span>
    <span class="mobile-nav-label">Menu</span>
  `

  sidebar.insertBefore(toggle, nav)

  toggle.addEventListener('click', event => {
    event.stopPropagation()
    const opening = !sidebar.classList.contains('mobile-menu-open')
    sidebar.classList.toggle('mobile-menu-open', opening)
    toggle.setAttribute('aria-expanded', opening ? 'true' : 'false')
    toggle.setAttribute('aria-label', opening ? 'Close Ledgerly navigation' : 'Open Ledgerly navigation')
  })

  nav.addEventListener('click', event => {
    if ((event.target as HTMLElement).closest('button')) closeMenu(sidebar, toggle)
  })

  sidebar.addEventListener('keydown', event => {
    if (event.key === 'Escape') {
      closeMenu(sidebar, toggle)
      toggle.focus()
    }
  })
}

function scanForSidebar() {
  document.querySelectorAll<HTMLElement>('.sidebar').forEach(setupSidebar)
}

export function installMobileNavigation() {
  scanForSidebar()

  const observer = new MutationObserver(scanForSidebar)
  observer.observe(document.documentElement, { childList: true, subtree: true })

  document.addEventListener('click', event => {
    if (window.innerWidth > MOBILE_NAV_BREAKPOINT) return
    document.querySelectorAll<HTMLElement>('.sidebar.mobile-menu-open').forEach(sidebar => {
      if (sidebar.contains(event.target as Node)) return
      const toggle = sidebar.querySelector<HTMLButtonElement>('.mobile-nav-toggle')
      if (toggle) closeMenu(sidebar, toggle)
    })
  })

  window.addEventListener('resize', () => {
    if (window.innerWidth <= MOBILE_NAV_BREAKPOINT) return
    document.querySelectorAll<HTMLElement>('.sidebar.mobile-menu-open').forEach(sidebar => {
      const toggle = sidebar.querySelector<HTMLButtonElement>('.mobile-nav-toggle')
      if (toggle) closeMenu(sidebar, toggle)
    })
  })
}
