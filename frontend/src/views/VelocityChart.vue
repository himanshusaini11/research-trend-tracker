<template>
  <div ref="chartContainer" class="p-6">

    <!-- Mode toggle -->
    <div v-if="!auth.isDemo && auth.isValid" class="flex items-center gap-3 mb-6">
      <div class="flex items-center border border-border rounded-lg overflow-hidden">
        <button
          v-for="tab in tabs" :key="tab.value"
          @click="switchMode(tab.value)"
          :class="[
            'px-4 py-1.5 text-xs font-medium transition-colors',
            vState.mode === tab.value ? 'bg-accent-blue text-bg' : 'text-text-muted hover:text-text-primary',
          ]"
        >{{ tab.label }}</button>
      </div>
      <span v-if="vState.mode === 'user'" class="text-text-muted text-xs">
        Concept prominence from your {{ userPaperCount }} uploaded paper{{ userPaperCount !== 1 ? 's' : '' }}
      </span>
    </div>

    <div v-if="loading" class="text-text-muted text-sm py-12 text-center">Loading…</div>
    <div v-else-if="error" class="text-accent-red text-sm py-12 text-center">{{ error }}</div>

    <template v-else-if="concepts.length">
      <!-- Velocity / prominence bar chart -->
      <h3 class="text-text-muted text-xs uppercase tracking-wider mb-3">
        {{ vState.mode === 'global'
          ? 'Velocity (145K papers, 2022–2024) — Top 20'
          : 'Concept Prominence (your papers) — Top 20' }}
      </h3>
      <svg ref="velocitySvg" class="w-full mb-8" :height="chartHeight" />

      <!-- Composite score chart -->
      <h3 class="text-text-muted text-xs uppercase tracking-wider mb-3">
        {{ vState.mode === 'global' ? 'Composite Score — Top 20' : 'Coverage Score — Top 20' }}
      </h3>
      <svg ref="compositeSvg" class="w-full mb-8" :height="chartHeight" />

      <!-- Sortable data table -->
      <h3 class="text-text-muted text-xs uppercase tracking-wider mb-3">All Concept Signals</h3>
      <div class="bg-surface border border-border rounded-lg overflow-hidden">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-border">
              <th class="text-left text-text-muted px-4 py-2 font-medium cursor-pointer hover:text-text-primary select-none" @click="sortBy('concept_name')">
                Concept {{ sortIndicator('concept_name') }}
              </th>
              <th class="text-right text-text-muted px-4 py-2 font-medium cursor-pointer hover:text-text-primary select-none" @click="sortBy('velocity')">
                {{ vState.mode === 'global' ? 'Velocity' : 'Prominence' }} {{ sortIndicator('velocity') }}
              </th>
              <th class="text-right text-text-muted px-4 py-2 font-medium cursor-pointer hover:text-text-primary select-none" @click="sortBy('acceleration')">
                {{ vState.mode === 'global' ? 'Acceleration' : 'Coverage' }} {{ sortIndicator('acceleration') }}
              </th>
              <th class="text-right text-text-muted px-4 py-2 font-medium cursor-pointer hover:text-text-primary select-none" @click="sortBy('composite_score')">
                Composite {{ sortIndicator('composite_score') }}
              </th>
              <th class="text-right text-text-muted px-4 py-2 font-medium">
                {{ vState.mode === 'global' ? 'Trend' : 'Papers' }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="c in sortedConcepts" :key="c.concept_name"
              class="border-b border-border/50 hover:bg-bg/50 transition-colors">
              <td class="px-4 py-2 text-text-primary">{{ c.concept_name }}</td>
              <td class="px-4 py-2 text-right font-mono"
                :class="c.velocity >= 0 ? 'text-accent-green' : 'text-accent-red'">
                {{ c.velocity >= 0 ? '+' : '' }}{{ c.velocity.toFixed(1) }}
              </td>
              <td class="px-4 py-2 text-right font-mono"
                :class="c.acceleration >= 0 ? 'text-accent-green' : 'text-accent-red'">
                {{ c.acceleration >= 0 ? '+' : '' }}{{ c.acceleration.toFixed(1) }}
              </td>
              <td class="px-4 py-2 text-right text-text-primary font-mono">{{ c.composite_score.toFixed(2) }}</td>
              <td class="px-4 py-2 text-right">
                <span v-if="vState.mode === 'user'" class="text-text-muted text-xs">{{ c.weeks_of_data }}p</span>
                <TrendBar v-else :trend="c.trend" />
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>

    <div v-else-if="vState.mode === 'user' && !loading" class="text-center py-12 space-y-3">
      <p class="text-text-muted text-sm">No uploaded papers yet.</p>
      <button @click="$router.push('/dashboard/upload')"
        class="px-5 py-2 bg-accent-blue text-bg text-xs font-medium rounded-lg hover:bg-blue-400 transition-colors">
        Upload Papers →
      </button>
    </div>
    <div v-else class="text-text-muted text-sm py-12 text-center">No data available.</div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import * as d3 from 'd3'
import TrendBar from '../components/TrendBar.vue'
import api from '../services/api'
import { useAuthStore } from '../stores/auth'
import { useVelocityState } from '../stores/velocityState'

const auth  = useAuthStore()
const vState = useVelocityState()

const tabs = [
  { value: 'global', label: 'Global (145K papers)' },
  { value: 'user',   label: 'My Papers' },
]

const loading        = ref(true)
const error          = ref(null)
const concepts       = ref([])
const userPaperCount = ref(0)
const chartContainer = ref(null)
const velocitySvg    = ref(null)
const compositeSvg   = ref(null)
const chartHeight    = 240

function sortBy(key) {
  if (vState.sortKey === key) {
    vState.sortDir = vState.sortDir === 'asc' ? 'desc' : 'asc'
  } else {
    vState.sortKey = key
    vState.sortDir = key === 'concept_name' ? 'asc' : 'desc'
  }
}

function sortIndicator(key) {
  if (vState.sortKey !== key) return ''
  return vState.sortDir === 'asc' ? ' ▲' : ' ▼'
}

const sortedConcepts = computed(() => {
  return [...concepts.value].sort((a, b) => {
    const mul  = vState.sortDir === 'asc' ? 1 : -1
    const aVal = a[vState.sortKey]
    const bVal = b[vState.sortKey]
    if (typeof aVal === 'string') return mul * aVal.localeCompare(bVal)
    return mul * (aVal > bVal ? 1 : aVal < bVal ? -1 : 0)
  })
})

let resizeObserver = null
let d3Tooltip = null

function getTooltip() {
  if (!d3Tooltip) {
    d3Tooltip = d3.select('body').append('div')
      .attr('id', 'rtt-chart-tooltip')
      .style('position',       'absolute')
      .style('background',     'var(--canvas-tooltip-bg)')
      .style('border',         '1px solid var(--canvas-tooltip-border)')
      .style('padding',        '8px 12px')
      .style('border-radius',  '6px')
      .style('pointer-events', 'none')
      .style('font-size',      '12px')
      .style('color',          'var(--canvas-tooltip-text)')
      .style('opacity',        0)
      .style('z-index',        9999)
  }
  return d3Tooltip
}

async function load() {
  loading.value = true
  error.value   = null
  concepts.value = []
  try {
    if (vState.mode === 'global') {
      concepts.value = await api.getTopConcepts(200)
    } else {
      const papers = await api.getUserPapers()
      userPaperCount.value = papers.filter(p => p.status === 'processed').length
      concepts.value = await api.getUserVelocity()
    }
  } catch (e) {
    error.value = e.response?.status === 401
      ? 'Session expired — please log in again.'
      : (e.response?.data?.detail ?? e.message ?? 'Failed to load.')
  } finally {
    loading.value = false
  }
}

function switchMode(m) {
  vState.mode    = m
  vState.sortKey = 'composite_score'
  vState.sortDir = 'desc'
  load()
}

async function renderCharts() {
  await nextTick()
  const containerWidth = chartContainer.value?.clientWidth || 800
  drawChart(velocitySvg.value,  concepts.value, 'velocity',        containerWidth)
  drawChart(compositeSvg.value, concepts.value, 'composite_score', containerWidth)
}

watch(concepts, (val) => { if (val.length) renderCharts() })

function drawChart(svgEl, data, field, containerWidth) {
  if (!svgEl) return
  const sorted = [...data].sort((a, b) => b[field] - a[field]).slice(0, 20)
  const width  = containerWidth || svgEl.getBoundingClientRect().width || 800
  const margin = { top: 22, right: 20, bottom: 100, left: 60 }
  const innerW = width - margin.left - margin.right
  const innerH = chartHeight - margin.top - margin.bottom

  d3.select(svgEl).selectAll('*').remove()

  const svg = d3.select(svgEl)
    .attr('width', width)
    .append('g')
    .attr('transform', `translate(${margin.left},${margin.top})`)

  const x = d3.scaleBand()
    .domain(sorted.map(d => d.concept_name))
    .range([0, innerW])
    .padding(0.2)

  const maxVal = d3.max(sorted, d => d[field]) ?? 1
  const y = d3.scaleLinear()
    .domain([0, maxVal * 1.18])
    .range([innerH, 0])

  svg.append('g')
    .call(d3.axisLeft(y).ticks(4).tickSize(-innerW))
    .call(g => g.select('.domain').remove())
    .call(g => g.selectAll('.tick line').style('stroke', 'var(--canvas-tooltip-bg)'))
    .call(g => g.selectAll('.tick text').style('fill', 'rgb(var(--color-text-muted))').attr('font-size', 11))

  const tip = getTooltip()

  svg.selectAll('rect')
    .data(sorted)
    .join('rect')
    .attr('x',      d => x(d.concept_name))
    .attr('y',      d => y(d[field]))
    .attr('width',  x.bandwidth())
    .attr('height', d => Math.max(1, innerH - y(d[field])))
    .style('fill',  d => `var(--canvas-${d.trend}, var(--canvas-stable))`)
    .attr('rx', 2)
    .on('mouseover', (event, d) => {
      tip.transition().duration(150).style('opacity', 1)
      tip.html(`
        <strong>${d.concept_name}</strong><br/>
        Prominence: +${d.velocity.toFixed(1)}<br/>
        Coverage: +${d.acceleration.toFixed(1)}<br/>
        Trend: ${d.trend}<br/>
        Papers: ${d.weeks_of_data ?? '—'}
      `)
        .style('left', `${event.pageX + 12}px`)
        .style('top',  `${event.pageY - 28}px`)
    })
    .on('mousemove', (event) => {
      tip.style('left', `${event.pageX + 12}px`)
         .style('top',  `${event.pageY - 28}px`)
    })
    .on('mouseout', () => tip.transition().duration(150).style('opacity', 0))

  svg.selectAll('.val-label')
    .data(sorted)
    .join('text')
    .attr('class', 'val-label')
    .attr('x', d => x(d.concept_name) + x.bandwidth() / 2)
    .attr('y', d => y(d[field]) - 4)
    .attr('text-anchor', 'middle')
    .style('fill', 'var(--canvas-label)')
    .attr('font-size', 9)
    .text(d => `+${Math.round(d[field])}`)

  svg.append('g')
    .attr('transform', `translate(0,${innerH})`)
    .call(d3.axisBottom(x).tickSize(0))
    .call(g => g.select('.domain').style('stroke', 'var(--canvas-tooltip-bg)'))
    .call(g => g.selectAll('.tick text')
      .style('fill', 'rgb(var(--color-text-muted))')
      .attr('font-size', 10)
      .attr('transform', 'rotate(-45)')
      .style('text-anchor', 'end')
      .attr('dx', '-0.4em')
      .attr('dy', '0.1em')
    )
}

onMounted(() => {
  load().then(() => {
    if (chartContainer.value) {
      resizeObserver = new ResizeObserver(() => {
        if (concepts.value.length > 0) renderCharts()
      })
      resizeObserver.observe(chartContainer.value)
    }
  })
})

onUnmounted(() => {
  if (resizeObserver) resizeObserver.disconnect()
  if (d3Tooltip) {
    d3Tooltip.remove()
    d3Tooltip = null
  }
})
</script>
