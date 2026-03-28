<template>
  <div class="h-full overflow-auto bg-bg">
    <div class="max-w-3xl mx-auto px-6 py-8 space-y-6">

      <!-- Demo locked state -->
      <div v-if="auth.isDemo"
        class="bg-surface border border-border rounded-xl p-10 flex flex-col items-center text-center gap-4">
        <div class="text-4xl">🔒</div>
        <h2 class="text-text-primary font-semibold">Sign in to upload your papers</h2>
        <p class="text-text-muted text-sm max-w-xs">
          Create a free account to upload PDFs and build your personal research knowledge graph.
        </p>
        <button @click="$router.push('/')"
          class="px-6 py-2 bg-accent-blue text-bg text-sm font-medium rounded-lg
                 hover:bg-blue-400 transition-colors">
          Sign in / Register
        </button>
      </div>

      <template v-else>
        <!-- Header + quota -->
        <div class="flex items-start justify-between">
          <div>
            <h1 class="text-text-primary font-semibold text-lg">Upload Papers</h1>
            <p class="text-text-muted text-xs mt-0.5">Extract concepts from your own research PDFs</p>
          </div>
          <div class="text-right">
            <div class="text-text-muted text-xs uppercase tracking-wider mb-1">Lifetime uploads</div>
            <div class="text-text-primary font-mono font-semibold text-xl">
              {{ lifetimeUsed }} <span class="text-text-muted text-sm font-normal">/ 30</span>
            </div>
            <div class="text-text-muted text-[10px] mt-0.5">{{ 30 - lifetimeUsed }} remaining</div>
          </div>
        </div>

        <!-- Upload zone -->
        <div
          @dragover.prevent="dragging = true"
          @dragleave.prevent="dragging = false"
          @drop.prevent="onDrop"
          @click="fileInput?.click()"
          :class="[
            'border-2 border-dashed rounded-xl px-6 py-10 flex flex-col items-center gap-3 cursor-pointer transition-colors',
            dragging ? 'border-accent-blue bg-accent-blue/5' : 'border-border hover:border-accent-blue/50',
          ]"
        >
          <input ref="fileInput" type="file" accept=".pdf" class="hidden" @change="onFileSelect" />
          <div class="text-3xl select-none">📄</div>
          <div class="text-text-primary text-sm font-medium">
            Drop a PDF here or click to browse
          </div>
          <div class="text-text-muted text-xs">Max 20 MB · PDF only · Up to 10 active files</div>
        </div>

        <!-- Validation error -->
        <p v-if="uploadError" class="text-accent-red text-xs -mt-2">{{ uploadError }}</p>

        <!-- Upload progress -->
        <div v-if="uploading"
          class="bg-surface border border-border rounded-xl px-5 py-4 flex items-center gap-4">
          <div class="flex-1">
            <div class="text-text-primary text-xs font-medium mb-1.5">{{ pendingFilename }}</div>
            <div class="h-1.5 bg-bg rounded-full overflow-hidden">
              <div class="h-full bg-accent-blue rounded-full transition-all duration-300"
                :style="{ width: uploadProgress + '%' }" />
            </div>
          </div>
          <span class="text-text-muted text-xs font-mono">{{ uploadProgress }}%</span>
        </div>

        <!-- Active jobs -->
        <div v-if="activeJobs.length" class="space-y-2">
          <div class="text-text-muted text-xs uppercase tracking-wider">Processing</div>
          <div v-for="job in activeJobs" :key="job.job_id"
            class="bg-surface border border-border rounded-lg px-4 py-3 flex items-center gap-3">
            <span :class="statusDot(job.status)" class="w-2 h-2 rounded-full shrink-0" />
            <span class="text-text-muted text-xs flex-1 font-mono">{{ job.job_id.slice(0, 8) }}…</span>
            <span :class="statusLabel(job.status)"
              class="text-[10px] uppercase tracking-wider font-medium">
              {{ job.status }}
            </span>
          </div>
        </div>

        <!-- Processed papers list -->
        <div v-if="papers.length" class="bg-surface border border-border rounded-xl overflow-hidden">
          <div class="px-5 py-3 border-b border-border flex items-center justify-between">
            <span class="text-text-primary text-sm font-medium">Your Papers</span>
            <button @click="exportData"
              class="text-[10px] text-accent-blue hover:underline uppercase tracking-wider">
              Export JSON ↓
            </button>
          </div>
          <div v-for="(p, i) in papers" :key="p.id"
            :class="['px-5 py-3 flex items-center gap-3', i < papers.length - 1 ? 'border-b border-border/50' : '']">
            <span :class="statusDot(p.status)" class="w-2 h-2 rounded-full shrink-0" />
            <span class="text-text-primary text-xs flex-1 truncate" :title="p.filename">{{ p.filename }}</span>
            <span v-if="p.status === 'processed'" class="text-text-muted text-[10px] font-mono whitespace-nowrap">
              {{ p.concept_count }} concepts
            </span>
            <span :class="statusLabel(p.status)" class="text-[10px] uppercase tracking-wider font-medium whitespace-nowrap">
              {{ p.status }}
            </span>
          </div>
        </div>

        <!-- Empty state -->
        <div v-else-if="!uploading && !activeJobs.length"
          class="text-center text-text-muted text-sm py-4">
          No papers uploaded yet. Drop a PDF above to get started.
        </div>
      </template>

    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import api from '../services/api'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()

