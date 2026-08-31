import { FormEvent, useEffect, useMemo, useState } from 'react'
import { api, type AccountInput, type TransactionInput } from './api'
import AuthScreen from './AuthScreen'
import type { Account, Budget, Dashboard, FinancialAccount, Goal, MonthlyTrend, Transaction, TransactionType } from './types'

const money = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })
const defaultCategories = ['Housing', 'Utilities', 'Groceries', 'Dining', 'Transportation', 'Fuel', 'Healthcare', 'Shopping', 'Entertainment', 'Childcare', 'Pets', 'Subscriptions', 'Insurance', 'Debt payments', 'Income', 'Miscellaneous']
const accountTypes: { value: FinancialAccount['type']; label: string }[] = [
  { value: 'checking', label: 'Checking' },
  { value: 'savings', label: 'Savings' },
  { value: 'cash', label: 'Cash' },
  { value: 'credit', label: 'Credit card' },
  { value: 'loan', label: 'Loan / debt' },
  { value: 'investment', label: 'Investment tracking' },
  { value: 'other', label: 'Other' },
]
const navItems = ['Overview', 'Accounts', 'Transactions', 'Budgets', 'Goals', 'Reports', 'Settings'] as const
const today = () => new Date().toISOString().slice(0, 10)

type Notify = (message: string, tone?: 'success' | 'error') => void

type TxDraft = {
  description: string
  amount: string
  accountId: string
  category: string
  subcategory: string
  tags: string
  date: string
  notes: string
}

const emptyTx = (accountId = ''): TxDraft => ({ description: '', amount: '', accountId, category: 'Groceries', subcategory: '', tags: '', date: today(), notes: '' })

function Metric({ label, value, tone = 'green', detail }: { label: string; value: string; tone?: string; detail?: string }) {
  return <article className={`metric ${tone}`}><span>{label}</span><strong>{value}</strong>{detail && <small>{detail}</small>}</article>
}

function Progress({ value, danger = false, warning = false }: { value: number; danger?: boolean; warning?: boolean }) {
  const safe = Math.min(Math.max(value, 0), 100)
  return <div className={`progress ${danger ? 'danger' : warning ? 'warning' : ''}`}><span style={{ width: `${safe}%` }} /></div>
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
      <div className="brand"><div className="logo-mark small">L</div><div><strong>Ledgerly</strong><span>Full control. Smarter decisions.</span></div></div>
      <nav aria-label="Primary navigation">{navItems.map(item => <button key={item} className={active === item ? 'active' : ''} aria-current={active === item ? 'page' : undefined} onClick={() => setActive(item)}><span className="nav-dot" />{item}</button>)}</nav>
      <div className="sidebar-foot"><span>Ledgerly v1.2</span><button className="logout" onClick={() => signOut()}>Sign out</button></div>
    </aside>

    <main className="dashboard">
      <header>
        <div><span className="eyebrow">PERSONAL FINANCE</span><h1>{active}</h1><p>{pageDescription(active)}</p></div>
        {active !== 'Settings' && <button className="secondary" disabled={refreshing} onClick={refresh}>{refreshing ? 'Refreshing…' : 'Refresh data'}</button>}
      </header>
      {error && <div className="error" role="alert">{error}</div>}
      {!data ? <div className="loading"><span className="spinner" />Loading Ledgerly…</div> : <>
        {active === 'Overview' && <Overview data={data} refresh={refresh} notify={notify} />}
        {active === 'Accounts' && <AccountsPage data={data} refresh={refresh} notify={notify} />}
        {active === 'Transactions' && <TransactionPage data={data} refresh={refresh} notify={notify} />}
        {active === 'Budgets' && <BudgetPage data={data} refresh={refresh} notify={notify} />}
        {active === 'Goals' && <GoalPage data={data} refresh={refresh} notify={notify} />}
        {active === 'Reports' && <ReportsPage data={data} />}
        {active === 'Settings' && <SettingsPage data={data} refresh={refresh} notify={notify} signOut={signOut} />}
      </>}
    </main>
  </div>
}

function pageDescription(active: string) {
  if (active === 'Accounts') return 'Track where your money lives and what you owe.'
  if (active === 'Transactions') return 'Search, filter, edit, import, and move money between accounts.'
  if (active === 'Budgets') return 'Set monthly category limits and see what is still safe to spend.'
  if (active === 'Goals') return 'Build measurable progress toward the things that matter most.'
  if (active === 'Reports') return 'Turn your transaction history into useful financial context.'
  if (active === 'Settings') return 'Manage your account, security, appearance, and financial data.'
  return 'One clear snapshot of your money this month.'
}

