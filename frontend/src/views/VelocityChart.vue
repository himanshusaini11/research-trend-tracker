<template>
  <div class="p-6">
    <div v-if="loading" class="text-text-muted text-sm py-12 text-center">Loading…</div>
    <div v-else-if="error" class="text-accent-red text-sm py-12 text-center">{{ error }}</div>

    <template v-else-if="concepts.length">
      <!-- Velocity bar chart -->
      <h3 class="text-text-muted text-xs uppercase tracking-wider mb-3">
        Velocity (citations/week)
      </h3>
      <svg ref="velocitySvg" class="w-full mb-8" :height="chartHeight" />

      <!-- Composite score chart -->
      <h3 class="text-text-muted text-xs uppercase tracking-wider mb-3">
        Composite Score
      </h3>
      <svg ref="compositeSvg" class="w-full mb-8" :height="chartHeight" />

      <!-- Data table -->
      <h3 class="text-text-muted text-xs uppercase tracking-wider mb-3">All Concept Signals</h3>
      <div class="bg-surface border border-border rounded-lg overflow-hidden">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-border">
              <th class="text-left text-text-muted px-4 py-2 font-medium">Concept</th>
              <th class="text-right text-text-muted px-4 py-2 font-medium">Velocity</th>
              <th class="text-right text-text-muted px-4 py-2 font-medium">Acceleration</th>
              <th class="text-right text-text-muted px-4 py-2 font-medium">Composite</th>
              <th class="text-right text-text-muted px-4 py-2 font-medium">Trend</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="c in concepts" :key="c.concept_name"
              class="border-b border-border/50 hover:bg-bg/50 transition-colors"
            >
              <td class="px-4 py-2 text-text-primary">{{ c.concept_name }}</td>
              <td class="px-4 py-2 text-right text-text-primary font-mono">{{ c.velocity.toFixed(3) }}</td>
              <td class="px-4 py-2 text-right font-mono"
                :class="c.acceleration >= 0 ? 'text-accent-green' : 'text-accent-red'"
              >
                {{ c.acceleration >= 0 ? '+' : '' }}{{ c.acceleration.toFixed(3) }}
              </td>
              <td class="px-4 py-2 text-right text-text-primary font-mono">{{ c.composite_score.toFixed(3) }}</td>
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
import { ref, watch, onMounted, nextTick } from 'vue'
import * as d3 from 'd3'
import TrendBar from '../components/TrendBar.vue'
import api from '../services/api'

const loading     = ref(true)
const error       = ref(null)
const concepts    = ref([])
const velocitySvg  = ref(null)
const compositeSvg = ref(null)
const chartHeight  = 240

const trendColor = {
  accelerating: '#00d4aa',
  decelerating: '#ff6b6b',
  stable:       '#4a9eff',
}

async function load() {
  try {
    concepts.value = await api.getTopConcepts()
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

async function renderCharts() {
  await nextTick()
  // Use the container's actual rendered width; SVG ref gives clientWidth=0 before paint
  const containerWidth = velocitySvg.value?.parentElement?.clientWidth || 800
  drawChart(velocitySvg.value, concepts.value, 'velocity', containerWidth)
  drawChart(compositeSvg.value, concepts.value, 'composite_score', containerWidth)
}

watch(concepts, (val) => { if (val.length) renderCharts() })

function drawChart(svgEl, data, field, containerWidth) {
  if (!svgEl) return
  const sorted = [...data].sort((a, b) => b[field] - a[field])
  const width  = containerWidth || svgEl.getBoundingClientRect().width || 800
  const margin = { top: 10, right: 20, bottom: 90, left: 55 }
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

  const y = d3.scaleLinear()
    .domain([0, d3.max(sorted, d => d[field]) * 1.1])
    .range([innerH, 0])

  // Grid lines
  svg.append('g')
    .call(d3.axisLeft(y).ticks(4).tickSize(-innerW))
    .call(g => g.select('.domain').remove())
    .call(g => g.selectAll('.tick line').attr('stroke', '#1e1e2e'))
    .call(g => g.selectAll('.tick text').attr('fill', '#64748b').attr('font-size', 11))

  // Bars
  const tooltip = d3.select('body').select('#d3-tooltip')

  svg.selectAll('rect')
    .data(sorted)
    .join('rect')
    .attr('x', d => x(d.concept_name))
    .attr('y', d => y(d[field]))
    .attr('width', x.bandwidth())
    .attr('height', d => innerH - y(d[field]))
    .attr('fill', d => trendColor[d.trend] ?? '#4a9eff')
    .attr('rx', 2)
    .on('mouseover', (event, d) => {
      tooltip
        .style('display', 'block')
        .style('left', `${event.pageX + 12}px`)
        .style('top', `${event.pageY - 28}px`)
        .html(`
          <div style="font-weight:500">${d.concept_name}</div>
          <div>velocity: ${d.velocity.toFixed(3)}</div>
          <div>acceleration: ${d.acceleration.toFixed(3)}</div>
          <div>trend: ${d.trend}</div>
        `)
    })
    .on('mousemove', (event) => {
      tooltip
        .style('left', `${event.pageX + 12}px`)
        .style('top', `${event.pageY - 28}px`)
    })
    .on('mouseout', () => tooltip.style('display', 'none'))

  // X axis
  svg.append('g')
    .attr('transform', `translate(0,${innerH})`)
    .call(d3.axisBottom(x).tickSize(0))
    .call(g => g.select('.domain').attr('stroke', '#1e1e2e'))
    .call(g => g.selectAll('.tick text')
      .attr('fill', '#64748b')
      .attr('font-size', 10)
      .attr('transform', 'rotate(-40)')
      .style('text-anchor', 'end')
    )
}

onMounted(load)

</script>
