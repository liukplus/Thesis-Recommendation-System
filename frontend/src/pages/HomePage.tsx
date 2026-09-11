import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Button from '../components/UI/Button'
import './HomePage.css'

export default function HomePage() {
  const [query, setQuery] = useState('')
  const navigate = useNavigate()

  const handleSearch = () => {
    if (query.trim()) {
      navigate(`/search?q=${encodeURIComponent(query)}`)
    }
  }

  const exampleQueries = [
    'deep learning for natural language processing',
    'transformer architecture survey',
    'reinforcement learning in robotics',
    'graph neural networks applications',
  ]

  return (
    <div className="home-page">
      <section className="hero">
        <h1 className="hero-title">
          Discover Research Papers with{' '}
          <span className="hero-accent">AI-Powered Search</span>
        </h1>
        <p className="hero-subtitle">
          An intelligent paper recommendation system with multi-stage RAG pipeline
          and agentic research assistance.
        </p>

        <div className="hero-search">
          <input
            type="text"
            className="hero-input"
            placeholder="Ask a research question or search for papers..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          />
          <Button variant="primary" size="lg" onClick={handleSearch}>
            Search
          </Button>
        </div>

        <div className="example-queries">
          <span className="example-label">Try:</span>
          {exampleQueries.map((q) => (
            <button
              key={q}
              className="example-chip"
              onClick={() => setQuery(q)}
            >
              {q}
            </button>
          ))}
        </div>
      </section>

      <section className="features">
        <div className="feature-card">
          <div className="feature-icon">🔍</div>
          <h3>Multi-Source Search</h3>
          <p>
            Retrieve papers from multiple sources including local databases,
            semantic search, and external APIs.
          </p>
        </div>
        <div className="feature-card">
          <div className="feature-icon">⚡</div>
          <h3>8-Stage Pipeline</h3>
          <p>
            From query parsing to citation verification, our pipeline ensures
            high-quality, grounded results.
          </p>
        </div>
        <div className="feature-card">
          <div className="feature-icon">🤖</div>
          <h3>Agent Assistant</h3>
          <p>
            Let the AI agent do the research for you — plan, search, summarize,
            and synthesize findings automatically.
          </p>
        </div>
      </section>
    </div>
  )
}