function Overview({ data, refresh, notify }: { data: Dashboard; refresh: () => Promise<void>; notify: Notify }) {
  const totalGoalSaved = data.goals.reduce((sum, goal) => sum + goal.saved, 0)
  const totalGoalTarget = data.goals.reduce((sum, goal) => sum + goal.target, 0)
  const overBudget = data.budgets.filter(b => b.status === 'over').length
  const topCategory = data.categories[0]
  const activeAccounts = data.accounts.filter(account => !account.archived)

  return <>
    <section className="metrics">
      <Metric label="Tracked balance" value={money.format(data.totalBalance)} detail={activeAccounts.length ? `${activeAccounts.length} active account${activeAccounts.length === 1 ? '' : 's'}` : 'Transactions not assigned to accounts yet'} />
      <Metric label="This month income" value={money.format(data.income)} detail={`${data.transactions.filter(t => t.transactionType === 'income' && t.date.slice(0, 7) === today().slice(0, 7)).length} income entries`} />
      <Metric label="This month expenses" value={money.format(data.expenses)} tone="red" detail={`${data.transactions.filter(t => t.transactionType === 'expense' && t.date.slice(0, 7) === today().slice(0, 7)).length} expense entries`} />
      <Metric label="Net cash flow" value={money.format(data.netCashFlow)} tone="amber" detail={`${data.savingsRate.toFixed(1)}% monthly savings rate`} />
    </section>

    <section className="grid overview-grid">
      <TrendChart trend={data.monthlyTrend} />
      <article className="card insights-card">
        <div className="card-head"><h3>Financial insights</h3><span>From your data</span></div>
        {data.insights.length ? <div className="insight-list">{data.insights.slice(0, 5).map((insight, index) => <div key={`${insight}-${index}`}><span>Insight {index + 1}</span><strong>{insight}</strong></div>)}</div> : <Empty title="Not enough data yet" body="Add transactions and budgets to generate useful context." />}
      </article>
    </section>

    {activeAccounts.length > 0 && <section className="card accounts-strip"><div className="card-head"><div><h3>Accounts</h3><p>Current balances from opening balance plus account transactions.</p></div><span>{money.format(data.availableBalance)} included in totals</span></div><div className="account-balance-grid">{activeAccounts.slice(0, 6).map(account => <div key={account.id}><span>{account.name}<small>{account.institution || accountTypeLabel(account.type)}</small></span><strong className={account.currentBalance < 0 ? 'expense' : ''}>{money.format(account.currentBalance)}</strong></div>)}</div></section>}

    <section className="grid two">
      <article className="card"><div className="card-head"><h3>Spending breakdown</h3><span>Current month</span></div>
        {data.categories.length ? <div className="category-list">{data.categories.map(c => <div key={c.category}><span>{c.category}</span><strong>{money.format(c.amount)}</strong><Progress value={data.expenses ? (c.amount / data.expenses) * 100 : 0} /></div>)}</div> : <Empty title="No spending yet" body="Expense transactions will appear here automatically." />}
      </article>
      <article className="card"><div className="card-head"><h3>Budget progress</h3><span>{money.format(data.budgetRemaining)} remaining</span></div>
        {data.budgets.length ? <div className="category-list">{data.budgets.map(b => <div key={b.id}><span>{b.category}</span><strong className={b.status === 'over' ? 'expense' : ''}>{money.format(b.spent)} / {money.format(b.limit)}</strong><Progress danger={b.status === 'over'} warning={b.status === 'approaching'} value={b.percentUsed} /></div>)}</div> : <Empty title="No budget yet" body="Create this month's first category budget." />}
      </article>
    </section>

    <section className="grid two">
      <TransactionSummary transactions={data.transactions.slice(0, 6)} />
      <article className="card"><div className="card-head"><h3>Savings goals</h3><span>{data.goals.length} active</span></div>
        {data.goals.length ? <div className="category-list">{data.goals.slice(0, 5).map(g => <div key={g.id}><span>{g.name}</span><strong>{money.format(g.saved)} / {money.format(g.target)}</strong><Progress value={g.percentComplete} /></div>)}</div> : <Empty title="No savings goals" body="Create a savings goal to start measuring progress." />}
      </article>
    </section>

    <section className="grid two">
      <article className="card"><div className="card-head"><h3>This month's money</h3><span>{data.monthlyPlan.daysRemaining} days remaining</span></div><div className="plan-list"><div><span>Actual income</span><strong>{money.format(data.monthlyPlan.actualIncome)}</strong></div><div><span>Budgeted expenses</span><strong>{money.format(data.monthlyPlan.budgetedExpenses)}</strong></div><div><span>Actual expenses</span><strong>{money.format(data.monthlyPlan.actualExpenses)}</strong></div><div><span>Unbudgeted spending</span><strong>{money.format(data.monthlyPlan.unbudgetedSpending)}</strong></div><div><span>Net result</span><strong className={data.monthlyPlan.netResult >= 0 ? 'income' : 'expense'}>{money.format(data.monthlyPlan.netResult)}</strong></div></div></article>
      <article className="card"><div className="card-head"><h3>Goal funding</h3><span>Across all goals</span></div>{totalGoalTarget ? <><strong className="hero-number">{Math.min((totalGoalSaved / totalGoalTarget) * 100, 100).toFixed(0)}%</strong><Progress value={(totalGoalSaved / totalGoalTarget) * 100} /><p>{money.format(totalGoalSaved)} saved toward {money.format(totalGoalTarget)} in targets.</p></> : <Empty />}{overBudget > 0 && <p className="callout warning-copy">{overBudget} budget{overBudget === 1 ? ' is' : 's are'} currently over the monthly limit.</p>}{topCategory && <p className="callout">Your largest spending category this month is {topCategory.category} at {money.format(topCategory.amount)}.</p>}</article>
    </section>

    {!data.transactions.length && !data.budgets.length && !data.goals.length && !data.accounts.length && <button className="primary demo" onClick={async () => { try { await api.seedDemo(); await refresh(); notify('Fictional demo data loaded. Explore Ledgerly!') } catch (e) { notify(e instanceof Error ? e.message : 'Unable to load demo data', 'error') } }}>Load fictional demo data</button>}
  </>
}

function TrendChart({ trend }: { trend: MonthlyTrend[] }) {
  const max = Math.max(1, ...trend.flatMap(item => [item.income, item.expenses]))
  return <article className="card trend-card">
    <div className="card-head"><div><h3>Cash flow trend</h3><p>Income vs. expenses over six months. Transfers are excluded.</p></div><div className="legend"><span className="income-key">Income</span><span className="expense-key">Expenses</span></div></div>
    <div className="trend-chart">{trend.map(item => <div className="trend-column" key={item.month}>
      <div className="bars"><span className="bar income-bar" title={`Income ${money.format(item.income)}`} style={{ height: `${Math.max((item.income / max) * 100, item.income ? 4 : 0)}%` }} /><span className="bar expense-bar" title={`Expenses ${money.format(item.expenses)}`} style={{ height: `${Math.max((item.expenses / max) * 100, item.expenses ? 4 : 0)}%` }} /></div>
      <strong>{item.month}</strong><small className={item.net >= 0 ? 'income' : 'expense'}>{money.format(item.net)}</small>
    </div>)}</div>
  </article>
}

function TransactionSummary({ transactions }: { transactions: Transaction[] }) {
  return <article className="card"><div className="card-head"><h3>Recent transactions</h3><span>{transactions.length} shown</span></div>
    {transactions.length ? <div className="transactions">{transactions.map(t => <TransactionRow key={t.id} transaction={t} />)}</div> : <Empty title="No transactions yet" body="Add a transaction or import a CSV." />}
  </article>
}

