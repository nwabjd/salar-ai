import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const apiSource = readFileSync(new URL('../src/api.ts', import.meta.url), 'utf8')

test('mobile chat stream delegates terminal SSE events to the shared dispatcher', () => {
  assert.match(apiSource, /handleChatStreamEvent/)
  assert.match(apiSource, /if \(terminal\) return/)
})
