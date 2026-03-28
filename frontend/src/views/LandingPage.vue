<template>
  <div class="min-h-screen bg-bg text-text-primary flex flex-col">

    <!-- Top nav -->
    <header class="border-b border-border px-6 py-4 flex items-center justify-between">
      <div class="flex items-center gap-2">
        <span class="text-accent-blue text-2xl">◈</span>
        <span class="text-text-primary font-semibold text-sm tracking-wide">Research Trend Tracker</span>
      </div>
      <div class="flex items-center gap-3">
        <a
          href="https://github.com"
          target="_blank"
          class="text-text-muted hover:text-text-primary text-xs transition-colors"
        >GitHub</a>
        <button
          @click="showLogin = true"
          class="text-xs text-text-muted border border-border px-4 py-1.5 rounded-lg
                 hover:border-accent-blue hover:text-text-primary transition-colors"
        >
          Sign in
        </button>
      </div>
    </header>

    <!-- Hero -->
    <section class="flex-1 flex flex-col items-center justify-center text-center px-6 py-20">
      <div class="text-accent-blue text-6xl mb-6 select-none">◈</div>
      <h1 class="text-4xl sm:text-5xl font-bold text-text-primary mb-4 leading-tight">
        Research Trend Tracker
      </h1>
      <p class="text-text-muted text-lg sm:text-xl max-w-2xl mb-10">
        AI-powered research trend intelligence engine — graph-grounded predictions from 145K arXiv papers.
      </p>
      <div class="flex items-center gap-4 flex-wrap justify-center">
        <button
          @click="enterDemo"
          class="px-8 py-3 bg-accent-blue text-bg font-semibold rounded-lg
                 hover:bg-blue-400 transition-colors text-sm"
        >
          Live Demo
        </button>
        <button
          @click="showLogin = true"
          class="px-8 py-3 border border-border text-text-primary font-semibold rounded-lg
                 hover:border-accent-blue transition-colors text-sm"
        >
          Sign In
        </button>
      </div>
      <p class="text-text-muted/60 text-xs mt-4">Demo is read-only · No account required</p>
    </section>

    <!-- Feature cards -->
    <section class="px-6 pb-16 max-w-5xl mx-auto w-full">
      <h2 class="text-center text-text-muted text-xs uppercase tracking-widest mb-8">What's inside</h2>
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div v-for="f in features" :key="f.title"
          class="bg-surface border border-border rounded-xl p-5 hover:border-accent-blue/40 transition-colors">
          <div class="text-2xl mb-3">{{ f.icon }}</div>
          <h3 class="text-text-primary font-semibold text-sm mb-1.5">{{ f.title }}</h3>
          <p class="text-text-muted text-xs leading-relaxed">{{ f.desc }}</p>
        </div>
      </div>
    </section>

    <!-- Tech stack -->
    <section class="border-t border-border px-6 py-10 max-w-5xl mx-auto w-full">
      <h2 class="text-center text-text-muted text-xs uppercase tracking-widest mb-6">Built with</h2>
      <div class="flex flex-wrap justify-center gap-3">
        <span v-for="t in techStack" :key="t"
          class="px-3 py-1.5 bg-surface border border-border rounded-full text-xs text-text-muted
                 hover:border-accent-blue/40 hover:text-text-primary transition-colors">
          {{ t }}
        </span>
      </div>
    </section>

    <!-- Footer -->
    <footer class="border-t border-border px-6 py-4 flex items-center justify-between text-xs text-text-muted">
      <span>v2.3.0</span>
      <a href="https://github.com" target="_blank"
        class="hover:text-text-primary transition-colors">
        GitHub →
      </a>
    </footer>

    <!-- Login modal -->
    <LoginModal v-if="showLogin" @close="showLogin = false" />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import LoginModal from '../components/LoginModal.vue'
import { useAuthStore } from '../stores/auth'
import api from '../services/api'

const router   = useRouter()
const auth     = useAuthStore()
const showLogin = ref(false)

const features = [
  {
    icon: '⬡',
    title: 'Knowledge Graph',
    desc: 'Force-directed graph of 200 AI/ML concepts extracted from 145K papers. Explore co-occurrence and centrality.',
  },
  {
    icon: '◎',
    title: 'Trend Prediction',
    desc: 'LLM-synthesized reports identify emerging directions, unexplored gaps, and predicted convergences.',
  },
  {
    icon: '⟿',
    title: 'Velocity Tracking',
    desc: 'Week-over-week velocity and acceleration signals reveal which concepts are gaining or losing momentum.',
  },
  {
    icon: '◉',
    title: 'Paper Analysis',
    desc: 'Apache AGE graph connects 144,997 papers via MENTIONS and CO_OCCURS_WITH edges for deep concept analysis.',
  },
]

const techStack = [
  'FastAPI', 'PostgreSQL', 'TimescaleDB', 'Apache AGE',
  'Redis', 'Airflow', 'Ollama', 'Vue 3', 'D3.js', 'Python 3.12',
]

async function enterDemo() {
  try {
    const data = await api.getDemoToken()
    auth.setToken(data.access_token)
    router.push('/dashboard/graph')
  } catch {
    // Fallback: open login modal
    showLogin.value = true
  }
}
</script>
