// How many cards a card grid shows per row at most (2, 4, 6 or 8), kept locally and shared
// by every grid that offers the choice.
import { useSyncExternalStore } from 'react'

export const CARDS_PER_ROW = [2, 4, 6, 8] as const
export type CardsPerRow = (typeof CARDS_PER_ROW)[number]

const STORAGE_KEY = 'mindgrid.cards-per-row'
const listeners = new Set<() => void>()

export const isCardsPerRow = (value: unknown): value is CardsPerRow =>
  CARDS_PER_ROW.includes(value as CardsPerRow)

function read(): CardsPerRow {
  try {
    const n = Number(localStorage.getItem(STORAGE_KEY))
    return isCardsPerRow(n) ? n : 2
  } catch {
    return 2
  }
}

let current: CardsPerRow = read()

export function getCardsPerRow(): CardsPerRow {
  return current
}

export function setCardsPerRow(n: CardsPerRow): void {
  if (n === current) return
  current = n
  try {
    localStorage.setItem(STORAGE_KEY, String(n))
  } catch {
    // storage blocked: keep the choice for this document only
  }
  listeners.forEach((fn) => fn())
}

export function subscribeCardsPerRow(fn: () => void): () => void {
  listeners.add(fn)
  return () => listeners.delete(fn)
}

export function useCardsPerRow(): CardsPerRow {
  return useSyncExternalStore(subscribeCardsPerRow, getCardsPerRow)
}
