import { useAgentStore } from '../store/useAgentStore'
import ChatInput from '../components/Chat/ChatInput'
import MessageList from '../components/Chat/MessageList'
import StepIndicator from '../components/Agent/StepIndicator'
import ErrorAlert from '../components/UI/ErrorAlert'
import './AgentPage.css'

export default function AgentPage() {
  const {
    messages,
    isLoading,
    isStreaming,
    error,
    plan,
    currentStep,
    sendMessage,
    reset,
  } = useAgentStore()

  const handleSend = (message: string) => {
    sendMessage(message, true) // stream = true
  }

  return (
    <div className="agent-page">
      <div className="agent-sidebar">
        <div className="sidebar-header">
          <h2>Research Agent</h2>
          <p className="sidebar-desc">
            AI-powered research assistant that plans, searches, and synthesizes findings.
          </p>
        </div>

        {plan.length > 0 && (
          <StepIndicator steps={plan} currentStep={currentStep} />
        )}

        <div className="agent-stats">
          <div className="stat-item">
            <span className="stat-value">{messages.filter(m => m.role === 'user').length}</span>
            <span className="stat-label">Messages</span>
          </div>
          <div className="stat-item">
            <span className="stat-value">{currentStep}</span>
            <span className="stat-label">Steps</span>
          </div>
        </div>

        <button className="reset-btn" onClick={reset}>
          New Conversation
        </button>
      </div>

      <div className="agent-main">
        <div className="agent-content">
          {error && <ErrorAlert message={error} />}

          {messages.length === 0 ? (
            <div className="agent-welcome">
              <div className="welcome-icon">🤖</div>
              <h2>Hi! I'm your research assistant.</h2>
              <p>
                Ask me anything about academic papers. I'll plan my approach,
                search for relevant papers, and synthesize the findings for you.
              </p>
              <div className="suggestions">
                <p className="suggestions-label">Try asking about:</p>
                <div className="suggestion-chips">
                  {[
                    'survey on large language models',
                    'latest advances in computer vision',
                    'how do transformers work?',
                  ].map((q) => (
                    <button
                      key={q}
                      className="suggestion-chip"
                      onClick={() => handleSend(q)}
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <MessageList messages={messages} loading={isLoading || isStreaming} />
          )}
        </div>

        <ChatInput
          onSend={handleSend}
          disabled={isLoading || isStreaming}
          placeholder="Ask about any research topic..."
        />
      </div>
    </div>
  )
}
