import { useState, useEffect } from 'react'
import { motion, useReducedMotion } from 'framer-motion'
import { Toaster } from 'react-hot-toast'
import Header from './components/Header'
import SearchBar from './components/SearchBar'
import LibraryPanel from './components/LibraryPanel'
import AnswerCard from './components/AnswerCard'
import ReadingPanel from './components/ReadingPanel'
import FloatingDecorations from './components/FloatingDecorations'
import { useOracle } from './hooks/useOracle'
import { useSavedQueries } from './hooks/useSavedQueries'
import crescentMoonCat from './assets/cats/crescentmooncat.PNG'
import './styles/App.css'

const staggerContainer = {
  animate: { transition: { staggerChildren: 0.1 } },
}

const staggerItem = {
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.4 } },
}

export default function App() {
  const {
    books,
    answer,
    loading,
    uploading,
    totalChunks,
    suggestions,
    reasoningSteps,
    readingPanel,
    allTopics,
    uploadBook,
    deleteBook,
    updateBookTopic,
    queryOracle,
    openChapterByTitle,
    openChapterByIndex,
    closeReadingPanel,
  } = useOracle()

  const { savedQueries, saveQuery, removeQuery, isSaved, getSavedId, clearAll } = useSavedQueries()

  const [displayedAnswer, setDisplayedAnswer] = useState(null)

  // The answer to show: live answer from useOracle takes priority, otherwise show a saved selection
  const activeAnswer = answer ?? displayedAnswer

  // Clear the saved selection whenever a new live answer arrives
  useEffect(() => {
    if (answer && displayedAnswer) {
      setDisplayedAnswer(null)
    }
  }, [answer])

  function handleSelectSaved(entry) {
    setDisplayedAnswer({
      question: entry.question,
      answer: entry.answer,
      sources: entry.sources,
      match_type: entry.matchType,
      book_id: entry.bookId,
      book_title: entry.bookTitle,
    })
  }

  function handleToggleSave() {
    if (!activeAnswer) return
    if (isSaved(activeAnswer.question)) {
      const id = getSavedId(activeAnswer.question)
      if (id) removeQuery(id)
    } else {
      saveQuery(activeAnswer)
    }
  }

  const prefersReduced = useReducedMotion()

  return (
    <div className="app">
      <FloatingDecorations />
      <Toaster position="top-right" />
      <motion.img
        src={crescentMoonCat}
        alt=""
        className="bg-crescent-cat"
        loading="lazy"
        animate={prefersReduced ? {} : { y: [0, -5, 0] }}
        transition={{ duration: 4, repeat: Infinity, ease: 'easeInOut' }}
      />
      <motion.div
        className="app-container"
        variants={prefersReduced ? {} : staggerContainer}
        initial="initial"
        animate="animate"
      >
        <motion.div variants={prefersReduced ? {} : staggerItem}>
          <Header />
        </motion.div>
        <motion.div variants={prefersReduced ? {} : staggerItem}>
          <SearchBar onSearch={queryOracle} loading={loading} books={books.filter(b => b.status === 'ready')} allTopics={allTopics} />
        </motion.div>
        <motion.div className="main-layout" variants={prefersReduced ? {} : staggerItem}>
          <LibraryPanel
            books={books}
            totalChunks={totalChunks}
            uploading={uploading}
            onUpload={uploadBook}
            onDelete={deleteBook}
            onChapterClick={(bookId, bookTitle, chapterIndex) =>
              openChapterByIndex(bookId, bookTitle, chapterIndex)
            }
            savedQueries={savedQueries}
            onSelectSaved={handleSelectSaved}
            onRemoveSaved={removeQuery}
            onClearSaved={clearAll}
            allTopics={allTopics}
            onUpdateTopic={updateBookTopic}
          />
          <AnswerCard
            answer={activeAnswer}
            loading={loading}
            suggestions={suggestions}
            onSuggest={queryOracle}
            onSourceClick={(src) =>
              openChapterByTitle(src.book_id, src.book_title, src.chapter, src.highlight_text?.length ? src.highlight_text : src.excerpt)
            }
            isSaved={activeAnswer ? isSaved(activeAnswer.question) : false}
            onToggleSave={handleToggleSave}
            reasoningSteps={reasoningSteps}
          />
        </motion.div>
      </motion.div>
      <ReadingPanel panel={readingPanel} onClose={closeReadingPanel} />
    </div>
  )
}
