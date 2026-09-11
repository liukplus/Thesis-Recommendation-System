import type { Paper } from '../../types'
import './PaperCard.css'

interface PaperCardProps {
  paper: Paper
  rank?: number
}

export default function PaperCard({ paper, rank }: PaperCardProps) {
  return (
    <article className="paper-card">
      {rank !== undefined && <div className="paper-rank">{rank}</div>}
      <div className="paper-body">
        <h3 className="paper-title">{paper.title}</h3>
        <div className="paper-meta">
          {paper.authors && <span className="paper-authors">{paper.authors}</span>}
          {paper.venue && (
            <>
              <span className="paper-meta-dot">·</span>
              <span className="paper-venue">{paper.venue}</span>
            </>
          )}
          {paper.year && (
            <>
              <span className="paper-meta-dot">·</span>
              <span className="paper-year">{paper.year}</span>
            </>
          )}
        </div>
        {paper.abstract && (
          <p className="paper-abstract">{paper.abstract}</p>
        )}
        <div className="paper-footer">
          {paper.score !== undefined && (
            <span className="paper-score">
              Relevance: {Math.round(paper.score * 100)}%
            </span>
          )}
          {paper.doi && (
            <span className="paper-doi">DOI: {paper.doi}</span>
          )}
        </div>
      </div>
    </article>
  )
}
