import { FormEvent, useEffect, useMemo, useState } from 'react'
import { api, type TransactionInput } from './api'
import type { Budget, Dashboard, Goal, MonthlyTrend, Transaction } from './types'

const money = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })
const categories = ['Income', 'Housing', 'Food & Dining', 'Utilities', 'Transport', 'Lifestyle', 'Health', 'Shopping', 'Subscriptions', 'Travel', 'Education', 'Other']
const navItems = ['Overview', 'Transactions', 'Budgets', 'Goals'] as const
const today = () => new Date().toISOString().slice(0, 10)

type Notify = (message: string, tone?: 'success' | 'error') => void

type TxDraft = {
  description: string
  amount: string
  category: string
  date: string
  notes: string
}

const emptyTx = (): TxDraft => ({ description: '', amount: '', category: 'Food & Dining', date: today(), notes: '' })

function Metric({ label, value, tone = 'green', detail }: { label: string; value: string; tone?: string; detail?: string }) {
  return <article className={`metric ${tone}`}><span>{label}</span><strong>{value}</strong>{detail && <small>{detail}</small>}</article>
}

function Progress({ value, danger = false }: { value: number; danger?: boolean }) {
  const safe = Math.min(Math.max(value, 0), 100)
  return <div className={`progress ${danger ? 'danger' : ''}`}><span style={{ width: `${safe}%` }} /></div>
}

function Empty({ title = 'Nothing here yet', body = 'Add your first item to get started.' }: { title?: string; body?: string }) {
  return <div className="empty"><strong>{title}</strong><span>{body}</span></div>
}

function Toast({ message, tone }: { message: string; tone: 'success' | 'error' }) {
  if (!message) return null
  return <div className={`toast ${tone}`}>{message}</div>
}

function App() {
  const [token, setToken] = useState(localStorage.getItem('ledgerly_token'))
  const [data, setData] = useState<Dashboard | null>(null)
  const [error, setError] = useState('')
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [active, setActive] = useState<(typeof navItems)[number]>('Overview')
  const [toast, setToast] = useState({ message: '', tone: 'success' as 'success' | 'error' })
  const [refreshing, setRefreshing] = useState(false)

  const notify: Notify = (message, tone = 'success') => {
    setToast({ message, tone })
    window.setTimeout(() => setToast({ message: '', tone }), 3200)
  }

  const refresh = async () => {
    try {
      setRefreshing(true)
      setError('')
      setData(await api.dashboard())
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Unable to load dashboard'
      setError(message)
      if (message.toLowerCase().includes('token') || message.toLowerCase().includes('authorization')) {
        localStorage.removeItem('ledgerly_token')
        setToken(null)
      }
    } finally {
      setRefreshing(false)
    }
  }

  useEffect(() => { if (token) void refresh() }, [token])

  const handleAuth = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    try {
      setError('')
      const result = mode === 'login'
        ? await api.login(String(form.get('email')), String(form.get('password')))
        : await api.register(String(form.get('email')), String(form.get('password')))
      localStorage.setItem('ledgerly_token', result.accessToken)
      setToken(result.accessToken)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Authentication failed')
    }
  }

  const signOut = () => {
    localStorage.removeItem('ledgerly_token')
    setToken(null)
    setData(null)
    setActive('Overview')
  }

  if (!token) {
    return <main className="auth-shell">
      <section className="brand-panel">
        <div className="logo-mark">L</div>
        <h1>Ledgerly</h1>
        <p>Personal finance. Full control. Smarter decisions.</p>
        <div className="brand-proof">
          <div><strong>01</strong><span>Track every dollar</span></div>
          <div><strong>02</strong><span>Build realistic budgets</span></div>
          <div><strong>03</strong><span>Turn goals into progress</span></div>
        </div>
      </section>
      <section className="auth-wrap">
        <div className="auth-card">
          <span className="eyebrow">WELCOME TO LEDGERLY</span>
          <h2>{mode === 'login' ? 'Welcome back' : 'Create your account'}</h2>
          <p>Build a clearer picture of your money.</p>
          <form onSubmit={handleAuth}>
            <label>Email<input name="email" type="email" autoComplete="email" required placeholder="you@example.com" /></label>
            <label>Password<input name="password" type="password" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} minLength={8} required placeholder="Minimum 8 characters" /></label>
            {error && <div className="error">{error}</div>}
            <button className="primary" type="submit">{mode === 'login' ? 'Sign in' : 'Create account'}</button>
          </form>
          <button className="text-button" onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError('') }}>
            {mode === 'login' ? 'Need an account? Register' : 'Already registered? Sign in'}
          </button>
        </div>
      </section>
    </main>
  }

  return <div className="app-shell">
    <Toast {...toast} />
    <aside className="sidebar">
      <div className="brand"><div className="logo-mark small">L</div><div><strong>Ledgerly</strong><span>Money, clarified.</span></div></div>
      <nav>{navItems.map(item => <button key={item} className={active === item ? 'active' : ''} onClick={() => setActive(item)}><span className="nav-dot" />{item}</button>)}</nav>
      <div className="sidebar-foot"><span>Local portfolio build</span><button className="logout" onClick={signOut}>Sign out</button></div>
    </aside>

    <main className="dashboard">
      <header>
        <div><span className="eyebrow">PERSONAL FINANCE</span><h1>{active}</h1><p>{pageDescription(active)}</p></div>
        <button className="secondary" disabled={refreshing} onClick={refresh}>{refreshing ? 'Refreshing…' : 'Refresh data'}</button>
      </header>
      {error && <div className="error">{error}</div>}
      {!data ? <div className="loading"><span className="spinner" />Loading Ledgerly…</div> : <>
        {active === 'Overview' && <Overview data={data} refresh={refresh} notify={notify} />}
        {active === 'Transactions' && <TransactionPage data={data} refresh={refresh} notify={notify} />}
        {active === 'Budgets' && <BudgetPage data={data} refresh={refresh} notify={notify} />}
        {active === 'Goals' && <GoalPage data={data} refresh={refresh} notify={notify} />}
      </>}
    </main>
  </div>
}

