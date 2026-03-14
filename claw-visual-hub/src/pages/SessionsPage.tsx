import { useEffect, useMemo, useState } from 'react'
import { fetchSessions } from '../data/api'
import type { SessionTask } from '../types'

type Filter = 'all' | SessionTask['status']

export function SessionsPage() {
  const [filter, setFilter] = useState<Filter>('all')
  const [keyword, setKeyword] = useState('')
  const [tasks, setTasks] = useState<SessionTask[]>([])
  const [error, setError] = useState('')

  useEffect(() => {
    let alive = true
    const load = async () => {
      try {
        const data = await fetchSessions()
        if (!alive) return
        setTasks(data)
        setError('')
      } catch (e) {
        if (!alive) return
        setError(String(e))
      }
    }
    load()
    const timer = setInterval(load, 20000)
    return () => {
      alive = false
      clearInterval(timer)
    }
  }, [])

  const rows = useMemo(() => {
    return tasks.filter((t) => {
      const byStatus = filter === 'all' || t.status === filter
      const byKeyword = !keyword || `${t.name} ${t.id} ${t.owner}`.toLowerCase().includes(keyword.toLowerCase())
      return byStatus && byKeyword
    })
  }, [filter, keyword, tasks])

  return (
    <section>
      <h2>会话 / 任务列表（真实数据）</h2>
      {error && <p className="hint">{error}</p>}
      <div className="toolbar">
        <input placeholder="按名称/ID/Owner 过滤" value={keyword} onChange={(e) => setKeyword(e.target.value)} />
        <select value={filter} onChange={(e) => setFilter(e.target.value as Filter)}>
          <option value="all">全部</option>
          <option value="running">running</option>
          <option value="queued">queued</option>
          <option value="failed">failed</option>
          <option value="done">done</option>
        </select>
      </div>
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>类型</th>
            <th>名称</th>
            <th>Owner</th>
            <th>状态</th>
            <th>更新时间</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              <td>{row.id}</td>
              <td>{row.type}</td>
              <td>{row.name}</td>
              <td>{row.owner}</td>
              <td><span className={`pill ${row.status}`}>{row.status}</span></td>
              <td>{row.updatedAt}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}
