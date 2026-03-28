<template>
  <div class="bg-bg border border-border rounded-lg overflow-hidden">
    <div class="px-3 py-2 border-b border-border flex items-center justify-between">
      <span class="text-text-muted text-xs uppercase tracking-wider">Ask AI about this concept</span>
      <div class="flex items-center gap-2">
        <button
          @click="thinkingMode = !thinkingMode"
          :title="thinkingMode ? 'Thinking mode ON — click to disable' : 'Enable thinking mode'"
          :class="[
            'text-[10px] px-2 py-0.5 rounded border transition-colors',
            thinkingMode
              ? 'border-accent-blue/60 text-accent-blue bg-accent-blue/10'
              : 'border-border text-text-muted/50 hover:text-text-muted',
          ]"
        >💭 Think</button>
        <span class="text-text-muted/50 text-[10px]">qwen3.5:27b</span>
      </div>
    </div>

    <!-- Message thread -->
    <div ref="messagesEl" class="overflow-y-auto p-3 space-y-2" style="max-height: 280px">
      <div v-for="msg in messages" :key="msg.id">
        <!-- Thinking block (collapsible) -->
        <div v-if="msg.thinking" class="mb-1">
          <button
            @click="msg.thinkOpen = !msg.thinkOpen"
            class="text-[10px] text-text-muted/50 hover:text-text-muted flex items-center gap-1 transition-colors"
          >
            <span>{{ msg.thinkOpen ? '▾' : '▸' }}</span>
            <span>Reasoning ({{ msg.thinking.length }} chars)</span>
          </button>
          <div v-if="msg.thinkOpen"
            class="mt-1 text-[10px] text-text-muted/70 bg-surface border border-border/50
                   rounded px-2 py-2 leading-relaxed whitespace-pre-wrap max-h-40 overflow-y-auto">
            {{ msg.thinking }}
          </div>
        </div>
        <!-- Message bubble -->
        <div :class="msg.role === 'user' ? 'flex justify-end' : 'flex justify-start'">
          <div :class="[
            'text-xs rounded-lg px-3 py-2 max-w-[85%] leading-relaxed text-text-primary',
            msg.role === 'user'
              ? 'bg-accent-blue/10 border border-accent-blue/20'
              : 'bg-bg border border-border',
          ]">{{ msg.content }}</div>
        </div>
      </div>

      <!-- Thinking indicator -->
      <div v-if="loading" class="flex justify-start">
        <div class="text-text-muted text-xs rounded-lg px-3 py-2 bg-bg border border-border">
          <span class="animate-pulse">{{ thinkingMode ? 'Thinking…' : 'Answering…' }}</span>
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
      >Ask</button>
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
The user is exploring a knowledge graph built from 145,000 academic papers published between 2022 and 2024. \
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