function pageDescription(active: string) {
  if (active === 'Transactions') return 'Search, categorize, edit, and manage your cash flow.'
  if (active === 'Budgets') return 'Set monthly guardrails and see where your money is going.'
  if (active === 'Goals') return 'Build momentum toward the things that matter most.'
  return 'A clear snapshot of your financial month.'
}

function Overview({ data, refresh, notify }: { data: Dashboard; refresh: () => Promise<void>; notify: Notify }) {
  const totalGoalSaved = data.goals.reduce((sum, goal) => sum + goal.saved, 0)
  const totalGoalTarget = data.goals.reduce((sum, goal) => sum + goal.target, 0)
  const overBudget = data.budgets.filter(b => b.spent > b.limit).length
  const topCategory = data.categories[0]

  return <>
    <section className="metrics">
      <Metric label="Net balance" value={money.format(data.totalBalance)} detail="Income minus tracked spending" />
      <Metric label="Income" value={money.format(data.income)} detail={`${data.transactions.filter(t => t.amount > 0).length} income entries`} />
      <Metric label="Expenses" value={money.format(data.expenses)} tone="red" detail={`${data.transactions.filter(t => t.amount < 0).length} expense entries`} />
      <Metric label="Savings rate" value={`${data.savingsRate.toFixed(1)}%`} tone="amber" detail={data.savingsRate >= 20 ? 'Healthy monthly margin' : 'Room to improve'} />
    </section>

    <section className="grid overview-grid">
      <TrendChart trend={data.monthlyTrend} />
      <article className="card insights-card">
        <div className="card-head"><h3>Quick insights</h3><span>At a glance</span></div>
        <div className="insight-list">
          <div><span>Top spending category</span><strong>{topCategory ? `${topCategory.category} · ${money.format(topCategory.amount)}` : 'No spending yet'}</strong></div>
          <div><span>Budget health</span><strong className={overBudget ? 'expense' : 'income'}>{overBudget ? `${overBudget} over limit` : 'All budgets on track'}</strong></div>
          <div><span>Goal funding</span><strong>{totalGoalTarget ? `${Math.min((totalGoalSaved / totalGoalTarget) * 100, 100).toFixed(0)}% funded` : 'No goals yet'}</strong></div>
        </div>
      </article>
    </section>

    <section className="grid two">
      <article className="card"><div className="card-head"><h3>Spending breakdown</h3><span>All tracked expenses</span></div>
        {data.categories.length ? <div className="category-list">{data.categories.map(c => <div key={c.category}><span>{c.category}</span><strong>{money.format(c.amount)}</strong><Progress value={data.expenses ? (c.amount / data.expenses) * 100 : 0} /></div>)}</div> : <Empty />}
      </article>
      <article className="card"><div className="card-head"><h3>Budget progress</h3><span>Current month</span></div>
        {data.budgets.length ? <div className="category-list">{data.budgets.map(b => <div key={b.id}><span>{b.category}</span><strong className={b.spent > b.limit ? 'expense' : ''}>{money.format(b.spent)} / {money.format(b.limit)}</strong><Progress danger={b.spent > b.limit} value={(b.spent / b.limit) * 100} /></div>)}</div> : <Empty />}
      </article>
    </section>

    <section className="grid two">
      <TransactionSummary transactions={data.transactions.slice(0, 6)} />
      <article className="card"><div className="card-head"><h3>Savings goals</h3><span>{data.goals.length} active</span></div>
        {data.goals.length ? <div className="category-list">{data.goals.slice(0, 5).map(g => <div key={g.id}><span>{g.name}</span><strong>{money.format(g.saved)} / {money.format(g.target)}</strong><Progress value={(g.saved / g.target) * 100} /></div>)}</div> : <Empty />}
      </article>
    </section>

    {!data.transactions.length && <button className="primary demo" onClick={async () => { try { await api.seedDemo(); await refresh(); notify('Demo data loaded. Explore the dashboard!') } catch (e) { notify(e instanceof Error ? e.message : 'Unable to load demo data', 'error') } }}>Load realistic demo data</button>}
  </>
}

