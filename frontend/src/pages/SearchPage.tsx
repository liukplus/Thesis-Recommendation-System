import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { usePipelineStore } from '../store/usePipelineStore'
import Button from '../components/UI/Button'
import ResultList from '../components/Results/ResultList'
import ErrorAlert from '../components/UI/ErrorAlert'
import './SearchPage.css'

export default function SearchPage() {
  const [searchParams] = useSearchParams()
  const urlQuery = searchParams.get('q') || ''

  const {
    query,
    result,
    stages,
    isLoading,
    isStreaming,
    error,
    progress,
    setQuery,
    streamPipeline,
  } = usePipelineStore()

  const [localQuery, setLocalQuery] = useState(urlQuery || query)

  useEffect(() => {
    if (urlQuery) {
      setLocalQuery(urlQuery)
      setQuery(urlQuery)
      streamPipeline(urlQuery)
    }
  }, [urlQuery]) // eslint-disable-line react-hooks/exhaustive-deps

  const handleSearch = () => {
    if (localQuery.trim()) {
      setQuery(localQuery)
      streamPipeline(localQuery)
    }
  }

  return (
    <div className="search-page">
      <div className="search-header">
        <h1>Paper Search</h1>
        <p className="search-description">
          Run the full 8-stage research pipeline to find and analyze relevant papers.
        </p>
      </div>

      <div className="search-bar">
        <input
          type="text"
          className="search-input"
          placeholder="Enter your research query..."
          value={localQuery}
          onChange={(e) => setLocalQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          disabled={isLoading}
        />
        <Button
          variant="primary"
          onClick={handleSearch}
          loading={isLoading}
          disabled={!localQuery.trim()}
        >
          Search
        </Button>
      </div>

      {error && <ErrorAlert message={error} onRetry={handleSearch} />}

      {/* Pipeline stages progress */}
      {stages.length > 0 && (
        <div className="pipeline-progress">
          <div className="progress-bar">
            <div
              className="progress-fill"
              style={{ width: `${progress * 100}%` }}
            />
          </div>
          <div className="stages-row">
            {stages.map((stage, i) => (
              <div
                key={stage.name}
                className={`stage-pill ${stage.success ? 'success' : 'running'}`}
              >
                <span className="stage-num">{i + 1}</span>
                <span className="stage-name">{stage.name.replace(/_/g, ' ')}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Answer */}
      {result?.answer && (
        <div className="answer-section">
          <h2>Answer</h2>
          <div className="answer-content">
            <p>{result.answer}</p>
          </div>
        </div>
      )}

      {/* Results */}
      <div className="results-section">
        <h2>
          Results
          {result?.papers && (
            <span className="results-count">({result.papers.length} papers)</span>
          )}
        </h2>
        <ResultList
          papers={result?.papers || []}
          loading={isLoading}
        />
      </div>
    </div>
  )
}
