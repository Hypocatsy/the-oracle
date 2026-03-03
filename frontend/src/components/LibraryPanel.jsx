import { useState } from 'react'
import { motion, useReducedMotion } from 'framer-motion'
import { useDropzone } from 'react-dropzone'
import { Plus, ChevronDown, ChevronUp } from 'lucide-react'
import BookItem from './BookItem'
import SavedTab from './SavedTab'
import bookCat from '../assets/cats/bookcat.PNG'
import '../styles/LibraryPanel.css'

function BookCatDecor() {
  const prefersReduced = useReducedMotion()
  return (
    <motion.img
      src={bookCat}
      alt=""
      className="library-bookcat"
      loading="lazy"
      animate={prefersReduced ? {} : { y: [0, -5, 0] }}
      transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
    />
  )
}

function GroupedBookList({ books, onDelete, onChapterClick, allTopics, onUpdateTopic, collapsedTopics, toggleTopic }) {
  // Group books by topic
  const groups = {}
  for (const book of books) {
    const topic = book.topic || 'Uncategorized'
    if (!groups[topic]) groups[topic] = []
    groups[topic].push(book)
  }

  // Sort topics: named topics alphabetically, Uncategorized last
  const sortedTopics = Object.keys(groups).sort((a, b) => {
    if (a === 'Uncategorized') return 1
    if (b === 'Uncategorized') return -1
    return a.localeCompare(b)
  })

  // Flat index counter for BookItem color cycling
  let flatIndex = 0

  return sortedTopics.map(topic => {
    const collapsed = collapsedTopics.has(topic)
    const topicBooks = groups[topic]
    const startIndex = flatIndex
    flatIndex += topicBooks.length

    return (
      <div key={topic} className="topic-section">
        <button className="topic-section-header" onClick={() => toggleTopic(topic)}>
          <span className={`topic-section-chevron ${collapsed ? '' : 'topic-section-chevron-open'}`}>▸</span>
          <span className="topic-section-name">{topic}</span>
          <span className="topic-section-count">({topicBooks.length})</span>
        </button>
        {!collapsed && (
          <div className="topic-section-books">
            {topicBooks.map((book, i) => (
              <BookItem
                key={book.id}
                book={book}
                index={startIndex + i}
                onDelete={onDelete}
                onChapterClick={onChapterClick}
                allTopics={allTopics}
                onUpdateTopic={onUpdateTopic}
              />
            ))}
          </div>
        )}
      </div>
    )
  })
}

function LibraryContent({ books, uploading, onDelete, onChapterClick, getRootProps, getInputProps, allTopics, onUpdateTopic }) {
  const [collapsedTopics, setCollapsedTopics] = useState(new Set())

  const toggleTopic = (topic) => {
    setCollapsedTopics(prev => {
      const next = new Set(prev)
      if (next.has(topic)) next.delete(topic)
      else next.add(topic)
      return next
    })
  }

  return (
    <>
      <div className="library-header-row">
        <h2 className="library-heading">
          <span>📖</span> Your Library
        </h2>
        <div {...getRootProps()} className="add-book-btn-wrapper">
          <input {...getInputProps()} />
          <button className="add-book-btn" disabled={uploading}>
            <Plus size={14} />
            {uploading ? 'Adding...' : 'Add Book'}
          </button>
        </div>
      </div>
      <div className="book-list">
        <GroupedBookList
          books={books}
          onDelete={onDelete}
          onChapterClick={onChapterClick}
          allTopics={allTopics}
          onUpdateTopic={onUpdateTopic}
          collapsedTopics={collapsedTopics}
          toggleTopic={toggleTopic}
        />
      </div>
      {books.length > 0 && (
        <p className="library-stats">
          {books.length} book{books.length !== 1 ? 's' : ''}
        </p>
      )}
    </>
  )
}

function SidebarTabs({ activeTab, onTabChange }) {
  return (
    <div className="sidebar-tabs">
      <button
        className={`sidebar-tab ${activeTab === 'library' ? 'sidebar-tab-active' : ''}`}
        onClick={() => onTabChange('library')}
      >
        Library
      </button>
      <button
        className={`sidebar-tab ${activeTab === 'saved' ? 'sidebar-tab-active' : ''}`}
        onClick={() => onTabChange('saved')}
      >
        Saved
      </button>
    </div>
  )
}

export default function LibraryPanel({
  books, totalChunks, uploading, onUpload, onDelete, onChapterClick,
  savedQueries, onSelectSaved, onRemoveSaved, onClearSaved,
  allTopics, onUpdateTopic,
}) {
  const [mobileOpen, setMobileOpen] = useState(false)
  const [activeTab, setActiveTab] = useState('library')

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: (files) => files[0] && onUpload(files[0]),
    accept: { 'application/epub+zip': ['.epub'] },
    multiple: false,
    disabled: uploading,
  })

  const sharedProps = { books, uploading, onDelete, onChapterClick, getRootProps, getInputProps, isDragActive, allTopics, onUpdateTopic }

  const tabContent = activeTab === 'library' ? (
    <LibraryContent {...sharedProps} />
  ) : (
    <SavedTab
      savedQueries={savedQueries ?? []}
      onSelect={onSelectSaved}
      onRemove={onRemoveSaved}
      onClearAll={onClearSaved}
    />
  )

  return (
    <>
      {/* Desktop */}
      <aside className="library-desktop">
        <div className="library-card card">
          <BookCatDecor />
          <SidebarTabs activeTab={activeTab} onTabChange={setActiveTab} />
          {tabContent}
        </div>
      </aside>

      {/* Mobile */}
      <div className="library-mobile">
        <button
          className="library-mobile-toggle"
          onClick={() => setMobileOpen(!mobileOpen)}
        >
          <span>📖 Your Library ({books.length} book{books.length !== 1 ? 's' : ''})</span>
          {mobileOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </button>
        {mobileOpen && (
          <div className="library-mobile-content">
            <SidebarTabs activeTab={activeTab} onTabChange={setActiveTab} />
            {tabContent}
          </div>
        )}
      </div>
    </>
  )
}
