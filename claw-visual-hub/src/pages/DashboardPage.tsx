import { useEffect, useState } from 'react'
import { fetchDashboardCards } from '../data/api'
import type { SystemCard } from '../types'

export function DashboardPage() {
  const [cards, setCards] = useState<SystemCard[]>([])
  const [error, setError] = useState('')

  useEffect(() => {
    let alive = true
    const load = async () => {
      try {
        const data = await fetchDashboardCards()
        if (!alive) return
        setCards(data)
        setError('')
      } catch (e) {
        if (!alive) return
        setError(String(e))
      }
    }
    load()
    const timer = setInterval(load, 15000)
    return () => {
      alive = false
      clearInterval(timer)
    }
  }, [])

  return (
    <section>
      <h2>系统状态（真实数据）</h2>
      {error && <p className="hint">{error}</p>}
      <div className="card-grid">
        {cards.map((card) => (
          <article key={card.key} className="card">
            <div className="card-top">
              <span>{card.label}</span>
              <span className={`dot ${card.status}`} />
            </div>
            <div className="card-value">{card.value}</div>
          </article>
        ))}
      </div>
    </section>
  )
}