function TransactionRow({ transaction, onEdit, onDelete }: { transaction: Transaction; onEdit?: (t: Transaction) => void; onDelete?: (t: Transaction) => void }) {
  const isTransfer = transaction.transactionType === 'transfer'
  return <div className="transaction"><div className="transaction-main"><span className={`tx-icon ${transaction.amount >= 0 ? 'positive' : ''} ${isTransfer ? 'transfer-icon' : ''}`}>{isTransfer ? '↔' : transaction.amount >= 0 ? '+' : '−'}</span><div><strong>{transaction.description}</strong><span>{isTransfer ? 'Transfer' : transaction.category}{transaction.subcategory ? ` / ${transaction.subcategory}` : ''} · {transaction.accountName || 'Unassigned'} · {new Date(`${transaction.date}T12:00:00`).toLocaleDateString()}</span>{transaction.tags.length > 0 && <small>#{transaction.tags.join(' #')}</small>}{transaction.notes && <small>{transaction.notes}</small>}</div></div><div className="amount-wrap"><strong className={isTransfer ? '' : transaction.amount < 0 ? 'expense' : 'income'}>{money.format(transaction.amount)}</strong>{(onEdit || onDelete) && <div className="row-actions">{onEdit && !isTransfer && <button title="Edit transaction" onClick={() => onEdit(transaction)}>Edit</button>}{onDelete && <button className="danger-button" title="Delete transaction" onClick={() => onDelete(transaction)}>{isTransfer ? 'Delete transfer' : 'Delete'}</button>}</div>}</div></div>
}

function AccountsPage({ data, refresh, notify }: { data: Dashboard; refresh: () => Promise<void>; notify: Notify }) {
  const blank: AccountInput = { name: '', type: 'checking', institution: '', openingBalance: 0, description: '', includeInTotals: true, archived: false }
  const [draft, setDraft] = useState<AccountInput>(blank)
  const [openingBalance, setOpeningBalance] = useState('0')
  const [editing, setEditing] = useState<FinancialAccount | null>(null)
  const [busy, setBusy] = useState(false)

  const reset = () => { setDraft(blank); setOpeningBalance('0'); setEditing(null) }
  const edit = (account: FinancialAccount) => {
    setEditing(account)
    setDraft({ name: account.name, type: account.type, institution: account.institution, openingBalance: account.openingBalance, description: account.description, includeInTotals: account.includeInTotals, archived: account.archived })
    setOpeningBalance(String(account.openingBalance))
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    try {
      setBusy(true)
      const payload = { ...draft, openingBalance: Number(openingBalance) }
      if (editing) await api.updateAccount(editing.id, payload)
      else await api.addAccount(payload)
      await refresh(); notify(editing ? 'Account updated.' : 'Account added.'); reset()
    } catch (error) { notify(error instanceof Error ? error.message : 'Unable to save account', 'error') }
    finally { setBusy(false) }
  }
  const toggleArchive = async (account: FinancialAccount) => {
    try { await api.updateAccount(account.id, { archived: !account.archived }); await refresh(); notify(account.archived ? 'Account restored.' : 'Account archived.') }
    catch (error) { notify(error instanceof Error ? error.message : 'Unable to update account', 'error') }
  }
  const remove = async (account: FinancialAccount) => {
    if (!window.confirm(`Delete “${account.name}”? Accounts with transactions should normally be archived instead.`)) return
    try { await api.deleteFinancialAccount(account.id); await refresh(); notify('Account deleted.') }
    catch (error) { notify(error instanceof Error ? error.message : 'Unable to delete account', 'error') }
  }

  const included = data.accounts.filter(account => !account.archived && account.includeInTotals)
  return <div className="page-stack">
    <section className="grid form-grid">
      <article className="card form-card"><div className="card-head"><div><h3>{editing ? 'Edit financial account' : 'Add financial account'}</h3><p>Represent checking, savings, cash, credit, debt, or other money you track.</p></div>{editing && <button className="text-button inline" onClick={reset}>Cancel edit</button>}</div><form className="stack" onSubmit={submit}><div className="field-row"><label>Account name<input value={draft.name} onChange={e => setDraft({ ...draft, name: e.target.value })} required maxLength={120} placeholder="Everyday checking" /></label><label>Type<select value={draft.type} onChange={e => setDraft({ ...draft, type: e.target.value as FinancialAccount['type'] })}>{accountTypes.map(type => <option key={type.value} value={type.value}>{type.label}</option>)}</select></label></div><div className="field-row"><label>Institution <span className="optional">optional</span><input value={draft.institution || ''} onChange={e => setDraft({ ...draft, institution: e.target.value })} maxLength={120} placeholder="Bank or provider" /></label><label>Opening balance<input value={openingBalance} onChange={e => setOpeningBalance(e.target.value)} type="number" step="0.01" required /></label></div><label>Description <span className="optional">optional</span><textarea value={draft.description || ''} onChange={e => setDraft({ ...draft, description: e.target.value })} maxLength={500} rows={2} placeholder="What this account is used for" /></label><label className="check-row"><input type="checkbox" checked={draft.includeInTotals !== false} onChange={e => setDraft({ ...draft, includeInTotals: e.target.checked })} />Include this account in Ledgerly totals</label>{editing && <label className="check-row"><input type="checkbox" checked={draft.archived === true} onChange={e => setDraft({ ...draft, archived: e.target.checked })} />Archive this account</label>}<button className="primary" disabled={busy}>{busy ? 'Saving…' : editing ? 'Update account' : 'Add account'}</button></form></article>
      <article className="card mini-summary"><h3>Account snapshot</h3><div><span>Tracked accounts</span><strong>{data.accounts.length}</strong></div><div><span>Included in totals</span><strong>{included.length}</strong></div><div><span>Available balance</span><strong className={data.availableBalance < 0 ? 'expense' : 'income'}>{money.format(data.availableBalance)}</strong></div></article>
    </section>
    <section className="account-grid">{data.accounts.length ? data.accounts.map(account => <article className={`card account-card ${account.archived ? 'archived' : ''}`} key={account.id}><div className="card-head"><div><span className="account-type">{accountTypeLabel(account.type)}</span><h3>{account.name}</h3><p>{account.institution || 'Manual account'}</p></div><div className="row-actions"><button onClick={() => edit(account)}>Edit</button><button onClick={() => toggleArchive(account)}>{account.archived ? 'Restore' : 'Archive'}</button><button className="danger-button" onClick={() => remove(account)}>Delete</button></div></div><strong className={`account-balance ${account.currentBalance < 0 ? 'expense' : ''}`}>{money.format(account.currentBalance)}</strong><div className="account-meta"><span>{account.transactionCount} transaction{account.transactionCount === 1 ? '' : 's'}</span><span>{account.includeInTotals ? 'Included in totals' : 'Excluded from totals'}</span></div>{account.description && <p>{account.description}</p>}</article>) : <article className="card"><Empty title="No accounts yet" body="Add your first account. Ledgerly can still work manually without connecting to a bank." /></article>}</section>
  </div>
}

function TransactionPage({ data, refresh, notify }: { data: Dashboard; refresh: () => Promise<void>; notify: Notify }) {
  const activeAccounts = data.accounts.filter(account => !account.archived)
  const firstAccount = activeAccounts[0]?.id ? String(activeAccounts[0].id) : ''
  const [draft, setDraft] = useState<TxDraft>(emptyTx(firstAccount))
  const [transactionType, setTransactionType] = useState<TransactionType>('expense')
  const [editing, setEditing] = useState<number | null>(null)
  const [transferFrom, setTransferFrom] = useState(firstAccount)
  const [transferTo, setTransferTo] = useState(activeAccounts[1]?.id ? String(activeAccounts[1].id) : '')
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState('All')
  const [accountFilter, setAccountFilter] = useState('All')
  const [kind, setKind] = useState<'All' | TransactionType>('All')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [sort, setSort] = useState<'newest' | 'oldest' | 'high' | 'low'>('newest')
  const [busy, setBusy] = useState(false)
  const categories = useMemo(() => Array.from(new Set([...defaultCategories, ...data.transactions.map(t => t.category), ...data.budgets.map(b => b.category)])).filter(Boolean).sort(), [data.transactions, data.budgets])

  useEffect(() => {
    if (!draft.accountId && firstAccount) setDraft(current => ({ ...current, accountId: firstAccount }))
    if (!transferFrom && firstAccount) setTransferFrom(firstAccount)
    if (!transferTo && activeAccounts.length > 1) setTransferTo(String(activeAccounts[1].id))
  }, [firstAccount, activeAccounts.length, draft.accountId, transferFrom, transferTo])

  const filtered = useMemo(() => {
    const items = data.transactions.filter(t => {
      const matchesSearch = `${t.description} ${t.category} ${t.subcategory} ${t.accountName || ''} ${t.tags.join(' ')} ${t.notes || ''}`.toLowerCase().includes(search.toLowerCase())
      const matchesCategory = category === 'All' || t.category === category
      const matchesAccount = accountFilter === 'All' || String(t.accountId || '') === accountFilter
      const matchesKind = kind === 'All' || t.transactionType === kind
      const matchesStart = !startDate || t.date >= startDate
      const matchesEnd = !endDate || t.date <= endDate
      return matchesSearch && matchesCategory && matchesAccount && matchesKind && matchesStart && matchesEnd
    })
    return [...items].sort((a, b) => {
      if (sort === 'oldest') return a.date.localeCompare(b.date) || a.id - b.id
      if (sort === 'high') return Math.abs(b.amount) - Math.abs(a.amount)
      if (sort === 'low') return Math.abs(a.amount) - Math.abs(b.amount)
      return b.date.localeCompare(a.date) || b.id - a.id
    })
  }, [data.transactions, search, category, accountFilter, kind, startDate, endDate, sort])

  const reset = () => { setDraft(emptyTx(firstAccount)); setEditing(null); setTransactionType('expense') }
  const edit = (t: Transaction) => { setEditing(t.id); setTransactionType(t.transactionType); setDraft({ description: t.description, amount: String(Math.abs(t.amount)), accountId: t.accountId ? String(t.accountId) : '', category: t.category, subcategory: t.subcategory || '', tags: t.tags.join(', '), date: t.date, notes: t.notes || '' }); window.scrollTo({ top: 0, behavior: 'smooth' }) }

  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    const rawAmount = Math.abs(Number(draft.amount))
    try {
      setBusy(true)
      if (transactionType === 'transfer') {
        if (!transferFrom || !transferTo) throw new Error('Choose both a source and destination account.')
        await api.addTransfer({ fromAccountId: Number(transferFrom), toAccountId: Number(transferTo), amount: rawAmount, date: draft.date, description: draft.description || 'Account transfer', notes: draft.notes })
        notify('Transfer recorded without counting it as income or spending.')
      } else {
        const payload: TransactionInput = { description: draft.description, amount: transactionType === 'expense' ? -rawAmount : rawAmount, transactionType, accountId: draft.accountId ? Number(draft.accountId) : null, category: transactionType === 'income' ? (draft.category || 'Income') : draft.category, subcategory: draft.subcategory, tags: draft.tags.split(',').map(tag => tag.trim()).filter(Boolean), date: draft.date, notes: draft.notes }
        if (editing) await api.updateTransaction(editing, payload)
        else await api.addTransaction(payload)
        notify(editing ? 'Transaction updated.' : 'Transaction added.')
      }
      await refresh(); reset()
    } catch (error) { notify(error instanceof Error ? error.message : 'Unable to save transaction', 'error') }
    finally { setBusy(false) }
  }

  const remove = async (t: Transaction) => {
    if (!window.confirm(t.transactionType === 'transfer' ? 'Delete both sides of this transfer?' : `Delete “${t.description}”?`)) return
    try { await api.deleteTransaction(t.id); await refresh(); notify(t.transactionType === 'transfer' ? 'Transfer deleted.' : 'Transaction deleted.'); if (editing === t.id) reset() }
    catch (error) { notify(error instanceof Error ? error.message : 'Unable to delete transaction', 'error') }
  }

  return <div className="page-stack">
    <datalist id="ledgerly-categories">{categories.map(item => <option key={item} value={item} />)}</datalist>
    <section className="grid form-grid">
      <article className="card form-card"><div className="card-head"><div><h3>{editing ? 'Edit transaction' : transactionType === 'transfer' ? 'Move money' : 'Add transaction'}</h3><p>{transactionType === 'transfer' ? 'Transfers move money between your accounts without inflating income or expenses.' : editing ? 'Update the selected entry.' : 'Record money entering or leaving an account.'}</p></div>{editing && <button className="text-button inline" onClick={reset}>Cancel edit</button>}</div>
        <form className="stack" onSubmit={submit}>
          <div className="type-toggle three" role="group" aria-label="Transaction type"><button type="button" className={transactionType === 'expense' ? 'active' : ''} onClick={() => { setTransactionType('expense'); setEditing(null) }}>Expense</button><button type="button" className={transactionType === 'income' ? 'active income-type' : ''} onClick={() => { setTransactionType('income'); setEditing(null); setDraft({ ...draft, category: 'Income' }) }}>Income</button><button type="button" disabled={!!editing} className={transactionType === 'transfer' ? 'active transfer-type' : ''} onClick={() => { setTransactionType('transfer'); setEditing(null) }}>Transfer</button></div>
          {transactionType === 'transfer' ? <>
            {activeAccounts.length < 2 && <div className="error">Create at least two active accounts before recording a transfer.</div>}
            <div className="field-row"><label>From account<select value={transferFrom} onChange={e => setTransferFrom(e.target.value)} required><option value="">Choose account</option>{activeAccounts.map(account => <option key={account.id} value={account.id}>{account.name} · {money.format(account.currentBalance)}</option>)}</select></label><label>To account<select value={transferTo} onChange={e => setTransferTo(e.target.value)} required><option value="">Choose account</option>{activeAccounts.map(account => <option key={account.id} value={account.id}>{account.name} · {money.format(account.currentBalance)}</option>)}</select></label></div>
            <div className="field-row"><label>Amount<input value={draft.amount} onChange={e => setDraft({ ...draft, amount: e.target.value })} type="number" min="0.01" step="0.01" required placeholder="0.00" /></label><label>Date<input value={draft.date} onChange={e => setDraft({ ...draft, date: e.target.value })} type="date" required /></label></div><label>Description <span className="optional">optional</span><input value={draft.description} onChange={e => setDraft({ ...draft, description: e.target.value })} maxLength={80} placeholder="Move to savings" /></label><label>Notes <span className="optional">optional</span><textarea value={draft.notes} onChange={e => setDraft({ ...draft, notes: e.target.value })} maxLength={500} rows={2} /></label>
          </> : <>
            <div className="field-row"><label>Description<input value={draft.description} onChange={e => setDraft({ ...draft, description: e.target.value })} required maxLength={80} placeholder="e.g. Grocery run" /></label><label>Amount<input value={draft.amount} onChange={e => setDraft({ ...draft, amount: e.target.value })} type="number" min="0.01" step="0.01" required placeholder="0.00" /></label></div>
            <div className="field-row"><label>Account <span className="optional">optional</span><select value={draft.accountId} onChange={e => setDraft({ ...draft, accountId: e.target.value })}><option value="">Unassigned / manual</option>{activeAccounts.map(account => <option key={account.id} value={account.id}>{account.name} · {money.format(account.currentBalance)}</option>)}</select></label><label>Date<input value={draft.date} onChange={e => setDraft({ ...draft, date: e.target.value })} type="date" required /></label></div>
            <div className="field-row"><label>Category<input list="ledgerly-categories" value={draft.category} onChange={e => setDraft({ ...draft, category: e.target.value })} required maxLength={80} placeholder="Groceries" /></label><label>Subcategory <span className="optional">optional</span><input value={draft.subcategory} onChange={e => setDraft({ ...draft, subcategory: e.target.value })} maxLength={80} placeholder="Household" /></label></div>
            <label>Tags <span className="optional">optional, comma-separated</span><input value={draft.tags} onChange={e => setDraft({ ...draft, tags: e.target.value })} maxLength={240} placeholder="recurring, work" /></label><label>Notes <span className="optional">optional</span><textarea value={draft.notes} onChange={e => setDraft({ ...draft, notes: e.target.value })} maxLength={500} rows={2} placeholder="Add context for later" /></label>
          </>}
          <button className="primary" disabled={busy || (transactionType === 'transfer' && activeAccounts.length < 2)}>{busy ? 'Saving…' : editing ? 'Update transaction' : transactionType === 'transfer' ? 'Record transfer' : 'Save transaction'}</button>
        </form>
      </article>
      <article className="card mini-summary"><h3>This month</h3><div><span>Income</span><strong className="income">{money.format(data.income)}</strong></div><div><span>Expenses</span><strong className="expense">{money.format(data.expenses)}</strong></div><div><span>Net cash flow</span><strong className={data.netCashFlow >= 0 ? 'income' : 'expense'}>{money.format(data.netCashFlow)}</strong></div><div><span>Transfers</span><strong>{data.transactions.filter(t => t.transactionType === 'transfer' && t.date.slice(0, 7) === today().slice(0, 7)).length / 2}</strong></div></article>
    </section>

    <section className="card transaction-manager">
      <div className="card-head"><div><h3>Transaction history</h3><p>{filtered.length} of {data.transactions.length} entries</p></div></div>
      <div className="filters wide"><input aria-label="Search transactions" value={search} onChange={e => setSearch(e.target.value)} placeholder="Search description, category, account, tags, or notes…" /><select aria-label="Filter category" value={category} onChange={e => setCategory(e.target.value)}><option>All</option>{categories.map(item => <option key={item}>{item}</option>)}</select><select aria-label="Filter account" value={accountFilter} onChange={e => setAccountFilter(e.target.value)}><option value="All">All accounts</option>{data.accounts.map(account => <option key={account.id} value={account.id}>{account.name}</option>)}</select><select aria-label="Filter type" value={kind} onChange={e => setKind(e.target.value as typeof kind)}><option value="All">All types</option><option value="income">Income</option><option value="expense">Expense</option><option value="transfer">Transfer</option></select><input aria-label="Start date" type="date" value={startDate} onChange={e => setStartDate(e.target.value)} /><input aria-label="End date" type="date" value={endDate} onChange={e => setEndDate(e.target.value)} /><select aria-label="Sort transactions" value={sort} onChange={e => setSort(e.target.value as typeof sort)}><option value="newest">Newest first</option><option value="oldest">Oldest first</option><option value="high">Largest amount</option><option value="low">Smallest amount</option></select></div>
      {filtered.length ? <div className="transactions">{filtered.map(t => <TransactionRow key={t.id} transaction={t} onEdit={edit} onDelete={remove} />)}</div> : <Empty title="No matching transactions" body="Try changing your search or filters." />}
    </section>
  </div>
}