const fileInput    = ref(null)
const dragging     = ref(false)
const uploading    = ref(false)
const uploadProgress = ref(0)
const uploadError  = ref('')
const pendingFilename = ref('')
const papers       = ref([])
const activeJobs   = ref([])
const lifetimeUsed = ref(0)

let pollTimer = null

// ── Status helpers ─────────────────────────────────────────────────────────
function statusDot(s) {
  return {
    pending:    'bg-accent-gray',
    processing: 'bg-accent-blue animate-pulse',
    processed:  'bg-accent-green',
    complete:   'bg-accent-green',
    failed:     'bg-accent-red',
  }[s] ?? 'bg-accent-gray'
}

function statusLabel(s) {
  return {
    pending:    'text-text-muted',
    processing: 'text-accent-blue',
    processed:  'text-accent-green',
    complete:   'text-accent-green',
    failed:     'text-accent-red',
  }[s] ?? 'text-text-muted'
}

// ── File handling ──────────────────────────────────────────────────────────
function onDrop(e) {
  dragging.value = false
  const file = e.dataTransfer.files[0]
  if (file) uploadFile(file)
}

function onFileSelect(e) {
  const file = e.target.files[0]
  if (file) uploadFile(file)
  e.target.value = ''
}

async function uploadFile(file) {
  uploadError.value = ''

  if (!file.name.toLowerCase().endsWith('.pdf')) {
    uploadError.value = 'Only PDF files are accepted'
    return
  }
  if (file.size > 20 * 1024 * 1024) {
    uploadError.value = 'File exceeds 20 MB limit'
    return
  }

  pendingFilename.value = file.name
  uploading.value = true
  uploadProgress.value = 0

  try {
    const formData = new FormData()
    formData.append('file', file)

    const result = await api.uploadPaper(formData, (pct) => {
      uploadProgress.value = pct
    })

    // Add to active jobs for polling
    activeJobs.value.unshift({ job_id: result.job_id, status: 'pending' })
    lifetimeUsed.value += 1
    startPolling()
    await loadPapers()
  } catch (e) {
    uploadError.value = e.response?.data?.detail ?? 'Upload failed'
  } finally {
    uploading.value = false
    uploadProgress.value = 0
    pendingFilename.value = ''
  }
}

// ── Polling ────────────────────────────────────────────────────────────────
function startPolling() {
  if (pollTimer) return
  pollTimer = setInterval(pollJobs, 3000)
}

async function pollJobs() {
  if (!activeJobs.value.length) {
    clearInterval(pollTimer)
    pollTimer = null
    return
  }

  const pending = activeJobs.value.filter(j => !['complete', 'failed'].includes(j.status))
  if (!pending.length) {
    clearInterval(pollTimer)
    pollTimer = null
    await loadPapers()
    return
  }

  await Promise.all(pending.map(async (job) => {
    try {
      const updated = await api.getJobStatus(job.job_id)
      job.status = updated.status
      if (updated.status === 'complete') await loadPapers()
    } catch { /* ignore transient errors */ }
  }))
}

// ── Data loading ───────────────────────────────────────────────────────────
async function loadPapers() {
  try {
    papers.value = await api.getUserPapers()
    // Estimate lifetime from active papers (server is authoritative)
  } catch { /* ignore */ }
}

async function exportData() {
  try {
    await api.exportUserData()
  } catch (e) {
    alert(e.response?.data?.detail ?? 'Export failed')
  }
}

onMounted(async () => {
  if (!auth.isDemo) {
    await loadPapers()
    // Resume polling for any in-progress jobs
    const inProgress = papers.value.filter(p => ['pending', 'processing'].includes(p.status))
    if (inProgress.length) startPolling()
  }
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>
