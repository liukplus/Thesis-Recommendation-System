import type { PlanStep } from '../../types'
import './StepIndicator.css'

interface StepIndicatorProps {
  steps: PlanStep[]
  currentStep?: number
}

export default function StepIndicator({ steps, currentStep = 0 }: StepIndicatorProps) {
  if (!steps.length) return null

  return (
    <div className="step-indicator">
      <h4 className="step-indicator-title">Plan</h4>
      <div className="step-list">
        {steps.map((step) => (
          <div
            key={step.index}
            className={`step-item step-${step.status}`}
          >
            <div className="step-icon">
              {step.status === 'completed' && '✓'}
              {step.status === 'in_progress' && '●'}
              {step.status === 'pending' && step.index}
              {step.status === 'failed' && '✕'}
            </div>
            <div className="step-content">
              <p className="step-description">{step.description}</p>
              {step.tool && (
                <span className="step-tool">Tool: {step.tool}</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
