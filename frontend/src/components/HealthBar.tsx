import './HealthBar.css'

interface Props {
  health: {
    ollama: boolean
    model: string
    identity_loaded: boolean
  }
}

export function HealthBar({ health }: Props) {
  return (
    <div className="health-bar" role="status" aria-label="System status">
      <HealthDot label="Ollama" ok={health.ollama} />
      <HealthDot label="Identity" ok={health.identity_loaded} />
    </div>
  )
}

function HealthDot({ label, ok }: { label: string; ok: boolean }) {
  return (
    <span className={`health-dot-wrap ${ok ? 'ok' : 'err'}`} title={`${label}: ${ok ? 'OK' : 'Not ready'}`}>
      <span className="health-dot" />
      <span className="health-label">{label}</span>
    </span>
  )
}
