import { FormEvent, useEffect, useMemo, useState } from 'react'
import { api, type TransactionInput } from './api'
import AuthScreen from './AuthScreen'
import type { Account, Budget, Dashboard, Goal, MonthlyTrend, Transaction } from './types'

const money = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })
const categories = ['Income', 'Housing', 'Food & Dining', 'Utilities', 'Transport', 'Lifestyle', 'Health', 'Shopping', 'Subscriptions', 'Travel', 'Education', 'Other']
const navItems = ['Overview', 'Transactions', 'Budgets', 'Goals', 'Settings'] as const
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
  return <div className={`toast ${tone}`} role="status" aria-live="polite">{message}</div>
}

function App() {
  const [token, setToken] = useState(localStorage.getItem('ledgerly_token'))
  const [data, setData] = useState<Dashboard | null>(null)
  const [error, setError] = useState('')
  const [authMessage, setAuthMessage] = useState('')
  const [active, setActive] = useState<(typeof navItems)[number]>('Overview')
  const [toast, setToast] = useState({ message: '', tone: 'success' as 'success' | 'error' })
  const [refreshing, setRefreshing] = useState(false)

  const notify: Notify = (message, tone = 'success') => {
    setToast({ message, tone })
    window.setTimeout(() => setToast({ message: '', tone }), 3200)
  }

  const signOut = (reason = '') => {
    localStorage.removeItem('ledgerly_token')
    setToken(null)
    setData(null)
    setActive('Overview')
    setError('')
    setAuthMessage(reason)
  }

  useEffect(() => {
    const expired = () => signOut('Your session expired. Please sign in again.')
    window.addEventListener('ledgerly:unauthorized', expired)
    return () => window.removeEventListener('ledgerly:unauthorized', expired)
  }, [])

  const refresh = async () => {
    try {
      setRefreshing(true)
      setError('')
      setData(await api.dashboard())
    } catch (e) {
      if (localStorage.getItem('ledgerly_token')) setError(e instanceof Error ? e.message : 'Unable to load dashboard')
    } finally {
      setRefreshing(false)
    }
  }

  useEffect(() => { if (token) void refresh() }, [token])

  if (!token) {
    return <AuthScreen initialMessage={authMessage} onAuthenticated={result => {
      localStorage.setItem('ledgerly_token', result.accessToken)
      setAuthMessage('')
      setToken(result.accessToken)
    }} />
  }

  return <div className="app-shell">
    <Toast {...toast} />
    <aside className="sidebar">
      <div className="brand"><div className="logo-mark small">L</div><div><strong>Ledgerly</strong><span>Money, clarified.</span></div></div>
      <nav aria-label="Primary navigation">{navItems.map(item => <button key={item} className={active === item ? 'active' : ''} aria-current={active === item ? 'page' : undefined} onClick={() => setActive(item)}><span className="nav-dot" />{item}</button>)}</nav>
      <div className="sidebar-foot"><span>Ledgerly v1.0</span><button className="logout" onClick={() => signOut()}>Sign out</button></div>
    </aside>

    <main className="dashboard">
      <header>
        <div><span className="eyebrow">PERSONAL FINANCE</span><h1>{active}</h1><p>{pageDescription(active)}</p></div>
        {active !== 'Settings' && <button className="secondary" disabled={refreshing} onClick={refresh}>{refreshing ? 'Refreshing…' : 'Refresh data'}</button>}
      </header>
      {error && <div className="error" role="alert">{error}</div>}
      {!data ? <div className="loading"><span className="spinner" />Loading Ledgerly…</div> : <>
        {active === 'Overview' && <Overview data={data} refresh={refresh} notify={notify} />}
        {active === 'Transactions' && <TransactionPage data={data} refresh={refresh} notify={notify} />}
        {active === 'Budgets' && <BudgetPage data={data} refresh={refresh} notify={notify} />}
        {active === 'Goals' && <GoalPage data={data} refresh={refresh} notify={notify} />}
        {active === 'Settings' && <SettingsPage data={data} refresh={refresh} notify={notify} signOut={signOut} />}
      </>}
    </main>
  </div>
}

function pageDescription(active: string) {
  if (active === 'Transactions') return 'Search, filter, edit, import, and manage your cash flow.'
  if (active === 'Budgets') return 'Set monthly guardrails and see where your money is going.'
  if (active === 'Goals') return 'Build momentum toward the things that matter most.'
  if (active === 'Settings') return 'Manage your account, security, and financial data.'
  return 'A clear snapshot of your financial month.'
}

