<template>
  <!-- Backdrop -->
  <div
    class="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4"
    @click.self="$emit('close')"
  >
    <div class="bg-surface border border-border rounded-xl p-8 w-full max-w-md shadow-2xl">
      <!-- Header -->
      <div class="flex items-center justify-between mb-6">
        <div>
          <h2 class="text-text-primary font-semibold">{{ isRegister ? 'Create account' : 'Sign in' }}</h2>
          <p class="text-text-muted text-xs mt-0.5">Research Trend Tracker</p>
        </div>
        <button
          @click="$emit('close')"
          class="text-text-muted hover:text-text-primary text-xl leading-none transition-colors"
        >×</button>
      </div>

      <!-- Form -->
      <form @submit.prevent="submit" class="space-y-4">
        <div>
          <label class="block text-text-muted text-xs uppercase tracking-wider mb-1.5">Email</label>
          <input
            v-model="email"
            type="email"
            required
            autocomplete="email"
            placeholder="you@example.com"
            class="w-full bg-bg border border-border text-text-primary text-sm rounded-lg
                   px-3 py-2.5 focus:outline-none focus:border-accent-blue
                   placeholder:text-text-muted transition-colors"
          />
        </div>

        <div>
          <label class="block text-text-muted text-xs uppercase tracking-wider mb-1.5">Password</label>
          <input
            v-model="password"
            type="password"
            required
            :autocomplete="isRegister ? 'new-password' : 'current-password'"
            placeholder="••••••••"
            class="w-full bg-bg border border-border text-text-primary text-sm rounded-lg
                   px-3 py-2.5 focus:outline-none focus:border-accent-blue
                   placeholder:text-text-muted transition-colors"
          />
        </div>

        <p v-if="errorMsg" class="text-accent-red text-xs">{{ errorMsg }}</p>

        <button
          type="submit"
          :disabled="loading"
          class="w-full bg-accent-blue text-bg font-medium py-2.5 rounded-lg
                 hover:bg-blue-400 disabled:opacity-50 disabled:cursor-not-allowed
                 transition-colors text-sm"
        >
          {{ loading ? 'Please wait…' : (isRegister ? 'Create account' : 'Sign in') }}
        </button>
      </form>

      <!-- Toggle -->
      <p class="text-text-muted text-xs text-center mt-5">
        {{ isRegister ? 'Already have an account?' : "Don't have an account?" }}
        <button
          @click="toggle"
          class="text-accent-blue hover:underline ml-1"
        >
          {{ isRegister ? 'Sign in' : 'Register' }}
        </button>
      </p>
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
  loading.value  = true
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
