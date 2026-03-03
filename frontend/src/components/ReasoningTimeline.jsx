import { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Search, BookOpen, Type, ChevronDown } from 'lucide-react'
import '../styles/ReasoningTimeline.css'

const TOOL_ICONS = {
  search_book: Search,
  get_chapter: BookOpen,
  search_by_keyword: Type,
  list_books: BookOpen,
  get_surrounding_context: BookOpen,
}

const TOOL_LABELS = {
  search_book: 'Searching books',
  get_chapter: 'Reading chapter',
  search_by_keyword: 'Keyword search',
  list_books: 'Listing books',
  get_surrounding_context: 'Getting context',
}

function formatToolCall(event) {
  const label = TOOL_LABELS[event.tool] || event.tool
  const query = event.args?.query || event.args?.keyword || event.args?.chapter_title || ''
  return query ? `${label}: "${query}"` : label
}

function StepItem({ event }) {
  if (event.type === 'thought') {
    return (
      <div className="rt-step rt-thought">
        <span className="rt-icon">💭</span>
        <span className="rt-text">{event.content}</span>
      </div>
    )
  }

  if (event.type === 'tool_call') {
    const Icon = TOOL_ICONS[event.tool] || Search
    return (
      <div className="rt-step rt-tool-call">
        <span className="rt-icon"><Icon size={14} /></span>
        <span className="rt-text">{formatToolCall(event)}</span>
      </div>
    )
  }

  if (event.type === 'tool_result') {
    return (
      <div className="rt-step rt-tool-result">
        <span className="rt-icon">✓</span>
        <span className="rt-text">{event.summary}</span>
      </div>
    )
  }

  return null
}

export default function ReasoningTimeline({ steps = [], loading = false }) {
  const [collapsed, setCollapsed] = useState(false)
  const scrollRef = useRef(null)

  // Auto-expand while loading, allow collapse after
  useEffect(() => {
    if (loading) setCollapsed(false)
  }, [loading])

  // Auto-scroll to bottom as new steps arrive
  useEffect(() => {
    if (scrollRef.current && !collapsed) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [steps.length, collapsed])

  if (steps.length === 0 && !loading) return null

  const stepCount = new Set(
    steps.map(s => s.step).filter(s => s != null)
  ).size || steps.length
  const toggleLabel = loading
    ? 'Thinking...'
    : `${stepCount} reasoning step${stepCount !== 1 ? 's' : ''}`

  return (
    <div className="rt-container">
      <button
        className="rt-toggle"
        onClick={() => !loading && setCollapsed(c => !c)}
        disabled={loading}
      >
        <ChevronDown
          size={14}
          className={`rt-chevron ${collapsed ? 'rt-chevron-collapsed' : ''}`}
        />
        <span>{toggleLabel}</span>
        {loading && <span className="rt-spinner" />}
      </button>

      <AnimatePresence>
        {!collapsed && (
          <motion.div
            className="rt-steps"
            ref={scrollRef}
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
          >
            {steps.map((event, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.15, delay: 0.03 }}
              >
                <StepItem event={event} />
              </motion.div>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
