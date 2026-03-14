import { useEffect, useState } from 'react'
import { fetchLogs } from '../data/api'
import type { LogItem } from '../types'

export function LogsPage() {
  const [logs, setLogs] = useState<LogItem[]>([])
  const [running, setRunning] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let alive = true
    const load = async () => {
      try {
        const data = await fetchLogs(120)
        if (!alive) return
        setLogs(data)
        setError('')
      } catch (e) {
        if (!alive) return
        setError(String(e))
      }
    }

    load()
    if (!running) return
    const timer = setInterval(load, 5000)
    return () => {
      alive = false
      clearInterval(timer)
    }
  }, [running])

  return (
    <section>
      <h2>日志流（真实网关日志）</h2>
      <button onClick={() => setRunning((v) => !v)}>{running ? '暂停' : '继续'}</button>
      {error && <p className="hint">{error}</p>}
      <div className="log-box">
        {logs.map((log, idx) => (
          <div key={`${log.ts}-${idx}`} className="log-line">
            <span>[{new Date(log.ts).toLocaleTimeString('zh-CN', { hour12: false })}]</span>
            <span className={`lv ${log.level.toLowerCase()}`}>{log.level}</span>
            <span>{log.source}</span>
            <span>{log.message}</span>
          </div>
        ))}
      </div>
    </section>
  )
}
