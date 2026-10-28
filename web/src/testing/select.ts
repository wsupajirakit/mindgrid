// Drives the Radix Select in tests: open the trigger, then click the option by name.
import { fireEvent, screen } from '@testing-library/react'

export async function pickOption(trigger: HTMLElement, name: string | RegExp): Promise<void> {
  fireEvent.click(trigger)
  fireEvent.click(await screen.findByRole('option', { name }))
}
