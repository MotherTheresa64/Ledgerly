import { EmailAuthProvider, deleteUser, reauthenticateWithCredential, updatePassword } from 'firebase/auth'
import { firebaseAuth } from './firebase'
import type { Account, Dashboard, Goal, Transaction } from './types'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000/api'

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

async function currentFirebaseUser() {
  await firebaseAuth.authStateReady()
  return firebaseAuth.currentUser
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const user = await currentFirebaseUser()
  const token = user ? await user.getIdToken() : ''
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {}),
    },
  })

  const data = await response.json().catch(() => ({})) as Record<string, unknown>
  if (!response.ok) {
    if (response.status === 401) {
      localStorage.removeItem('ledgerly_token')
      window.dispatchEvent(new CustomEvent('ledgerly:unauthorized'))
    }
    throw new ApiError(String(data.error || data.msg || 'Request failed'), response.status, typeof data.code === 'string' ? data.code : undefined, data)
  }
  return data as T
}

export type TransactionInput = {
  description: string
  amount: number
  category: string
  date: string
  notes?: string
}

export const api = {
  account: () => request<Account>('/account'),
  changePassword: async (currentPassword: string, newPassword: string) => {
    const user = await currentFirebaseUser()
    if (!user?.email) throw new Error('Sign in again before changing your password.')
    await reauthenticateWithCredential(user, EmailAuthProvider.credential(user.email, currentPassword))
    await updatePassword(user, newPassword)
    const accessToken = await user.getIdToken(true)
    localStorage.setItem('ledgerly_token', accessToken)
    return { updated: true, accessToken }
  },
  deleteAccount: async (password: string) => {
    const user = await currentFirebaseUser()
    if (!user?.email) throw new Error('Sign in again before deleting your account.')
    await reauthenticateWithCredential(user, EmailAuthProvider.credential(user.email, password))
    const result = await request<{ deleted: boolean }>('/account', { method: 'DELETE' })
    await deleteUser(user)
    return result
  },
  dashboard: () => request<Dashboard>('/dashboard'),
  addTransaction: (payload: TransactionInput) => request<Transaction>('/transactions', { method: 'POST', body: JSON.stringify(payload) }),
  importTransactions: (transactions: TransactionInput[]) =>
    request<{ imported: number }>('/transactions/import', { method: 'POST', body: JSON.stringify({ transactions }) }),
  updateTransaction: (id: number, payload: TransactionInput) => request<Transaction>(`/transactions/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  deleteTransaction: (id: number) => request<{ deleted: number }>(`/transactions/${id}`, { method: 'DELETE' }),
  addBudget: (payload: { category: string; limit: number }) => request('/budgets', { method: 'POST', body: JSON.stringify(payload) }),
  updateBudget: (id: number, limit: number) => request(`/budgets/${id}`, { method: 'PATCH', body: JSON.stringify({ limit }) }),
  deleteBudget: (id: number) => request<{ deleted: number }>(`/budgets/${id}`, { method: 'DELETE' }),
  addGoal: (payload: { name: string; target: number; saved: number }) => request<Goal>('/goals', { method: 'POST', body: JSON.stringify(payload) }),
  updateGoal: (id: number, payload: Partial<Pick<Goal, 'name' | 'target' | 'saved'>>) => request<Goal>(`/goals/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  contributeGoal: (id: number, amount: number) => request<Goal>(`/goals/${id}/contribute`, { method: 'POST', body: JSON.stringify({ amount }) }),
  deleteGoal: (id: number) => request<{ deleted: number }>(`/goals/${id}`, { method: 'DELETE' }),
  clearData: () => request<{ cleared: boolean }>('/data', { method: 'DELETE' }),
  seedDemo: () => request<{ seeded: boolean }>('/demo/seed', { method: 'POST' }),
  resetDemo: () => request<{ seeded: boolean; reset: boolean }>('/demo/reset', { method: 'POST' }),
}
