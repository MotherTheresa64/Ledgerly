export type TransactionType = 'income' | 'expense' | 'transfer'

export type Transaction = {
  id: number
  description: string
  amount: number
  transactionType: TransactionType
  accountId: number | null
  accountName: string | null
  category: string
  subcategory: string
  tags: string[]
  transferGroup: string | null
  date: string
  notes?: string
}

export type BudgetStatus = 'healthy' | 'approaching' | 'over'

export type Budget = {
  id: number
  category: string
  limit: number
  spent: number
  remaining: number
  percentUsed: number
  status: BudgetStatus
}

export type Goal = {
  id: number
  name: string
  target: number
  saved: number
  targetDate: string | null
  notes: string
  amountRemaining: number
  percentComplete: number
  isOverfunded: boolean
  overfundedBy: number
  trackingOnly: boolean
}

export type MonthlyTrend = {
  month: string
  income: number
  expenses: number
  net: number
}

export type FinancialAccount = {
  id: number
  name: string
  type: 'checking' | 'savings' | 'cash' | 'credit' | 'loan' | 'investment' | 'other'
  balanceRole: 'asset' | 'liability'
  institution: string
  openingBalance: number
  currentBalance: number
  netWorthContribution: number
  description: string
  includeInTotals: boolean
  archived: boolean
  transactionCount: number
  createdAt: string | null
}

export type Account = {
  email: string
  emailVerified: boolean
  createdAt: string | null
  financialAccountCount: number
  transactionCount: number
  budgetCount: number
  goalCount: number
}

export type MonthlyPlan = {
  expectedIncome: number
  actualIncome: number
  budgetedExpenses: number
  actualExpenses: number
  amountRemaining: number
  unbudgetedSpending: number
  savingsContribution: number
  netResult: number
  daysRemaining: number
}

export type Dashboard = {
  totalBalance: number
  netWorth: number
  availableBalance: number
  assetBalance: number
  liabilityBalance: number
  income: number
  expenses: number
  netCashFlow: number
  savingsRate: number
  budgetRemaining: number
  unbudgetedSpending: number
  categories: { category: string; amount: number }[]
  accounts: FinancialAccount[]
  transactions: Transaction[]
  budgets: Budget[]
  goals: Goal[]
  monthlyTrend: MonthlyTrend[]
  monthlyPlan: MonthlyPlan
  insights: string[]
}

export type ExportBundle = {
  schemaVersion: number
  moneySemantics: string
  exportedAt: string
  accounts: FinancialAccount[]
  transactions: Transaction[]
  budgets: Budget[]
  goals: Goal[]
}
