<template>
  <div class="modernist" style="border-right: 2px solid var(--mn-color-divider); border-bottom: 2px solid var(--mn-color-divider)">
    <div class="acc-head" @click="$emit('toggle')">
      <span>{{ title }}</span>
      <span>{{ open ? '−' : '+' }}</span>
    </div>
    <div v-if="open" class="acc-body">
      <slot />
    </div>
  </div>
</template>

<script setup>
defineProps({
  title: { type: String, required: true },
  open:  { type: Boolean, default: false },
})
defineEmits(['toggle'])
</script>
