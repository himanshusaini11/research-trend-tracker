import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useVelocityState = defineStore('velocityState', () => {
  const mode    = ref('global')
  const sortKey = ref('composite_score')
  const sortDir = ref('desc')

  return { mode, sortKey, sortDir }
})
