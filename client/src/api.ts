import type { Account, Dashboard, Goal, Transaction } from './types'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000/api'

export type AuthUser = { email: string; emailVerified: boolean }
export type AuthSuccess = { accessToken: string; user: AuthUser }
export type RegisterResult = AuthSuccess | {
  verificationRequired: true
  emailSent: boolean
  email: string
  message: string
}

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

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem('ledgerly_token')
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
    if (response.status === 401 && token) {
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
  register: (email: string, password: string) =>
    request<RegisterResult>('/auth/register', { method: 'POST', body: JSON.stringify({ email, password }) }),
  login: (email: string, password: string) =>
    request<AuthSuccess>('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),
  verifyEmail: (token: string) =>
    request<AuthSuccess & { verified: true }>('/auth/verify-email', { method: 'POST', body: JSON.stringify({ token }) }),
  resendVerification: (email: string) =>
    request<{ message: string }>('/auth/resend-verification', { method: 'POST', body: JSON.stringify({ email }) }),
  forgotPassword: (email: string) =>
    request<{ message: string }>('/auth/forgot-password', { method: 'POST', body: JSON.stringify({ email }) }),
  resetPassword: (token: string, newPassword: string) =>
    request<{ updated: boolean }>('/auth/reset-password', { method: 'POST', body: JSON.stringify({ token, newPassword }) }),
  account: () => request<Account>('/account'),
  changePassword: async (currentPassword: string, newPassword: string) => {
    const result = await request<{ updated: boolean; accessToken: string }>('/account/password', { method: 'PATCH', body: JSON.stringify({ currentPassword, newPassword }) })
    localStorage.setItem('ledgerly_token', result.accessToken)
    return result
  },
  deleteAccount: (password: string) =>
    request<{ deleted: boolean }>('/account', { method: 'DELETE', body: JSON.stringify({ password }) }),
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