function TrendChart({ trend }: { trend: MonthlyTrend[] }) {
  const max = Math.max(1, ...trend.flatMap(item => [item.income, item.expenses]))
  return <article className="card trend-card">
    <div className="card-head"><div><h3>Cash flow trend</h3><p>Income vs. expenses over six months</p></div><div className="legend"><span className="income-key">Income</span><span className="expense-key">Expenses</span></div></div>
    <div className="trend-chart">{trend.map(item => <div className="trend-column" key={item.month}>
      <div className="bars"><span className="bar income-bar" title={`Income ${money.format(item.income)}`} style={{ height: `${Math.max((item.income / max) * 100, item.income ? 4 : 0)}%` }} /><span className="bar expense-bar" title={`Expenses ${money.format(item.expenses)}`} style={{ height: `${Math.max((item.expenses / max) * 100, item.expenses ? 4 : 0)}%` }} /></div>
      <strong>{item.month}</strong><small className={item.net >= 0 ? 'income' : 'expense'}>{money.format(item.net)}</small>
    </div>)}</div>
  </article>
}

function TransactionSummary({ transactions }: { transactions: Transaction[] }) {
  return <article className="card"><div className="card-head"><h3>Recent transactions</h3><span>{transactions.length} shown</span></div>
    {transactions.length ? <div className="transactions">{transactions.map(t => <TransactionRow key={t.id} transaction={t} />)}</div> : <Empty />}
  </article>
}

function TransactionRow({ transaction, onEdit, onDelete }: { transaction: Transaction; onEdit?: (t: Transaction) => void; onDelete?: (t: Transaction) => void }) {
  return <div className="transaction"><div className="transaction-main"><span className={`tx-icon ${transaction.amount >= 0 ? 'positive' : ''}`}>{transaction.amount >= 0 ? '+' : '−'}</span><div><strong>{transaction.description}</strong><span>{transaction.category} · {new Date(`${transaction.date}T12:00:00`).toLocaleDateString()}</span>{transaction.notes && <small>{transaction.notes}</small>}</div></div><div className="amount-wrap"><strong className={transaction.amount < 0 ? 'expense' : 'income'}>{money.format(transaction.amount)}</strong>{(onEdit || onDelete) && <div className="row-actions">{onEdit && <button title="Edit transaction" onClick={() => onEdit(transaction)}>Edit</button>}{onDelete && <button className="danger-button" title="Delete transaction" onClick={() => onDelete(transaction)}>Delete</button>}</div>}</div></div>
}

