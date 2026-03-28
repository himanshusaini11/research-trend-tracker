import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { jwtDecode } from 'jwt-decode'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('rtt_token') || '')
  const user  = ref(null)

  const isValid = computed(() => {
    if (!token.value) return false
    try {
      const decoded = jwtDecode(token.value)
      return decoded.exp * 1000 > Date.now()
    } catch {
      return false
    }
  })

  const isDemo = computed(() => {
    if (!token.value) return false
    try {
      return jwtDecode(token.value).role === 'demo'
    } catch {
      return false
    }
  })

  const isAdmin = computed(() => {
    if (!token.value) return false
    try {
      return jwtDecode(token.value).is_admin === true
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

  // Restore decoded user on load
  function restoreSession() {
    if (isValid.value) {
      try { user.value = jwtDecode(token.value) } catch { /* ignore */ }
    }
  }

  function setToken(t) {
    token.value = t
    localStorage.setItem('rtt_token', t)
    try { user.value = jwtDecode(t) } catch { user.value = null }
  }

  function clear() {
    token.value = ''
    user.value  = null
    localStorage.removeItem('rtt_token')
  }

  // login / register call the backend; return error string or null
  async function login(email, password) {
    const { default: api } = await import('../services/api')
    try {
      const data = await api.login(email, password)
      setToken(data.access_token)
      return null
    } catch (e) {
      return e.response?.data?.detail ?? 'Login failed'
    }
  }

  async function register(email, password) {
    const { default: api } = await import('../services/api')
    try {
      const data = await api.register(email, password)
      setToken(data.access_token)
      return null
    } catch (e) {
      return e.response?.data?.detail ?? 'Registration failed'
    }
  }

  function logout(router) {
    clear()
    if (router) router.push('/')
  }

  restoreSession()

  return { token, user, isValid, isDemo, isAdmin, expiresAt, setToken, clear, login, register, logout, restoreSession }
})
