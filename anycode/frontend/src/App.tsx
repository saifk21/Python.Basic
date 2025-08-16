import React, { useMemo, useState } from 'react'
import MultiFilePanel from './components/MultiFilePanel'

function useApiBase() {
	return useMemo(() => {
		return ''
	}, [])
}

type GeneratedCode = {
	code: string
	language?: string
	filename?: string
	model?: string
}

export default function App() {
	const apiBase = useApiBase()
	const [instruction, setInstruction] = useState('Generate a FastAPI service that exposes /hello returning {"message":"hi"}.')
	const [language, setLanguage] = useState('python')
	const [framework, setFramework] = useState('fastapi')
	const [filename, setFilename] = useState('service.py')
	const [temperature, setTemperature] = useState(0.2)
	const [loading, setLoading] = useState(false)
	const [error, setError] = useState<string | null>(null)
	const [result, setResult] = useState<GeneratedCode | null>(null)
	const [jobs, setJobs] = useState<Array<{ job_id: string; files: string[]; created_at: number }>>([])
	const [tab, setTab] = useState<'single' | 'multi'>('single')

	async function generate() {
		setLoading(true)
		setError(null)
		setResult(null)
		try {
			const res = await fetch(`${apiBase}/api/generate`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ instruction, language, framework, filename, temperature }),
			})
			if (!res.ok) throw new Error(`HTTP ${res.status}`)
			const data: GeneratedCode = await res.json()
			setResult(data)
		} catch (e: any) {
			setError(e?.message || 'Failed to generate')
		} finally {
			setLoading(false)
		}
	}

	async function save() {
		if (!result?.code) return
		try {
			const res = await fetch(`${apiBase}/api/save`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ code: result.code, filename: result.filename || filename }),
			})
			if (!res.ok) throw new Error(`HTTP ${res.status}`)
			await loadJobs()
		} catch (e) {
			console.error(e)
		}
	}

	async function loadJobs() {
		try {
			const res = await fetch(`${apiBase}/api/jobs`)
			if (!res.ok) throw new Error(`HTTP ${res.status}`)
			const data = await res.json()
			setJobs(data.jobs || [])
		} catch (e) {
			console.error(e)
		}
	}

	return (
		<div style={{ maxWidth: 1100, margin: '0 auto', padding: 24, fontFamily: 'Inter, system-ui, Arial' }}>
			<h1>AnyCode Generator</h1>
			<p>Describe what you want, pick a language/framework, and generate code. Save outputs as jobs.</p>

			<div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
				<button onClick={() => setTab('single')} disabled={tab === 'single'}>Single file</button>
				<button onClick={() => setTab('multi')} disabled={tab === 'multi'}>Multi file</button>
			</div>

			{tab === 'single' ? (
				<div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
					<div>
						<label>Instruction</label>
						<textarea
							value={instruction}
							onChange={(e) => setInstruction(e.target.value)}
							rows={8}
							style={{ width: '100%' }}
						/>

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
								<label>Filename</label>
								<input value={filename} onChange={(e) => setFilename(e.target.value)} style={{ width: '100%' }} />
							</div>
							<div>
								<label>Temperature</label>
								<input type="number" step="0.1" min={0} max={1} value={temperature} onChange={(e) => setTemperature(Number(e.target.value))} style={{ width: '100%' }} />
							</div>
						</div>

						<div style={{ marginTop: 12, display: 'flex', gap: 8 }}>
							<button disabled={loading} onClick={generate}>{loading ? 'Generating…' : 'Generate'}</button>
							<button disabled={!result} onClick={save}>Save</button>
						</div>
					</div>

					<div>
						<label>Result</label>
						<div style={{ border: '1px solid #ddd', borderRadius: 6, padding: 12, minHeight: 300, background: '#fafafa' }}>
							{error && <div style={{ color: 'red' }}>{error}</div>}
							{result ? (
								<pre style={{ whiteSpace: 'pre-wrap', margin: 0 }}>
									{result.code}
								</pre>
							) : (
								<div style={{ color: '#888' }}>No output yet.</div>
							)}
						</div>

						<div style={{ marginTop: 16 }}>
							<div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
								<h3 style={{ margin: 0 }}>Saved Jobs</h3>
								<button onClick={loadJobs}>Refresh</button>
							</div>
							<ul>
								{jobs.map((j) => (
									<li key={j.job_id}>
										<code>{j.job_id}</code> — {j.files.join(', ')}
									</li>
								))}
							</ul>
						</div>
					</div>
				</div>
			) : (
				<MultiFilePanel />
			)}
		</div>
	)
}