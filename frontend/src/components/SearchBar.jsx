import { useState } from 'react'
import { Search, BookOpen } from 'lucide-react'
import catPawWand from '../assets/cats/catpawwand.PNG'
import '../styles/SearchBar.css'

export default function SearchBar({ onSearch, loading, books = [], allTopics = [] }) {
  const [query, setQuery] = useState('')
  const [selectedBookId, setSelectedBookId] = useState('')
  const [selectedTopic, setSelectedTopic] = useState('')

  const filteredBooks = selectedTopic
    ? books.filter(b => b.topic === selectedTopic)
    : books

  const handleSubmit = (e) => {
    e.preventDefault()
    if (query.trim() && !loading) {
      onSearch(query, selectedBookId || null, selectedTopic || null)
    }
  }

  return (
    <div className="search-bar-container">
      {allTopics.length > 0 && (
        <div className="topic-chips">
          <button
            className={`topic-chip ${selectedTopic === '' ? 'topic-chip-active' : ''}`}
            type="button"
            onClick={() => { setSelectedTopic(''); setSelectedBookId('') }}
          >
            All
          </button>
          {allTopics.map(topic => (
            <button
              key={topic}
              className={`topic-chip ${selectedTopic === topic ? 'topic-chip-active' : ''}`}
              type="button"
              onClick={() => { setSelectedTopic(topic); setSelectedBookId('') }}
            >
              {topic}
            </button>
          ))}
        </div>
      )}
      <form className="search-form" onSubmit={handleSubmit}>
        <div className="search-input-wrapper">
          <Search className="search-icon" size={16} />
          <div className="book-filter-wrapper">
            <BookOpen className="book-filter-icon" size={14} />
            <select
              className="book-filter-select"
              value={selectedBookId}
              onChange={(e) => setSelectedBookId(e.target.value)}
            >
              <option value="">All Books</option>
              {filteredBooks.map((book) => (
                <option key={book.id} value={book.id}>{book.title}</option>
              ))}
            </select>
          </div>
          <input
            className="search-input"
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ask the oracle anything..."
          />
        </div>
        <div className="divine-button-wrapper">
          <button
            className="divine-button"
            type="submit"
            disabled={loading || !query.trim()}
          >
            {loading ? '...' : 'Divine'}
          </button>
          <img src={catPawWand} alt="" className="divine-cat-paw" loading="lazy" />
        </div>
      </form>
    </div>
  )
}
