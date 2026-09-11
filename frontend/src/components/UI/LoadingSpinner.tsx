import './LoadingSpinner.css'

interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg'
  label?: string
}

export default function LoadingSpinner({ size = 'md', label }: LoadingSpinnerProps) {
  return (
    <div className={`spinner-container spinner-${size}`}>
      <div className="spinner" role="status" aria-label="Loading" />
      {label && <span className="spinner-label">{label}</span>}
    </div>
  )
}
