import express from 'express'
import cors from 'cors'
import { execFile } from 'node:child_process'
import { promisify } from 'node:util'

const execFileAsync = promisify(execFile)
const app = express()
const cache = new Map()

const PORT = Number(process.env.PORT || 19190)
const HOST = process.env.HOST || '0.0.0.0'
const OPENCLAW_BIN = process.env.OPENCLAW_BIN || '/home/chenyechao/.npm-global/bin/openclaw'
const APP_ORIGIN = process.env.APP_ORIGIN || '*'

app.use(cors({ origin: APP_ORIGIN === '*' ? true : APP_ORIGIN }))

function extractFirstJsonBlock(text) {
  const start = text.indexOf('{')
  const end = text.lastIndexOf('}')
  if (start < 0 || end < 0 || end <= start) throw new Error('No JSON object found in output')
  return JSON.parse(text.slice(start, end + 1))
}

async function runOpenClaw(args) {
  const { stdout, stderr } = await execFileAsync(OPENCLAW_BIN, args, {
    maxBuffer: 20 * 1024 * 1024,
    env: process.env,
  })
  // openclaw frequently prints config warnings before JSON; ignore unless command fails
  return { stdout: stdout ?? '', stderr: stderr ?? '' }
}

async function withCache(key, ttlMs, loader) {
  const now = Date.now()
  const hit = cache.get(key)
  if (hit && hit.expiresAt > now && hit.value !== undefined) return hit.value
  if (hit?.promise) return hit.promise
  const promise = loader()
    .then((value) => {
      cache.set(key, { value, expiresAt: now + ttlMs })
      return value
    })
    .finally(() => {
      const current = cache.get(key)
      if (current?.promise) cache.set(key, { value: current.value, expiresAt: current.expiresAt || 0 })
    })
  cache.set(key, { ...(hit || {}), promise, expiresAt: now + ttlMs })
  return promise
}

async function getGatewayStatus() {
  return withCache('gateway-status', 2000, async () => {
    const { stdout } = await runOpenClaw(['gateway', 'status', '--json'])
    return extractFirstJsonBlock(stdout)
  })
}

async function getSessions(limit = 200) {
  return withCache(`sessions-${limit}`, 4000, async () => {
    const { stdout } = await runOpenClaw(['sessions', '--json'])
    const data = extractFirstJsonBlock(stdout)
    const sessions = Array.isArray(data.sessions) ? data.sessions.slice(0, limit) : []
    return { count: data.count ?? sessions.length, sessions }
  })
}

async function getLogs(limit = 120) {
  return withCache(`logs-${limit}`, 1500, async () => {
    const { stdout } = await runOpenClaw(['logs', '--json', '--limit', String(limit)])
    const lines = stdout
    .split('\n')
    .map((l) => l.trim())
    .filter(Boolean)
    .filter((l) => l.startsWith('{'))
    .map((l) => {
      try {
        return JSON.parse(l)
      } catch {
        return null
      }
    })
    .filter(Boolean)

    const meta = lines.find((x) => x.type === 'meta') ?? null
    const logs = lines.filter((x) => x.type === 'log').map((x) => ({
      ts: x.time,
      level: String(x.level || 'info').toUpperCase(),
      source: x.subsystem || 'openclaw',
      message: x.message || x.raw || '',
    }))

    return { meta, logs }
  })
}

app.get('/api/health', async (_req, res) => {
  try {
    const status = await getGatewayStatus()
    res.json({ ok: true, gateway: status.rpc?.ok === true, port: status.gateway?.port })
  } catch (err) {
    res.status(500).json({ ok: false, error: String(err) })
  }
})

app.get('/api/dashboard', async (_req, res) => {
  try {
    const [status, sessions, logs] = await Promise.all([
      getGatewayStatus(),
      getSessions(200),
      getLogs(200),
    ])

    const liveSessions = sessions.sessions.filter((s) => (s.ageMs ?? Number.MAX_SAFE_INTEGER) <= 30 * 60 * 1000)
    const total = logs.logs.length || 1
    const errCount = logs.logs.filter((l) => l.level === 'ERROR').length
    const warnCount = logs.logs.filter((l) => l.level === 'WARN').length

    res.json({
      cards: [
        { key: 'gateway', label: 'Gateway', value: status.rpc?.ok ? 'Online' : 'Offline', status: status.rpc?.ok ? 'healthy' : 'critical' },
        { key: 'bind', label: 'Bind', value: `${status.gateway?.bindHost || '-'}:${status.gateway?.port || '-'}`, status: 'healthy' },
        { key: 'sessions', label: 'Active Sessions(30m)', value: String(liveSessions.length), status: liveSessions.length > 0 ? 'healthy' : 'warning' },
        { key: 'sessionTotal', label: 'Total Sessions', value: String(sessions.count ?? 0), status: 'healthy' },
        { key: 'warnRate', label: 'WARN Rate', value: `${Math.round((warnCount / total) * 100)}%`, status: warnCount > 20 ? 'warning' : 'healthy' },
        { key: 'errorRate', label: 'ERROR Rate', value: `${Math.round((errCount / total) * 100)}%`, status: errCount > 0 ? 'critical' : 'healthy' },
      ],
    })
  } catch (err) {
    res.status(500).json({ error: String(err) })
  }
})

app.get('/api/sessions', async (req, res) => {
  try {
    const limit = Number(req.query.limit || 200)
    const data = await getSessions(limit)
    const rows = data.sessions.map((s) => {
      const age = s.ageMs ?? Number.MAX_SAFE_INTEGER
      const status = age < 10 * 60 * 1000 ? 'running' : age < 60 * 60 * 1000 ? 'queued' : 'done'
      return {
        id: s.sessionId || s.key,
        type: 'session',
        name: s.key,
        owner: s.agentId || 'unknown',
        status,
        updatedAt: s.updatedAt ? new Date(s.updatedAt).toLocaleString('zh-CN', { hour12: false }) : '-',
      }
    })
    res.json({ rows, count: data.count })
  } catch (err) {
    res.status(500).json({ error: String(err) })
  }
})

app.get('/api/logs', async (req, res) => {
  try {
    const limit = Number(req.query.limit || 120)
    const data = await getLogs(limit)
    res.json(data)
  } catch (err) {
    res.status(500).json({ error: String(err) })
  }
})

app.get('/api/config', async (_req, res) => {
  try {
    const status = await getGatewayStatus()
    res.json({
      gatewayUrl: status.rpc?.url || 'ws://127.0.0.1:18789',
      runtime: 'openclaw-gateway',
      logPollSeconds: 2,
      authMode: 'token-or-device',
      features: ['dashboard', 'sessions', 'logs', 'config(ro)'],
      bindHost: status.gateway?.bindHost,
      bindMode: status.gateway?.bindMode,
      controlUiAllowedOrigins: status.config?.daemon?.controlUi?.allowedOrigins || [],
    })
  } catch (err) {
    res.status(500).json({ error: String(err) })
  }
})

app.listen(PORT, HOST, () => {
  console.log(`[claw-visual-hub] API server listening on http://${HOST}:${PORT}`)
})
