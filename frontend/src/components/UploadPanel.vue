<template>
  <div class="modernist" style="height: 100%; overflow: auto; background: var(--mn-color-bg); padding: 24px">

    <!-- Demo locked state -->
    <div v-if="auth.isDemo" style="padding: 48px; text-align: center; background: var(--mn-color-surface)">
      <div style="width: 32px; height: 32px; border: 2px solid var(--mn-color-divider); margin: 0 auto 16px"></div>
      <p style="margin-bottom: 16px">Upload is disabled for the read-only demo role.</p>
      <button class="btn btn-primary" @click="$router.push('/')">Sign in / Register</button>
    </div>

    <template v-else>
      <div style="display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 20px">
        <h3 style="margin: 0">Upload Papers</h3>
        <span class="tag tag-outline">{{ lifetimeUsed }} / 30 lifetime · {{ 30 - lifetimeUsed }} remaining</span>
      </div>

      <!-- Upload zone -->
      <div
        style="border: 2px dashed var(--mn-color-divider); padding: 48px; text-align: center; margin-bottom: 24px; cursor: pointer"
        @dragover.prevent="dragging = true"
        @dragleave.prevent="dragging = false"
        @drop.prevent="onDrop"
        @click="fileInput?.click()"
        :style="dragging ? { borderColor: 'var(--mn-color-accent)' } : {}"
      >
        <input ref="fileInput" type="file" accept=".pdf" style="display: none" @change="onFileSelect" />
        <p style="margin-bottom: 6px">Drag and drop PDFs here, or click to browse</p>
        <p style="opacity: .55; font-size: 12px; margin: 0">PDF only · 20MB max · up to 10 active files</p>
      </div>

      <p v-if="uploadError" style="color: var(--mn-color-accent-700); font-size: 13px; margin-top: -16px; margin-bottom: 16px">{{ uploadError }}</p>

      <!-- Upload progress -->
      <div v-if="uploading" style="margin-bottom: 24px">
        <div style="display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 6px">
          <span>{{ pendingFilename }}</span><span>{{ uploadProgress }}%</span>
        </div>
        <div style="height: 6px; background: var(--mn-color-neutral-200)">
          <div :style="{ height: '100%', width: uploadProgress + '%', background: 'var(--mn-color-accent)' }"></div>
        </div>
      </div>

      <!-- Active jobs -->
      <template v-if="activeJobs.length">
        <h6 style="opacity: .6; margin-bottom: 10px">PROCESSING</h6>
        <div style="margin-bottom: 24px; display: flex; flex-direction: column; gap: 6px">
          <div v-for="job in activeJobs" :key="job.job_id" style="display: flex; align-items: center; gap: 10px; padding: 8px 12px; background: var(--mn-color-surface)">
            <span :style="{ width: '7px', height: '7px', flex: 'none', background: statusDotColor(job.status) }"></span>
            <span style="flex: 1; font-size: 12px; opacity: .7">{{ job.job_id.slice(0, 8) }}…</span>
            <span style="opacity: .7; font-size: 12px">{{ job.status }}</span>
          </div>
        </div>
      </template>

      <div style="display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 10px">
        <h6 style="opacity: .6; margin: 0">YOUR PAPERS</h6>
        <button class="btn btn-ghost" @click="exportData">Export JSON ↓</button>
      </div>

      <p v-if="!papers.length" style="opacity: .6">Nothing uploaded yet.</p>
      <table v-else class="table">
        <thead><tr><th></th><th>Filename</th><th>Concepts</th><th>Status</th></tr></thead>
        <tbody>
          <tr v-for="p in papers" :key="p.id">
            <td><span :style="{ width: '7px', height: '7px', display: 'inline-block', background: statusDotColor(p.status) }"></span></td>
            <td>{{ p.filename }}</td>
            <td>{{ p.status === 'processed' ? p.concept_count : '—' }}</td>
            <td>{{ p.status }}</td>
          </tr>
        </tbody>
      </table>
    </template>

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

// Status dot colors — same literal palette as the design (#5fa832 for
// success, matching the Dashboard session-status dot), accent for active
// states, mono-accent tokens for the rest since there's no separate red/gray.
function statusDotColor(s) {
  return {
    pending:    'var(--mn-color-neutral-500)',
    processing: 'var(--mn-color-accent)',
    processed:  '#5fa832',
    complete:   '#5fa832',
    failed:     'var(--mn-color-accent-2-500)',
  }[s] ?? 'var(--mn-color-neutral-500)'
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
