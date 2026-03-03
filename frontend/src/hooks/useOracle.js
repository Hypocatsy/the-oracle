import { useState, useEffect, useCallback, useRef } from 'react'
import axios from 'axios'
import toast from 'react-hot-toast'

export function useOracle() {
  const [books, setBooks] = useState([])
  const [answer, setAnswer] = useState(null)
  const [loading, setLoading] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [suggestions, setSuggestions] = useState([])
  const [reasoningSteps, setReasoningSteps] = useState([])
  const queryAbortRef = useRef(null)
  const chapterAbortRef = useRef(null)

  const fetchBooks = useCallback(async () => {
    try {
      const res = await axios.get('/api/books')
      setBooks(res.data)
    } catch {
      toast.error('Failed to load books')
    }
  }, [])

  useEffect(() => {
    fetchBooks()
  }, [fetchBooks])

  // Poll for processing books
  useEffect(() => {
    const hasProcessing = books.some(b => b.status === 'processing')
    if (!hasProcessing) return

    const interval = setInterval(fetchBooks, 2000)
    return () => clearInterval(interval)
  }, [books, fetchBooks])

  const fetchSuggestions = useCallback(async () => {
    try {
      const res = await axios.get('/api/suggestions')
      setSuggestions(res.data.suggestions)
    } catch {
      // Silently fail — suggestions are non-critical
    }
  }, [])

  useEffect(() => {
    const hasReady = books.some(b => b.status === 'ready')
    if (hasReady) {
      fetchSuggestions()
    } else {
      setSuggestions([])
    }
  }, [books, fetchSuggestions])

  const uploadBook = useCallback(async (file) => {
    setUploading(true)
    try {
      const formData = new FormData()
      formData.append('file', file)
      await axios.post('/api/books/upload', formData)
      toast.success('Book uploaded! Processing...')
      await fetchBooks()
    } catch (err) {
      const msg = err.response?.data?.detail || 'Upload failed'
      toast.error(msg)
    } finally {
      setUploading(false)
    }
  }, [fetchBooks])

  const deleteBook = useCallback(async (bookId) => {
    try {
      await axios.delete(`/api/books/${bookId}`)
      toast.success('Book removed')
      await fetchBooks()
    } catch {
      toast.error('Failed to delete book')
    }
  }, [fetchBooks])

  const updateBookTopic = useCallback(async (bookId, topic) => {
    try {
      await axios.patch(`/api/books/${bookId}/topic`, { topic })
      await fetchBooks()
    } catch {
      toast.error('Failed to update topic')
    }
  }, [fetchBooks])

  const allTopics = [...new Set(books.map(b => b.topic).filter(Boolean))].sort()

  const queryOracle = useCallback(async (question, bookId = null, topic = null) => {
    if (!question.trim()) return
    queryAbortRef.current?.abort()
    const controller = new AbortController()
    queryAbortRef.current = controller
    setLoading(true)
    setAnswer(null)
    setReasoningSteps([])

    try {
      const body = { question }
      if (bookId) body.book_id = bookId
      if (topic) body.topic = topic

      const response = await fetch('/api/query/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: controller.signal,
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        // Keep the last incomplete line in the buffer
        buffer = lines.pop() || ''

        for (const line of lines) {
          const trimmed = line.trim()
          if (!trimmed.startsWith('data: ')) continue

          let event
          try {
            event = JSON.parse(trimmed.slice(6))
          } catch {
            continue
          }

          if (event.type === 'thought' || event.type === 'tool_call' || event.type === 'tool_result') {
            setReasoningSteps(prev => [...prev, event])
          } else if (event.type === 'answer') {
            setAnswer({
              question: event.question,
              answer: event.answer,
              sources: event.sources,
              match_type: event.match_type,
            })
            setLoading(false)
          } else if (event.type === 'error') {
            toast.error(`Oracle error: ${event.detail}`)
            setLoading(false)
          }
        }
      }
    } catch (err) {
      if (err.name === 'AbortError') return
      toast.error('The Oracle is confused... please try again')
    } finally {
      setLoading(false)
    }
  }, [])

  // Reading panel state
  const [readingPanel, setReadingPanel] = useState(null)

  const openChapterByTitle = useCallback(async (bookId, bookTitle, chapterTitle, excerpt) => {
    chapterAbortRef.current?.abort()
    const controller = new AbortController()
    chapterAbortRef.current = controller
    setReadingPanel({ bookTitle, chapterTitle, chapterText: '', highlightExcerpt: excerpt, loading: true })
    try {
      const res = await axios.get(`/api/books/${bookId}/chapters/by-title`, {
        params: { title: chapterTitle },
        signal: controller.signal,
      })
      setReadingPanel(prev => prev && { ...prev, chapterText: res.data.text, chapterTitle: res.data.title, loading: false })
    } catch (err) {
      if (axios.isCancel(err)) return
      toast.error('Could not load chapter')
      setReadingPanel(null)
    }
  }, [])

  const openChapterByIndex = useCallback(async (bookId, bookTitle, chapterIndex) => {
    chapterAbortRef.current?.abort()
    const controller = new AbortController()
    chapterAbortRef.current = controller
    setReadingPanel({ bookTitle, chapterTitle: '', chapterText: '', highlightExcerpt: null, loading: true })
    try {
      const res = await axios.get(`/api/books/${bookId}/chapters/${chapterIndex}`, { signal: controller.signal })
      setReadingPanel(prev => prev && { ...prev, chapterText: res.data.text, chapterTitle: res.data.title, loading: false })
    } catch (err) {
      if (axios.isCancel(err)) return
      toast.error('Could not load chapter')
      setReadingPanel(null)
    }
  }, [])

  const closeReadingPanel = useCallback(() => {
    setReadingPanel(null)
  }, [])

  // Abort in-flight requests on unmount
  useEffect(() => {
    return () => {
      queryAbortRef.current?.abort()
      chapterAbortRef.current?.abort()
    }
  }, [])

  const totalChunks = books
    .filter(b => b.status === 'ready')
    .reduce((sum, b) => sum + b.chunk_count, 0)

  return {
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
  }
}
