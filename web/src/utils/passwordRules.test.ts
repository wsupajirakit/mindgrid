import { describe, expect, it } from 'vitest'
import { passwordChecks, passwordReady } from './passwordRules.ts'

describe('password rules', () => {
  it('needs nine characters with a lowercase letter, an uppercase letter and a digit', () => {
    expect(passwordReady('Abcdefgh1', 'Abcdefgh1')).toBe(true)
    expect(passwordReady('Abcdef1!', 'Abcdef1!')).toBe(false)
    expect(passwordChecks('abcdefgh1')).toEqual(
      { length: true, lower: true, upper: false, digit: true })
    expect(passwordChecks('ÁBCDEFGHé')).toEqual(
      { length: true, lower: false, upper: true, digit: false })
  })

  it('allows symbols without needing them, and the repeat must match', () => {
    expect(passwordReady('Ab1 !@#$%^&*', 'Ab1 !@#$%^&*')).toBe(true)
    expect(passwordReady('Abcdefgh1', 'Abcdefgh2')).toBe(false)
  })
})
