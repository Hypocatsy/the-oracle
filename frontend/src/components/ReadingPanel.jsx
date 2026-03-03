import { useEffect, useRef, useState, useCallback } from 'react'
import { createPortal } from 'react-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { X, Loader2, ChevronUp, ChevronDown } from 'lucide-react'
import '../styles/ReadingPanel.css'

function findParagraphInText(text, para) {
  // Try exact match first
  let idx = text.indexOf(para)
  if (idx !== -1) return { idx, len: para.length }
  // Try progressively shorter from end
  let shortened = para
  while (shortened.length > 60) {
    shortened = shortened.slice(0, Math.floor(shortened.length * 0.75)).trimEnd()
    idx = text.indexOf(shortened)
    if (idx !== -1) return { idx, len: shortened.length }
  }
  return null
}

function findAllRegions(text, chunk) {
  // Split chunk into lines; group consecutive short lines together
  // so ingredient lists get highlighted as one block
  const lines = chunk.split('\n').map((l) => l.trim()).filter(Boolean)
  const groups = []
  let currentGroup = []

  for (const line of lines) {
    if (line.length >= 30) {
      // Flush any accumulated short lines as a group
      if (currentGroup.length > 0) {
        groups.push(currentGroup.join('\n'))
        currentGroup = []
      }
      groups.push(line)
    } else {
      currentGroup.push(line)
    }
  }
  if (currentGroup.length > 0) {
    groups.push(currentGroup.join('\n'))
  }

  const regions = []
  for (const group of groups) {
    const match = findParagraphInText(text, group)
    if (match) regions.push(match)
  }
  // If grouping found nothing, try the whole chunk with shortening
  if (regions.length === 0) {
    const match = findParagraphInText(text, chunk)
    if (match) regions.push(match)
  }
  return regions
}

function highlightExcerpts(text, excerpts) {
  if (!text) return text
  if (!excerpts) return text
  // Normalize: accept string or array
  const chunks = Array.isArray(excerpts) ? excerpts : [excerpts]
  if (chunks.length === 0) return text

  // Find all match regions from all chunks, tagging each with its chunk index
  const regions = []
  for (let ci = 0; ci < chunks.length; ci++) {
    const chunk = chunks[ci]
    if (!chunk) continue
    const clean = chunk.replace(/…$/, '').trimEnd()
    const matches = findAllRegions(text, clean)
    for (const m of matches) {
      regions.push({ ...m, chunk: ci })
    }
  }

  if (regions.length === 0) return text

  // Sort by position and merge overlapping regions (keep earliest chunk index)
  regions.sort((a, b) => a.idx - b.idx)
  const merged = [regions[0]]
  for (let i = 1; i < regions.length; i++) {
    const prev = merged[merged.length - 1]
    const curr = regions[i]
    if (curr.idx <= prev.idx + prev.len) {
      prev.len = Math.max(prev.len, curr.idx + curr.len - prev.idx)
    } else {
      merged.push(curr)
    }
  }

  // Build JSX with highlights, tagging each mark with its chunk index
  const parts = []
  let pos = 0
  for (const { idx, len, chunk } of merged) {
    if (idx > pos) parts.push(text.slice(pos, idx))
    parts.push(
      <mark key={idx} data-chunk={chunk}>
        {text.slice(idx, idx + len)}
      </mark>
    )
    pos = idx + len
  }
  if (pos < text.length) parts.push(text.slice(pos))
  return <>{parts}</>
}

export default function ReadingPanel({ panel, onClose }) {
  const bodyRef = useRef(null)
  const [currentChunk, setCurrentChunk] = useState(0)
  const [chunkIds, setChunkIds] = useState([])

  // Get distinct chunk indices in document order (by first appearance)
  const getChunkIds = useCallback(() => {
    if (!bodyRef.current) return []
    const marks = Array.from(bodyRef.current.querySelectorAll('mark[data-chunk]'))
    const seen = new Set()
    const ids = []
    for (const m of marks) {
      const id = m.dataset.chunk
      if (!seen.has(id)) {
        seen.add(id)
        ids.push(id)
      }
    }
    return ids
  }, [])

  const scrollToChunk = useCallback((index) => {
    if (chunkIds.length === 0) return
    const clamped = Math.max(0, Math.min(index, chunkIds.length - 1))
    setCurrentChunk(clamped)
    const target = bodyRef.current?.querySelector(`mark[data-chunk="${chunkIds[clamped]}"]`)
    if (target) target.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }, [chunkIds])

  const goNext = useCallback(() => {
    scrollToChunk(currentChunk + 1)
  }, [currentChunk, scrollToChunk])

  const goPrev = useCallback(() => {
    scrollToChunk(currentChunk - 1)
  }, [currentChunk, scrollToChunk])

  // Auto-scroll to first chunk and count distinct chunks
  useEffect(() => {
    if (!panel || panel.loading) return
    const timer = setTimeout(() => {
      const ids = getChunkIds()
      setChunkIds(ids)
      setCurrentChunk(0)
      if (ids.length > 0) {
        const first = bodyRef.current?.querySelector(`mark[data-chunk="${ids[0]}"]`)
        if (first) first.scrollIntoView({ behavior: 'smooth', block: 'center' })
      }
    }, 100)
    return () => clearTimeout(timer)
  }, [panel, getChunkIds])

  // Close on Escape, navigate on arrow keys
  useEffect(() => {
    if (!panel) return
    function handleKey(e) {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [panel, onClose])

  return createPortal(
    <AnimatePresence>
      {panel && (
        <>
          <motion.div
            className="reading-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={onClose}
          />
          <motion.div
            className="reading-panel"
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', damping: 30, stiffness: 300 }}
          >
            <div className="reading-header">
              <div className="reading-header-text">
                <div className="reading-book-title">{panel.bookTitle}</div>
                <div className="reading-chapter-title">{panel.chapterTitle}</div>
              </div>
              <button className="reading-close-btn" onClick={onClose} title="Close">
                <X size={20} />
              </button>
            </div>
            {panel.loading ? (
              <div className="reading-loading">
                <Loader2 size={20} />
                Loading chapter...
              </div>
            ) : (
              <>
                {chunkIds.length > 1 && (
                  <div className="reading-nav">
                    <button
                      className="reading-nav-btn"
                      onClick={goPrev}
                      disabled={currentChunk === 0}
                      title="Previous chunk"
                    >
                      <ChevronUp size={16} />
                    </button>
                    <span className="reading-nav-counter">
                      {currentChunk + 1} / {chunkIds.length}
                    </span>
                    <button
                      className="reading-nav-btn"
                      onClick={goNext}
                      disabled={currentChunk === chunkIds.length - 1}
                      title="Next chunk"
                    >
                      <ChevronDown size={16} />
                    </button>
                  </div>
                )}
                <div className="reading-body" ref={bodyRef}>
                  {highlightExcerpts(panel.chapterText || '', panel.highlightExcerpt)}
                </div>
              </>
            )}
          </motion.div>
        </>
      )}
    </AnimatePresence>,
    document.body
  )
}
