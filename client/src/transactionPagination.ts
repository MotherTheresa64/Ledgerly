const PAGE_SIZE = 10

let currentPage = 1
let scheduled = false
let lastList: HTMLElement | null = null
let lastSignature = ''

function signatureFor(rows: HTMLElement[]) {
  return rows.map(row => row.textContent || '').join('\u001f')
}

function visiblePageNumbers(page: number, totalPages: number) {
  if (totalPages <= 7) return Array.from({ length: totalPages }, (_, index) => index + 1)

  const pages = new Set<number>([1, totalPages, page - 1, page, page + 1])
  if (page <= 4) [2, 3, 4, 5].forEach(value => pages.add(value))
  if (page >= totalPages - 3) [totalPages - 4, totalPages - 3, totalPages - 2, totalPages - 1].forEach(value => pages.add(value))
  return [...pages].filter(value => value >= 1 && value <= totalPages).sort((a, b) => a - b)
}

function scrollHistoryIntoView() {
  const manager = document.querySelector<HTMLElement>('.transaction-manager')
  if (!manager) return
  const top = manager.getBoundingClientRect().top + window.scrollY - 12
  window.scrollTo({ top, behavior: 'smooth' })
}

function renderPagination(list: HTMLElement, totalPages: number) {
  const manager = list.closest<HTMLElement>('.transaction-manager')
  if (!manager) return

  let nav = manager.querySelector<HTMLElement>('.transaction-pagination')
  if (totalPages <= 1) {
    nav?.remove()
    return
  }

  if (!nav) {
    nav = document.createElement('nav')
    nav.className = 'transaction-pagination'
    nav.setAttribute('aria-label', 'Transaction history pages')
    list.insertAdjacentElement('afterend', nav)
  }

  const state = `${currentPage}:${totalPages}`
  if (nav.dataset.state === state) return
  nav.dataset.state = state
  nav.replaceChildren()

  const addButton = (label: string, page: number, options: { active?: boolean; disabled?: boolean; aria?: string } = {}) => {
    const button = document.createElement('button')
    button.type = 'button'
    button.textContent = label
    button.className = options.active ? 'active' : ''
    button.disabled = !!options.disabled
    if (options.active) button.setAttribute('aria-current', 'page')
    if (options.aria) button.setAttribute('aria-label', options.aria)
    button.addEventListener('click', () => {
      if (page === currentPage || page < 1 || page > totalPages) return
      currentPage = page
      applyPagination(false)
      scrollHistoryIntoView()
    })
    nav!.appendChild(button)
  }

  addButton('‹', currentPage - 1, { disabled: currentPage === 1, aria: 'Previous page' })

  const pages = visiblePageNumbers(currentPage, totalPages)
  let previous = 0
  for (const page of pages) {
    if (previous && page - previous > 1) {
      const ellipsis = document.createElement('span')
      ellipsis.className = 'pagination-ellipsis'
      ellipsis.textContent = '…'
      ellipsis.setAttribute('aria-hidden', 'true')
      nav.appendChild(ellipsis)
    }
    addButton(String(page), page, { active: page === currentPage, aria: `Page ${page}` })
    previous = page
  }

  addButton('›', currentPage + 1, { disabled: currentPage === totalPages, aria: 'Next page' })

  const summary = document.createElement('span')
  summary.className = 'pagination-summary'
  summary.textContent = `Page ${currentPage} of ${totalPages}`
  nav.appendChild(summary)
}

function applyPagination(resetOnListChange = true) {
  const list = document.querySelector<HTMLElement>('.transaction-manager .transactions')
  if (!list) {
    lastList = null
    lastSignature = ''
    currentPage = 1
    return
  }

  const rows = Array.from(list.children).filter((child): child is HTMLElement => child instanceof HTMLElement && child.classList.contains('transaction'))
  const signature = signatureFor(rows)

  if (resetOnListChange && (list !== lastList || signature !== lastSignature)) currentPage = 1
  lastList = list
  lastSignature = signature

  const totalPages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE))
  currentPage = Math.min(Math.max(currentPage, 1), totalPages)
  const start = (currentPage - 1) * PAGE_SIZE
  const end = start + PAGE_SIZE

  rows.forEach((row, index) => {
    row.hidden = index < start || index >= end
  })

  renderPagination(list, totalPages)
}

function schedulePagination() {
  if (scheduled) return
  scheduled = true
  window.requestAnimationFrame(() => {
    scheduled = false
    applyPagination(true)
  })
}

export function installTransactionPagination() {
  schedulePagination()
  const observer = new MutationObserver(schedulePagination)
  observer.observe(document.body, { childList: true, subtree: true })
}