function TransactionPage({ data, refresh, notify }: { data: Dashboard; refresh: () => Promise<void>; notify: Notify }) {
  const [draft, setDraft] = useState<TxDraft>(emptyTx())
  const [editing, setEditing] = useState<number | null>(null)
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState('All')
  const [kind, setKind] = useState<'All' | 'Income' | 'Expense'>('All')
  const [busy, setBusy] = useState(false)

  const filtered = useMemo(() => data.transactions.filter(t => {
    const matchesSearch = `${t.description} ${t.category} ${t.notes || ''}`.toLowerCase().includes(search.toLowerCase())
    const matchesCategory = category === 'All' || t.category === category
    const matchesKind = kind === 'All' || (kind === 'Income' ? t.amount > 0 : t.amount < 0)
    return matchesSearch && matchesCategory && matchesKind
  }), [data.transactions, search, category, kind])

  const reset = () => { setDraft(emptyTx()); setEditing(null) }
  const edit = (t: Transaction) => { setEditing(t.id); setDraft({ description: t.description, amount: String(t.amount), category: t.category, date: t.date, notes: t.notes || '' }); window.scrollTo({ top: 0, behavior: 'smooth' }) }

  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    const payload: TransactionInput = { ...draft, amount: Number(draft.amount) }
    try {
      setBusy(true)
      if (editing) await api.updateTransaction(editing, payload)
      else await api.addTransaction(payload)
      await refresh()
      notify(editing ? 'Transaction updated.' : 'Transaction added.')
      reset()
    } catch (error) {
      notify(error instanceof Error ? error.message : 'Unable to save transaction', 'error')
    } finally { setBusy(false) }
  }

  const remove = async (t: Transaction) => {
    if (!window.confirm(`Delete “${t.description}”?`)) return
    try { await api.deleteTransaction(t.id); await refresh(); notify('Transaction deleted.'); if (editing === t.id) reset() }
    catch (error) { notify(error instanceof Error ? error.message : 'Unable to delete transaction', 'error') }
  }

  return <div className="page-stack">
    <section className="grid form-grid">
      <article className="card form-card"><div className="card-head"><div><h3>{editing ? 'Edit transaction' : 'Add transaction'}</h3><p>{editing ? 'Update the selected entry.' : 'Record income or an expense.'}</p></div>{editing && <button className="text-button inline" onClick={reset}>Cancel edit</button>}</div>
        <form className="stack" onSubmit={submit}>
          <div className="field-row"><label>Description<input value={draft.description} onChange={e => setDraft({ ...draft, description: e.target.value })} required placeholder="e.g. Grocery run" /></label><label>Amount<input value={draft.amount} onChange={e => setDraft({ ...draft, amount: e.target.value })} type="number" step="0.01" required placeholder="Negative = expense" /></label></div>
          <div className="field-row"><label>Category<select value={draft.category} onChange={e => setDraft({ ...draft, category: e.target.value })}>{categories.map(item => <option key={item}>{item}</option>)}</select></label><label>Date<input value={draft.date} onChange={e => setDraft({ ...draft, date: e.target.value })} type="date" required /></label></div>
          <label>Notes <span className="optional">optional</span><textarea value={draft.notes} onChange={e => setDraft({ ...draft, notes: e.target.value })} rows={2} placeholder="Add context for later" /></label>
          <button className="primary" disabled={busy}>{busy ? 'Saving…' : editing ? 'Update transaction' : 'Save transaction'}</button>
        </form>
      </article>
      <article className="card mini-summary"><h3>This account</h3><div><span>Transactions</span><strong>{data.transactions.length}</strong></div><div><span>Total income</span><strong className="income">{money.format(data.income)}</strong></div><div><span>Total expenses</span><strong className="expense">{money.format(data.expenses)}</strong></div></article>
    </section>

    <section className="card transaction-manager">
      <div className="card-head"><div><h3>Transaction history</h3><p>{filtered.length} of {data.transactions.length} entries</p></div></div>
      <div className="filters"><input aria-label="Search transactions" value={search} onChange={e => setSearch(e.target.value)} placeholder="Search description, category, or notes…" /><select aria-label="Filter category" value={category} onChange={e => setCategory(e.target.value)}><option>All</option>{Array.from(new Set(data.transactions.map(t => t.category))).sort().map(item => <option key={item}>{item}</option>)}</select><select aria-label="Filter type" value={kind} onChange={e => setKind(e.target.value as typeof kind)}><option>All</option><option>Income</option><option>Expense</option></select></div>
      {filtered.length ? <div className="transactions">{filtered.map(t => <TransactionRow key={t.id} transaction={t} onEdit={edit} onDelete={remove} />)}</div> : <Empty title="No matching transactions" body="Try changing your search or filters." />}
    </section>
  </div>
}

