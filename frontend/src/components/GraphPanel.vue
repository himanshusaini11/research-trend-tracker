<template>
  <div ref="container" class="w-full h-full relative">
    <svg ref="svg" class="w-full h-full" />

    <!-- Tooltip -->
    <div
      v-show="tooltip.visible"
      :style="{ left: tooltip.x + 'px', top: tooltip.y + 'px' }"
      class="absolute pointer-events-none bg-surface border border-border rounded-lg px-3 py-2
             text-xs shadow-lg z-20 min-w-40"
    >
      <div class="text-text-primary font-medium mb-1">{{ tooltip.name }}</div>
      <div class="text-text-muted">composite: <span class="text-text-primary">{{ tooltip.composite }}</span></div>
      <div class="text-text-muted">velocity: <span class="text-text-primary">{{ tooltip.velocity }}</span></div>
      <div class="text-text-muted">trend:
        <span :style="{ color: trendColor[tooltip.trend] }">{{ tooltip.trend }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'
import * as d3 from 'd3'

const props = defineProps({
  concepts:    { type: Array,  default: () => [] },
  trendFilter: { type: String, default: 'all' },
})

const container = ref(null)
const svg       = ref(null)
const tooltip   = ref({ visible: false, x: 0, y: 0, name: '', composite: '', velocity: '', trend: '' })

const trendColor = {
  accelerating: '#00d4aa',
  decelerating: '#ff6b6b',
  stable:       '#4a9eff',
}

function toTitleCase(name) {
  return name.split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')
}

let simulation = null
let zoomBehavior = null
let svgSelection = null
let gSelection   = null

function nodeColor(d) {
  return trendColor[d.trend] ?? '#8892a4'
}

function nodeRadius(d) {
  return Math.max(8, d.composite_score * 40 + 8)
}

function buildGraph() {
  if (!svg.value || !props.concepts.length) return

  const el     = svg.value
  const width  = el.clientWidth  || 1200
  const height = el.clientHeight || 700

  d3.select(el).selectAll('*').remove()

  svgSelection = d3.select(el)
    .attr('viewBox', `0 0 ${width} ${height}`)

  // Zoom layer
  gSelection = svgSelection.append('g')

  zoomBehavior = d3.zoom()
    .scaleExtent([0.2, 5])
    .on('zoom', (event) => gSelection.attr('transform', event.transform))

  svgSelection.call(zoomBehavior)

  // Filter by trend
  const filtered = props.trendFilter === 'all'
    ? props.concepts
    : props.concepts.filter(c => c.trend === props.trendFilter)

  // Deduplicate by normalized (lowercase) name — keep highest composite_score
  const deduped = new Map()
  for (const c of filtered) {
    const key = c.concept_name.toLowerCase()
    if (!deduped.has(key) || c.composite_score > deduped.get(key).composite_score) {
      deduped.set(key, c)
    }
  }

  const nodes = Array.from(deduped.values()).map(c => ({
    id:              c.concept_name.toLowerCase(),
    display:         toTitleCase(c.concept_name.toLowerCase()),
    composite_score: c.composite_score,
    velocity:        c.velocity,
    trend:           c.trend,
  }))

  // Derive edges using normalized (lowercase) node IDs — same keys used in deduped Map
  const links = []
  const threshold = 0.15
  for (let i = 0; i < nodes.length; i++) {
    for (let j = i + 1; j < nodes.length; j++) {
      if (Math.abs(nodes[i].composite_score - nodes[j].composite_score) < threshold) {
        // source/target reference the lowercase .id field used by d3.forceLink
        links.push({ source: nodes[i].id, target: nodes[j].id })
      }
    }
  }

  // Simulation
  simulation = d3.forceSimulation(nodes)
    .force('link',    d3.forceLink(links).id(d => d.id).distance(80).strength(0.3))
    .force('charge',  d3.forceManyBody().strength(-300))
    .force('center',  d3.forceCenter(width / 2, height / 2))
    .force('collide', d3.forceCollide(d => nodeRadius(d) + 20))

  // Edges
  const link = gSelection.append('g')
    .selectAll('line')
    .data(links)
    .join('line')
    .attr('stroke', '#1e1e2e')
    .attr('stroke-width', 1)

  // Nodes
  const node = gSelection.append('g')
    .selectAll('circle')
    .data(nodes)
    .join('circle')
    .attr('r',    d => nodeRadius(d))
    .attr('fill', d => nodeColor(d))
    .attr('fill-opacity', 0.85)
    .attr('stroke', '#0a0a0f')
    .attr('stroke-width', 1.5)
    .call(
      d3.drag()
        .on('start', (event, d) => {
          if (!event.active) simulation.alphaTarget(0.3).restart()
          d.fx = d.x; d.fy = d.y
        })
        .on('drag', (event, d) => { d.fx = event.x; d.fy = event.y })
        .on('end', (event, d) => {
          if (!event.active) simulation.alphaTarget(0)
          d.fx = null; d.fy = null
        })
    )
    .on('mouseover', (event, d) => {
      const rect = container.value.getBoundingClientRect()
      tooltip.value = {
        visible:   true,
        x:         event.clientX - rect.left + 12,
        y:         event.clientY - rect.top  - 12,
        name:      d.display,
        composite: d.composite_score.toFixed(3),
        velocity:  d.velocity.toFixed(3),
        trend:     d.trend,
      }
      // Highlight connected nodes
      const connectedIds = new Set(
        links
          .filter(l => l.source.id === d.id || l.target.id === d.id)
          .flatMap(l => [l.source.id, l.target.id])
      )
      node.attr('fill-opacity', n => (n.id === d.id || connectedIds.has(n.id)) ? 1.0 : 0.15)
      link.attr('stroke-opacity', l => (l.source.id === d.id || l.target.id === d.id) ? 0.8 : 0.1)
    })
    .on('mousemove', (event) => {
      const rect = container.value.getBoundingClientRect()
      tooltip.value.x = event.clientX - rect.left + 12
      tooltip.value.y = event.clientY - rect.top  - 12
    })
    .on('mouseout', () => {
      tooltip.value.visible = false
      node.attr('fill-opacity', 0.85)
      link.attr('stroke-opacity', 1)
    })

  // Labels for larger nodes
  const label = gSelection.append('g')
    .selectAll('text')
    .data(nodes.filter(d => nodeRadius(d) > 14))
    .join('text')
    .text(d => d.display.length > 18 ? d.display.slice(0, 17) + '…' : d.display)
    .attr('text-anchor', 'middle')
    .attr('dy', d => nodeRadius(d) + 12)
    .attr('fill', '#64748b')
    .attr('font-size', 10)
    .attr('pointer-events', 'none')

  simulation.on('tick', () => {
    link
      .attr('x1', d => d.source.x)
      .attr('y1', d => d.source.y)
      .attr('x2', d => d.target.x)
      .attr('y2', d => d.target.y)
    node
      .attr('cx', d => d.x)
      .attr('cy', d => d.y)
    label
      .attr('x', d => d.x)
      .attr('y', d => d.y)
  })
}

function resetZoom() {
  if (svgSelection && zoomBehavior) {
    svgSelection.transition().duration(400).call(zoomBehavior.transform, d3.zoomIdentity)
  }
}

defineExpose({ resetZoom })

watch(() => props.concepts, buildGraph, { deep: true })
onMounted(buildGraph)
onUnmounted(() => { if (simulation) simulation.stop() })
</script>