function BudgetPage({ data, refresh, notify }: { data: Dashboard; refresh: () => Promise<void>; notify: Notify }) {
  const categories = useMemo(() => Array.from(new Set([...defaultCategories.filter(item => item !== 'Income'), ...data.transactions.filter(t => t.transactionType === 'expense').map(t => t.category)])).filter(Boolean).sort(), [data.transactions])
  const [editing, setEditing] = useState<Budget | null>(null)
  const [category, setCategory] = useState('Groceries')
  const [limit, setLimit] = useState('')
  const reset = () => { setEditing(null); setCategory('Groceries'); setLimit('') }
  const submit = async (e: FormEvent<HTMLFormElement>) => { e.preventDefault(); try { if (editing) await api.updateBudget(editing.id, Number(limit)); else await api.addBudget({ category, limit: Number(limit) }); await refresh(); notify(editing ? 'Budget updated.' : 'Budget saved.'); reset() } catch (error) { notify(error instanceof Error ? error.message : 'Unable to save budget', 'error') } }
  const edit = (budget: Budget) => { setEditing(budget); setCategory(budget.category); setLimit(String(budget.limit)); window.scrollTo({ top: 0, behavior: 'smooth' }) }
  const remove = async (budget: Budget) => { if (!window.confirm(`Delete the ${budget.category} budget?`)) return; try { await api.deleteBudget(budget.id); await refresh(); notify('Budget deleted.'); if (editing?.id === budget.id) reset() } catch (error) { notify(error instanceof Error ? error.message : 'Unable to delete budget', 'error') } }

  return <div className="page-stack"><datalist id="budget-categories">{categories.map(item => <option key={item} value={item} />)}</datalist>
    <section className="grid form-grid"><article className="card form-card"><div className="card-head"><div><h3>{editing ? `Edit ${editing.category}` : 'Create monthly budget'}</h3><p>Set a monthly category guardrail. Spending is derived from actual expense transactions.</p></div>{editing && <button className="text-button inline" onClick={reset}>Cancel edit</button>}</div><form className="stack" onSubmit={submit}><label>Category<input list="budget-categories" value={category} disabled={!!editing} onChange={e => setCategory(e.target.value)} required maxLength={80} /></label><label>Monthly limit<input value={limit} onChange={e => setLimit(e.target.value)} type="number" min="0.01" step="0.01" required placeholder="600.00" /></label><button className="primary">{editing ? 'Update budget' : 'Save budget'}</button></form></article><article className="card mini-summary"><h3>Where this month stands</h3><div><span>Budgeted expenses</span><strong>{money.format(data.monthlyPlan.budgetedExpenses)}</strong></div><div><span>Budget remaining</span><strong className={data.budgetRemaining >= 0 ? 'income' : 'expense'}>{money.format(data.budgetRemaining)}</strong></div><div><span>Unbudgeted spending</span><strong>{money.format(data.unbudgetedSpending)}</strong></div><div><span>Days remaining</span><strong>{data.monthlyPlan.daysRemaining}</strong></div></article></section>
    <section className="budget-grid">{data.budgets.length ? data.budgets.map(b => { const over = b.status === 'over'; const approaching = b.status === 'approaching'; return <article className={`card budget-card ${over ? 'over' : approaching ? 'approaching' : ''}`} key={b.id}><div className="card-head"><div><span className={`budget-status ${b.status}`}>{b.status === 'over' ? 'OVER BUDGET' : b.status === 'approaching' ? 'APPROACHING LIMIT' : 'HEALTHY'}</span><h3>{b.category}</h3><span>{b.percentUsed.toFixed(0)}% used · {data.monthlyPlan.daysRemaining} days left</span></div><div className="row-actions"><button onClick={() => edit(b)}>Edit</button><button className="danger-button" onClick={() => remove(b)}>Delete</button></div></div><strong className="budget-value">{money.format(b.spent)} <span>/ {money.format(b.limit)}</span></strong><Progress value={b.percentUsed} danger={over} warning={approaching} /><div className="budget-foot"><span>{over ? 'Over budget by' : 'Remaining'}</span><strong className={over ? 'expense' : 'income'}>{money.format(Math.abs(b.remaining))}</strong></div></article> }) : <article className="card"><Empty title="No budget yet" body="Create this month's first category budget." /></article>}</section>
  </div>
}

