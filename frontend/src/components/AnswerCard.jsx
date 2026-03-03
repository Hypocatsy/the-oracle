import { useState } from 'react'
import { motion, AnimatePresence, useReducedMotion } from 'framer-motion'
import { ChevronRight, BookOpen, Star } from 'lucide-react'
import TarotLoader from './TarotLoader'
import ReasoningTimeline from './ReasoningTimeline'
import catWithBooks from '../assets/cats/catwithbooks1.PNG'
import crystalBallCat from '../assets/cats/crystalballcat.PNG'
import chonkyCat from '../assets/cats/chonkycat.png'
import '../styles/AnswerCard.css'
import '../styles/ReasoningTimeline.css'

const SOURCE_BG = ['#fef6e8', '#fdf0e8', '#fceeed', '#f3eef6', '#f8f1e0']

function getSourceBg(index) {
  return SOURCE_BG[index % SOURCE_BG.length]
}

function formatSource(src) {
  let text = `[${src.book_title}]`
  if (src.section) {
    text += ` · ${src.section}`
    if (src.chapter) text += ` (${src.chapter})`
  } else if (src.chapter) {
    text += ` · ${src.chapter}`
  }
  if (src.page) text += `, Page ${src.page}`
  return text
}

function IdleState({ suggestions, onSuggest }) {
  return (
    <div className="idle-state">
      <img src={catWithBooks} alt="" className="idle-cat-img" loading="lazy" />
      <p className="idle-text">Ask me anything about your books...</p>
      {suggestions.length > 0 && (
        <div className="suggestions-section">
          <p className="suggestions-label">Try asking:</p>
          <div className="suggestions-list">
            {suggestions.map((q, i) => (
              <button
                key={i}
                className="suggestion-pill"
                onClick={() => onSuggest(q)}
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function LoadingState({ reasoningSteps }) {
  if (reasoningSteps && reasoningSteps.length > 0) {
    return (
      <div className="loading-with-reasoning">
        <div className="tarot-side">
          <TarotLoader />
        </div>
        <div className="reasoning-side">
          <ReasoningTimeline steps={reasoningSteps} loading={true} />
        </div>
      </div>
    )
  }
  return (
    <div className="loading-state">
      <TarotLoader />
    </div>
  )
}


function MatchBanner({ matchType }) {
  if (matchType === 'none') {
    return (
      <div className="partial-banner">
        No exact matches found in your library — try rephrasing or adding more books
      </div>
    )
  }
  if (matchType === 'partial') {
    return (
      <div className="partial-banner">
        I couldn't find an exact match, but here's what's closest in your library
      </div>
    )
  }
  return null
}

function AnswerContent({ answer, onSourceClick, isSaved, onToggleSave, reasoningSteps }) {
  const [expanded, setExpanded] = useState(null)

  function toggleSource(index) {
    setExpanded(expanded === index ? null : index)
  }

  return (
    <>
      <div className="answer-question-row">
        <h3 className="answer-question">{answer.question}</h3>
        {onToggleSave && (
          <button
            className={`save-star-btn ${isSaved ? 'save-star-active' : ''}`}
            title={isSaved ? 'Remove from saved' : 'Save this answer'}
            onClick={onToggleSave}
          >
            <Star size={18} fill={isSaved ? 'var(--gold)' : 'none'} />
          </button>
        )}
      </div>
      {reasoningSteps && reasoningSteps.length > 0 && (
        <div className="answer-reasoning">
          <ReasoningTimeline steps={reasoningSteps} loading={false} />
        </div>
      )}
      <MatchBanner matchType={answer.match_type} />
      {answer.match_type === 'none' ? (
        <div className="no-match-state">
          <img src={chonkyCat} alt="" className="no-match-cat" loading="lazy" />
          <p className="no-match-text">
            This topic isn't covered in your library. Try rephrasing or adding more books!
          </p>
        </div>
      ) : (
        <div className="answer-body">{answer.answer}</div>
      )}
      {answer.sources.length > 0 && (
        <div className="sources-section">
          <p className="sources-heading">Sources</p>
          <div className="sources-list">
            {answer.sources.map((src, i) => (
              <div key={i}>
                <div
                  className="source-item"
                  style={{ backgroundColor: getSourceBg(i) }}
                  onClick={() => toggleSource(i)}
                >
                  <span>📖</span>
                  <span className="source-label">{formatSource(src)}</span>
                  {onSourceClick && src.book_id && (
                    <button
                      className="source-open-btn"
                      title="Open full chapter"
                      onClick={(e) => { e.stopPropagation(); onSourceClick(src) }}
                    >
                      <BookOpen size={13} />
                    </button>
                  )}
                  <ChevronRight
                    size={14}
                    className={`source-chevron ${expanded === i ? 'source-chevron-open' : ''}`}
                  />
                </div>
                {expanded === i && src.excerpt && (
                  <div className="source-excerpt">{src.excerpt}</div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  )
}

const fadeVariants = {
  initial: { opacity: 0 },
  animate: { opacity: 1 },
  exit: { opacity: 0 },
}

const slideVariants = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0 },
}

export default function AnswerCard({ answer, loading, suggestions, onSuggest, onSourceClick, isSaved, onToggleSave, reasoningSteps }) {
  const prefersReduced = useReducedMotion()

  return (
    <div className="answer-card">
      <AnimatePresence mode="wait">
        {loading ? (
          <motion.div key="loading" {...fadeVariants}>
            <LoadingState reasoningSteps={reasoningSteps} />
          </motion.div>
        ) : answer ? (
          <motion.div key="answer" {...slideVariants} transition={{ duration: 0.3 }}>
            <AnswerContent answer={answer} onSourceClick={onSourceClick} isSaved={isSaved} onToggleSave={onToggleSave} reasoningSteps={reasoningSteps} />
          </motion.div>
        ) : (
          <motion.div key="idle" {...fadeVariants}>
            <IdleState suggestions={suggestions || []} onSuggest={onSuggest} />
          </motion.div>
        )}
      </AnimatePresence>
      <motion.img
        src={crystalBallCat}
        alt=""
        className="answer-card-mascot"
        loading="lazy"
        animate={prefersReduced ? {} : { y: [0, -5, 0] }}
        transition={{ duration: 3.5, repeat: Infinity, ease: 'easeInOut' }}
      />
    </div>
  )
}
