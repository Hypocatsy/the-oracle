import { useState } from 'react'

const STORAGE_KEY = 'oracle-saved'

function readStorage() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

function writeStorage(entries) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(entries))
}

export function useSavedQueries() {
  const [savedQueries, setSavedQueries] = useState(() => readStorage())

  function saveQuery(answerObj) {
    const entry = {
      id: crypto.randomUUID(),
      question: answerObj.question,
      answer: answerObj.answer,
      sources: answerObj.sources,
      matchType: answerObj.match_type,
      bookId: answerObj.book_id ?? null,
      bookTitle: answerObj.book_title ?? null,
      timestamp: Date.now(),
    }
    const updated = [entry, ...savedQueries]
    setSavedQueries(updated)
    writeStorage(updated)
  }

  function removeQuery(id) {
    const updated = savedQueries.filter((q) => q.id !== id)
    setSavedQueries(updated)
    writeStorage(updated)
  }

  function isSaved(question) {
    return savedQueries.some((q) => q.question === question)
  }

  function getSavedId(question) {
    return savedQueries.find((q) => q.question === question)?.id ?? null
  }

  function clearAll() {
    setSavedQueries([])
    writeStorage([])
  }

  return { savedQueries, saveQuery, removeQuery, isSaved, getSavedId, clearAll }
}
