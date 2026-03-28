import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useGraphState = defineStore('graphState', () => {
  const graphMode   = ref('global')
  const topN        = ref(200)
  const trendFilter = ref('all')
  const modelView   = ref('all')
  const userTopN    = ref(50)
  // Zoom transform — { x, y, k } — persisted so navigating away doesn't reset zoom
  const zoomTransform = ref({ x: 0, y: 0, k: 1 })

  return { graphMode, topN, trendFilter, modelView, userTopN, zoomTransform }
})
