<template>
  <div class="bg-bg border border-border rounded-lg overflow-hidden">
    <div class="px-3 py-2 border-b border-border flex items-center justify-between">
      <span class="text-text-muted text-xs uppercase tracking-wider">Ask AI about this concept</span>
      <span class="text-text-muted/50 text-[10px]">Ollama · llama3.2</span>
    </div>

    <!-- Message thread -->
    <div
      ref="messagesEl"
      class="overflow-y-auto p-3 space-y-2"
      style="max-height: 220px"
    >
      <div
        v-for="msg in messages" :key="msg.id"
        :class="msg.role === 'user' ? 'flex justify-end' : 'flex justify-start'"
      >
        <div
          :class="[
            'text-xs rounded-lg px-3 py-2 max-w-[85%] leading-relaxed',
            msg.role === 'user'
              ? 'text-text-primary'
              : 'text-text-primary',
          ]"
          :style="msg.role === 'user'
            ? { background: 'rgba(74,158,255,0.12)', border: '1px solid rgba(74,158,255,0.2)' }
            : { background: '#0a0a0f', border: '1px solid #1e1e2e' }
          "
        >{{ msg.content }}</div>
      </div>

      <!-- Thinking indicator -->
      <div v-if="loading" class="flex justify-start">
        <div
          class="text-text-muted text-xs rounded-lg px-3 py-2"
          style="background: #0a0a0f; border: 1px solid #1e1e2e"
        >
          <span class="animate-pulse">Thinking…</span>
        </div>
      </div>
    </div>

    <!-- Input row -->
    <div class="border-t border-border px-3 py-2 flex gap-2">
      <input
        ref="inputEl"
        v-model="inputText"
        type="text"
        placeholder="Ask a question…"
        class="flex-1 bg-surface border border-border text-text-primary text-xs rounded px-3 py-1.5
               focus:outline-none focus:border-accent-blue placeholder:text-text-muted/50"
        @keydown.enter.prevent="sendMessage"
        :disabled="loading"
      />
      <button
        @click="sendMessage"
        :disabled="loading || !inputText.trim()"
        class="text-xs px-3 py-1.5 bg-accent-blue text-bg rounded font-medium
               hover:bg-blue-400 disabled:opacity-40 disabled:cursor-not-allowed transition-colors shrink-0"
      >
        Ask
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'

const props = defineProps({
  conceptName: { type: String, required: true },
})

const messages  = ref([])
const inputText = ref('')
const loading   = ref(false)
const messagesEl = ref(null)
const inputEl   = ref(null)

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

  try {
    const response = await fetch(OLLAMA_URL, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model:   'llama3.2',
        stream:  false,
        messages: [
          {
            role:    'system',
            content: `You are a research assistant explaining AI/ML research concepts. \
The user is exploring a knowledge graph built from 145,000 academic papers published between 2022 and 2024. \
Be concise (max 3 sentences), accurate, and mention research trends when relevant. \
Current concept: "${props.conceptName}"`,
          },
          ...messages.value
            .filter(m => m.id > 0)
            .map(m => ({ role: m.role, content: m.content })),
        ],
      }),
    })

    const data  = await response.json()
    const reply = data.message?.content || 'No response from Ollama.'
    messages.value.push({ id: Date.now(), role: 'assistant', content: reply })
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
    content: `I can explain "${name}" in the context of recent AI/ML research (2022–2024). What would you like to know?`,
  }]
  inputText.value = ''
}, { immediate: true })
</script>
