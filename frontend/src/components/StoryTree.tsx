import React, { useState, useEffect } from 'react'
import { ChevronRight, ChevronDown, Book, FileText, Plus, Folder } from 'lucide-react'
import { storyApi, chaptersApi, Series, Book as BookType } from '../lib/api'

interface Chapter {
  id: number
  title: string
  chapter_number: number
  word_count?: number
}

interface StoryTreeProps {
  onSelectSeries?: (series: Series) => void
  onSelectBook?: (book: BookType, series: Series) => void
  onSelectChapter?: (chapter: Chapter, book: BookType, series: Series) => void
  selectedSeriesId?: number
  selectedBookId?: number
  selectedChapterId?: number
}

export function StoryTree({
  onSelectSeries,
  onSelectBook,
  onSelectChapter,
  selectedSeriesId,
  selectedBookId,
  selectedChapterId
}: StoryTreeProps) {
  const [seriesList, setSeriesList] = useState<Series[]>([])
  const [expandedSeries, setExpandedSeries] = useState<Set<number>>(new Set())
  const [expandedBooks, setExpandedBooks] = useState<Set<number>>(new Set())
  const [booksBySeriesId, setBooksBySeriesId] = useState<Record<number, BookType[]>>({})
  const [chaptersByBookId, setChaptersByBookId] = useState<Record<number, Chapter[]>>({})
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadSeries()
  }, [])

  const loadSeries = async () => {
    try {
      const response = await storyApi.listSeries()
      const series = Array.isArray(response) ? response : response.series || []
      setSeriesList(series)
      
      // Auto-expand selected series
      if (selectedSeriesId) {
        setExpandedSeries(new Set([selectedSeriesId]))
      }
    } catch (error) {
      console.error('Failed to load series:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadBooks = async (seriesId: number) => {
    if (booksBySeriesId[seriesId]) return
    
    try {
      const response = await storyApi.listBooks(seriesId)
      const books = Array.isArray(response) ? response : response.books || []
      setBooksBySeriesId(prev => ({ ...prev, [seriesId]: books }))
    } catch (error) {
      console.error('Failed to load books:', error)
    }
  }

  const loadChapters = async (bookId: number) => {
    if (chaptersByBookId[bookId]) return
    
    try {
      const response = await chaptersApi.list(bookId)
      const chapters = Array.isArray(response) ? response : response.chapters || []
      setChaptersByBookId(prev => ({ ...prev, [bookId]: chapters }))
    } catch (error) {
      console.error('Failed to load chapters:', error)
    }
  }

  const toggleSeries = async (seriesId: number) => {
    const newExpanded = new Set(expandedSeries)
    if (newExpanded.has(seriesId)) {
      newExpanded.delete(seriesId)
    } else {
      newExpanded.add(seriesId)
      await loadBooks(seriesId)
    }
    setExpandedSeries(newExpanded)
  }

  const toggleBook = async (bookId: number) => {
    const newExpanded = new Set(expandedBooks)
    if (newExpanded.has(bookId)) {
      newExpanded.delete(bookId)
    } else {
      newExpanded.add(bookId)
      await loadChapters(bookId)
    }
    setExpandedBooks(newExpanded)
  }

  if (loading) {
    return (
      <div className="p-4 text-gray-400 text-sm">
        Loading stories...
      </div>
    )
  }

  return (
    <div className="story-tree text-sm">
      <div className="px-3 py-2 text-xs font-semibold text-gray-400 uppercase tracking-wider flex items-center justify-between">
        <span>📚 My Stories</span>
        <button 
          className="p-1 hover:bg-gray-700 rounded"
          title="New Series"
        >
          <Plus className="w-3 h-3" />
        </button>
      </div>
      
      {seriesList.length === 0 ? (
        <div className="px-4 py-8 text-center text-gray-500">
          <Folder className="w-8 h-8 mx-auto mb-2 opacity-50" />
          <p>No stories yet</p>
          <button className="mt-2 text-blue-400 hover:text-blue-300 text-xs">
            + Create your first series
          </button>
        </div>
      ) : (
        <ul className="space-y-0.5">
          {seriesList.map(series => (
            <li key={series.id}>
              {/* Series Level */}
              <div 
                className={`flex items-center px-3 py-1.5 cursor-pointer hover:bg-gray-800 rounded-md mx-1 ${
                  selectedSeriesId === series.id ? 'bg-gray-800 text-white' : 'text-gray-300'
                }`}
              >
                <button 
                  onClick={() => toggleSeries(series.id)}
                  className="p-0.5 hover:bg-gray-700 rounded mr-1"
                >
                  {expandedSeries.has(series.id) ? (
                    <ChevronDown className="w-4 h-4" />
                  ) : (
                    <ChevronRight className="w-4 h-4" />
                  )}
                </button>
                <Folder className="w-4 h-4 mr-2 text-yellow-500" />
                <span 
                  className="flex-1 truncate"
                  onClick={() => onSelectSeries?.(series)}
                >
                  {series.title}
                </span>
                <span className="text-xs text-gray-500">
                  {series.planned_books || '?'} books
                </span>
              </div>
              
              {/* Books Level */}
              {expandedSeries.has(series.id) && (
                <ul className="ml-4 space-y-0.5 mt-0.5">
                  {(booksBySeriesId[series.id] || []).map(book => (
                    <li key={book.id}>
                      <div 
                        className={`flex items-center px-3 py-1.5 cursor-pointer hover:bg-gray-800 rounded-md mx-1 ${
                          selectedBookId === book.id ? 'bg-gray-800 text-white' : 'text-gray-300'
                        }`}
                      >
                        <button 
                          onClick={() => toggleBook(book.id)}
                          className="p-0.5 hover:bg-gray-700 rounded mr-1"
                        >
                          {expandedBooks.has(book.id) ? (
                            <ChevronDown className="w-4 h-4" />
                          ) : (
                            <ChevronRight className="w-4 h-4" />
                          )}
                        </button>
                        <Book className="w-4 h-4 mr-2 text-blue-400" />
                        <span 
                          className="flex-1 truncate"
                          onClick={() => onSelectBook?.(book, series)}
                        >
                          {book.book_number ? `Part ${book.book_number}: ` : ''}{book.title}
                        </span>
                      </div>
                      
                      {/* Chapters Level */}
                      {expandedBooks.has(book.id) && (
                        <ul className="ml-6 space-y-0.5 mt-0.5">
                          {(chaptersByBookId[book.id] || []).map(chapter => (
                            <li key={chapter.id}>
                              <div 
                                className={`flex items-center px-3 py-1 cursor-pointer hover:bg-gray-800 rounded-md mx-1 ${
                                  selectedChapterId === chapter.id ? 'bg-gray-800 text-white' : 'text-gray-400'
                                }`}
                                onClick={() => onSelectChapter?.(chapter, book, series)}
                              >
                                <FileText className="w-3.5 h-3.5 mr-2 text-gray-500" />
                                <span className="flex-1 truncate text-xs">
                                  Ch {chapter.chapter_number}: {chapter.title}
                                </span>
                                {chapter.word_count && (
                                  <span className="text-xs text-gray-600">
                                    {(chapter.word_count / 1000).toFixed(1)}k
                                  </span>
                                )}
                              </div>
                            </li>
                          ))}
                          {(chaptersByBookId[book.id] || []).length === 0 && (
                            <li className="px-4 py-2 text-xs text-gray-600 italic">
                              No chapters yet
                            </li>
                          )}
                        </ul>
                      )}
                    </li>
                  ))}
                  {(booksBySeriesId[series.id] || []).length === 0 && (
                    <li className="px-4 py-2 text-xs text-gray-600 italic">
                      No books yet
                    </li>
                  )}
                </ul>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
