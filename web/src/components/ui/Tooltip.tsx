import { Tooltip as Radix } from 'radix-ui'
import type { ReactNode } from 'react'

export function TooltipProvider({ children }: { children: ReactNode }) {
  return <Radix.Provider delayDuration={200}>{children}</Radix.Provider>
}

export function Tooltip({ text, side = 'right', children }: { text: string,
  side?: 'right' | 'bottom' | 'top', children: ReactNode }) {
  return (
    <Radix.Root>
      <Radix.Trigger asChild>{children}</Radix.Trigger>
      <Radix.Portal>
        <Radix.Content side={side} sideOffset={6}
          className="mg-pop z-50 rounded-md bg-foreground px-2 py-1 text-xs text-background
            shadow">
          {text}
        </Radix.Content>
      </Radix.Portal>
    </Radix.Root>
  )
}
