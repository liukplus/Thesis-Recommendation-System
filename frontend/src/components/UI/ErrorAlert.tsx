import './ErrorAlert.css'

interface ErrorAlertProps {
  message: string
  onRetry?: () => void
}

export default function ErrorAlert({ message, onRetry }: ErrorAlertProps) {
  return (
    <div className="error-alert" role="alert">
      <div className="error-icon">⚠️</div>
      <div className="error-content">
        <p className="error-message">{message}</p>
        {onRetry && (
          <button className="error-retry" onClick={onRetry}>
            Try again
          </button>
        )}
      </div>
    </div>
  )
}
