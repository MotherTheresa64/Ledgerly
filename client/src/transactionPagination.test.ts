import { describe, expect, it } from 'vitest'
import { visiblePageNumbers } from './transactionPagination'


describe('transaction pagination', () => {
  it('shows every page for short histories', () => {
    expect(visiblePageNumbers(2, 5)).toEqual([1, 2, 3, 4, 5])
  })

  it('keeps the first, current neighborhood, and last page for long histories', () => {
    expect(visiblePageNumbers(8, 20)).toEqual([1, 7, 8, 9, 20])
  })

  it('keeps useful navigation near either edge', () => {
    expect(visiblePageNumbers(1, 20)).toEqual([1, 2, 3, 4, 5, 20])
    expect(visiblePageNumbers(20, 20)).toEqual([1, 16, 17, 18, 19, 20])
  })
})
