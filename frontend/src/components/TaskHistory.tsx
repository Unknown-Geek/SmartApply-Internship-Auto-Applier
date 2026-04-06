import { StatusBadge } from './StatusBadge'
import './TaskHistory.css'

interface Task {
  task_id: string
  status: string
  job_url: string
  created_at: string
  result?: string
  error?: string
}

interface Props {
  tasks: Task[]
  activeTaskId: string | null
  onSelect: (id: string) => void
}

export function TaskHistory({ tasks, activeTaskId, onSelect }: Props) {
  const formatUrl = (url: string) => {
    try {
      const u = new URL(url)
      return u.hostname + u.pathname.slice(0, 40) + (u.pathname.length > 40 ? '…' : '')
    } catch {
      return url.slice(0, 60)
    }
  }

  const formatTime = (iso: string) => {
    const d = new Date(iso)
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }

  return (
    <section className="task-history" id="task-history">
      <h2 className="section-title">
        <span>📋</span> Application History
      </h2>
      <div className="task-list">
        {tasks.map(task => (
          <button
            key={task.task_id}
            id={`task-${task.task_id}`}
            className={`task-item ${task.task_id === activeTaskId ? 'active' : ''}`}
            onClick={() => onSelect(task.task_id)}
          >
            <div className="task-item-left">
              <span className="task-url">{formatUrl(task.job_url)}</span>
              <span className="task-time">{formatTime(task.created_at)}</span>
            </div>
            <StatusBadge status={task.status} />
          </button>
        ))}
      </div>
    </section>
  )
}
