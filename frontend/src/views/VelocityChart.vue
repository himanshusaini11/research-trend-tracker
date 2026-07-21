<template>
  <div ref="chartContainer" class="modernist" style="padding: 24px">

    <!-- Mode toggle -->
    <div v-if="!auth.isDemo && auth.isValid" style="display: flex; align-items: center; gap: 14px; margin-bottom: 24px; flex-wrap: wrap">
      <div class="seg">
        <label v-for="tab in tabs" :key="tab.value" class="seg-opt">
          <input type="radio" name="vmode" :checked="vState.mode === tab.value" @change="switchMode(tab.value)" />{{ tab.label }}
        </label>
      </div>
      <span v-if="vState.mode === 'user'" style="opacity: .6; font-size: 12px">
        Concept prominence from your {{ userPaperCount }} uploaded paper{{ userPaperCount !== 1 ? 's' : '' }}
      </span>
    </div>

    <div v-if="loading" style="opacity: .6; font-size: 14px; padding: 48px 0; text-align: center">Loading…</div>
    <div v-else-if="error" style="color: var(--mn-color-accent-700); font-size: 14px; padding: 48px 0; text-align: center">{{ error }}</div>

    <template v-else-if="concepts.length">
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 28px">
        <div>
          <h6 style="opacity: .6; margin-bottom: 10px">
            TOP 20 · {{ vState.mode === 'global' ? 'VELOCITY' : 'PROMINENCE' }}
          </h6>
          <svg ref="velocitySvg" style="width: 100%" :height="chartHeight" />
        </div>
        <div>
          <h6 style="opacity: .6; margin-bottom: 10px">
            TOP 20 · {{ vState.mode === 'global' ? 'COMPOSITE SCORE' : 'COVERAGE SCORE' }}
          </h6>
          <svg ref="compositeSvg" style="width: 100%" :height="chartHeight" />
        </div>
      </div>

      <table class="table">
        <thead>
          <tr>
            <th style="cursor: pointer" @click="sortBy('concept_name')">Concept {{ sortIndicator('concept_name') }}</th>
            <th style="cursor: pointer; text-align: right" @click="sortBy('velocity')">
              {{ vState.mode === 'global' ? 'Velocity' : 'Prominence' }} {{ sortIndicator('velocity') }}
            </th>
            <th style="cursor: pointer; text-align: right" @click="sortBy('acceleration')">
              {{ vState.mode === 'global' ? 'Acceleration' : 'Coverage' }} {{ sortIndicator('acceleration') }}
            </th>
            <th style="cursor: pointer; text-align: right" @click="sortBy('composite_score')">
              Composite {{ sortIndicator('composite_score') }}
            </th>
            <th style="text-align: right">{{ vState.mode === 'global' ? 'Trend' : 'Papers' }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="c in sortedConcepts" :key="c.concept_name">
            <td>{{ c.concept_name }}</td>
            <td style="text-align: right">{{ c.velocity >= 0 ? '+' : '' }}{{ c.velocity.toFixed(1) }}</td>
            <td style="text-align: right">{{ c.acceleration >= 0 ? '+' : '' }}{{ c.acceleration.toFixed(1) }}</td>
            <td style="text-align: right">{{ c.composite_score.toFixed(2) }}</td>
            <td style="text-align: right">
              <span v-if="vState.mode === 'user'" style="opacity: .6; font-size: 12px">{{ c.weeks_of_data }}p</span>
              <TrendBar v-else :trend="c.trend" />
            </td>
          </tr>
        </tbody>
      </table>
    </template>

    <div v-else-if="vState.mode === 'user' && !loading" style="text-align: center; padding: 48px; background: var(--mn-color-surface)">
      <p style="margin-bottom: 16px">No papers uploaded yet.</p>
      <button class="btn btn-primary" @click="$router.push('/dashboard/upload')">Upload Papers →</button>
    </div>
    <div v-else style="opacity: .6; font-size: 14px; padding: 48px 0; text-align: center">No data available.</div>
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
      .style('background',     'var(--mn-color-surface)')
      .style('border',         '1px solid var(--mn-color-divider)')
      .style('padding',        '8px 12px')
      .style('pointer-events', 'none')
      .style('font-size',      '12px')
      .style('color',          'var(--mn-color-text)')
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
  const containerWidth = chartContainer.value?.clientWidth ? chartContainer.value.clientWidth / 2 - 12 : 380
  // Mono-accent system: velocity/prominence bars use accent, composite/coverage use neutral
  drawChart(velocitySvg.value,  concepts.value, 'velocity',        containerWidth, 'var(--mn-color-accent-500)')
  drawChart(compositeSvg.value, concepts.value, 'composite_score', containerWidth, 'var(--mn-color-neutral-500)')
}

watch(concepts, (val) => { if (val.length) renderCharts() })

function drawChart(svgEl, data, field, containerWidth, fillColor) {
  if (!svgEl) return
  const sorted = [...data].sort((a, b) => b[field] - a[field]).slice(0, 20)
  const width  = containerWidth || svgEl.getBoundingClientRect().width || 380
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
    .call(g => g.selectAll('.tick line').style('stroke', 'var(--mn-color-divider)'))
    .call(g => g.selectAll('.tick text').style('fill', 'var(--mn-color-text)').style('opacity', 0.6).attr('font-size', 11))

  const tip = getTooltip()

  svg.selectAll('rect')
    .data(sorted)
    .join('rect')
    .attr('x',      d => x(d.concept_name))
    .attr('y',      d => y(d[field]))
    .attr('width',  x.bandwidth())
    .attr('height', d => Math.max(1, innerH - y(d[field])))
    .style('fill',  fillColor)
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
    .style('fill', 'var(--mn-color-text)')
    .style('opacity', 0.7)
    .attr('font-size', 9)
    .text(d => `+${Math.round(d[field])}`)

  svg.append('g')
    .attr('transform', `translate(0,${innerH})`)
    .call(d3.axisBottom(x).tickSize(0))
    .call(g => g.select('.domain').style('stroke', 'var(--mn-color-divider)'))
    .call(g => g.selectAll('.tick text')
      .style('fill', 'var(--mn-color-text)')
      .style('opacity', 0.6)
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
