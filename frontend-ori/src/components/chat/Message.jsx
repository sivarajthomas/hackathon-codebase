import { motion } from 'framer-motion'

// Render inline emphasis: **bold**, `code`. Returns an array of React nodes.
function renderInline(text) {
  const nodes = []
  const re = /(\*\*(.+?)\*\*|`(.+?)`)/g
  let last = 0
  let m
  let key = 0
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) nodes.push(text.slice(last, m.index))
    if (m[2] !== undefined) {
      nodes.push(<strong key={key++} className="font-semibold">{m[2]}</strong>)
    } else if (m[3] !== undefined) {
      nodes.push(
        <code key={key++} className="rounded bg-black/5 px-1 py-0.5 text-[0.85em]">
          {m[3]}
        </code>,
      )
    }
    last = m.index + m[0].length
  }
  if (last < text.length) nodes.push(text.slice(last))
  return nodes
}

// Minimal, dependency-free Markdown-lite renderer for chat replies:
// headings (#, ##, ###), bullet lists (-, *, •), and paragraphs with **bold**.
function renderMarkdown(text) {
  const lines = (text || '').replace(/\r\n/g, '\n').split('\n')
  const blocks = []
  let list = null
  let para = []
  let key = 0

  const flushPara = () => {
    if (para.length) {
      blocks.push(
        <p key={key++} className="mb-2 last:mb-0">
          {renderInline(para.join(' '))}
        </p>,
      )
      para = []
    }
  }
  const flushList = () => {
    if (list) {
      blocks.push(
        <ul key={key++} className="mb-2 ml-4 list-disc space-y-1 last:mb-0">
          {list.map((item, i) => (
            <li key={i}>{renderInline(item)}</li>
          ))}
        </ul>,
      )
      list = null
    }
  }

  for (const raw of lines) {
    const line = raw.trimEnd()
    if (!line.trim()) {
      flushPara()
      flushList()
      continue
    }
    const heading = line.match(/^(#{1,3})\s+(.*)$/)
    const bullet = line.match(/^\s*(?:[-*•])\s+(.*)$/)
    if (heading) {
      flushPara()
      flushList()
      blocks.push(
        <p key={key++} className="mb-1 mt-1 font-semibold first:mt-0">
          {renderInline(heading[2])}
        </p>,
      )
    } else if (bullet) {
      flushPara()
      if (!list) list = []
      list.push(bullet[1])
    } else {
      flushList()
      para.push(line.trim())
    }
  }
  flushPara()
  flushList()
  return blocks
}

// A single chat bubble with a smooth spring entrance. `role` is 'user' | 'ai'.
export default function Message({ role, text, accent }) {
  const isUser = role === 'user'

  return (
    <motion.div
      initial={{ opacity: 0, y: 16, scale: 0.96 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ type: 'spring', stiffness: 320, damping: 26 }}
      className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}
    >
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
          isUser
            ? 'rounded-br-sm bg-brand-brownDeep text-white'
            : 'rounded-bl-sm border border-brand-brown/10 bg-white text-brand-brownDeep shadow-sm'
        }`}
        style={
          !isUser
            ? { boxShadow: `0 6px 24px -16px ${accent}`, borderColor: `${accent}33` }
            : undefined
        }
      >
        {isUser ? text : renderMarkdown(text)}
      </div>
    </motion.div>
  )
}