function GoalPage({ data, refresh, notify }: { data: Dashboard; refresh: () => Promise<void>; notify: Notify }) {
  const [editing, setEditing] = useState<Goal | null>(null)
  const [name, setName] = useState('')
  const [target, setTarget] = useState('')
  const [saved, setSaved] = useState('')
  const [targetDate, setTargetDate] = useState('')
  const [notes, setNotes] = useState('')
  const [contributions, setContributions] = useState<Record<number, string>>({})

  const reset = () => { setEditing(null); setName(''); setTarget(''); setSaved(''); setTargetDate(''); setNotes('') }
  const submit = async (e: FormEvent<HTMLFormElement>) => { e.preventDefault(); try { const payload = { name, target: Number(target), saved: Number(saved || 0), targetDate: targetDate || null, notes }; if (editing) await api.updateGoal(editing.id, payload); else await api.addGoal(payload); await refresh(); notify(editing ? 'Goal updated.' : 'Goal created.'); reset() } catch (error) { notify(error instanceof Error ? error.message : 'Unable to save goal', 'error') } }
  const edit = (goal: Goal) => { setEditing(goal); setName(goal.name); setTarget(String(goal.target)); setSaved(String(goal.saved)); setTargetDate(goal.targetDate || ''); setNotes(goal.notes || ''); window.scrollTo({ top: 0, behavior: 'smooth' }) }
  const contribute = async (goal: Goal) => { const amount = Number(contributions[goal.id]); if (!amount || amount <= 0) return notify('Enter a positive contribution amount.', 'error'); try { await api.contributeGoal(goal.id, amount); setContributions({ ...contributions, [goal.id]: '' }); await refresh(); notify(`${money.format(amount)} added to ${goal.name}.`) } catch (error) { notify(error instanceof Error ? error.message : 'Unable to add contribution', 'error') } }
  const remove = async (goal: Goal) => { if (!window.confirm(`Delete “${goal.name}”?`)) return; try { await api.deleteGoal(goal.id); await refresh(); notify('Goal deleted.'); if (editing?.id === goal.id) reset() } catch (error) { notify(error instanceof Error ? error.message : 'Unable to delete goal', 'error') } }
  const totalSaved = data.goals.reduce((sum, goal) => sum + goal.saved, 0)
  const totalTarget = data.goals.reduce((sum, goal) => sum + goal.target, 0)

  return <div className="page-stack">
    <section className="grid form-grid"><article className="card form-card"><div className="card-head"><div><h3>{editing ? 'Edit savings goal' : 'Create savings goal'}</h3><p>Track a target, optional date, and measurable contributions.</p></div>{editing && <button className="text-button inline" onClick={reset}>Cancel edit</button>}</div><form className="stack" onSubmit={submit}><label>Goal name<input value={name} onChange={e => setName(e.target.value)} required maxLength={120} placeholder="Emergency fund" /></label><div className="field-row"><label>Target amount<input value={target} onChange={e => setTarget(e.target.value)} type="number" min="0.01" step="0.01" required placeholder="6000" /></label><label>Already saved<input value={saved} onChange={e => setSaved(e.target.value)} type="number" min="0" step="0.01" placeholder="0" /></label></div><label>Target date <span className="optional">optional</span><input value={targetDate} onChange={e => setTargetDate(e.target.value)} type="date" /></label><label>Notes <span className="optional">optional</span><textarea value={notes} onChange={e => setNotes(e.target.value)} maxLength={1000} rows={2} placeholder="Why this goal matters or what it covers" /></label><button className="primary">{editing ? 'Update goal' : 'Save goal'}</button></form></article><article className="card mini-summary"><h3>Goal progress</h3><div><span>Total saved</span><strong className="income">{money.format(totalSaved)}</strong></div><div><span>Combined targets</span><strong>{money.format(totalTarget)}</strong></div><div><span>Overall funded</span><strong>{totalTarget ? `${Math.min((totalSaved / totalTarget) * 100, 100).toFixed(0)}%` : '0%'}</strong></div></article></section>
    <section className="goal-grid">{data.goals.length ? data.goals.map(g => { const done = g.saved >= g.target; const monthly = suggestedMonthlyContribution(g); return <article className={`card goal-card ${done ? 'complete' : ''}`} key={g.id}><div className="card-head"><div><span className="goal-status">{done ? 'GOAL REACHED' : 'IN PROGRESS'}</span><h3>{g.name}</h3>{g.targetDate && <span>Target {new Date(`${g.targetDate}T12:00:00`).toLocaleDateString()}</span>}</div><div className="row-actions"><button onClick={() => edit(g)}>Edit</button><button className="danger-button" onClick={() => remove(g)}>Delete</button></div></div><div className="goal-amount"><strong>{money.format(g.saved)}</strong><span>of {money.format(g.target)}</span></div><Progress value={g.percentComplete} /><div className="goal-meta"><span>{Math.min(g.percentComplete, 100).toFixed(0)}% funded</span><span>{done ? 'Complete' : `${money.format(g.amountRemaining)} to go`}</span></div>{monthly !== null && !done && <p className="goal-guidance">About {money.format(monthly)}/month would reach this goal by the target date.</p>}{g.notes && <p>{g.notes}</p>}{!done && <div className="contribution"><input aria-label={`Contribution to ${g.name}`} type="number" min="0.01" step="0.01" placeholder="Add contribution" value={contributions[g.id] || ''} onChange={e => setContributions({ ...contributions, [g.id]: e.target.value })} /><button className="secondary" onClick={() => contribute(g)}>Add funds</button></div>}</article> }) : <article className="card"><Empty title="No savings goals" body="Create a savings goal and start tracking progress." /></article>}</section>
  </div>
}

