import { useState, useEffect, useRef } from 'react'

interface LogEntry {
  timestamp: string
  level: string
  message: string
  step?: number
}

interface AgentSocketState {
  logs: LogEntry[]
  status: string
  result: string | null
  error: string | null
  question: string | null
}

const WS_URL = import.meta.env.VITE_WS_URL || ''

export function useAgentSocket(taskId: string | null): AgentSocketState {
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [status, setStatus] = useState('pending')
  const [result, setResult] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [question, setQuestion] = useState<string | null>(null)
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    if (!taskId) return

    // Reset state for new task
    setLogs([])
    setStatus('pending')
    setResult(null)
    setError(null)
    setQuestion(null)

    // Close any existing connection
    wsRef.current?.close()

    const url = `${WS_URL}/ws/agent/${taskId}`
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)

        if (msg.type === 'status') {
          setStatus(msg.status)
          setQuestion(msg.question ?? null)
          if (msg.status !== 'waiting') setQuestion(null)
        } else if (msg.type === 'done') {
          setStatus(msg.result ? 'completed' : 'failed')
          if (msg.result) setResult(msg.result)
          if (msg.error) setError(msg.error)
        } else if (msg.error) {
          setError(msg.error)
        } else if (msg.message) {
          // Log entry
          setLogs((prev: LogEntry[]) => [...prev, msg as LogEntry])
        }
      } catch (e) {
        console.error('WS parse error:', e)
      }
    }

    ws.onerror = () => setStatus('failed')
    ws.onclose = () => {}

    return () => {
      ws.close()
    }
  }, [taskId])

  return { logs, status, result, error, question }
}
