import * as React from 'react'
import { useState, useRef } from 'react'
import './IdentityPanel.css'

const API_URL = import.meta.env.VITE_API_URL || ''

interface Props {
  onIdentityLoaded: () => void
}

export function IdentityPanel({ onIdentityLoaded }: Props) {
  const [csvStatus, setCsvStatus] = useState<'idle' | 'uploading' | 'done' | 'error'>('idle')
  const [pdfStatus, setPdfStatus] = useState<'idle' | 'uploading' | 'done' | 'error'>('idle')
  const [csvFields, setCsvFields] = useState<string[]>([])
  const [pdfKb, setPdfKb] = useState<number | null>(null)
  const csvRef = useRef<HTMLInputElement>(null)
  const pdfRef = useRef<HTMLInputElement>(null)

  const uploadCsv = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setCsvStatus('uploading')
    const form = new FormData()
    form.append('file', file)
    try {
      const r = await fetch(`${API_URL}/api/identity/csv`, { method: 'POST', body: form })
      const data = await r.json()
      if (!r.ok) throw new Error(data.detail)
      setCsvFields(data.fields_loaded || [])
      setCsvStatus('done')
      onIdentityLoaded()
    } catch {
      setCsvStatus('error')
    }
  }

  const uploadPdf = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setPdfStatus('uploading')
    const form = new FormData()
    form.append('file', file)
    try {
      const r = await fetch(`${API_URL}/api/identity/resume`, { method: 'POST', body: form })
      const data = await r.json()
      if (!r.ok) throw new Error(data.detail)
      setPdfKb(data.size_kb)
      setPdfStatus('done')
    } catch {
      setPdfStatus('error')
    }
  }

  return (
    <div className="identity-panel" id="identity-panel">
      <h2 className="section-title">
        <span>🪪</span> Your Identity Data
      </h2>
      <div className="identity-grid">
        {/* CSV Upload */}
        <div className={`identity-card ${csvStatus}`}>
          <div className="identity-card-icon">📋</div>
          <div className="identity-card-body">
            <div className="identity-card-title">Identity CSV</div>
            <div className="identity-card-sub">
              {csvStatus === 'done'
                ? `${csvFields.length} fields loaded: ${csvFields.slice(0, 3).join(', ')}…`
                : 'Upload your identity.csv file'}
            </div>
          </div>
          <label className={`identity-upload-btn ${csvStatus === 'uploading' ? 'loading' : ''}`}>
            {csvStatus === 'done' ? '✓ Loaded' : csvStatus === 'uploading' ? '…' : 'Upload CSV'}
            <input
              id="csv-upload-input"
              ref={csvRef}
              type="file"
              accept=".csv"
              style={{ display: 'none' }}
              onChange={uploadCsv}
            />
          </label>
        </div>

        {/* PDF Upload */}
        <div className={`identity-card ${pdfStatus}`}>
          <div className="identity-card-icon">📄</div>
          <div className="identity-card-body">
            <div className="identity-card-title">Resume PDF</div>
            <div className="identity-card-sub">
              {pdfStatus === 'done'
                ? `${pdfKb} KB uploaded`
                : 'Upload your resume.pdf file'}
            </div>
          </div>
          <label className={`identity-upload-btn ${pdfStatus === 'uploading' ? 'loading' : ''}`}>
            {pdfStatus === 'done' ? '✓ Loaded' : pdfStatus === 'uploading' ? '…' : 'Upload PDF'}
            <input
              id="pdf-upload-input"
              ref={pdfRef}
              type="file"
              accept=".pdf"
              style={{ display: 'none' }}
              onChange={uploadPdf}
            />
          </label>
        </div>
      </div>
      <p className="identity-hint">
        Files are stored locally on the server. Not sent to any cloud service.
      </p>
    </div>
  )
}