function ReportsPage({ data }: { data: Dashboard }) {
  const monthStart = `${today().slice(0, 7)}-01`
  const [startDate, setStartDate] = useState(monthStart)
  const [endDate, setEndDate] = useState(today())
  const filtered = useMemo(() => data.transactions.filter(t => t.transactionType !== 'transfer' && (!startDate || t.date >= startDate) && (!endDate || t.date <= endDate)), [data.transactions, startDate, endDate])
  const income = filtered.filter(t => t.transactionType === 'income').reduce((sum, t) => sum + Math.abs(t.amount), 0)
  const expenses = filtered.filter(t => t.transactionType === 'expense').reduce((sum, t) => sum + Math.abs(t.amount), 0)
  const categories = Array.from(filtered.filter(t => t.transactionType === 'expense').reduce((map, t) => map.set(t.category, (map.get(t.category) || 0) + Math.abs(t.amount)), new Map<string, number>()).entries()).sort((a, b) => b[1] - a[1])
  const largest = [...filtered].sort((a, b) => Math.abs(b.amount) - Math.abs(a.amount)).slice(0, 6)

  return <div className="page-stack"><section className="card report-controls"><div className="card-head"><div><h3>Report range</h3><p>Transfers are excluded from income and spending reports.</p></div></div><div className="field-row"><label>Start date<input type="date" value={startDate} onChange={e => setStartDate(e.target.value)} /></label><label>End date<input type="date" value={endDate} onChange={e => setEndDate(e.target.value)} /></label></div></section>
    <section className="metrics report-metrics"><Metric label="Income" value={money.format(income)} /><Metric label="Expenses" value={money.format(expenses)} tone="red" /><Metric label="Net cash flow" value={money.format(income - expenses)} tone="amber" /><Metric label="Transactions" value={String(filtered.length)} detail={`${startDate || 'Beginning'} through ${endDate || 'Today'}`} /></section>
    <section className="grid two"><article className="card"><div className="card-head"><h3>Spending by category</h3><span>{categories.length} categories</span></div>{categories.length ? <div className="category-list">{categories.map(([name, amount]) => <div key={name}><span>{name}</span><strong>{money.format(amount)}</strong><Progress value={expenses ? amount / expenses * 100 : 0} /></div>)}</div> : <Empty title="No expenses in this range" body="Choose a broader date range or add expense transactions." />}</article><article className="card"><div className="card-head"><h3>Largest transactions</h3><span>By absolute amount</span></div>{largest.length ? <div className="transactions">{largest.map(transaction => <TransactionRow key={transaction.id} transaction={transaction} />)}</div> : <Empty />}</article></section>
    <section className="grid two"><TrendChart trend={data.monthlyTrend} /><article className="card"><div className="card-head"><h3>Account balances</h3><span>Current</span></div>{data.accounts.length ? <div className="plan-list">{data.accounts.filter(account => !account.archived).map(account => <div key={account.id}><span>{account.name}<small>{accountTypeLabel(account.type)}</small></span><strong className={account.currentBalance < 0 ? 'expense' : ''}>{money.format(account.currentBalance)}</strong></div>)}</div> : <Empty title="No accounts yet" body="Add accounts to compare balances here." />}</article></section>
    <section className="card"><div className="card-head"><div><h3>Budget performance</h3><p>Current-month category limits compared with actual expense transactions.</p></div><span>{data.budgets.length} budgets</span></div>{data.budgets.length ? <div className="report-budget-grid">{data.budgets.map(b => <div key={b.id}><span>{b.category}</span><strong className={b.status === 'over' ? 'expense' : ''}>{b.percentUsed.toFixed(0)}% · {money.format(b.remaining)} remaining</strong><Progress value={b.percentUsed} danger={b.status === 'over'} warning={b.status === 'approaching'} /></div>)}</div> : <Empty title="No budgets to report" body="Create a budget to measure category performance." />}</section>
  </div>
}

