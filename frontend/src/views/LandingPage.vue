<template>
  <div class="modernist" style="min-height: 100vh; background: var(--mn-color-bg); color: var(--mn-color-text)">

    <!-- Top nav -->
    <div class="nav" style="justify-content: space-between">
      <div class="nav-brand" style="cursor: pointer" @click="router.push('/')">ALETHEIA</div>
      <div style="display: flex; align-items: center; gap: 24px">
        <a href="https://github.com" target="_blank" style="font-size: 14px">GitHub ↗</a>
        <button class="btn btn-primary" @click="showLogin = true">Sign in</button>
      </div>
    </div>

    <!-- Hero -->
    <div style="padding: 96px 64px 80px; border-bottom: 2px solid var(--mn-color-divider)">
      <div style="max-width: 760px">
        <h6 style="color: var(--mn-color-accent); margin-bottom: 14px">GRAPH-GROUNDED RESEARCH INTELLIGENCE</h6>
        <h1 style="font-size: 64px; max-width: 14ch">Watch the research frontier move before it's obvious.</h1>
        <p style="font-size: 17px; max-width: 56ch; opacity: .8; margin-bottom: 32px">
          Aletheia ingests the arXiv corpus into a live knowledge graph, tracks concept velocity over time,
          and asks a local model to synthesize where the field is heading next.
        </p>
        <div style="display: flex; gap: 14px">
          <button class="btn btn-primary" style="padding: 12px 22px; font-size: 15px" @click="enterDemo">
            Live Demo →
          </button>
          <button class="btn btn-secondary" style="padding: 12px 22px; font-size: 15px" @click="showLogin = true">
            Sign In
          </button>
        </div>
      </div>
    </div>

    <!-- Feature cards -->
    <div style="display: grid; grid-template-columns: repeat(4, 1fr)">
      <div v-for="f in featureCards" :key="f.title"
        style="padding: 36px 28px; border-right: 2px solid var(--mn-color-divider); border-bottom: 2px solid var(--mn-color-divider)">
        <div style="width: 28px; height: 28px; background: var(--mn-color-accent); margin-bottom: 20px"></div>
        <h4 style="font-size: 18px; margin-bottom: 8px">{{ f.title }}</h4>
        <p style="font-size: 13.5px; opacity: .75; margin: 0">{{ f.desc }}</p>
      </div>
    </div>

    <!-- Tech stack -->
    <div style="padding: 28px 64px; border-bottom: 2px solid var(--mn-color-divider); display: flex; gap: 10px; flex-wrap: wrap">
      <span v-for="t in techStack" :key="t" class="pill">{{ t }}</span>
    </div>

    <!-- Footer -->
    <div style="padding: 22px 64px; display: flex; justify-content: space-between; align-items: center; font-size: 12px; opacity: .6">
      <span>v3.0.0</span>
      <div style="display: flex; gap: 18px">
        <a href="https://github.com" target="_blank">GitHub</a>
        <a href="#" @click.prevent="router.push('/login')">Developer login</a>
      </div>
    </div>

    <!-- Auth modal -->
    <LoginModal v-if="showLogin" @close="showLogin = false" />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import LoginModal from '../components/LoginModal.vue'
import { useAuthStore } from '../stores/auth'
import api from '../services/api'

const router    = useRouter()
const auth      = useAuthStore()
const showLogin = ref(false)

const featureCards = [
  { title: 'Knowledge Graph',  desc: 'A live Apache AGE graph of research concepts, built from arXiv full text.' },
  { title: 'Trend Prediction', desc: 'A local model synthesizes emerging directions, gaps, and convergences.' },
  { title: 'Velocity Tracking', desc: 'Concept momentum over time — centrality, velocity, acceleration.' },
  { title: 'Paper Analysis',   desc: 'Upload your own PDFs for a personal graph and personal predictions.' },
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
    // Fallback: open the auth modal
    showLogin.value = true
  }
}
</script>
