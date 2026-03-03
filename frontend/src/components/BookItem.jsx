import { useState, useRef, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { motion } from 'framer-motion'
import { Trash2, Loader2, ChevronRight } from 'lucide-react'
import axios from 'axios'
import '../styles/BookItem.css'

const BOOK_COLORS = [
  { bg: '#fef6e8', icon: '#d4a574' },
  { bg: '#fdf0e8', icon: '#d4a574' },
  { bg: '#fceeed', icon: '#d4a574' },
  { bg: '#f3eef6', icon: '#d4a574' },
  { bg: '#f8f1e0', icon: '#d4a574' },
]

function getBookColor(index) {
  return BOOK_COLORS[index % BOOK_COLORS.length]
}

export default function BookItem({ book, index, onDelete, onChapterClick, allTopics = [], onUpdateTopic }) {
  const [hovered, setHovered] = useState(false)
  const [showPopover, setShowPopover] = useState(false)
  const [editingTopic, setEditingTopic] = useState(false)
  const [summary, setSummary] = useState(book.summary || null)
  const [chapterCount, setChapterCount] = useState(book.chapter_count || 0)
  const [loadingSummary, setLoadingSummary] = useState(false)
  const [popoverPos, setPopoverPos] = useState(null)
  const [tocOpen, setTocOpen] = useState(false)
  const [chapters, setChapters] = useState(book.chapters || [])
  const [loadingChapters, setLoadingChapters] = useState(false)
  const popoverRef = useRef(null)
  const titleRef = useRef(null)
  const color = getBookColor(index)

  useEffect(() => {
    if (!showPopover) return
    function handleClickOutside(e) {
      if (
        popoverRef.current && !popoverRef.current.contains(e.target) &&
        titleRef.current && !titleRef.current.contains(e.target)
      ) {
        setShowPopover(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [showPopover])

  async function handleTocToggle(e) {
    e.stopPropagation()
    if (book.status !== 'ready') return
    const opening = !tocOpen
    setTocOpen(opening)
    if (opening && chapters.length === 0 && !loadingChapters) {
      setLoadingChapters(true)
      try {
        const res = await axios.get(`/api/books/${book.id}/chapters`)
        setChapters(res.data)
      } catch {
        setChapters([])
      } finally {
        setLoadingChapters(false)
      }
    }
  }

  async function handleTitleClick(e) {
    e.stopPropagation()
    if (showPopover) {
      setShowPopover(false)
      return
    }
    // Calculate position from the title element
    if (titleRef.current) {
      const rect = titleRef.current.getBoundingClientRect()
      setPopoverPos({ top: rect.bottom + 8, left: rect.left })
    }
    setShowPopover(true)

    if (!summary && !loadingSummary) {
      setLoadingSummary(true)
      try {
        const res = await axios.get(`/api/books/${book.id}/summary`)
        setSummary(res.data.summary)
        setChapterCount(res.data.chapter_count)
      } catch {
        setSummary('Summary unavailable.')
      } finally {
        setLoadingSummary(false)
      }
    }
  }

  const popover = showPopover && popoverPos && createPortal(
    <div
      className="book-popover"
      ref={popoverRef}
      style={{ top: popoverPos.top, left: popoverPos.left }}
    >
      <div className="book-popover-arrow" />
      <div className="book-popover-title">{book.title}</div>
      {loadingSummary ? (
        <div className="book-popover-loading">
          <Loader2 size={14} className="book-spinner" /> Generating summary…
        </div>
      ) : (
        <>
          <p className="book-popover-summary">{summary}</p>
          {chapterCount > 0 && (
            <div className="book-popover-stats">
              {chapterCount} chapter{chapterCount !== 1 ? 's' : ''}
            </div>
          )}
        </>
      )}
    </div>,
    document.body
  )

  return (
    <>
      <motion.div
        className="book-item"
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        initial={{ opacity: 0, x: -10 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.3, delay: index * 0.08 }}
      >
        <div
          className={`book-icon ${book.status === 'ready' ? 'book-icon-clickable' : ''}`}
          style={{ backgroundColor: color.bg }}
          onClick={handleTocToggle}
        >
          {book.status === 'ready' ? (
            <ChevronRight size={14} className={`book-toc-chevron ${tocOpen ? 'book-toc-chevron-open' : ''}`} />
          ) : '📖'}
        </div>
        <div className="book-info">
          <div className="book-title" ref={titleRef} onClick={handleTitleClick}>
            {book.title}
          </div>
          {book.status === 'processing' && (
            <div className="book-status processing">
              <Loader2 size={10} className="book-spinner" /> Processing...
            </div>
          )}
          {book.status === 'error' && (
            <div className="book-status error">Error</div>
          )}
          {book.status === 'ready' && !editingTopic && (
            <div
              className="book-topic-badge"
              onClick={(e) => { e.stopPropagation(); setEditingTopic(true) }}
              title="Click to change topic"
            >
              {book.topic || 'Uncategorized'}
            </div>
          )}
          {editingTopic && editingTopic !== 'new' && (
            <div className="book-topic-edit" onClick={(e) => e.stopPropagation()}>
              <select
                autoFocus
                defaultValue={book.topic || ''}
                onChange={(e) => {
                  if (e.target.value === '__new__') {
                    setEditingTopic('new')
                  } else {
                    onUpdateTopic?.(book.id, e.target.value)
                    setEditingTopic(false)
                  }
                }}
                onBlur={() => setEditingTopic(false)}
              >
                <option value="">Uncategorized</option>
                {allTopics.map(t => <option key={t} value={t}>{t}</option>)}
                <option value="__new__">+ New topic...</option>
              </select>
            </div>
          )}
          {editingTopic === 'new' && (
            <div className="book-topic-edit" onClick={(e) => e.stopPropagation()}>
              <input
                autoFocus
                placeholder="New topic name..."
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && e.target.value.trim()) {
                    onUpdateTopic?.(book.id, e.target.value.trim())
                    setEditingTopic(false)
                  } else if (e.key === 'Escape') {
                    setEditingTopic(false)
                  }
                }}
                onBlur={(e) => {
                  if (e.target.value.trim()) {
                    onUpdateTopic?.(book.id, e.target.value.trim())
                  }
                  setEditingTopic(false)
                }}
              />
            </div>
          )}
        </div>
        {hovered && (
          <button className="book-delete" onClick={() => onDelete(book.id)} title="Remove book">
            <Trash2 size={14} />
          </button>
        )}
      </motion.div>
      {popover}
      {tocOpen && (
        <div className="book-chapter-list">
          {loadingChapters ? (
            <div className="book-chapter-loading">
              <Loader2 size={12} className="book-spinner" /> Loading chapters...
            </div>
          ) : chapters.length === 0 ? (
            <div className="book-chapter-loading">No chapters found</div>
          ) : (
            chapters.map((ch) => (
              <div
                key={ch.index}
                className="book-chapter-item"
                onClick={() => onChapterClick && onChapterClick(book.id, book.title, ch.index)}
              >
                {ch.title}
              </div>
            ))
          )}
        </div>
      )}
    </>
  )
}
