<template>
  <div class="modernist" style="min-height: 100vh; background: var(--mn-color-bg); color: var(--mn-color-text);
              display: flex; align-items: center; justify-content: center; padding: 24px">
    <div style="width: min(560px, 100%)">
      <button class="btn btn-ghost" style="margin-bottom: 24px" @click="router.push('/')">← Back</button>
      <h6 style="color: var(--mn-color-accent)">DEVELOPER PATH</h6>
      <h2 style="margin-bottom: 6px">Connect with a raw token</h2>
      <p style="opacity: .7; font-size: 14px; margin-bottom: 24px">
        Not linked from the main flow — paste a JWT minted locally.
      </p>

      <div class="field" style="margin-bottom: 14px">
        <label>JWT token</label>
        <textarea
          v-model="tokenInput" class="input" rows="5"
          placeholder="eyJhbGciOiJIUzI1NiIs…"
        ></textarea>
      </div>

      <p v-if="error" style="color: var(--mn-color-accent-700); font-size: 13px; margin-bottom: 14px">{{ error }}</p>

      <button class="btn btn-primary btn-block" :disabled="!tokenInput.trim()" @click="connect">Connect</button>

      <div class="hr"></div>

      <p style="font-size: 12.5px; opacity: .6">Mint a dev token locally:</p>
      <pre style="background: var(--mn-color-surface); padding: 12px; font-size: 12px; overflow: auto">uv run python -c "from app.core.security import create_access_token; print(create_access_token({'sub':'demo'}))"</pre>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router     = useRouter()
const auth       = useAuthStore()
const tokenInput = ref('')
const error      = ref('')

function connect() {
  const t = tokenInput.value.trim()
  if (!t) return

  try {
    auth.setToken(t)
    if (!auth.isValid) {
      auth.clear()
      error.value = 'Token is invalid or expired.'
      return
    }
    router.push('/dashboard/graph')
  } catch {
    error.value = 'Invalid token format.'
  }
}
</script>
