<template>
  <div class="modernist">
    <div class="dialog-backdrop" @click.self="$emit('close')">
      <div class="dialog">
        <div style="display: flex; justify-content: space-between; align-items: center">
          <h4 class="dialog-title" style="margin: 0">{{ isRegister ? 'Create account' : 'Sign in' }}</h4>
          <button class="btn btn-icon" @click="$emit('close')">×</button>
        </div>

        <form @submit.prevent="submit" style="display: contents">
          <div class="field">
            <label>Email</label>
            <input v-model="email" class="input" type="email" autocomplete="email" />
          </div>
          <div class="field">
            <label>Password</label>
            <input
              v-model="password" class="input" type="password"
              :autocomplete="isRegister ? 'new-password' : 'current-password'"
            />
          </div>

          <p v-if="errorMsg" style="color: var(--mn-color-accent-700); font-size: 13px; margin: 0">
            {{ errorMsg }}
          </p>

          <button type="submit" class="btn btn-primary btn-block" :disabled="loading">
            {{ loading ? 'Please wait…' : (isRegister ? 'Create account' : 'Sign in') }}
          </button>
        </form>

        <p style="text-align: center; font-size: 13px; margin: 0">
          <a href="#" @click.prevent="toggle">
            {{ isRegister ? 'Already have an account? Sign in' : "Don't have an account? Register" }}
          </a>
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const emit   = defineEmits(['close'])
const router = useRouter()
const auth   = useAuthStore()

const email      = ref('')
const password   = ref('')
const errorMsg   = ref('')
const loading    = ref(false)
const isRegister = ref(false)

function toggle() {
  isRegister.value = !isRegister.value
  errorMsg.value   = ''
}

async function submit() {
  errorMsg.value = ''

  if (!email.value.trim() || !password.value.trim()) {
    errorMsg.value = 'Email and password are required.'
    return
  }

  loading.value = true
  try {
    const err = isRegister.value
      ? await auth.register(email.value, password.value)
      : await auth.login(email.value, password.value)

    if (err) {
      errorMsg.value = err
    } else {
      emit('close')
      router.push('/dashboard/graph')
    }
  } finally {
    loading.value = false
  }
}
</script>
