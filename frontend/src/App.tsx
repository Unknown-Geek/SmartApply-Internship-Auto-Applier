import { useState, useEffect } from 'react'
import { JobInput } from './components/JobInput'
import { AgentTerminal } from './components/AgentTerminal'
import { StatusBadge } from './components/StatusBadge'
import { HealthBar } from './components/HealthBar'
import { TaskHistory } from './components/TaskHistory'
import { IdentityPanel } from './components/IdentityPanel'
import { useAgentSocket } from './hooks/useAgentSocket'
import './App.css'

const API_URL = import.meta.env.VITE_API_URL || ''

interface Task {
  task_id: string
  status: string
  job_url: string
  created_at: string
  logs: LogEntry[]
  result?: string
  error?: string
  question?: string
}

interface LogEntry {
  timestamp: string
  level: string
  message: string
  step?: number
}

interface Health {
  status?: string
  model: string
  identity_loaded: boolean
  ollama?: { ok: boolean; detail?: string }
  context_mode?: { ok: boolean; detail?: string }
}

export default function App() {
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null)
  const [tasks, setTasks] = useState<Task[]>([])
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [health, setHealth] = useState<Health | null>(null)
  const [humanAnswer, setHumanAnswer] = useState('')
  const [isSendingAnswer, setIsSendingAnswer] = useState(false)

  const { logs, status, result, error, question } = useAgentSocket(activeTaskId)

  // Health check on mount
  useEffect(() => {
    const checkHealth = async () => {
      try {
        const r = await fetch(`${API_URL}/api/health`)
        const data = await r.json()
        setHealth(data)
      } catch {
        setHealth(null)
      }
    }
    checkHealth()
    const interval = setInterval(checkHealth, 10000)
    return () => clearInterval(interval)
  }, [])

  const handleApply = async (jobUrl: string) => {
    setIsSubmitting(true)
    try {
      const r = await fetch(`${API_URL}/api/jobs/apply`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ job_url: jobUrl }),
      })
      const task: Task = await r.json()
      setTasks((prev: Task[]) => [task, ...prev])
      setActiveTaskId(task.task_id)
    } catch (e) {
      console.error('Failed to submit job:', e)
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleSendAnswer = async () => {
    if (!activeTaskId || !humanAnswer.trim()) return
    setIsSendingAnswer(true)
    try {
      await fetch(`${API_URL}/api/jobs/${activeTaskId}/answer`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ answer: humanAnswer.trim() }),
      })
      setHumanAnswer('')
    } catch (e) {
      console.error('Failed to send answer:', e)
    } finally {
      setIsSendingAnswer(false)
    }
  }

  return (
    <div className="app">
      {/* ─── Animated background ───────────────────────────────────────────── */}
      <div className="bg-orbs" aria-hidden="true">
        <div className="orb orb-1" />
        <div className="orb orb-2" />
        <div className="orb orb-3" />
      </div>

      {/* ─── Header ────────────────────────────────────────────────────────── */}
      <header className="header">
        <div className="header-inner">
          <div className="logo">
            <span className="logo-icon">⚡</span>
            <span className="logo-text">Smart<span className="logo-accent">Apply</span></span>
          </div>
          <div className="header-meta">
            <span className="model-badge">
              <span className="model-dot" />
              qwen2.5-coder:7b
            </span>
            {health && <HealthBar health={health} />}
          </div>
        </div>
      </header>

      {/* ─── Main ──────────────────────────────────────────────────────────── */}
      <main className="main">
        {/* Hero section */}
        <section className="hero">
          <h1 className="hero-title">
            Apply to jobs<br />
            <span className="gradient-text">autonomously.</span>
          </h1>
          <p className="hero-sub">
            Paste any job URL. Our AI agent reads the form, fills it with your identity,
            and hits submit — while you watch every step in real time.
          </p>
        </section>

        {/* Identity upload */}
        <IdentityPanel onIdentityLoaded={() => setHealth((h: Health | null) => h ? {...h, identity_loaded: true} : h)} />

        {/* Job input */}
        <JobInput onSubmit={handleApply} isLoading={isSubmitting} />

        {/* Active task terminal */}
        {activeTaskId && (
          <section className="terminal-section">
            <div className="terminal-header">
              <span className="terminal-title">🤖 Agent Loop</span>
              <StatusBadge status={status} />
            </div>
            <AgentTerminal
              logs={logs}
              result={result}
              error={error}
              status={status}
            />

            {/* Human input panel when agent is waiting */}
            {status === 'waiting' && question && (
              <div className="human-input-panel">
                <div className="human-input-question">
                  <span className="human-input-icon">?</span>
                  <span>{question}</span>
                </div>
                <div className="human-input-row">
                  <input
                    type="text"
                    className="human-input-field"
                    placeholder="Type your answer..."
                    value={humanAnswer}
                    onChange={(e) => setHumanAnswer(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && humanAnswer.trim()) handleSendAnswer()
                    }}
                    disabled={isSendingAnswer}
                    autoFocus
                  />
                  <button
                    className="human-input-send"
                    onClick={handleSendAnswer}
                    disabled={isSendingAnswer || !humanAnswer.trim()}
                  >
                    {isSendingAnswer ? 'Sending...' : 'Send'}
                  </button>
                </div>
              </div>
            )}
          </section>
        )}

        {/* Task history */}
        {tasks.length > 0 && (
          <TaskHistory
            tasks={tasks}
            activeTaskId={activeTaskId}
            onSelect={setActiveTaskId}
          />
        )}
      </main>

      <footer className="footer">
        <span>Smart Apply · Powered by <code>qwen2.5-coder:7b</code> via Ollama · 100% local</span>
      </footer>
    </div>
  )
}
