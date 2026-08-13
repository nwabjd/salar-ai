import { readFileSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'
import postcss from 'postcss'

const __dirname = dirname(fileURLToPath(import.meta.url))
const srcPath = resolve(__dirname, '../../../../Downloads/salaar-consumer-landing-page/salaar-consumer/src/app/globals.css')
const outPath = resolve(__dirname, '../src/landing.css')
const SCOPE = '#salar-landing'

const css = readFileSync(srcPath, 'utf8')
const root = postcss.parse(css)

function splitTopLevel(input, sep) {
  const parts = []
  let depth = 0
  let current = ''
  let quote = null
  for (let i = 0; i < input.length; i++) {
    const ch = input[i]
    if (quote) {
      current += ch
      if (ch === quote && input[i - 1] !== '\\') quote = null
      continue
    }
    if (ch === '"' || ch === "'") { quote = ch; current += ch; continue }
    if (ch === '(' || ch === '[') depth++
    else if (ch === ')' || ch === ']') depth--
    if (ch === sep && depth === 0) { parts.push(current); current = ''; continue }
    current += ch
  }
  if (current) parts.push(current)
  return parts
}

function scopeSelector(selector) {
  return splitTopLevel(selector, ',').map((raw) => {
    const s = raw.trim()
    if (!s) return s
    if (s === ':root') return SCOPE
    if (/^(html|body)([\s:.#\[>*]|$)/.test(s)) return s.replace(/^(html|body)/, SCOPE)
    return `${SCOPE} ${s}`
  }).join(', ')
}

const keyframeMap = {}
root.walkAtRules(/^keyframes$/i, (atRule) => {
  const oldName = atRule.params.trim()
  const newName = `sl-${oldName}`
  keyframeMap[oldName] = newName
  atRule.params = newName
})

root.walkDecls((decl) => {
  if (decl.prop !== 'animation' && decl.prop !== 'animation-name') return
  decl.value = decl.value.split(/\s+/).map((token) => keyframeMap[token] || token).join(' ')
})

root.walkRules((rule) => {
  if (rule.parent && rule.parent.type === 'atrule' && /^keyframes$/i.test(rule.parent.name)) return
  if (!rule.selector) return
  rule.selector = scopeSelector(rule.selector)
})

const override = `\n/* ---- integration overrides ---- */\n${SCOPE} {\n  position: fixed;\n  inset: 0;\n  overflow-y: auto;\n  overflow-x: hidden;\n  -webkit-overflow-scrolling: touch;\n}\n${SCOPE} .site-shell { min-height: 100%; }\n${SCOPE} .enter-app-button {\n  height: 43px;\n  padding: 0 18px;\n  border: 1px solid rgba(71, 51, 128, 0.18);\n  border-radius: 14px;\n  font-size: 13px;\n  font-weight: 700;\n  color: #5e596d;\n  background: rgba(255, 255, 255, 0.7);\n  cursor: pointer;\n  transition: color .2s ease, border-color .2s ease, transform .2s ease;\n}\n${SCOPE} .enter-app-button:hover { border-color: rgba(112, 81, 222, 0.4); color: var(--violet); transform: translateY(-1px); }\n`

const header = `/* Auto-generated from salaar-consumer/src/app/globals.css via scripts/scope-landing-css.mjs.\n   All rules are scoped under #salar-landing so they cannot clash with the SALAR app shell. */\n`
writeFileSync(outPath, header + root.toString() + override, 'utf8')
console.log(`wrote ${outPath}`)
