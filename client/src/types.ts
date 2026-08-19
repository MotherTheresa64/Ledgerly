export type Transaction = {
  id: number
  description: string
  amount: number
  category: string
  date: string
  notes?: string
}

export type Budget = {
  id: number
  category: string
  limit: number
  spent: number
  remaining: number
}

export type Goal = {
  id: number
  name: string
  target: number
  saved: number
}

export type MonthlyTrend = {
  month: string
  income: number
  expenses: number
  net: number
}

export type Account = {
  email: string
  createdAt: string | null
  transactionCount: number
  budgetCount: number
  goalCount: number
}

export type Dashboard = {
  totalBalance: number
  income: number
  expenses: number
  savingsRate: number
  categories: { category: string; amount: number }[]
  transactions: Transaction[]
  budgets: Budget[]
  goals: Goal[]
  monthlyTrend: MonthlyTrend[]
}
