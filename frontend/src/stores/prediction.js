import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '../services/api'

export const usePredictionStore = defineStore('prediction', () => {
  const mode       = ref('global')   // persists across navigation
  const generating = ref(false)
  const result     = ref(null)
  const error      = ref(null)
  let _controller  = null

  async function generate() {
    if (generating.value) return
    generating.value = true
    error.value      = null
    _controller      = new AbortController()

    try {
      result.value = await api.getUserPredictions({ signal: _controller.signal })
    } catch (e) {
      // ERR_CANCELED = user clicked Stop — not an error worth surfacing
      if (e.code === 'ERR_CANCELED' || e.name === 'CanceledError') {
        error.value = null
      } else {
        error.value = e.response?.data?.detail ?? e.message ?? 'Failed to generate prediction.'
      }
    } finally {
      generating.value = false
      _controller      = null
    }
  }

  function stop() {
    if (_controller) _controller.abort()
  }

  return { mode, generating, result, error, generate, stop }
})
