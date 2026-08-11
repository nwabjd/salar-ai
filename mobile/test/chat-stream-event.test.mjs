import assert from 'node:assert/strict'
import test from 'node:test'

import { handleChatStreamEvent } from '../src/chat-stream-event.ts'

test('error event reports detail, closes, and is terminal', () => {
  const errors = []
  let closes = 0

  const terminal = handleChatStreamEvent(
    { type: 'error', detail: 'Sanitized failure', error: 'compatibility fallback' },
    {
      onToken: () => assert.fail('unexpected token'),
      onDone: () => assert.fail('unexpected done'),
      onError: error => errors.push(error),
      close: () => { closes += 1 },
    },
  )

  assert.equal(terminal, true)
  assert.deepEqual(errors, ['Sanitized failure'])
  assert.equal(closes, 1)
})

test('error event falls back to compatibility error text', () => {
  const errors = []

  handleChatStreamEvent(
    { type: 'error', error: 'Older backend failure' },
    {
      onToken: () => undefined,
      onDone: () => undefined,
      onError: error => errors.push(error),
      close: () => undefined,
    },
  )

  assert.deepEqual(errors, ['Older backend failure'])
})