function Overview({ data, refresh, notify }: { data: Dashboard; refresh: () => Promise<void>; notify: Notify }) {
  const totalGoalSaved = data.goals.reduce((sum, goal) => sum + goal.saved, 0)
  const totalGoalTarget = data.goals.reduce((sum, goal) => sum + goal.target, 0)
  const overBudget = data.budgets.filter(b => b.spent > b.limit).length
  const topCategory = data.categories[0]

  return <>
    <section className="metrics">
      <Metric label="Net balance" value={money.format(data.totalBalance)} detail="All tracked income minus spending" />
      <Metric label="This month income" value={money.format(data.income)} detail={`${data.transactions.filter(t => t.amount > 0 && t.date.slice(0, 7) === today().slice(0, 7)).length} income entries`} />
      <Metric label="This month expenses" value={money.format(data.expenses)} tone="red" detail={`${data.transactions.filter(t => t.amount < 0 && t.date.slice(0, 7) === today().slice(0, 7)).length} expense entries`} />
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
      <article className="card"><div className="card-head"><h3>Spending breakdown</h3><span>Current month</span></div>
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

    {!data.transactions.length && !data.budgets.length && !data.goals.length && <button className="primary demo" onClick={async () => { try { await api.seedDemo(); await refresh(); notify('Demo data loaded. Explore the dashboard!') } catch (e) { notify(e instanceof Error ? e.message : 'Unable to load demo data', 'error') } }}>Load realistic demo data</button>}
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
  const [transactionType, setTransactionType] = useState<'Expense' | 'Income'>('Expense')
  const [editing, setEditing] = useState<number | null>(null)
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState('All')
  const [kind, setKind] = useState<'All' | 'Income' | 'Expense'>('All')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [sort, setSort] = useState<'newest' | 'oldest' | 'high' | 'low'>('newest')
  const [busy, setBusy] = useState(false)

  const filtered = useMemo(() => {
    const items = data.transactions.filter(t => {
      const matchesSearch = `${t.description} ${t.category} ${t.notes || ''}`.toLowerCase().includes(search.toLowerCase())
      const matchesCategory = category === 'All' || t.category === category
      const matchesKind = kind === 'All' || (kind === 'Income' ? t.amount > 0 : t.amount < 0)
      const matchesStart = !startDate || t.date >= startDate
      const matchesEnd = !endDate || t.date <= endDate
      return matchesSearch && matchesCategory && matchesKind && matchesStart && matchesEnd
    })
    return [...items].sort((a, b) => {
      if (sort === 'oldest') return a.date.localeCompare(b.date) || a.id - b.id
      if (sort === 'high') return Math.abs(b.amount) - Math.abs(a.amount)
      if (sort === 'low') return Math.abs(a.amount) - Math.abs(b.amount)
      return b.date.localeCompare(a.date) || b.id - a.id
    })
  }, [data.transactions, search, category, kind, startDate, endDate, sort])

  const reset = () => { setDraft(emptyTx()); setEditing(null); setTransactionType('Expense') }
  const edit = (t: Transaction) => { setEditing(t.id); setTransactionType(t.amount >= 0 ? 'Income' : 'Expense'); setDraft({ description: t.description, amount: String(Math.abs(t.amount)), category: t.category, date: t.date, notes: t.notes || '' }); window.scrollTo({ top: 0, behavior: 'smooth' }) }

  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    const rawAmount = Math.abs(Number(draft.amount))
    const payload: TransactionInput = { ...draft, amount: transactionType === 'Expense' ? -rawAmount : rawAmount }
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
          <div className="type-toggle" role="group" aria-label="Transaction type"><button type="button" className={transactionType === 'Expense' ? 'active' : ''} onClick={() => { setTransactionType('Expense'); if (draft.category === 'Income') setDraft({ ...draft, category: 'Food & Dining' }) }}>Expense</button><button type="button" className={transactionType === 'Income' ? 'active income-type' : ''} onClick={() => { setTransactionType('Income'); setDraft({ ...draft, category: 'Income' }) }}>Income</button></div>
          <div className="field-row"><label>Description<input value={draft.description} onChange={e => setDraft({ ...draft, description: e.target.value })} required maxLength={180} placeholder="e.g. Grocery run" /></label><label>Amount<input value={draft.amount} onChange={e => setDraft({ ...draft, amount: e.target.value })} type="number" min="0.01" step="0.01" required placeholder="0.00" /></label></div>
          <div className="field-row"><label>Category<select value={draft.category} onChange={e => setDraft({ ...draft, category: e.target.value })}>{(transactionType === 'Income' ? ['Income'] : categories.filter(item => item !== 'Income')).map(item => <option key={item}>{item}</option>)}</select></label><label>Date<input value={draft.date} onChange={e => setDraft({ ...draft, date: e.target.value })} type="date" required /></label></div>
          <label>Notes <span className="optional">optional</span><textarea value={draft.notes} onChange={e => setDraft({ ...draft, notes: e.target.value })} maxLength={2000} rows={2} placeholder="Add context for later" /></label>
          <button className="primary" disabled={busy}>{busy ? 'Saving…' : editing ? 'Update transaction' : 'Save transaction'}</button>
        </form>
      </article>
      <article className="card mini-summary"><h3>This account</h3><div><span>Transactions</span><strong>{data.transactions.length}</strong></div><div><span>This month income</span><strong className="income">{money.format(data.income)}</strong></div><div><span>This month expenses</span><strong className="expense">{money.format(data.expenses)}</strong></div></article>
    </section>

    <section className="card transaction-manager">
      <div className="card-head"><div><h3>Transaction history</h3><p>{filtered.length} of {data.transactions.length} entries</p></div></div>
      <div className="filters"><input aria-label="Search transactions" value={search} onChange={e => setSearch(e.target.value)} placeholder="Search description, category, or notes…" /><select aria-label="Filter category" value={category} onChange={e => setCategory(e.target.value)}><option>All</option>{Array.from(new Set(data.transactions.map(t => t.category))).sort().map(item => <option key={item}>{item}</option>)}</select><select aria-label="Filter type" value={kind} onChange={e => setKind(e.target.value as typeof kind)}><option>All</option><option>Income</option><option>Expense</option></select><input aria-label="Start date" type="date" value={startDate} onChange={e => setStartDate(e.target.value)} /><input aria-label="End date" type="date" value={endDate} onChange={e => setEndDate(e.target.value)} /><select aria-label="Sort transactions" value={sort} onChange={e => setSort(e.target.value as typeof sort)}><option value="newest">Newest first</option><option value="oldest">Oldest first</option><option value="high">Largest amount</option><option value="low">Smallest amount</option></select></div>
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
    <section className="grid form-grid"><article className="card form-card"><div className="card-head"><div><h3>{editing ? 'Edit savings goal' : 'Create savings goal'}</h3><p>Give your savings a clear destination.</p></div>{editing && <button className="text-button inline" onClick={reset}>Cancel edit</button>}</div><form className="stack" onSubmit={submit}><label>Goal name<input value={name} onChange={e => setName(e.target.value)} required maxLength={120} placeholder="Emergency fund" /></label><div className="field-row"><label>Target amount<input value={target} onChange={e => setTarget(e.target.value)} type="number" min="1" step="0.01" required placeholder="6000" /></label><label>Already saved<input value={saved} onChange={e => setSaved(e.target.value)} type="number" min="0" step="0.01" placeholder="0" /></label></div><button className="primary">{editing ? 'Update goal' : 'Save goal'}</button></form></article><article className="card mini-summary"><h3>Goal progress</h3><div><span>Total saved</span><strong className="income">{money.format(totalSaved)}</strong></div><div><span>Combined targets</span><strong>{money.format(totalTarget)}</strong></div><div><span>Overall funded</span><strong>{totalTarget ? `${Math.min((totalSaved / totalTarget) * 100, 100).toFixed(0)}%` : '0%'}</strong></div></article></section>
    <section className="goal-grid">{data.goals.length ? data.goals.map(g => { const percent = (g.saved / g.target) * 100; const done = g.saved >= g.target; return <article className={`card goal-card ${done ? 'complete' : ''}`} key={g.id}><div className="card-head"><div><span className="goal-status">{done ? 'GOAL REACHED' : 'IN PROGRESS'}</span><h3>{g.name}</h3></div><div className="row-actions"><button onClick={() => edit(g)}>Edit</button><button className="danger-button" onClick={() => remove(g)}>Delete</button></div></div><div className="goal-amount"><strong>{money.format(g.saved)}</strong><span>of {money.format(g.target)}</span></div><Progress value={percent} /><div className="goal-meta"><span>{Math.min(percent, 100).toFixed(0)}% funded</span><span>{done ? 'Complete' : `${money.format(g.target - g.saved)} to go`}</span></div>{!done && <div className="contribution"><input aria-label={`Contribution to ${g.name}`} type="number" min="0.01" step="0.01" placeholder="Add contribution" value={contributions[g.id] || ''} onChange={e => setContributions({ ...contributions, [g.id]: e.target.value })} /><button className="secondary" onClick={() => contribute(g)}>Add funds</button></div>}</article> }) : <article className="card"><Empty title="No savings goals yet" body="Create a goal and start tracking your progress." /></article>}</section>
  </div>
}

