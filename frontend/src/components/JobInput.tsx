import { useState, useRef } from 'react'
import './JobInput.css'

interface Props {
  onSubmit: (url: string) => void
  isLoading: boolean
}

export function JobInput({ onSubmit, isLoading }: Props) {
  const [url, setUrl] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = url.trim()
    if (!trimmed || isLoading) return
    onSubmit(trimmed)
  }

  const isValid = url.trim().startsWith('http')

  return (
    <form className="job-input-form" onSubmit={handleSubmit} id="apply-form">
      <div className="job-input-card">
        <label className="job-input-label" htmlFor="job-url-input">
          <span className="label-icon">🔗</span>
          Job Application URL
        </label>
        <div className="job-input-row">
          <input
            id="job-url-input"
            ref={inputRef}
            type="url"
            className="job-input-field"
            placeholder="https://jobs.company.com/apply/..."
            value={url}
            onChange={e => setUrl(e.target.value)}
            disabled={isLoading}
            autoFocus
            spellCheck={false}
          />
          <button
            id="apply-submit-btn"
            type="submit"
            className={`job-submit-btn ${isLoading ? 'loading' : ''} ${!isValid ? 'disabled' : ''}`}
            disabled={!isValid || isLoading}
          >
            {isLoading ? (
              <>
                <span className="spinner" />
                Submitting…
              </>
            ) : (
              <>
                <span>Apply Now</span>
                <span className="btn-arrow">→</span>
              </>
            )}
          </button>
        </div>
        <p className="job-input-hint">
          Supports LinkedIn, Workday, Greenhouse, Lever, and more.
          Paste the direct application URL.
        </p>
      </div>
    </form>
  )
}
