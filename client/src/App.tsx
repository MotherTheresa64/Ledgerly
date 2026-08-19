import { FormEvent, useEffect, useMemo, useState } from 'react'
import { api } from './api'
import type { Dashboard } from './types'

const money = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })

function Metric({ label, value, tone = 'green' }: { label: string; value: string; tone?: string }) {
  return <article className={`metric ${tone}`}><span>{label}</span><strong>{value}</strong></article>
}

function Progress({ value }: { value: number }) {
  return <div className="progress"><span style={{ width: `${Math.min(Math.max(value, 0), 100)}%` }} /></div>
}

function App() {
  const [token, setToken] = useState(localStorage.getItem('ledgerly_token'))
  const [data, setData] = useState<Dashboard | null>(null)
  const [error, setError] = useState('')
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [active, setActive] = useState('Overview')

  const refresh = async () => {
    try {
      setError('')
      setData(await api.dashboard())
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to load dashboard')
    }
  }

  useEffect(() => { if (token) void refresh() }, [token])

  const handleAuth = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    try {
      const result = mode === 'login'
        ? await api.login(String(form.get('email')), String(form.get('password')))
        : await api.register(String(form.get('email')), String(form.get('password')))
      localStorage.setItem('ledgerly_token', result.accessToken)
      setToken(result.accessToken)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Authentication failed')
    }
  }

  const categories = useMemo(() => data?.categories || [], [data])

  if (!token) {
    return <main className="auth-shell">
      <section className="brand-panel">
        <div className="logo-mark">L</div>
        <h1>Ledgerly</h1>
        <p>Personal finance. Full control. Smarter decisions.</p>
        <ul><li>Track spending</li><li>Budget smarter</li><li>Visualize growth</li><li>Set meaningful goals</li></ul>
      </section>
      <section className="auth-card">
        <span className="eyebrow">WELCOME TO LEDGERLY</span>
        <h2>{mode === 'login' ? 'Welcome back' : 'Create your account'}</h2>
        <p>Build a clearer picture of your money.</p>
        <form onSubmit={handleAuth}>
          <label>Email<input name="email" type="email" required placeholder="you@example.com" /></label>
          <label>Password<input name="password" type="password" minLength={8} required placeholder="Minimum 8 characters" /></label>
          {error && <div className="error">{error}</div>}
          <button className="primary" type="submit">{mode === 'login' ? 'Sign in' : 'Create account'}</button>
        </form>
        <button className="text-button" onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError('') }}>
          {mode === 'login' ? 'Need an account? Register' : 'Already registered? Sign in'}
        </button>
      </section>
    </main>
  }

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><div className="logo-mark small">L</div><strong>Ledgerly</strong></div>
      <nav>{['Overview', 'Transactions', 'Budgets', 'Goals'].map(item => <button key={item} className={active === item ? 'active' : ''} onClick={() => setActive(item)}>{item}</button>)}</nav>
      <button className="logout" onClick={() => { localStorage.removeItem('ledgerly_token'); setToken(null); setData(null) }}>Sign out</button>
    </aside>

    <main className="dashboard">
      <header><div><span className="eyebrow">PERSONAL FINANCE</span><h1>{active}</h1></div><button className="secondary" onClick={refresh}>Refresh</button></header>
      {error && <div className="error">{error}</div>}
      {!data ? <div className="loading">Loading Ledgerly…</div> : <>
        {active === 'Overview' && <>
          <section className="metrics">
            <Metric label="Total balance" value={money.format(data.totalBalance)} />
            <Metric label="Income" value={money.format(data.income)} />
            <Metric label="Expenses" value={money.format(data.expenses)} tone="red" />
            <Metric label="Savings rate" value={`${data.savingsRate.toFixed(1)}%`} tone="amber" />
          </section>
          <section className="grid two">
            <article className="card"><div className="card-head"><h3>Spending breakdown</h3><span>This month</span></div>
              {categories.length ? <div className="category-list">{categories.map(c => <div key={c.category}><span>{c.category}</span><strong>{money.format(c.amount)}</strong><Progress value={data.expenses ? (c.amount / data.expenses) * 100 : 0} /></div>)}</div> : <Empty />}
            </article>
            <article className="card"><div className="card-head"><h3>Budget progress</h3><span>Current month</span></div>
              {data.budgets.length ? <div className="category-list">{data.budgets.map(b => <div key={b.id}><span>{b.category}</span><strong>{money.format(b.spent)} / {money.format(b.limit)}</strong><Progress value={(b.spent / b.limit) * 100} /></div>)}</div> : <Empty />}
            </article>
          </section>
          <section className="grid two">
            <TransactionList data={data} refresh={refresh} />
            <article className="card"><div className="card-head"><h3>Savings goals</h3><span>{data.goals.length} active</span></div>
              {data.goals.length ? <div className="category-list">{data.goals.map(g => <div key={g.id}><span>{g.name}</span><strong>{money.format(g.saved)} / {money.format(g.target)}</strong><Progress value={(g.saved / g.target) * 100} /></div>)}</div> : <Empty />}
            </article>
          </section>
          {!data.transactions.length && <button className="primary demo" onClick={async () => { await api.seedDemo(); await refresh() }}>Load demo data</button>}
        </>}
        {active === 'Transactions' && <TransactionPage data={data} refresh={refresh} />}
        {active === 'Budgets' && <BudgetPage data={data} refresh={refresh} />}
        {active === 'Goals' && <GoalPage data={data} refresh={refresh} />}
      </>}
    </main>
  </div>
}

