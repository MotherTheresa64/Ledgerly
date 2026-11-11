import { EmailAuthProvider, deleteUser, reauthenticateWithCredential, updatePassword } from 'firebase/auth'
import { firebaseAuth } from './firebase'
import { withAsOf } from './date'
import type { Account, Dashboard, ExportBundle, FinancialAccount, Goal, Transaction, TransactionType } from './types'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000/api'
export const MAX_MONEY = 999_999_999.99
export const FIREBASE_SESSION_MARKER = 'firebase-session'

export type AuthUser = { email: string; emailVerified: boolean }
export type AuthSuccess = { accessToken: string; user: AuthUser }

export class ApiError extends Error {
  status: number
  code?: string
  details: Record<string, unknown>

  constructor(message: string, status: number, code?: string, details: Record<string, unknown> = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
  }
}

function assertMoney(value: number, label: string, allowZero = false) {
  const validMinimum = allowZero ? value >= 0 : value > 0
  const cents = Math.round(value * 100)
  const exactCents = Math.abs(value * 100 - cents) < Number.EPSILON * Math.max(1, Math.abs(value * 100)) * 4
  if (!Number.isFinite(value) || !validMinimum || value > MAX_MONEY || !exactCents) {
    const minimum = allowZero ? '$0.00' : '$0.01'
    throw new Error(`${label} must be between ${minimum} and $999,999,999.99 with at most two decimal places.`)
  }
}

