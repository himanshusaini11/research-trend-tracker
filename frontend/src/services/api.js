import axios from 'axios'
import { useAuthStore } from '../stores/auth'

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const client = axios.create({ baseURL: BASE_URL })

client.interceptors.request.use((config) => {
  const auth = useAuthStore()
  if (auth.token) {
    config.headers.Authorization = `Bearer ${auth.token}`
  }
  return config
})

// On 401: clear token and redirect to landing page
client.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      const auth = useAuthStore()
      auth.clear()
      window.location.href = '/'
    }
    return Promise.reject(err)
  },
)

export default {
  // ── Auth ──────────────────────────────────────────────────────────────────
  async login(email, password) {
    const { data } = await client.post('/api/auth/login', { email, password })
    return data
  },

  async register(email, password) {
    const { data } = await client.post('/api/auth/register', { email, password })
    return data
  },

  async getDemoToken() {
    const { data } = await client.get('/api/auth/demo')
    return data
  },

  // ── Graph ─────────────────────────────────────────────────────────────────
  async getTopConcepts(topN = 20, trendFilter = 'all', paperFrom = null, paperTo = null) {
    const params = { top_n: topN, trend_filter: trendFilter }
    if (paperFrom) params.paper_from = paperFrom
    if (paperTo)   params.paper_to   = paperTo
    const { data } = await client.get('/graph/top-concepts', { params })
    return data
  },

  async getGraphConcepts(limit = 200, offset = 0) {
    const { data } = await client.get('/graph/concepts', { params: { limit, offset } })
    return data
  },

  async getGraphStats() {
    const { data } = await client.get('/graph/stats')
    return data
  },

  async getLatestPredictions(topicContext = 'LLM/AI research Oct-Dec 2024', limit = 5) {
    const { data } = await client.get('/graph/predictions/latest', {
      params: { topic_context: topicContext, limit },
    })
    return data
  },

  async generatePrediction(topicContext = 'LLM/AI research Oct-Dec 2024') {
    const { data } = await client.post('/graph/predictions/generate', {
      topic_context: topicContext,
    })
    return data
  },

  // ── Upload ────────────────────────────────────────────────────────────────
  async uploadPaper(formData, onProgress) {
    const { data } = await client.post('/api/upload/papers', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (e) => {
        if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100))
      },
    })
    return data
  },

  async getJobStatus(jobId) {
    const { data } = await client.get(`/api/upload/jobs/${jobId}`)
    return data
  },

  async getUserPapers() {
    const { data } = await client.get('/api/upload/papers')
    return data
  },

  async exportUserData() {
    const response = await client.get('/api/upload/export', { responseType: 'blob' })
    const url = URL.createObjectURL(response.data)
    const a = document.createElement('a')
    a.href = url
    a.download = 'rtt-my-graph.json'
    a.click()
    URL.revokeObjectURL(url)
  },

  async getUserGraph(limit = 200) {
    const { data } = await client.get('/api/user/graph', { params: { limit } })
    return data
  },

  async getUserVelocity() {
    const { data } = await client.get('/api/user/graph/velocity')
    return data
  },

  async getUserPredictions({ signal } = {}) {
    const { data } = await client.post('/api/user/graph/predict', undefined, { signal })
    return data
  },

  // ── Admin ─────────────────────────────────────────────────────────────────
  async getAdminUsers() {
    const { data } = await client.get('/api/admin/users')
    return data
  },

  async getAdminStats() {
    const { data } = await client.get('/api/admin/stats')
    return data
  },

  async toggleAdminRole(userId) {
    const { data } = await client.patch(`/api/admin/users/${userId}/toggle-admin`)
    return data
  },

  // ── Simulation (ARIS v3.0.0) ──────────────────────────────────────────────
  async runSimulation(topicContext = 'AI/ML research', maxRounds = 3) {
    const { data } = await client.post('/graph/simulation/run', {
      topic_context: topicContext,
      max_rounds: maxRounds,
    })
    return data
  },

  async getSimulationResults(topicContext = 'AI/ML research', limit = 5) {
    const { data } = await client.get('/graph/simulation/results', {
      params: { topic_context: topicContext, limit },
    })
    return data
  },
}
