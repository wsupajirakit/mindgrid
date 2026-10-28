// Compiles messages/*.json into src/paraglide so `tsc -b` can run before `vite build`.
import { compile } from '@inlang/paraglide-js'
import { paraglideOptions } from '../i18n.config.ts'

await compile({ ...paraglideOptions, strategy: [...paraglideOptions.strategy] })
console.log('gen-i18n: compiled')
