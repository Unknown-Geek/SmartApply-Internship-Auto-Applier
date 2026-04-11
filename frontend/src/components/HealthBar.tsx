import './HealthBar.css'

interface ServiceStatus {
  ok: boolean
  detail?: string
}

interface HealthData {
  status?: string
  model: string
  identity_loaded: boolean
  ollama?: boolean | ServiceStatus
  context_mode?: ServiceStatus
  pinchtab?: ServiceStatus
}

interface Props {
  health: HealthData
}

function isOk(v: boolean | ServiceStatus | undefined): boolean {
  if (v === undefined) return false
  if (typeof v === 'boolean') return v
  return v.ok
}

export function HealthBar({ health }: Props) {
  return (
    <div className="health-bar" role="status" aria-label="System status">
      <HealthDot label="Ollama" ok={isOk(health.ollama)} />
      <HealthDot label="Context" ok={isOk(health.context_mode)} />
      <HealthDot label="Identity" ok={health.identity_loaded} />
    </div>
  )
}

function HealthDot({ label, ok }: { label: string; ok: boolean }) {
  return (
    <span className={`health-dot-wrap ${ok ? 'ok' : 'err'}`} title={`${label}: ${ok ? 'Ready' : 'Not ready'}`}>
      <span className="health-dot" />
      <span className="health-label">{label}</span>
    </span>
  )
}
