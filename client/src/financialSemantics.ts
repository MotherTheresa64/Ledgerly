function applyFinancialSemantics() {
  document.querySelectorAll<HTMLElement>('.metric > span').forEach(label => {
    if (label.textContent?.trim() === 'Tracked balance') label.textContent = 'Net worth'
  })

  const liquidity = document.querySelector<HTMLElement>('.accounts-strip .card-head > span')
  if (liquidity?.textContent?.includes(' included in totals')) {
    liquidity.textContent = liquidity.textContent.replace(' included in totals', ' liquid balance')
  }

  document.querySelectorAll<HTMLElement>('.sidebar-foot > span').forEach(version => {
    if (version.textContent?.trim() === 'Ledgerly v1.2') version.textContent = 'Ledgerly v1.3'
  })
}

export function installFinancialSemantics() {
  applyFinancialSemantics()
  let scheduled = false
  const observer = new MutationObserver(mutations => {
    if (!mutations.some(mutation => mutation.addedNodes.length || mutation.removedNodes.length)) return
    if (scheduled) return
    scheduled = true
    requestAnimationFrame(() => {
      scheduled = false
      applyFinancialSemantics()
    })
  })
  observer.observe(document.body, { childList: true, subtree: true })
}
