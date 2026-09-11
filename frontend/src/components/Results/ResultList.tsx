import type { Paper } from '../../types'
import PaperCard from './PaperCard'
import './ResultList.css'

interface ResultListProps {
  papers: Paper[]
  loading?: boolean
}

export default function ResultList({ papers, loading }: ResultListProps) {
  if (loading) {
    return (
      <div className="result-list">
        {[1, 2, 3].map((i) => (
          <div key={i} className="paper-card paper-skeleton">
            <div className="paper-body">
              <div className="skeleton-title" />
              <div className="skeleton-meta" />
              <div className="skeleton-text" />
              <div className="skeleton-text short" />
            </div>
          </div>
        ))}
      </div>
    )
  }

  if (!papers.length) {
    return (
      <div className="result-list-empty">
        <p>No papers found yet. Try a search query above.</p>
      </div>
    )
  }

  return (
    <div className="result-list">
      {papers.map((paper, index) => (
        <PaperCard key={paper.id} paper={paper} rank={index + 1} />
      ))}
    </div>
  )
}
