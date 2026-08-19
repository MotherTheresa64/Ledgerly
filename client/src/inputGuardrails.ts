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
    if (counter) counter.textContent = `${field.value.length} / ${max}`
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
  const observer = new MutationObserver(applyTransactionTextLimits)
  observer.observe(document.body, { childList: true, subtree: true })
}
