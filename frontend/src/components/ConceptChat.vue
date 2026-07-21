<template>
  <div class="modernist" style="display: flex; flex-direction: column; gap: 8px; padding: 12px;
              background: var(--mn-color-surface); flex: 1; min-height: 0">
    <div style="display: flex; align-items: center; justify-content: space-between">
      <h6 style="margin: 0; opacity: .7">ASK ABOUT THIS CONCEPT</h6>
      <div style="display: flex; align-items: center; gap: 8px">
        <button
          class="btn btn-ghost" style="padding: 2px 8px; font-size: 11px"
          :title="thinkingMode ? 'Thinking mode ON — click to disable' : 'Enable thinking mode'"
          @click="thinkingMode = !thinkingMode"
        >{{ thinkingMode ? '💭 Think: ON' : '💭 Think' }}</button>
        <span style="opacity: .4; font-size: 10px">qwen3.5:27b</span>
      </div>
    </div>

    <!-- Message thread -->
    <div ref="messagesEl" style="overflow-y: auto; display: flex; flex-direction: column; gap: 8px; flex: 1; min-height: 0">
      <div v-for="msg in messages" :key="msg.id">
        <div v-if="msg.thinking" style="margin-bottom: 4px">
          <button
            style="font-size: 10px; opacity: .55; background: none; border: none; cursor: pointer;
                   padding: 0; color: var(--mn-color-text); display: flex; align-items: center; gap: 4px"
            @click="msg.thinkOpen = !msg.thinkOpen"
          >
            <span>{{ msg.thinkOpen ? '▾' : '▸' }}</span>
            <span>Reasoning ({{ msg.thinking.length }} chars)</span>
          </button>
          <div v-if="msg.thinkOpen"
            style="font-size: 10px; opacity: .55; border-left: 2px solid var(--mn-color-divider);
                   padding-left: 8px; margin-top: 4px; white-space: pre-wrap; max-height: 160px; overflow-y: auto">
            {{ msg.thinking }}
          </div>
        </div>
        <div :style="msg.role === 'user' ? 'display: flex; justify-content: flex-end' : 'display: flex; justify-content: flex-start'">
          <div :style="msg.role === 'user'
            ? 'align-self: flex-end; max-width: 88%; padding: 8px 10px; background: var(--mn-color-accent-100); color: var(--mn-color-accent-800); font-size: 12px; line-height: 1.5'
            : 'max-width: 88%; padding: 8px 10px; background: var(--mn-color-bg); font-size: 12px; line-height: 1.5'"
          >{{ msg.content }}</div>
        </div>
      </div>

      <div v-if="loading" style="display: flex; justify-content: flex-start">
        <div style="padding: 8px 10px; background: var(--mn-color-bg); font-size: 12px; opacity: .6">
          {{ thinkingMode ? 'Thinking…' : 'Answering…' }}
        </div>
      </div>
    </div>

    <!-- Input row -->
    <div style="display: flex; gap: 8px; margin-top: auto">
      <input
        ref="inputEl" v-model="inputText" type="text" class="input" style="flex: 1"
        placeholder="Ask a question…" :disabled="loading"
        @keydown.enter.prevent="sendMessage"
      />
      <button class="btn btn-primary" :disabled="loading || !inputText.trim()" @click="sendMessage">Ask</button>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'

const props = defineProps({
  conceptName:  { type: String, required: true },
  systemPrompt: { type: String, default: null },
})

const messages    = ref([])
const inputText   = ref('')
const loading     = ref(false)
const thinkingMode = ref(false)
const messagesEl  = ref(null)
const inputEl     = ref(null)

const OLLAMA_URL = 'http://localhost:11434/api/chat'

function scrollToBottom() {
  nextTick(() => {
    if (messagesEl.value) messagesEl.value.scrollTop = messagesEl.value.scrollHeight
  })
}

async function sendMessage() {
  if (!inputText.value.trim() || loading.value) return

  const userMsg = inputText.value.trim()
  inputText.value = ''
  messages.value.push({ id: Date.now(), role: 'user', content: userMsg })
  loading.value = true
  scrollToBottom()

  // Prepend /think token when thinking mode is on
  const effectiveMsg = thinkingMode.value ? `/think ${userMsg}` : `/no_think ${userMsg}`

  try {
    const response = await fetch(OLLAMA_URL, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model:   'qwen3.5:27b',
        stream:  false,
        messages: [
          {
            role:    'system',
            content: props.systemPrompt ??
              `You are a research assistant explaining AI/ML research concepts. \
The user is exploring a knowledge graph built from academic papers. \
Be concise (max 3 sentences), accurate, and mention research trends when relevant. \
Current concept: "${props.conceptName}"`,
          },
          ...messages.value
            .filter(m => m.id > 0)
            .map(m => ({ role: m.role, content: m.content })),
          { role: 'user', content: effectiveMsg },
        ],
      }),
    })

    const data     = await response.json()
    const msg      = data.message ?? {}
    const thinking = msg.thinking ?? null
    const content  = msg.content  ?? 'No response from Ollama.'

    // Replace the last user message (which has the /think prefix) — show clean version
    const lastIdx = messages.value.length - 1
    messages.value[lastIdx] = { ...messages.value[lastIdx], content: userMsg }

    messages.value.push({
      id:        Date.now(),
      role:      'assistant',
      content,
      thinking,
      thinkOpen: false,
    })
  } catch {
    messages.value.push({
      id:      Date.now(),
      role:    'assistant',
      content: 'Cannot connect to Ollama. Make sure it is running on port 11434.',
    })
  } finally {
    loading.value = false
    scrollToBottom()
  }
}

// Seed greeting when concept changes
watch(() => props.conceptName, (name) => {
  messages.value = [{
    id:      0,
    role:    'assistant',
    content: `I can explain "${name}" in the context of recent research. What would you like to know?`,
  }]
  inputText.value = ''
}, { immediate: true })
</script>
