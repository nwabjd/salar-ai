import { Children, Fragment, useMemo, type ReactNode } from 'react'

type Token =
  | { t: 'text'; v: string }
  | { t: 'inline'; v: ReactNode }
  | { t: 'code'; lang: string; v: string }

function escapeHtml(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function inlineToReact(s: string, keyBase: string): ReactNode[] {
  const out: ReactNode[] = []
  const re = /(`[^`]+`)|(\*\*[^*]+\*\*)|(_[^_]+_)|(\[[^\]]+\]\([^)]+\))/g
  let last = 0
  let m: RegExpExecArray | null
  let i = 0
  while ((m = re.exec(s)) !== null) {
    if (m.index > last) out.push(s.slice(last, m.index))
    if (m[1]) {
      out.push(
        <code key={`${keyBase}-c${i++}`}>
          {m[1].slice(1, -1)}
        </code>,
      )
    } else if (m[2]) {
      out.push(<strong key={`${keyBase}-b${i++}`}>{m[2].slice(2, -2)}</strong>)
    } else if (m[3]) {
      out.push(<em key={`${keyBase}-i${i++}`}>{m[3].slice(1, -1)}</em>)
    } else if (m[4]) {
      const inner = m[4]
      const brk = inner.indexOf('](')
      const label = inner.slice(1, brk)
      const href = inner.slice(brk + 2, -1)
      out.push(
        <a key={`${keyBase}-a${i++}`} href={href} target="_blank" rel="noreferrer">
          {inlineToReact(label, `${keyBase}-al${i}`)}
        </a>,
      )
    }
    last = m.index + m[0].length
  }
  if (last < s.length) out.push(s.slice(last))
  return out
}

/** Strip inline markers for table cells / heading text extraction. */
function inlineText(s: string): string {
  return s.replace(/`([^`]+)`/g, '$1').replace(/\*\*([^*]+)\*\*/g, '$1').replace(/_([^_]+)_/g, '$1')
}

function buildToken(src: string): Token[] {
  const tokens: Token[] = []
  const split = src.split(/```/g)
  for (let i = 0; i < split.length; i++) {
    const part = split[i]
    if (i % 2 === 1) {
      const nl = part.indexOf('\n')
      const lang = nl === -1 ? part : part.slice(0, nl)
      const body = nl === -1 ? '' : part.slice(nl + 1)
      tokens.push({ t: 'code', lang: lang.trim(), v: body.trimEnd() })
    } else if (part) {
      tokens.push({ t: 'inline', v: part })
    }
  }
  return tokens
}

function renderTableCell(cell: string, key: string): ReactNode {
  return <>{inlineToReact(escapeHtml(cell.trim()).replace(/\s+/g, ' '), key)}</>
}

function renderTableBlock(lines: string[], key: string): ReactNode {
  const parseRow = (line: string): string[] => {
    const s = line.trim()
    const inner = s.replace(/^\|/, '').replace(/\|$/, '')
    return inner.split('|')
  }
  const rows = lines.slice(1).map(parseRow)
  const headerCells = parseRow(lines[0])
  const alignRow = rows.length && rows[0].every((c) => /^:?-{1,}:?$/.test(c.trim())) ? rows.shift()! : null
  void alignRow
  return (
    <div className="ws-table-wrap" key={key}>
      <table>
        <thead>
          <tr>
            {headerCells.map((c, i) => (
              <th key={`${key}-h${i}`}>{renderTableCell(c, `${key}-hc${i}`)}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, ri) => (
            <tr key={`${key}-r${ri}`}>
              {row.map((c, ci) => (
                <td key={`${key}-c${ci}`}>{renderTableCell(c, `${key}-rc${ri}-${ci}`)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function renderInlineMarkdown(block: Token[], key: string): ReactNode[] {
  const out: ReactNode[] = []
  block.forEach((tok, i) => {
    if (tok.t !== 'inline') return
    const text = tok.v as string
    const lines = text.split('\n')

    // Detect tables: first content line starts with | and second line is alignment.
    let li = 0
    while (li < lines.length) {
      const line = lines[li]
      const trimmed = line.trim()
      const looksLikeTable =
        trimmed.startsWith('|') &&
        li + 1 < lines.length &&
        /^\|?\s*:?-{2,}\s*(\|\s*:?-{2,}\s*)*\|?$/.test(lines[li + 1].trim())

      if (looksLikeTable) {
        const blockLines: string[] = [trimmed]
        let j = li + 1
        while (j < lines.length && lines[j].trim().startsWith('|')) {
          blockLines.push(lines[j].trim())
          j++
        }
        out.push(renderTableBlock(blockLines, `${key}-t${out.length}`))
        li = j
        continue
      }

      // Inline markdown within the line, fall back to inlineToReact
      if (trimmed) {
        const nodes = inlineToReact(escapeHtml(trimmed), `${key}-l${li}`)
        out.push(
          <p key={`${key}-p${li}`}>
            {nodes.map((n, ni) => (
              <Fragment key={`${key}-f${li}-${ni}`}>{n}</Fragment>
            ))}
            {'\n'}
          </p>,
        )
      }
      li++
    }
  })
  return out
}

export function RichBlock({ base, text }: { base: string; text: string }) {
  const nodes = useMemo(() => {
    const rawTokens = buildToken(text)
    const out: ReactNode[] = []
    rawTokens.forEach((tok, i) => {
      if (tok.t === 'code') {
        out.push(
          <pre key={`${base}-code${i}`}>
            <code className={tok.lang ? `language-${escapeHtml(tok.lang)}` : ''}>
              {tok.v}
            </code>
          </pre>,
        )
      } else {
        const rendered = renderInlineMarkdown([tok], `${base}-md${i}`)
        out.push(
          <Fragment key={`${base}-r${i}`}>
            {rendered.map((r, ri) => (
              <Fragment key={`${base}-rr${i}-${ri}`}>{r}</Fragment>
            ))}
          </Fragment>,
        )
      }
    })
    return out
  }, [base, text])

  return <div className="ws-rich">{nodes}</div>
}

export function inlineTextForTitle(text: string): string {
  return text.slice(0, 60).replace(/\s+/g, ' ').trim() || 'Conversation'
}