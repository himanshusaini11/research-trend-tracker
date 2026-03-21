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

export default {
  async getTopConcepts(topN = 20, trendFilter = 'all') {
    const { data } = await client.get('/graph/top-concepts', {
      params: { top_n: topN, trend_filter: trendFilter },
    })
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
}
