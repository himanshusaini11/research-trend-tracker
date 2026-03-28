import { ref, watch } from 'vue'

const STORAGE_KEY = 'rtt-theme'

// Module-level singleton so all components share the same theme state
const _theme = ref(localStorage.getItem(STORAGE_KEY) || 'system')

function _resolve(mode) {
  if (mode === 'dark')  return 'dark'
  if (mode === 'light') return 'light'
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function _apply(mode) {
  document.documentElement.setAttribute('data-theme', _resolve(mode))
  window.dispatchEvent(new CustomEvent('rtt-theme-change'))
}

// Keep in sync when OS preference changes while mode === 'system'
window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
  if (_theme.value === 'system') _apply('system')
})

// Apply on load (before any component mounts)
_apply(_theme.value)

watch(_theme, (mode) => {
  localStorage.setItem(STORAGE_KEY, mode)
  _apply(mode)
})

export function useTheme() {
  function setTheme(mode) { _theme.value = mode }
  return { theme: _theme, setTheme }
}