function SettingsPage({ data, refresh, notify, signOut }: { data: Dashboard; refresh: () => Promise<void>; notify: Notify; signOut: (reason?: string) => void }) {
  const [account, setAccount] = useState<Account | null>(null)
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [deletePassword, setDeletePassword] = useState('')
  const [busy, setBusy] = useState('')

  useEffect(() => { api.account().then(setAccount).catch(() => undefined) }, [data.transactions.length, data.budgets.length, data.goals.length])

  const changePassword = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (newPassword !== confirmPassword) return notify('New passwords do not match.', 'error')
    try { setBusy('password'); await api.changePassword(currentPassword, newPassword); setCurrentPassword(''); setNewPassword(''); setConfirmPassword(''); notify('Password updated successfully. Other sessions have been signed out.') }
    catch (error) { notify(error instanceof Error ? error.message : 'Unable to change password', 'error') }
    finally { setBusy('') }
  }

  const exportCsv = () => {
    const escape = (value: string | number) => `"${String(value).replaceAll('"', '""')}"`
    const rows = [['description', 'amount', 'category', 'date', 'notes'], ...data.transactions.map(t => [t.description, t.amount, t.category, t.date, t.notes || ''])]
    const csv = rows.map(row => row.map(escape).join(',')).join('\n')
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `ledgerly-transactions-${today()}.csv`
    anchor.click()
    URL.revokeObjectURL(url)
    notify(`Exported ${data.transactions.length} transactions.`)
  }

  const importCsv = async (file: File) => {
    try {
      setBusy('import')
      const text = await file.text()
      const rows = parseCsv(text)
      if (rows.length < 2) throw new Error('CSV is empty.')
      const headers = rows[0].map(value => value.trim().toLowerCase())
      const required = ['description', 'amount', 'category', 'date']
      if (required.some(field => !headers.includes(field))) throw new Error('CSV must include description, amount, category, and date headers.')
      const index = (field: string) => headers.indexOf(field)
      const payload: TransactionInput[] = rows.slice(1).filter(row => row.some(value => value.trim())).map(row => ({
        description: row[index('description')] || '',
        amount: Number(row[index('amount')]),
        category: row[index('category')] || '',
        date: row[index('date')] || '',
        notes: headers.includes('notes') ? row[index('notes')] || '' : '',
      }))
      const result = await api.importTransactions(payload)
      await refresh()
      notify(`Imported ${result.imported} transactions.`)
    } catch (error) { notify(error instanceof Error ? error.message : 'Unable to import CSV', 'error') }
    finally { setBusy('') }
  }

  const clearData = async () => {
    if (!window.confirm('Delete ALL transactions, budgets, and goals? Your account will remain active.')) return
    if (!window.confirm('This cannot be undone. Clear all financial data?')) return
    try { setBusy('clear'); await api.clearData(); await refresh(); notify('Financial data cleared.') }
    catch (error) { notify(error instanceof Error ? error.message : 'Unable to clear data', 'error') }
    finally { setBusy('') }
  }

  const resetDemo = async () => {
    if (!window.confirm('Replace all financial data with Ledgerly demo data?')) return
    try { setBusy('demo'); await api.resetDemo(); await refresh(); notify('Fresh six-month demo data loaded.') }
    catch (error) { notify(error instanceof Error ? error.message : 'Unable to reset demo data', 'error') }
    finally { setBusy('') }
  }

  const deleteAccount = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!window.confirm('Permanently delete your Ledgerly account and all data?')) return
    try { setBusy('delete'); await api.deleteAccount(deletePassword); signOut('Your account was deleted.') }
    catch (error) { notify(error instanceof Error ? error.message : 'Unable to delete account', 'error') }
    finally { setBusy('') }
  }

  return <div className="settings-grid">
    <article className="card settings-card"><div className="card-head"><div><h3>Account</h3><p>Your Ledgerly profile and usage summary.</p></div></div>{account ? <div className="account-summary"><div><span>Email</span><strong>{account.email}</strong></div><div><span>Email status</span><strong className={account.emailVerified ? 'income' : 'expense'}>{account.emailVerified ? 'Verified' : 'Unverified'}</strong></div><div><span>Member since</span><strong>{account.createdAt ? new Date(account.createdAt).toLocaleDateString() : '—'}</strong></div><div><span>Transactions</span><strong>{account.transactionCount}</strong></div><div><span>Budgets / goals</span><strong>{account.budgetCount} / {account.goalCount}</strong></div></div> : <div className="loading compact"><span className="spinner" />Loading account…</div>}</article>

    <article className="card settings-card"><div className="card-head"><div><h3>Change password</h3><p>Use a unique password with at least 10 characters, a letter, and a number.</p></div></div><form className="stack" onSubmit={changePassword}><label>Current password<input type="password" autoComplete="current-password" required value={currentPassword} onChange={e => setCurrentPassword(e.target.value)} /></label><label>New password<input type="password" autoComplete="new-password" minLength={10} maxLength={128} required value={newPassword} onChange={e => setNewPassword(e.target.value)} /></label><label>Confirm new password<input type="password" autoComplete="new-password" minLength={10} maxLength={128} required value={confirmPassword} onChange={e => setConfirmPassword(e.target.value)} /></label><button className="primary" disabled={busy === 'password'}>{busy === 'password' ? 'Updating…' : 'Update password'}</button></form></article>

    <article className="card settings-card data-tools"><div className="card-head"><div><h3>Data portability</h3><p>Your transaction history belongs to you.</p></div></div><div className="settings-actions"><button className="secondary" onClick={exportCsv} disabled={!data.transactions.length}>Export CSV</button><label className="file-button">{busy === 'import' ? 'Importing…' : 'Import CSV'}<input type="file" accept=".csv,text/csv" disabled={busy === 'import'} onChange={e => { const file = e.target.files?.[0]; if (file) void importCsv(file); e.currentTarget.value = '' }} /></label></div><small>CSV headers: description, amount, category, date, notes. Imports are validated before any rows are saved.</small></article>

    <article className="card settings-card"><div className="card-head"><div><h3>Demo & reset tools</h3><p>Useful for evaluating Ledgerly without manual data entry.</p></div></div><div className="settings-actions vertical"><button className="secondary" disabled={!!busy} onClick={resetDemo}>{busy === 'demo' ? 'Loading demo…' : 'Replace with fresh demo data'}</button><button className="danger-outline" disabled={!!busy} onClick={clearData}>{busy === 'clear' ? 'Clearing…' : 'Clear all financial data'}</button></div></article>

    <article className="card settings-card danger-zone"><div className="card-head"><div><h3>Danger zone</h3><p>Permanently remove your account and all associated data.</p></div></div><form className="stack" onSubmit={deleteAccount}><label>Confirm with your password<input type="password" autoComplete="current-password" required value={deletePassword} onChange={e => setDeletePassword(e.target.value)} /></label><button className="danger-primary" disabled={busy === 'delete'}>{busy === 'delete' ? 'Deleting…' : 'Delete account permanently'}</button></form></article>
  </div>
}

function parseCsv(input: string): string[][] {
  const rows: string[][] = []
  let row: string[] = []
  let cell = ''
  let quoted = false
  for (let i = 0; i < input.length; i += 1) {
    const char = input[i]
    const next = input[i + 1]
    if (char === '"' && quoted && next === '"') { cell += '"'; i += 1 }
    else if (char === '"') quoted = !quoted
    else if (char === ',' && !quoted) { row.push(cell); cell = '' }
    else if ((char === '\n' || char === '\r') && !quoted) {
      if (char === '\r' && next === '\n') i += 1
      row.push(cell); rows.push(row); row = []; cell = ''
    } else cell += char
  }
  if (cell.length || row.length) { row.push(cell); rows.push(row) }
  return rows
}

export default App
