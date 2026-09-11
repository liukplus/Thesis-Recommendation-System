import { useEffect, useRef } from 'react'
import MessageBubble from './MessageBubble'
import './MessageList.css'

interface Message {
  id: string
  role: 'user' | 'assistant' | 'system' | 'tool'
  content: string
  toolName?: string
  isError?: boolean
}

interface MessageListProps {
  messages: Message[]
  loading?: boolean
}

export default function MessageList({ messages, loading }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  return (
    <div className="message-list">
      {messages.map((msg) => (
        <MessageBubble key={msg.id} message={msg} />
      ))}
      {loading && (
        <div className="message-loading">
          <div className="typing-indicator">
            <span />
            <span />
            <span />
          </div>
        </div>
      )}
      <div ref={bottomRef} />
    </div>
  )
}
