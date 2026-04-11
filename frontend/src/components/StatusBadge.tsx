import './StatusBadge.css'

interface Props {
  status: string
}

const STATUS_CONFIG: Record<string, { label: string; color: string; dot: string }> = {
  pending:   { label: 'Pending',   color: '#a0aec0', dot: '#4a5568' },
  running:   { label: 'Running',   color: '#63b3ed', dot: '#63b3ed' },
  waiting:   { label: 'Waiting',   color: '#f6e05e', dot: '#f6e05e' },
  completed: { label: 'Completed', color: '#68d391', dot: '#68d391' },
  failed:    { label: 'Failed',    color: '#fc8181', dot: '#fc8181' },
}

export function StatusBadge({ status }: Props) {
  const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.pending

  return (
    <span className="status-badge" style={{ color: cfg.color, borderColor: `${cfg.color}30`, background: `${cfg.color}10` }}>
      <span className="status-dot" style={{ background: cfg.dot, boxShadow: status === 'running' ? `0 0 8px ${cfg.dot}` : 'none' }} />
      {cfg.label}
    </span>
  )
}
