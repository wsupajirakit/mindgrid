// The password rules, the same as the server's (backend platform/identity/passwords.py):
// at least MIN_LENGTH characters with an ASCII lowercase letter, uppercase letter and
// digit; any other character is allowed and none is required.
export const MIN_LENGTH = 9

export type Rule = 'length' | 'lower' | 'upper' | 'digit'

const TESTS: Record<Rule, (password: string) => boolean> = {
  length: (p) => p.length >= MIN_LENGTH,
  lower: (p) => /[a-z]/.test(p),
  upper: (p) => /[A-Z]/.test(p),
  digit: (p) => /[0-9]/.test(p),
}

export const RULES = Object.keys(TESTS) as Rule[]

export function passwordChecks(password: string): Record<Rule, boolean> {
  return Object.fromEntries(RULES.map((r) => [r, TESTS[r](password)])) as Record<Rule, boolean>
}

/** Meets every rule and the repeat matches: the form may be sent. */
export function passwordReady(password: string, repeat: string): boolean {
  return RULES.every((r) => TESTS[r](password)) && password === repeat
}
