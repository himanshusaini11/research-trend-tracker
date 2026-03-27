<template>
  <div ref="chartContainer" class="p-6">
    <div v-if="loading" class="text-text-muted text-sm py-12 text-center">Loading…</div>
    <div v-else-if="error" class="text-accent-red text-sm py-12 text-center">{{ error }}</div>

    <template v-else-if="concepts.length">
      <!-- Velocity bar chart -->
      <h3 class="text-text-muted text-xs uppercase tracking-wider mb-3">
        Velocity (145K papers, 2022–2024) — Top 20
      </h3>
      <svg ref="velocitySvg" class="w-full mb-8" :height="chartHeight" />

      <!-- Composite score chart -->
      <h3 class="text-text-muted text-xs uppercase tracking-wider mb-3">
        Composite Score — Top 20
      </h3>
      <svg ref="compositeSvg" class="w-full mb-8" :height="chartHeight" />

      <!-- Sortable data table (Fix 3) -->
      <h3 class="text-text-muted text-xs uppercase tracking-wider mb-3">All Concept Signals</h3>
      <div class="bg-surface border border-border rounded-lg overflow-hidden">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-border">
              <th
                class="text-left text-text-muted px-4 py-2 font-medium cursor-pointer
                       hover:text-text-primary select-none transition-colors"
                @click="sortBy('concept_name')"
              >
                Concept {{ sortIndicator('concept_name') }}
              </th>
              <th
                class="text-right text-text-muted px-4 py-2 font-medium cursor-pointer
                       hover:text-text-primary select-none transition-colors"
                @click="sortBy('velocity')"
              >
                Velocity {{ sortIndicator('velocity') }}
              </th>
              <th
                class="text-right text-text-muted px-4 py-2 font-medium cursor-pointer
                       hover:text-text-primary select-none transition-colors"
                @click="sortBy('acceleration')"
              >
                Acceleration {{ sortIndicator('acceleration') }}
              </th>
              <th
                class="text-right text-text-muted px-4 py-2 font-medium cursor-pointer
                       hover:text-text-primary select-none transition-colors"
                @click="sortBy('composite_score')"
              >
                Composite {{ sortIndicator('composite_score') }}
              </th>
              <th class="text-right text-text-muted px-4 py-2 font-medium">Trend</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="c in sortedConcepts" :key="c.concept_name"
              class="border-b border-border/50 hover:bg-bg/50 transition-colors"
            >
              <td class="px-4 py-2 text-text-primary">{{ c.concept_name }}</td>
              <td class="px-4 py-2 text-right font-mono"
                :class="c.velocity >= 0 ? 'text-accent-green' : 'text-accent-red'"
              >
                {{ c.velocity >= 0 ? '+' : '' }}{{ c.velocity.toFixed(1) }}
              </td>
              <td class="px-4 py-2 text-right font-mono"
                :class="c.acceleration >= 0 ? 'text-accent-green' : 'text-accent-red'"
              >
                {{ c.acceleration >= 0 ? '+' : '' }}{{ c.acceleration.toFixed(1) }}
              </td>
              <td class="px-4 py-2 text-right text-text-primary font-mono">{{ c.composite_score.toFixed(2) }}</td>
              <td class="px-4 py-2 text-right">
                <TrendBar :trend="c.trend" />
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>

    <div v-else class="text-text-muted text-sm py-12 text-center">No data available.</div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import * as d3 from 'd3'
import TrendBar from '../components/TrendBar.vue'
import api from '../services/api'

const loading        = ref(true)
const error          = ref(null)
const concepts       = ref([])
const chartContainer = ref(null)
const velocitySvg    = ref(null)
const compositeSvg   = ref(null)
const chartHeight    = 240

// Fix 3 — sortable columns
const sortKey = ref('composite_score')
const sortDir = ref('desc')

function sortBy(key) {
  if (sortKey.value === key) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortKey.value = key
    sortDir.value = key === 'concept_name' ? 'asc' : 'desc'
  }
}

function sortIndicator(key) {
  if (sortKey.value !== key) return ''
  return sortDir.value === 'asc' ? ' ▲' : ' ▼'
}

