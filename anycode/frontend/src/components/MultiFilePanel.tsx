import React, { useState } from 'react'

type FileSpec = {
	filename: string
	code: string
	language?: string
	purpose?: string
}

type Props = {}

export default function MultiFilePanel(props: Props) {
	const [instruction, setInstruction] = useState('Create a small Express server with a router and controller, including package.json and index.ts')
	const [language, setLanguage] = useState('typescript')
	const [framework, setFramework] = useState('express')
	const [numFiles, setNumFiles] = useState<number>(4)
	const [temperature, setTemperature] = useState(0.2)
	const [raw, setRaw] = useState('[]')
	const [loading, setLoading] = useState(false)
	const [error, setError] = useState<string | null>(null)

	async function generate() {
		setLoading(true)
		setError(null)
		try {
			const res = await fetch('/api/generate_multi', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ instruction, language, framework, num_files: numFiles, temperature }),
			})
			if (!res.ok) throw new Error(`HTTP ${res.status}`)
			const data = await res.json()
			setRaw(JSON.stringify(data.files || [], null, 2))
		} catch (e: any) {
			setError(e?.message || 'Failed to generate')
		} finally {
			setLoading(false)
		}
	}

	async function save() {
		try {
			const files: FileSpec[] = JSON.parse(raw)
			const res = await fetch('/api/save_multi', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ files }),
			})
			if (!res.ok) throw new Error(`HTTP ${res.status}`)
			alert('Saved! Check jobs list in the single-file panel.')
		} catch (e: any) {
			setError(e?.message || 'Invalid JSON or save failed')
		}
	}

	return (
		<div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
			<div>
				<h3>Multi-file generation</h3>
				<label>Instruction</label>
				<textarea value={instruction} onChange={(e) => setInstruction(e.target.value)} rows={6} style={{ width: '100%' }} />
				<div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginTop: 8 }}>
					<div>
						<label>Language</label>
						<input value={language} onChange={(e) => setLanguage(e.target.value)} style={{ width: '100%' }} />
					</div>
					<div>
						<label>Framework</label>
						<input value={framework} onChange={(e) => setFramework(e.target.value)} style={{ width: '100%' }} />
					</div>
					<div>
						<label>Approx Files</label>
						<input type="number" min={1} max={20} value={numFiles} onChange={(e) => setNumFiles(Number(e.target.value))} style={{ width: '100%' }} />
					</div>
					<div>
						<label>Temperature</label>
						<input type="number" step="0.1" min={0} max={1} value={temperature} onChange={(e) => setTemperature(Number(e.target.value))} style={{ width: '100%' }} />
					</div>
				</div>
				<div style={{ marginTop: 12, display: 'flex', gap: 8 }}>
					<button disabled={loading} onClick={generate}>{loading ? 'Generating…' : 'Generate'}</button>
					<button onClick={save}>Save All</button>
				</div>
				{error && <div style={{ color: 'red' }}>{error}</div>}
			</div>
			<div>
				<label>Files JSON</label>
				<textarea value={raw} onChange={(e) => setRaw(e.target.value)} rows={22} style={{ width: '100%', fontFamily: 'monospace' }} />
				<p style={{ color: '#666' }}>You can tweak individual files before saving.</p>
			</div>
		</div>
	)
}