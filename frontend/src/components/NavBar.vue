<template>
  <div class="modernist" style="display: contents">
    <div style="width: 216px; flex: none; display: flex; flex-direction: column; padding: 20px 16px;
                border-right: 2px solid var(--mn-color-divider)">
      <div
        style="font-family: var(--mn-font-heading); font-weight: var(--mn-font-heading-weight);
               font-size: 16px; margin-bottom: 24px; cursor: pointer"
        @click="router.push('/')"
      >ALETHEIA</div>

      <RouterLink
        v-for="item in items" :key="item.path" :to="item.path" custom
        v-slot="{ navigate, isExactActive }"
      >
        <button
          class="navlink"
          :style="route.path.startsWith(item.path)
            ? 'background: var(--mn-color-accent); color: var(--mn-color-bg)'
            : 'color: var(--mn-color-text); opacity: 0.75'"
          @click="navigate"
        >{{ item.label }}</button>
      </RouterLink>

      <div style="flex: 1"></div>

      <div class="seg" style="margin-bottom: 14px">
        <label v-for="t in themes" :key="t.mode" class="seg-opt">
          <input type="radio" name="theme" :checked="theme === t.mode" @change="setTheme(t.mode)" />{{ t.label }}
        </label>
      </div>
      <div style="font-size: 10.5px; opacity: .5">v3.0.0</div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { useTheme } from '../composables/useTheme'
import { useAuthStore } from '../stores/auth'

const route  = useRoute()
const router = useRouter()
const auth   = useAuthStore()
const { theme, setTheme } = useTheme()

const items = computed(() => {
  const base = [
    { path: '/dashboard/graph',       label: 'Knowledge Graph' },
    { path: '/dashboard/predictions', label: 'Predictions' },
    { path: '/dashboard/velocity',    label: 'Velocity' },
    { path: '/dashboard/simulation',  label: 'Simulation (ARIS)' },
  ]
  if (!auth.isDemo) base.push({ path: '/dashboard/upload', label: 'Upload' })
  if (auth.isAdmin)  base.push({ path: '/dashboard/admin',  label: 'Admin' })
  return base
})

const themes = [
  { mode: 'light',  label: 'Light' },
  { mode: 'system', label: 'Sys' },
  { mode: 'dark',   label: 'Dark' },
]
</script>
