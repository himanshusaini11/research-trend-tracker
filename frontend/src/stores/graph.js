import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '../services/api'

export const useGraphStore = defineStore('graph', () => {
  const concepts = ref([])
  const loading  = ref(false)
  const error    = ref(null)

  async function fetchConcepts(topN = 20, trendFilter = 'all') {
    loading.value = true
    error.value   = null
    try {
      concepts.value = await api.getTopConcepts(topN, trendFilter)
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  return { concepts, loading, error, fetchConcepts }
})
