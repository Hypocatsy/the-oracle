import { X } from 'lucide-react'
import '../styles/SavedTab.css'

export default function SavedTab({ savedQueries, onSelect, onRemove, onClearAll }) {
  if (savedQueries.length === 0) {
    return (
      <div className="saved-empty">
        <p>Save a query by clicking the star on any answer</p>
      </div>
    )
  }

  return (
    <div className="saved-tab">
      <div className="saved-list">
        {savedQueries.map((entry) => (
          <div key={entry.id} className="saved-item" onClick={() => onSelect(entry)}>
            <div className="saved-item-text">
              <span className="saved-question">
                {entry.question.length > 60
                  ? entry.question.slice(0, 60) + '...'
                  : entry.question}
              </span>
              {entry.bookTitle && (
                <span className="saved-book-tag">{entry.bookTitle}</span>
              )}
            </div>
            <button
              className="saved-remove-btn"
              title="Remove"
              onClick={(e) => {
                e.stopPropagation()
                onRemove(entry.id)
              }}
            >
              <X size={12} />
            </button>
          </div>
        ))}
      </div>
      <button className="saved-clear-btn" onClick={onClearAll}>
        Clear all
      </button>
    </div>
  )
}