async function currentFirebaseUser() {
  await firebaseAuth.authStateReady()
  return firebaseAuth.currentUser
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const user = await currentFirebaseUser()
  const token = user ? await user.getIdToken() : ''
  const headers = new Headers(options.headers || {})
  if (options.body !== undefined && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  if (token) headers.set('Authorization', `Bearer ${token}`)

  let response: Response
  try {
    response = await fetch(`${API_URL}${path}`, { ...options, headers })
  } catch {
    throw new ApiError('Unable to reach Ledgerly. Check your connection and try again.', 0)
  }

  const data = await response.json().catch(() => ({})) as Record<string, unknown>
  if (!response.ok) {
    if (response.status === 401) {
      localStorage.removeItem('ledgerly_token')
      window.dispatchEvent(new CustomEvent('ledgerly:unauthorized'))
    }
    const requestId = response.headers.get('X-Request-ID')
    const details = requestId ? { ...data, requestId } : data
    throw new ApiError(String(data.error || data.msg || 'Request failed'), response.status, typeof data.code === 'string' ? data.code : undefined, details)
  }
  return data as T
}

export type TransactionInput = {
  description: string
  amount: number
  transactionType?: Exclude<TransactionType, 'transfer'>
  accountId?: number | null
  category: string
  subcategory?: string
  tags?: string[]
  date: string
  notes?: string
}

export type AccountInput = {
  name: string
  type: FinancialAccount['type']
  institution?: string
  openingBalance: number
  description?: string
  includeInTotals?: boolean
  archived?: boolean
}

function validateTransaction(payload: TransactionInput) {
  assertMoney(Math.abs(payload.amount), 'Transaction amount')
  return payload
}

function validateGoal(payload: { name: string; target: number; saved: number; targetDate?: string | null; notes?: string }) {
  assertMoney(payload.target, 'Goal target')
  assertMoney(payload.saved, 'Saved amount', true)
  return payload
}

export const api = {
  account: () => request<Account>('/account'),
  changePassword: async (currentPassword: string, newPassword: string) => {
    const user = await currentFirebaseUser()
    if (!user?.email) throw new Error('Sign in again before changing your password.')
    await reauthenticateWithCredential(user, EmailAuthProvider.credential(user.email, currentPassword))
    await updatePassword(user, newPassword)
    await user.getIdToken(true)
    localStorage.setItem('ledgerly_token', FIREBASE_SESSION_MARKER)
    return { updated: true, accessToken: FIREBASE_SESSION_MARKER }
  },
  deleteAccount: async (password: string) => {
    const user = await currentFirebaseUser()
    if (!user?.email) throw new Error('Sign in again before deleting your account.')
    await reauthenticateWithCredential(user, EmailAuthProvider.credential(user.email, password))
    const result = await request<{ deleted: boolean }>('/account', { method: 'DELETE' })
    await deleteUser(user)
    return result
  },
  dashboard: () => request<Dashboard>(withAsOf('/dashboard')),
  accounts: () => request<FinancialAccount[]>('/accounts'),
  addAccount: (payload: AccountInput) => {
    assertMoney(Math.abs(payload.openingBalance), 'Opening balance', true)
    return request<FinancialAccount>('/accounts', { method: 'POST', body: JSON.stringify(payload) })
  },
  updateAccount: (id: number, payload: Partial<AccountInput>) => {
    if (payload.openingBalance !== undefined) assertMoney(Math.abs(payload.openingBalance), 'Opening balance', true)
    return request<FinancialAccount>(`/accounts/${id}`, { method: 'PATCH', body: JSON.stringify(payload) })
  },
  deleteFinancialAccount: (id: number, detachTransactions = false) => request<{ deleted: number }>(`/accounts/${id}${detachTransactions ? '?detach=true' : ''}`, { method: 'DELETE' }),
  addTransaction: (payload: TransactionInput) => request<Transaction>('/transactions', { method: 'POST', body: JSON.stringify(validateTransaction(payload)) }),
  addTransfer: (payload: { fromAccountId: number; toAccountId: number; amount: number; date: string; description?: string; notes?: string }) => {
    assertMoney(payload.amount, 'Transfer amount')
    return request<{ transferGroup: string; transactions: Transaction[] }>('/transfers', { method: 'POST', body: JSON.stringify(payload) })
  },
  importTransactions: (transactions: TransactionInput[], defaultAccountId?: number | null, allowPartial = true) =>
    request<{ imported: number; invalidRows: number[]; skippedDuplicates: number[] }>('/transactions/import', {
      method: 'POST',
      body: JSON.stringify({ transactions: transactions.map(validateTransaction), defaultAccountId: defaultAccountId || null, allowPartial }),
    }),
  updateTransaction: (id: number, payload: TransactionInput) => request<Transaction>(`/transactions/${id}`, { method: 'PATCH', body: JSON.stringify(validateTransaction(payload)) }),
  deleteTransaction: (id: number) => request<{ deleted: number; deletedTransfer?: string }>(`/transactions/${id}`, { method: 'DELETE' }),
  addBudget: (payload: { category: string; limit: number }) => {
    assertMoney(payload.limit, 'Monthly budget')
    return request(withAsOf('/budgets'), { method: 'POST', body: JSON.stringify(payload) })
  },
  updateBudget: (id: number, limit: number) => {
    assertMoney(limit, 'Monthly budget')
    return request(withAsOf(`/budgets/${id}`), { method: 'PATCH', body: JSON.stringify({ limit }) })
  },
  deleteBudget: (id: number) => request<{ deleted: number }>(`/budgets/${id}`, { method: 'DELETE' }),
  addGoal: (payload: { name: string; target: number; saved: number; targetDate?: string | null; notes?: string }) => request<Goal>('/goals', { method: 'POST', body: JSON.stringify(validateGoal(payload)) }),
  updateGoal: (id: number, payload: Partial<Pick<Goal, 'name' | 'target' | 'saved' | 'targetDate' | 'notes'>>) => {
    if (payload.target !== undefined) assertMoney(payload.target, 'Goal target')
    if (payload.saved !== undefined) assertMoney(payload.saved, 'Saved amount', true)
    return request<Goal>(`/goals/${id}`, { method: 'PATCH', body: JSON.stringify(payload) })
  },
  contributeGoal: (id: number, amount: number) => {
    assertMoney(amount, 'Contribution')
    return request<Goal>(`/goals/${id}/contribute`, { method: 'POST', body: JSON.stringify({ amount }) })
  },
  deleteGoal: (id: number) => request<{ deleted: number }>(`/goals/${id}`, { method: 'DELETE' }),
  exportData: () => request<ExportBundle>(withAsOf('/export')),
  clearData: () => request<{ cleared: boolean }>('/data', { method: 'DELETE' }),
  seedDemo: () => request<{ seeded: boolean }>(withAsOf('/demo/seed'), { method: 'POST' }),
  resetDemo: () => request<{ seeded: boolean; reset: boolean }>(withAsOf('/demo/reset'), { method: 'POST' }),
}