function BudgetPage({ data, refresh, notify }: { data: Dashboard; refresh: () => Promise<void>; notify: Notify }) {
  const [editing, setEditing] = useState<Budget | null>(null)
  const [category, setCategory] = useState('Food & Dining')
  const [limit, setLimit] = useState('')

  const reset = () => { setEditing(null); setCategory('Food & Dining'); setLimit('') }
  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    try {
      if (editing) await api.updateBudget(editing.id, Number(limit))
      else await api.addBudget({ category, limit: Number(limit) })
      await refresh(); notify(editing ? 'Budget updated.' : 'Budget saved.'); reset()
    } catch (error) { notify(error instanceof Error ? error.message : 'Unable to save budget', 'error') }
  }
  const edit = (budget: Budget) => { setEditing(budget); setCategory(budget.category); setLimit(String(budget.limit)); window.scrollTo({ top: 0, behavior: 'smooth' }) }
  const remove = async (budget: Budget) => {
    if (!window.confirm(`Delete the ${budget.category} budget?`)) return
    try { await api.deleteBudget(budget.id); await refresh(); notify('Budget deleted.'); if (editing?.id === budget.id) reset() }
    catch (error) { notify(error instanceof Error ? error.message : 'Unable to delete budget', 'error') }
  }

  return <div className="page-stack">
    <section className="grid form-grid"><article className="card form-card"><div className="card-head"><div><h3>{editing ? `Edit ${editing.category}` : 'Create monthly budget'}</h3><p>Set a spending ceiling for a category.</p></div>{editing && <button className="text-button inline" onClick={reset}>Cancel edit</button>}</div><form className="stack" onSubmit={submit}><label>Category<select value={category} disabled={!!editing} onChange={e => setCategory(e.target.value)}>{categories.filter(item => item !== 'Income').map(item => <option key={item}>{item}</option>)}</select></label><label>Monthly limit<input value={limit} onChange={e => setLimit(e.target.value)} type="number" min="1" step="0.01" required placeholder="500.00" /></label><button className="primary">{editing ? 'Update budget' : 'Save budget'}</button></form></article><article className="card mini-summary"><h3>Budget health</h3><div><span>Active budgets</span><strong>{data.budgets.length}</strong></div><div><span>On track</span><strong className="income">{data.budgets.filter(b => b.spent <= b.limit).length}</strong></div><div><span>Over limit</span><strong className="expense">{data.budgets.filter(b => b.spent > b.limit).length}</strong></div></article></section>
    <section className="budget-grid">{data.budgets.length ? data.budgets.map(b => { const percent = (b.spent / b.limit) * 100; const over = b.spent > b.limit; return <article className={`card budget-card ${over ? 'over' : ''}`} key={b.id}><div className="card-head"><div><h3>{b.category}</h3><span>{percent.toFixed(0)}% used</span></div><div className="row-actions"><button onClick={() => edit(b)}>Edit</button><button className="danger-button" onClick={() => remove(b)}>Delete</button></div></div><strong className="budget-value">{money.format(b.spent)} <span>/ {money.format(b.limit)}</span></strong><Progress value={percent} danger={over} /><div className="budget-foot"><span>{over ? 'Over budget by' : 'Remaining'}</span><strong className={over ? 'expense' : 'income'}>{money.format(Math.abs(b.remaining))}</strong></div></article> }) : <article className="card"><Empty title="No budgets yet" body="Create a category budget to start tracking monthly limits." /></article>}</section>
  </div>
}

