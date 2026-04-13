import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '../services/api'

export const useSimulationStore = defineStore('simulation', () => {
  const running  = ref(false)
  const jobId    = ref(null)
  const result   = ref(null)
  const error    = ref(null)

  let _pollTimer = null

  async function runSimulation(topicContext = 'AI/ML research', maxRounds = 3) {
    if (running.value) return
    running.value = true
    error.value   = null
    result.value  = null

    try {
      const res = await api.runSimulation(topicContext, maxRounds)
      jobId.value = res.job_id
      _startPolling(topicContext)
    } catch (e) {
      error.value   = e.response?.data?.detail ?? e.message ?? 'Failed to start simulation.'
      running.value = false
    }
  }

  function _startPolling(topicContext) {
    _pollTimer = setInterval(async () => {
      try {
        const rows = await api.getSimulationResults(topicContext, 1)
        if (rows.length > 0) {
          result.value  = rows[0]
          running.value = false
          clearInterval(_pollTimer)
          _pollTimer = null
        }
      } catch (_) {
        // keep polling — transient errors are expected while the task runs
      }
    }, 5000)
  }

  function reset() {
    if (_pollTimer) {
      clearInterval(_pollTimer)
      _pollTimer = null
    }
    running.value = false
    jobId.value   = null
    result.value  = null
    error.value   = null
  }

  return { running, jobId, result, error, runSimulation, reset }
})
