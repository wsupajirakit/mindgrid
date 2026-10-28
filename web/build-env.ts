// Build-time settings. One place, validated by zod, shared by vite.config.ts and scripts/.
import { z } from 'zod'

const basePath = z
  .string()
  .regex(/^\/(?:[a-z0-9-]+\/)*$/, 'must start and end with "/" and contain only a-z 0-9 - segments')

const schema = z.object({
  APP_BASE: basePath.default('/'),
  APP_API_BASE: basePath.default('/v1/'),
})

export type BuildEnv = z.infer<typeof schema>

export function readBuildEnv(source: Record<string, string | undefined> = process.env): BuildEnv {
  const parsed = schema.safeParse({ APP_BASE: source.APP_BASE, APP_API_BASE: source.APP_API_BASE })
  if (!parsed.success) {
    throw new Error(`Invalid build env: ${z.prettifyError(parsed.error)}`)
  }
  return parsed.data
}