function GoalPage({ data, refresh, notify }: { data: Dashboard; refresh: () => Promise<void>; notify: Notify }) {
  const [editing, setEditing] = useState<Goal | null>(null)
  const [name, setName] = useState('')
  const [target, setTarget] = useState('')
  const [saved, setSaved] = useState('')
  const [contributions, setContributions] = useState<Record<number, string>>({})

  const reset = () => { setEditing(null); setName(''); setTarget(''); setSaved('') }
  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    try {
      if (editing) await api.updateGoal(editing.id, { name, target: Number(target), saved: Number(saved || 0) })
      else await api.addGoal({ name, target: Number(target), saved: Number(saved || 0) })
      await refresh(); notify(editing ? 'Goal updated.' : 'Goal created.'); reset()
    } catch (error) { notify(error instanceof Error ? error.message : 'Unable to save goal', 'error') }
  }
  const edit = (goal: Goal) => { setEditing(goal); setName(goal.name); setTarget(String(goal.target)); setSaved(String(goal.saved)); window.scrollTo({ top: 0, behavior: 'smooth' }) }
  const contribute = async (goal: Goal) => {
    const amount = Number(contributions[goal.id])
    if (!amount || amount <= 0) return notify('Enter a positive contribution amount.', 'error')
    try { await api.contributeGoal(goal.id, amount); setContributions({ ...contributions, [goal.id]: '' }); await refresh(); notify(`${money.format(amount)} added to ${goal.name}.`) }
    catch (error) { notify(error instanceof Error ? error.message : 'Unable to add contribution', 'error') }
  }
  const remove = async (goal: Goal) => {
    if (!window.confirm(`Delete “${goal.name}”?`)) return
    try { await api.deleteGoal(goal.id); await refresh(); notify('Goal deleted.'); if (editing?.id === goal.id) reset() }
    catch (error) { notify(error instanceof Error ? error.message : 'Unable to delete goal', 'error') }
  }

  const totalSaved = data.goals.reduce((sum, goal) => sum + goal.saved, 0)
  const totalTarget = data.goals.reduce((sum, goal) => sum + goal.target, 0)

  return <div className="page-stack">
    <section className="grid form-grid"><article className="card form-card"><div className="card-head"><div><h3>{editing ? 'Edit savings goal' : 'Create savings goal'}</h3><p>Give your savings a clear destination.</p></div>{editing && <button className="text-button inline" onClick={reset}>Cancel edit</button>}</div><form className="stack" onSubmit={submit}><label>Goal name<input value={name} onChange={e => setName(e.target.value)} required placeholder="Emergency fund" /></label><div className="field-row"><label>Target amount<input value={target} onChange={e => setTarget(e.target.value)} type="number" min="1" step="0.01" required placeholder="6000" /></label><label>Already saved<input value={saved} onChange={e => setSaved(e.target.value)} type="number" min="0" step="0.01" placeholder="0" /></label></div><button className="primary">{editing ? 'Update goal' : 'Save goal'}</button></form></article><article className="card mini-summary"><h3>Goal progress</h3><div><span>Total saved</span><strong className="income">{money.format(totalSaved)}</strong></div><div><span>Combined targets</span><strong>{money.format(totalTarget)}</strong></div><div><span>Overall funded</span><strong>{totalTarget ? `${Math.min((totalSaved / totalTarget) * 100, 100).toFixed(0)}%` : '0%'}</strong></div></article></section>
    <section className="goal-grid">{data.goals.length ? data.goals.map(g => { const percent = (g.saved / g.target) * 100; const done = g.saved >= g.target; return <article className={`card goal-card ${done ? 'complete' : ''}`} key={g.id}><div className="card-head"><div><span className="goal-status">{done ? 'GOAL REACHED' : 'IN PROGRESS'}</span><h3>{g.name}</h3></div><div className="row-actions"><button onClick={() => edit(g)}>Edit</button><button className="danger-button" onClick={() => remove(g)}>Delete</button></div></div><div className="goal-amount"><strong>{money.format(g.saved)}</strong><span>of {money.format(g.target)}</span></div><Progress value={percent} /><div className="goal-meta"><span>{Math.min(percent, 100).toFixed(0)}% funded</span><span>{done ? 'Complete' : `${money.format(g.target - g.saved)} to go`}</span></div>{!done && <div className="contribution"><input aria-label={`Contribution to ${g.name}`} type="number" min="0.01" step="0.01" placeholder="Add contribution" value={contributions[g.id] || ''} onChange={e => setContributions({ ...contributions, [g.id]: e.target.value })} /><button className="secondary" onClick={() => contribute(g)}>Add funds</button></div>}</article> }) : <article className="card"><Empty title="No savings goals yet" body="Create a goal and start tracking your progress." /></article>}</section>
  </div>
}

export default App
