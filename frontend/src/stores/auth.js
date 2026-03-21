import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { jwtDecode } from 'jwt-decode'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('rtt_token') || '')

  const isValid = computed(() => {
    if (!token.value) return false
    try {
      const decoded = jwtDecode(token.value)
      return decoded.exp * 1000 > Date.now()
    } catch {
      return false
    }
  })

  const expiresAt = computed(() => {
    if (!token.value) return null
    try {
      const decoded = jwtDecode(token.value)
      return new Date(decoded.exp * 1000)
    } catch {
      return null
    }
  })

  function setToken(t) {
    token.value = t
    localStorage.setItem('rtt_token', t)
  }

  function clear() {
    token.value = ''
    localStorage.removeItem('rtt_token')
  }

  return { token, isValid, expiresAt, setToken, clear }
})