function SettingsPage({ data, refresh, notify, signOut }: { data: Dashboard; refresh: () => Promise<void>; notify: Notify; signOut: (reason?: string) => void }) {
  const [account, setAccount] = useState<Account | null>(null)
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [deletePassword, setDeletePassword] = useState('')
  const [importAccount, setImportAccount] = useState('')
  const [busy, setBusy] = useState('')

  useEffect(() => { api.account().then(setAccount).catch(() => undefined) }, [data.transactions.length, data.budgets.length, data.goals.length, data.accounts.length])

  const changePassword = async (event: FormEvent<HTMLFormElement>) => { event.preventDefault(); if (newPassword !== confirmPassword) return notify('New passwords do not match.', 'error'); try { setBusy('password'); await api.changePassword(currentPassword, newPassword); setCurrentPassword(''); setNewPassword(''); setConfirmPassword(''); notify('Password updated successfully.') } catch (error) { notify(error instanceof Error ? error.message : 'Unable to change password', 'error') } finally { setBusy('') } }

  const exportCsv = () => {
    const escape = (value: string | number) => `"${String(value).replaceAll('"', '""')}"`
    const rows = [['description', 'amount', 'type', 'account', 'category', 'subcategory', 'tags', 'date', 'notes'], ...data.transactions.map(t => [t.description, t.amount, t.transactionType, t.accountName || '', t.category, t.subcategory, t.tags.join('|'), t.date, t.notes || ''])]
    downloadText(rows.map(row => row.map(escape).join(',')).join('\n'), `ledgerly-transactions-${today()}.csv`, 'text/csv;charset=utf-8')
    notify(`Exported ${data.transactions.length} transactions.`)
  }

  const exportBackup = async () => { try { setBusy('backup'); const bundle = await api.exportData(); downloadText(JSON.stringify(bundle, null, 2), `ledgerly-backup-${today()}.json`, 'application/json'); notify('Full Ledgerly backup exported.') } catch (error) { notify(error instanceof Error ? error.message : 'Unable to export backup', 'error') } finally { setBusy('') } }

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
      const payload: TransactionInput[] = rows.slice(1).filter(row => row.some(value => value.trim())).map(row => {
        const amount = Number(row[index('amount')])
        const rawType = headers.includes('type') ? String(row[index('type')] || '').toLowerCase() : ''
        const transactionType: 'income' | 'expense' = rawType === 'income' || rawType === 'expense' ? rawType : amount >= 0 ? 'income' : 'expense'
        return { description: row[index('description')] || '', amount, transactionType, category: row[index('category')] || '', subcategory: headers.includes('subcategory') ? row[index('subcategory')] || '' : '', tags: headers.includes('tags') ? String(row[index('tags')] || '').split('|').map(tag => tag.trim()).filter(Boolean) : [], date: row[index('date')] || '', notes: headers.includes('notes') ? row[index('notes')] || '' : '' }
      })
      const result = await api.importTransactions(payload, importAccount ? Number(importAccount) : null, true)
      await refresh()
      const extras = [result.invalidRows.length ? `${result.invalidRows.length} invalid row(s) skipped` : '', result.skippedDuplicates.length ? `${result.skippedDuplicates.length} duplicate row(s) skipped` : ''].filter(Boolean).join('; ')
      notify(`Imported ${result.imported} transactions${extras ? `; ${extras}` : ''}.`)
    } catch (error) { notify(error instanceof Error ? error.message : 'Unable to import CSV', 'error') }
    finally { setBusy('') }
  }

  const clearData = async () => { if (!window.confirm('Delete ALL accounts, transactions, budgets, and goals? Your login will remain active.')) return; if (!window.confirm('This cannot be undone. Clear all financial data?')) return; try { setBusy('clear'); await api.clearData(); await refresh(); notify('Financial data cleared.') } catch (error) { notify(error instanceof Error ? error.message : 'Unable to clear data', 'error') } finally { setBusy('') } }
  const resetDemo = async () => { if (!window.confirm('Replace all financial data with fictional Ledgerly demo data?')) return; try { setBusy('demo'); await api.resetDemo(); await refresh(); notify('Fresh fictional demo data loaded.') } catch (error) { notify(error instanceof Error ? error.message : 'Unable to reset demo data', 'error') } finally { setBusy('') } }
  const deleteAccount = async (event: FormEvent<HTMLFormElement>) => { event.preventDefault(); if (!window.confirm('Permanently delete your Ledgerly account and all data?')) return; try { setBusy('delete'); await api.deleteAccount(deletePassword); signOut('Your account was deleted.') } catch (error) { notify(error instanceof Error ? error.message : 'Unable to delete account', 'error') } finally { setBusy('') } }

  return <div className="settings-grid">
    <article className="card settings-card"><div className="card-head"><div><h3>Account</h3><p>Your Ledgerly profile and usage summary.</p></div></div>{account ? <div className="account-summary"><div><span>Email</span><strong>{account.email}</strong></div><div><span>Email status</span><strong className={account.emailVerified ? 'income' : 'expense'}>{account.emailVerified ? 'Verified' : 'Unverified'}</strong></div><div><span>Member since</span><strong>{account.createdAt ? new Date(account.createdAt).toLocaleDateString() : '—'}</strong></div><div><span>Financial accounts</span><strong>{account.financialAccountCount}</strong></div><div><span>Transactions</span><strong>{account.transactionCount}</strong></div><div><span>Budgets / goals</span><strong>{account.budgetCount} / {account.goalCount}</strong></div></div> : <div className="loading compact"><span className="spinner" />Loading account…</div>}</article>
    <article className="card settings-card"><div className="card-head"><div><h3>Change password</h3><p>Password security is handled through Firebase Authentication.</p></div></div><form className="stack" onSubmit={changePassword}><label>Current password<input type="password" autoComplete="current-password" required value={currentPassword} onChange={e => setCurrentPassword(e.target.value)} /></label><label>New password<input type="password" autoComplete="new-password" minLength={10} maxLength={128} required value={newPassword} onChange={e => setNewPassword(e.target.value)} /></label><label>Confirm new password<input type="password" autoComplete="new-password" minLength={10} maxLength={128} required value={confirmPassword} onChange={e => setConfirmPassword(e.target.value)} /></label><button className="primary" disabled={busy === 'password'}>{busy === 'password' ? 'Updating…' : 'Update password'}</button></form></article>
    <article className="card settings-card data-tools"><div className="card-head"><div><h3>Data portability</h3><p>Your financial data belongs to you.</p></div></div><div className="settings-actions"><button className="secondary" onClick={exportCsv} disabled={!data.transactions.length}>Export transactions CSV</button><button className="secondary" onClick={exportBackup} disabled={busy === 'backup'}>{busy === 'backup' ? 'Exporting…' : 'Export full JSON backup'}</button></div><div className="import-tools"><label>Import into account <span className="optional">optional</span><select value={importAccount} onChange={e => setImportAccount(e.target.value)}><option value="">Leave unassigned</option>{data.accounts.filter(item => !item.archived).map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label className="file-button">{busy === 'import' ? 'Importing…' : 'Import transaction CSV'}<input type="file" accept=".csv,text/csv" disabled={busy === 'import'} onChange={e => { const file = e.target.files?.[0]; if (file) void importCsv(file); e.currentTarget.value = '' }} /></label></div><small>Required CSV headers: description, amount, category, date. Invalid rows and likely duplicates are skipped and reported instead of destroying the entire import.</small></article>
    <article className="card settings-card"><div className="card-head"><div><h3>Demo & reset tools</h3><p>Demo data is explicitly fictional and isolated to your account.</p></div></div><div className="settings-actions vertical"><button className="secondary" disabled={!!busy} onClick={resetDemo}>{busy === 'demo' ? 'Loading demo…' : 'Replace with fresh demo data'}</button><button className="danger-outline" disabled={!!busy} onClick={clearData}>{busy === 'clear' ? 'Clearing…' : 'Clear all financial data'}</button></div></article>
    <article className="card settings-card danger-zone"><div className="card-head"><div><h3>Danger zone</h3><p>Permanently remove your account and all associated financial data.</p></div></div><form className="stack" onSubmit={deleteAccount}><label>Confirm with your password<input type="password" autoComplete="current-password" required value={deletePassword} onChange={e => setDeletePassword(e.target.value)} /></label><button className="danger-primary" disabled={busy === 'delete'}>{busy === 'delete' ? 'Deleting…' : 'Delete account permanently'}</button></form></article>
  </div>
}

function accountTypeLabel(type: FinancialAccount['type']) { return accountTypes.find(item => item.value === type)?.label || 'Other' }

function suggestedMonthlyContribution(goal: Goal) {
  if (!goal.targetDate || goal.amountRemaining <= 0) return null
  const now = new Date(`${today()}T12:00:00`)
  const target = new Date(`${goal.targetDate}T12:00:00`)
  if (target <= now) return null
  const months = Math.max(1, (target.getFullYear() - now.getFullYear()) * 12 + target.getMonth() - now.getMonth() + (target.getDate() > now.getDate() ? 1 : 0))
  return goal.amountRemaining / months
}

function downloadText(text: string, filename: string, type: string) {
  const blob = new Blob([text], { type })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
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
