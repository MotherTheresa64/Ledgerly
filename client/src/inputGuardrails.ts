const DESCRIPTION_MAX = 80
const NOTES_MAX = 500

function addCounter(field: HTMLInputElement | HTMLTextAreaElement, max: number, kind: string) {
  field.maxLength = max
  const parent = field.parentElement
  if (!parent) return

  const selector = `.field-counter[data-for="${kind}"]`
  let counter = parent.querySelector<HTMLElement>(selector)
  if (!counter) {
    counter = document.createElement('small')
    counter.className = 'field-counter'
    counter.dataset.for = kind
    field.insertAdjacentElement('afterend', counter)
  }

  const update = () => {
    if (!counter) return
    const next = `${field.value.length} / ${max}`
    if (counter.textContent !== next) counter.textContent = next
  }

  if (!field.dataset.ledgerlyCounterBound) {
    field.addEventListener('input', update)
    field.dataset.ledgerlyCounterBound = 'true'
  }
  update()
}

function applyTransactionTextLimits() {
  document.querySelectorAll<HTMLLabelElement>('label').forEach(label => {
    const labelText = (label.childNodes[0]?.textContent || '').trim().toLowerCase()
    if (labelText === 'description') {
      const input = label.querySelector<HTMLInputElement>('input')
      if (input) addCounter(input, DESCRIPTION_MAX, 'transaction-description')
    }
    if (labelText === 'notes') {
      const textarea = label.querySelector<HTMLTextAreaElement>('textarea')
      if (textarea) addCounter(textarea, NOTES_MAX, 'transaction-notes')
    }
  })
}

export function installTransactionTextLimits() {
  applyTransactionTextLimits()

  let scheduled = false
  const observer = new MutationObserver(mutations => {
    // Only re-scan when React actually adds/removes elements. Counter text updates
    // must not recursively trigger another full DOM scan on mobile browsers.
    if (!mutations.some(mutation => mutation.addedNodes.length || mutation.removedNodes.length)) return
    if (scheduled) return

    scheduled = true
    requestAnimationFrame(() => {
      scheduled = false
      applyTransactionTextLimits()
    })
  })

  observer.observe(document.body, { childList: true, subtree: true })
}