function Empty() { return <div className="empty">No data yet. Add your first item to get started.</div> }

function TransactionList({ data, refresh }: { data: Dashboard; refresh: () => Promise<void> }) {
  return <article className="card"><div className="card-head"><h3>Recent transactions</h3><span>{data.transactions.length} shown</span></div>
    {data.transactions.length ? <div className="transactions">{data.transactions.slice(0, 6).map(t => <div className="transaction" key={t.id}><div><strong>{t.description}</strong><span>{t.category} · {new Date(t.date).toLocaleDateString()}</span></div><div className="amount-wrap"><strong className={t.amount < 0 ? 'expense' : 'income'}>{money.format(t.amount)}</strong><button title="Delete" onClick={async () => { await api.deleteTransaction(t.id); await refresh() }}>×</button></div></div>)}</div> : <Empty />}
  </article>
}

function TransactionPage({ data, refresh }: { data: Dashboard; refresh: () => Promise<void> }) {
  const submit = async (e: FormEvent<HTMLFormElement>) => { e.preventDefault(); const f = new FormData(e.currentTarget); await api.addTransaction({ description: String(f.get('description')), amount: Number(f.get('amount')), category: String(f.get('category')), date: String(f.get('date')) }); e.currentTarget.reset(); await refresh() }
  return <section className="grid two"><article className="card"><h3>Add transaction</h3><form className="stack" onSubmit={submit}><input name="description" required placeholder="Description" /><input name="amount" type="number" step="0.01" required placeholder="Use negative for expenses" /><input name="category" required placeholder="Category" /><input name="date" type="date" required /><button className="primary">Save transaction</button></form></article><TransactionList data={data} refresh={refresh} /></section>
}

function BudgetPage({ data, refresh }: { data: Dashboard; refresh: () => Promise<void> }) {
  const submit = async (e: FormEvent<HTMLFormElement>) => { e.preventDefault(); const f = new FormData(e.currentTarget); await api.addBudget({ category: String(f.get('category')), limit: Number(f.get('limit')) }); e.currentTarget.reset(); await refresh() }
  return <section className="grid two"><article className="card"><h3>Create monthly budget</h3><form className="stack" onSubmit={submit}><input name="category" required placeholder="Category" /><input name="limit" type="number" min="1" step="0.01" required placeholder="Monthly limit" /><button className="primary">Save budget</button></form></article><article className="card"><h3>Current budgets</h3><div className="category-list">{data.budgets.map(b => <div key={b.id}><span>{b.category}</span><strong>{money.format(b.spent)} / {money.format(b.limit)}</strong><Progress value={(b.spent / b.limit) * 100} /></div>)}</div></article></section>
}

function GoalPage({ data, refresh }: { data: Dashboard; refresh: () => Promise<void> }) {
  const submit = async (e: FormEvent<HTMLFormElement>) => { e.preventDefault(); const f = new FormData(e.currentTarget); await api.addGoal({ name: String(f.get('name')), target: Number(f.get('target')), saved: Number(f.get('saved') || 0) }); e.currentTarget.reset(); await refresh() }
  return <section className="grid two"><article className="card"><h3>Create savings goal</h3><form className="stack" onSubmit={submit}><input name="name" required placeholder="Goal name" /><input name="target" type="number" min="1" step="0.01" required placeholder="Target amount" /><input name="saved" type="number" min="0" step="0.01" placeholder="Already saved" /><button className="primary">Save goal</button></form></article><article className="card"><h3>Your goals</h3><div className="category-list">{data.goals.map(g => <div key={g.id}><span>{g.name}</span><strong>{money.format(g.saved)} / {money.format(g.target)}</strong><Progress value={(g.saved / g.target) * 100} /></div>)}</div></article></section>
}

export default App
