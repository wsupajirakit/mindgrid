// Paraglide compiler options shared by vite.config.ts and scripts/gen-i18n.ts.
export const paraglideOptions = {
  project: './project.inlang',
  outdir: './src/paraglide',
  strategy: ['localStorage', 'preferredLanguage', 'baseLocale'],
  localStorageKey: 'mindgrid.locale',
  emitTsDeclarations: true,
} as const