const sortedConcepts = computed(() => {
  return [...concepts.value].sort((a, b) => {
    const mul  = sortDir.value === 'asc' ? 1 : -1
    const aVal = a[sortKey.value]
    const bVal = b[sortKey.value]
    if (typeof aVal === 'string') return mul * aVal.localeCompare(bVal)
    return mul * ((aVal > bVal ? 1 : aVal < bVal ? -1 : 0))
  })
})

let resizeObserver = null

// Fix 2 — shared D3 tooltip created once, reused across charts
let d3Tooltip = null

function getTooltip() {
  if (!d3Tooltip) {
    d3Tooltip = d3.select('body').append('div')
      .attr('id', 'rtt-chart-tooltip')
      .style('position',       'absolute')
      .style('background',     '#1e1e2e')
      .style('border',         '1px solid #4a9eff')
      .style('padding',        '8px 12px')
      .style('border-radius',  '6px')
      .style('pointer-events', 'none')
      .style('font-size',      '12px')
      .style('color',          '#e2e8f0')
      .style('opacity',        0)
      .style('z-index',        9999)
  }
  return d3Tooltip
}

const trendColor = {
  accelerating: '#00d4aa',
  decelerating: '#ff6b6b',
  stable:       '#4a9eff',
}

async function load() {
  try {
    concepts.value = await api.getTopConcepts(200)
  } catch (e) {
    error.value = e.response?.status === 401
      ? 'Session expired — please log in again.'
      : (e.message ?? 'Failed to load concepts.')
  } finally {
    loading.value = false
  }
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

  // Grid lines
  svg.append('g')
    .call(d3.axisLeft(y).ticks(4).tickSize(-innerW))
    .call(g => g.select('.domain').remove())
    .call(g => g.selectAll('.tick line').attr('stroke', '#1e1e2e'))
    .call(g => g.selectAll('.tick text').attr('fill', '#64748b').attr('font-size', 11))

  // Bars with Fix 2 tooltip
  const tip = getTooltip()

  svg.selectAll('rect')
    .data(sorted)
    .join('rect')
    .attr('x',      d => x(d.concept_name))
    .attr('y',      d => y(d[field]))
    .attr('width',  x.bandwidth())
    .attr('height', d => Math.max(1, innerH - y(d[field])))
    .attr('fill',   d => trendColor[d.trend] ?? '#4a9eff')
    .attr('rx', 2)
    .on('mouseover', (event, d) => {
      tip.transition().duration(150).style('opacity', 1)
      tip.html(`
        <strong>${d.concept_name}</strong><br/>
        Velocity: ${d.velocity > 0 ? '+' : ''}${d.velocity.toFixed(1)}<br/>
        Acceleration: ${d.acceleration > 0 ? '+' : ''}${d.acceleration.toFixed(1)}<br/>
        Trend: ${d.trend}<br/>
        Weeks of data: ${d.weeks_of_data ?? '—'}
      `)
        .style('left', `${event.pageX + 12}px`)
        .style('top',  `${event.pageY - 28}px`)
    })
    .on('mousemove', (event) => {
      tip.style('left', `${event.pageX + 12}px`)
         .style('top',  `${event.pageY - 28}px`)
    })
    .on('mouseout', () => tip.transition().duration(150).style('opacity', 0))

  // Value labels on bars
  svg.selectAll('.val-label')
    .data(sorted)
    .join('text')
    .attr('class', 'val-label')
    .attr('x', d => x(d.concept_name) + x.bandwidth() / 2)
    .attr('y', d => y(d[field]) - 4)
    .attr('text-anchor', 'middle')
    .attr('fill', '#94a3b8')
    .attr('font-size', 9)
    .text(d => {
      const v = d[field]
      return v >= 0 ? `+${Math.round(v)}` : `${Math.round(v)}`
    })

  // X axis — 45° rotated labels
  svg.append('g')
    .attr('transform', `translate(0,${innerH})`)
    .call(d3.axisBottom(x).tickSize(0))
    .call(g => g.select('.domain').attr('stroke', '#1e1e2e'))
    .call(g => g.selectAll('.tick text')
      .attr('fill', '#64748b')
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
  // Remove the shared tooltip from the DOM
  if (d3Tooltip) {
    d3Tooltip.remove()
    d3Tooltip = null
  }
})
</script>
