import { useEffect, useRef } from 'react'
import './AgentTerminal.css'

interface LogEntry {
  timestamp: string
  level: string
  message: string
  step?: number
}

interface Props {
  logs: LogEntry[]
  status: string
  result?: string | null
  error?: string | null
}

const LEVEL_ICONS: Record<string, string> = {
  thought:     '💭',
  action:      '⚡',
  observation: '👁️',
  error:       '❌',
  info:        '📋',
}

const LEVEL_COLORS: Record<string, string> = {
  thought:     '#9f7aea',
  action:      '#63b3ed',
  observation: '#68d391',
  error:       '#fc8181',
  info:        '#a0aec0',
}

export function AgentTerminal({ logs, status, result, error }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  const isEmpty = logs.length === 0

  return (
    <div className="terminal" id="agent-terminal">
      {/* Terminal dots decoration */}
      <div className="terminal-dots" aria-hidden="true">
        <span className="dot dot-red" />
        <span className="dot dot-yellow" />
        <span className="dot dot-green" />
        <span className="terminal-path">~/smart-apply/agent.log</span>
      </div>

      <div className="terminal-body">
        {isEmpty && status === 'pending' && (
          <div className="terminal-empty">
            <span className="blink-cursor">▋</span>
            <span className="empty-text"> Waiting for agent to start…</span>
          </div>
        )}

        {logs.map((log, i) => (
          <div key={i} className={`log-line level-${log.level}`}>
            <span className="log-step">
              {log.step != null ? `[${String(log.step).padStart(2, '0')}]` : '    '}
            </span>
            <span className="log-icon">{LEVEL_ICONS[log.level] || '●'}</span>
            <span className="log-level" style={{ color: LEVEL_COLORS[log.level] || '#a0aec0' }}>
              {log.level.toUpperCase()}
            </span>
            <span className="log-message">{log.message}</span>
          </div>
        ))}

        {/* Running indicator */}
        {status === 'running' && (
          <div className="log-line running-indicator">
            <span className="log-step">    </span>
            <span className="thinking-dots">
              <span />
              <span />
              <span />
            </span>
            <span className="thinking-label">Agent thinking…</span>
          </div>
        )}

        {/* Result */}
        {status === 'completed' && result && (
          <div className="terminal-result success">
            <span>✅</span>
            <span>{result}</span>
          </div>
        )}
        {status === 'failed' && error && (
          <div className="terminal-result error">
            <span>❌</span>
            <span>{error}</span>
          </div>
        )}

        <div ref={bottomRef} />
      </div>
    </div>
  )
}
