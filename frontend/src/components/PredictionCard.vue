<template>
  <div class="modernist" style="margin-bottom: 12px">
    <strong style="display: block; margin-bottom: 2px; font-size: 13px; font-family: var(--mn-font-heading); font-weight: 700">
      {{ title }}
    </strong>
    <span style="opacity: .75; font-size: 13px">{{ body }}</span>
  </div>
</template>

<script setup>
defineProps({
  title: { type: String, required: true },
  body:  { type: String, default: '' },
})
</script>
