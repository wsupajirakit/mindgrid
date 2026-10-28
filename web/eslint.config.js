// Lint rules that keep web/ small, safe and layered. `npm run verify` fails on any error here.
//
// Layout (bulletproof-react): shared folders -> features -> app. Imports flow one way only:
//   shared   components hooks i18n services stores styles utils config testing
//   features features/<name>: may import shared code and itself, never another feature
//   app      app pages layouts: compose features and shared code
import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import stylistic from '@stylistic/eslint-plugin'
import tseslint from 'typescript-eslint'

const SHARED = ['components', 'hooks', 'i18n', 'services', 'stores', 'utils', 'config']
const APP = ['app', 'pages', 'layouts']

// Every UI text comes from messages/{en,th,it}.json. Text written into JSX or into a
// visible attribute would show in one language only, so it fails the build. Data from the API
// is rendered through expressions ({value}), which these selectors do not match.
const uiTextRules = [
  {
    selector: 'JSXText[value=/[A-Za-z\\u0E00-\\u0E7F]/]',
    message: 'UI text goes in messages/*.json (use m.key()), never in JSX.',
  },
  {
    selector: "JSXAttribute[name.name=/^(placeholder|title|alt|aria-label|label)$/] > Literal"
      + '[value=/[A-Za-z\\u0E00-\\u0E7F]/]',
    message: 'Visible attribute text goes in messages/*.json (use m.key()).',
  },
]
const htmlRules = [
  {
    selector: "JSXAttribute[name.name='dangerouslySetInnerHTML']",
    message: 'Render React elements, never HTML strings.',
  },
  {
    selector: "AssignmentExpression[left.property.name=/^(innerHTML|outerHTML)$/]",
    message: 'Never assign HTML strings to the DOM.',
  },
]
const browserImports = [
  { name: 'zod', message: "Use 'zod/mini' in browser code (full zod costs ~22 KB gzip)." },
  { name: 'markdown-to-jsx', message: 'Use MarkdownText from src/components/MarkdownText.tsx.' },
]
const folderImport = (names) => `(^|/)(${names.join('|')})/`

/** no-restricted-imports with the browser rules plus extra path patterns (flat config replaces
 * a rule's options per matching block, so every block carries the full list). */
const restrictedImports = (patterns = [], paths = browserImports) => ['error', { paths, patterns }]
const MARKDOWN_WRAPPER = 'src/components/MarkdownText.tsx'
const sharedOnly = [{
  regex: folderImport(['features', ...APP]),
  message: 'Shared code must not import features or the app layer (one-way imports).',
}]

export default tseslint.config(
  { ignores: [
    'dist', 'node_modules', 'src/paraglide', 'src/app/routeTree.gen.ts',
    'src/services/api/openapi.gen.ts',
  ] },
  {
    files: ['**/*.{ts,tsx,js}'],
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    languageOptions: { ecmaVersion: 2023, globals: { ...globals.browser, ...globals.node } },
    plugins: { 'react-hooks': reactHooks, '@stylistic': stylistic },
    rules: {
      ...reactHooks.configs.recommended.rules,
      '@stylistic/max-len': ['error', {
        code: 100, tabWidth: 2, ignoreUrls: false, ignoreStrings: false,
        ignoreTemplateLiterals: false, ignoreRegExpLiterals: false, ignoreComments: false,
      }],
      'max-lines': ['error', { max: 300, skipBlankLines: true, skipComments: true }],
      'max-lines-per-function': ['error', { max: 80, skipBlankLines: true, skipComments: true }],
      '@typescript-eslint/no-explicit-any': 'error',
      'no-restricted-syntax': ['error', ...htmlRules, ...uiTextRules],
    },
  },
  {
    files: ['src/**/*.{ts,tsx}'],
    ignores: [MARKDOWN_WRAPPER],
    rules: { 'no-restricted-imports': restrictedImports() },
  },
  {
    // The API prefix lives only in src/services/api (base comes from config).
    files: ['src/**/*.{ts,tsx}'],
    // Mocks stand in for the server: their payloads (paths, brand colours) are data.
    ignores: ['src/services/api/**', 'src/testing/**'],
    rules: {
      'no-restricted-syntax': ['error',
        {
          // Import/re-export specifiers such as '../services/api/client.ts' are fine.
          selector: 'Literal[value=/\\/v1\\//]:not(ImportDeclaration > Literal)'
            + ':not(ExportNamedDeclaration > Literal):not(ExportAllDeclaration > Literal)',
          message: 'API paths belong in src/services/api.',
        },
        {
          selector: "TemplateElement[value.raw=/\\/v1\\//]",
          message: 'API paths belong in src/services/api.',
        },
        {
          selector: "Literal[value=/#[0-9a-fA-F]{3,8}\\b|rgba?\\(/]",
          message: 'Colors come from theme tokens (CSS variables).',
        },
        ...htmlRules,
        ...uiTextRules,
      ],
    },
  },
  {
    // Shared code never depends on features or on the app layer.
    files: SHARED.map((dir) => `src/${dir}/**/*.{ts,tsx}`),
    ignores: [MARKDOWN_WRAPPER],
    rules: { 'no-restricted-imports': restrictedImports(sharedOnly) },
  },
  {
    // The one place allowed to import markdown-to-jsx (raw HTML parsing disabled there).
    files: [MARKDOWN_WRAPPER],
    rules: { 'no-restricted-imports': restrictedImports(sharedOnly, browserImports.slice(0, 1)) },
  },
  ...['features/*/*.{ts,tsx}', 'features/*/components/**/*.{ts,tsx}'].map((glob, depth) => ({
    // A feature imports itself and shared code only: never another feature, never the app layer.
    files: [`src/${glob}`],
    rules: {
      'no-restricted-imports': restrictedImports([
        {
          regex: depth === 0 ? '^\\.\\./(?!\\.\\./)' : '^\\.\\./\\.\\./(?!\\.\\./)',
          message: 'Features must not import each other; move shared code to a shared folder.',
        },
        { regex: folderImport(APP), message: 'Features must not import the app layer.' },
      ]),
    },
  })),
)
