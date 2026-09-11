import './MessageBubble.css'

interface Message {
  id: string
  role: 'user' | 'assistant' | 'system' | 'tool'
  content: string
  toolName?: string
  isError?: boolean
}

interface MessageBubbleProps {
  message: Message
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const { role, content, toolName, isError } = message

  const roleLabels: Record<string, string> = {
    user: 'You',
    assistant: 'Assistant',
    system: 'System',
    tool: toolName ? `Tool: ${toolName}` : 'Tool',
  }

  return (
    <div className={`message-bubble message-${role} ${isError ? 'message-error' : ''}`}>
      <div className="message-header">
        <span className="message-role">{roleLabels[role]}</span>
      </div>
      <div className="message-content">
        {role === 'tool' ? (
          <pre className="tool-content">{content}</pre>
        ) : (
          <p>{content}</p>
        )}
      </div>
    </div>
  )
}
