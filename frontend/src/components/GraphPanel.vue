<template>
  <div ref="container" class="w-full h-full relative overflow-hidden">
    <canvas ref="canvas" style="display: block" />

    <!-- Hover tooltip -->
    <div
      v-show="tooltip.visible"
      :style="{ left: tooltip.x + 'px', top: tooltip.y + 'px' }"
      class="absolute pointer-events-none bg-surface border border-border rounded-lg px-3 py-2
             text-xs shadow-lg z-20 min-w-44"
    >
      <div class="text-text-primary font-medium mb-1">{{ tooltip.name }}</div>
      <div class="text-text-muted">composite: <span class="text-text-primary font-mono">{{ tooltip.composite }}</span></div>
      <div class="text-text-muted">velocity: <span class="text-text-primary font-mono">{{ tooltip.velocity }}</span></div>
      <div class="text-text-muted">trend: <span :style="{ color: tooltip.trendColor }">{{ tooltip.trend }}</span></div>
      <div class="text-text-muted/60 mt-1 text-[10px]">dbl-click to zoom</div>
    </div>

    <!-- Stats overlay — bottom-right corner -->
    <div
      class="absolute bottom-4 right-4 pointer-events-none z-10
             bg-black/60 border border-white/10 rounded-lg px-3 py-2.5
             font-mono text-[11px] leading-relaxed backdrop-blur-sm"
      style="min-width: 180px"
    >
      <div class="text-white/40 uppercase tracking-wider text-[9px] mb-1.5">Graph Stats</div>
      <div class="flex justify-between gap-4">
        <span class="text-white/50">Nodes</span>
        <span class="text-white/90">{{ stats.totalNodes }}</span>
      </div>
      <div class="flex justify-between gap-4">
        <span class="text-white/50">Edges</span>
        <span class="text-white/90">{{ stats.totalEdges }}</span>
      </div>
      <div class="flex justify-between gap-4">
        <span class="text-white/50">Top</span>
        <span class="text-white/90 truncate max-w-[110px]" :title="stats.topConcept">{{ stats.topConcept || '—' }}</span>
      </div>
      <div class="border-t border-white/10 mt-1.5 pt-1.5">
        <div class="flex justify-between gap-4">
          <span class="text-white/50">Processed</span>
          <span class="text-white/90">{{ stats.papersProcessed != null ? stats.papersProcessed.toLocaleString() : '…' }}</span>
        </div>
        <div class="flex justify-between gap-4">
          <span class="text-white/50">Last run</span>
          <span class="text-white/90">{{ stats.lastRun || '…' }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'
import * as d3 from 'd3'
import api from '../services/api'
import { useGraphState } from '../stores/graphState'

const gState = useGraphState()

const props = defineProps({
  concepts:    { type: Array,  default: () => [] },
  trendFilter: { type: String, default: 'all' },
  searchQuery: { type: String, default: '' },
  focusNodeId: { type: String, default: null },
  nodeCount:   { type: Number, default: 200 },
})

const emit = defineEmits(['select'])

const container = ref(null)
const canvas    = ref(null)
const tooltip   = ref({ visible: false, x: 0, y: 0, name: '', composite: '', velocity: '', trend: '' })
const stats     = ref({
  totalNodes:      0,
  totalEdges:      0,
  topConcept:      '',
  papersProcessed: null,
  lastRun:         null,
})

// Canvas colors — populated from CSS variables at draw time via readCanvasColors()
let CANVAS_COLORS = {
  accelerating: '#00d4aa',
  decelerating: '#ff6b6b',
  stable:       '#4a9eff',
  default:      '#8892a4',
  edge:         '#4a9eff',
  label:        '#94a3b8',
  tooltipBg:    '#1e1e2e',
  tooltipBorder:'#4a9eff',
  tooltipText:  '#e2e8f0',
}

function readCanvasColors() {
  const s = getComputedStyle(document.documentElement)
  const get = (v) => s.getPropertyValue(v).trim()
  CANVAS_COLORS = {
    accelerating:  get('--canvas-accelerating'),
    decelerating:  get('--canvas-decelerating'),
    stable:        get('--canvas-stable'),
    default:       get('--canvas-default'),
    edge:          get('--canvas-edge'),
    label:         get('--canvas-label'),
    tooltipBg:     get('--canvas-tooltip-bg'),
    tooltipBorder: get('--canvas-tooltip-border'),
    tooltipText:   get('--canvas-tooltip-text'),
  }
}

// ── Mutable simulation state ───────────────────────────────────────────────
let ctx              = null
let canvasW          = 0
let canvasH          = 0
let simulation       = null
let zoomBehavior     = null
let canvasSel        = null
let currentTransform = d3.zoomIdentity
let nodes            = []
let links            = []
let top30Ids         = new Set()
let maxLinkWeight    = 1
let hoveredNode      = null
let selectedNodeId   = null
let connectedIds     = new Set()
let draggedNode      = null
let ro               = null

// ── Incremental loading state ──────────────────────────────────────────────
let allLoadedConcepts = []   // full cache of fetched concept data (grows on demand)
let fadingNodes       = new Set()
let animFrameId       = null
let batchTimer        = null

function toTitleCase(s) {
  return s.split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')
}

function nodeColor(d) {
  return CANVAS_COLORS[d.trend] ?? CANVAS_COLORS.default
}

// Fix 4 — normalize by max score so range spans 5–40px meaningfully
let _maxScore = 1

function nodeRadius(d) {
  const normalized = d.composite_score / _maxScore
  return Math.max(5, normalized * 35 + 5)
}

function deriveEdgesFrom(nodesSubset, cap = 100) {
  const edges = []
  for (let i = 0; i < nodesSubset.length; i++) {
    for (let j = i + 1; j < nodesSubset.length; j++) {
      const tokA = nodesSubset[i].id.split(' ')
      const tokB = nodesSubset[j].id.split(' ')
      const shared = tokA.filter(t => tokB.includes(t) && t.length > 3)
      if (shared.length > 0) {
        edges.push({ source: nodesSubset[i].id, target: nodesSubset[j].id, weight: shared.length })
      }
    }
  }
  return edges.sort((a, b) => b.weight - a.weight).slice(0, cap)
}

function getConnectedIds(nodeId) {
  const ids = new Set()
  for (const l of links) {
    const sid = typeof l.source === 'object' ? l.source.id : l.source
    const tid = typeof l.target === 'object' ? l.target.id : l.target
    if (sid === nodeId || tid === nodeId) { ids.add(sid); ids.add(tid) }
  }
  return ids
}

// ── Drawing ────────────────────────────────────────────────────────────────

function redraw() {
  if (!ctx || canvasW === 0) return
  ctx.clearRect(0, 0, canvasW, canvasH)
  ctx.save()
  ctx.translate(currentTransform.x, currentTransform.y)
  ctx.scale(currentTransform.k, currentTransform.k)
  drawEdges()
  drawNodes()
  drawLabels()
  ctx.restore()
}

function drawEdges() {
  ctx.shadowBlur = 0
  ctx.lineWidth  = 0.8 / currentTransform.k

  for (const lnk of links) {
    const src = lnk.source
    const tgt = lnk.target
    if (src.x == null || tgt.x == null) continue

    const srcConnected = selectedNodeId && (src.id === selectedNodeId || tgt.id === selectedNodeId)

    if (srcConnected) {
      ctx.globalAlpha = 0.8
      ctx.strokeStyle = CANVAS_COLORS.edge
      ctx.lineWidth   = 1.5 / currentTransform.k
    } else if (selectedNodeId) {
      ctx.globalAlpha = 0.06
      ctx.strokeStyle = CANVAS_COLORS.edge
      ctx.lineWidth   = 0.8 / currentTransform.k
    } else {
      ctx.globalAlpha = 0.3
      ctx.strokeStyle = CANVAS_COLORS.edge
      ctx.lineWidth   = 0.8 / currentTransform.k
    }

    ctx.beginPath()
    ctx.moveTo(src.x, src.y)
    ctx.lineTo(tgt.x, tgt.y)
    ctx.stroke()
  }
  ctx.globalAlpha = 1
}

function drawNodes() {
  const q = props.searchQuery.trim().toLowerCase()

  for (const node of nodes) {
    if (node.x == null) continue
    const r       = nodeRadius(node)
    const color   = nodeColor(node)
    const isHover = hoveredNode?.id === node.id
    const isSel   = selectedNodeId === node.id
    const isCon   = selectedNodeId ? connectedIds.has(node.id) : false

    let alpha = 0.85
    if (selectedNodeId && !isSel && !isCon) alpha = 0.12
    if (q && !node.id.includes(q))          alpha *= 0.15
    if (node.birthTime != null) {
      alpha *= Math.min((Date.now() - node.birthTime) / 300, 1)
    }

    // Glow
    if (isHover || isSel) {
      ctx.shadowBlur  = 18
      ctx.shadowColor = color
    } else {
      ctx.shadowBlur = 0
    }

    ctx.globalAlpha = alpha
    ctx.fillStyle   = color
    ctx.beginPath()
    ctx.arc(node.x, node.y, r, 0, Math.PI * 2)
    ctx.fill()

    // White ring for selected node
    if (isSel) {
      ctx.shadowBlur  = 0
      ctx.globalAlpha = 1
      ctx.strokeStyle = 'rgba(255,255,255,0.9)'
      ctx.lineWidth   = 2.5 / currentTransform.k
      ctx.beginPath()
      ctx.arc(node.x, node.y, r + 4 / currentTransform.k, 0, Math.PI * 2)
      ctx.stroke()
    }
  }
  ctx.globalAlpha = 1
  ctx.shadowBlur  = 0
}

function drawLabels() {
  const q        = props.searchQuery.trim().toLowerCase()
  const fontSize = Math.max(9, 11 / Math.max(currentTransform.k, 0.4))
  ctx.font       = `${fontSize}px Inter, system-ui, sans-serif`
  ctx.textAlign  = 'center'

  for (const node of nodes) {
    if (!top30Ids.has(node.id) || node.x == null) continue
    const r     = nodeRadius(node)
    const label = node.display.length > 20 ? node.display.slice(0, 19) + '…' : node.display

    let alpha = 0.65
    if (q && !node.id.includes(q))                          alpha = 0.08
    if (selectedNodeId && !connectedIds.has(node.id) && selectedNodeId !== node.id) alpha = 0.15

    ctx.globalAlpha = alpha
    ctx.fillStyle   = CANVAS_COLORS.label
    ctx.fillText(label, node.x, node.y + r + 13 / currentTransform.k)
  }
  ctx.globalAlpha = 1
}

// ── Stats update (reactive, called after nodes/links change) ───────────────

function updateStats() {
  const degreeMap = new Map()
  for (const lnk of links) {
    const s = typeof lnk.source === 'object' ? lnk.source.id : lnk.source
    const t = typeof lnk.target === 'object' ? lnk.target.id : lnk.target
    degreeMap.set(s, (degreeMap.get(s) ?? 0) + 1)
    degreeMap.set(t, (degreeMap.get(t) ?? 0) + 1)
  }
  let topNode = null, topDeg = -1
  for (const [id, deg] of degreeMap) {
    if (deg > topDeg) { topDeg = deg; topNode = id }
  }
  stats.value.totalNodes = nodes.length
  stats.value.totalEdges = links.length
  stats.value.topConcept = topNode
    ? toTitleCase(topNode)
    : (nodes[0]?.display ?? '')
}

// ── Graph build ────────────────────────────────────────────────────────────

function buildGraph() {
  if (!canvas.value || !allLoadedConcepts.length) return

  readCanvasColors()

  // Clear any in-flight batch timer
  if (batchTimer) { clearInterval(batchTimer); batchTimer = null }

  // Stop previous simulation
  if (simulation) simulation.stop()

  // Resize canvas to container
  canvasW = container.value.clientWidth  || 1000
  canvasH = container.value.clientHeight || 650
  canvas.value.width  = canvasW
  canvas.value.height = canvasH
  ctx = canvas.value.getContext('2d')

  // Filter + deduplicate from the loaded cache (capped at nodeCount prop)
  const source = allLoadedConcepts.slice(0, props.nodeCount)
  const filtered = props.trendFilter === 'all'
    ? source
    : source.filter(c => c.trend === props.trendFilter)

  const deduped = new Map()
  for (const c of filtered) {
    const key = c.concept_name.toLowerCase()
    if (!deduped.has(key) || c.composite_score > deduped.get(key).composite_score) {
      deduped.set(key, c)
    }
  }

  _maxScore = Math.max(...Array.from(deduped.values()).map(c => c.composite_score ?? 0), 1)

  nodes = Array.from(deduped.values()).map(c => ({
    id:              c.concept_name.toLowerCase(),
    display:         toTitleCase(c.concept_name.toLowerCase()),
    composite_score: c.composite_score ?? 0,
    velocity:        c.velocity ?? 0,
    acceleration:    c.acceleration ?? 0,
    centrality:      c.centrality_score ?? c.centrality ?? null,
    trend:           c.trend ?? 'stable',
    birthTime:       null,
  }))

  // Top 30 get labels; derive edges from top-100 for larger graphs, cap 200
  const sortedAll = [...nodes].sort((a, b) => b.composite_score - a.composite_score)
  top30Ids  = new Set(sortedAll.slice(0, 30).map(n => n.id))
  const edgeSrc = sortedAll.slice(0, Math.min(100, sortedAll.length))
  links     = deriveEdgesFrom(edgeSrc, 200)
  maxLinkWeight = Math.max(...links.map(l => l.weight), 1)

  updateStats()

  // Reset selection
  selectedNodeId = props.focusNodeId ?? null
  connectedIds   = selectedNodeId ? getConnectedIds(selectedNodeId) : new Set()

  // Simulation
  simulation = d3.forceSimulation(nodes)
    .alphaDecay(0.02)
    .force('link',    d3.forceLink(links).id(d => d.id).distance(60).strength(0.3))
    .force('charge',  d3.forceManyBody().strength(-150))
    .force('center',  d3.forceCenter(canvasW / 2, canvasH / 2).strength(0.3))
    .force('x',       d3.forceX(canvasW / 2).strength(0.08))
    .force('y',       d3.forceY(canvasH / 2).strength(0.08))
    .force('collide', d3.forceCollide(d => nodeRadius(d) + 12))
    .on('tick', () => {
      // Clamp nodes inside canvas bounds with padding equal to their radius
      for (const d of nodes) {
        const r = nodeRadius(d)
        if (d.x != null) d.x = Math.max(r, Math.min(canvasW - r, d.x))
        if (d.y != null) d.y = Math.max(r, Math.min(canvasH - r, d.y))
      }
      redraw()
    })

  canvasSel = d3.select(canvas.value)

  // ── Drag registered FIRST so it takes priority over zoom ──────────────────
  // Hit-test uses transform-adjusted coordinates to find the node under the
  // pointer. stopPropagation() prevents zoom from consuming the same event.
  canvasSel.call(
    d3.drag()
      .on('start', (event) => {
        const sx = event.sourceEvent.offsetX
        const sy = event.sourceEvent.offsetY
        const node = findNodeAt(sx, sy)
        if (!node) return                          // no node hit — let zoom pan
        draggedNode = node
        if (!event.active) simulation.alphaTarget(0.3).restart()
        draggedNode.fx = draggedNode.x
        draggedNode.fy = draggedNode.y
        event.sourceEvent.stopPropagation()        // prevent zoom from firing
      })
      .on('drag', (event) => {
        if (!draggedNode) return
        const sx = event.sourceEvent.offsetX
        const sy = event.sourceEvent.offsetY
        draggedNode.fx = (sx - currentTransform.x) / currentTransform.k
        draggedNode.fy = (sy - currentTransform.y) / currentTransform.k
      })
      .on('end', (event) => {
        if (!draggedNode) return
        if (!event.active) simulation.alphaTarget(0)
        draggedNode.fx = null
        draggedNode.fy = null
        draggedNode = null
      })
  )

  // ── Zoom registered AFTER drag (lower priority) ───────────────────────────
  zoomBehavior = d3.zoom()
    .scaleExtent([0.1, 8])
    .on('zoom', (event) => {
      currentTransform = event.transform
      gState.zoomTransform = { x: currentTransform.x, y: currentTransform.y, k: currentTransform.k }
      redraw()
    })

  canvasSel.call(zoomBehavior)
  canvasSel.on('dblclick.zoom', null) // override d3 default
}

// ── Incremental node addition ──────────────────────────────────────────────

function startFadeLoop() {
  if (animFrameId) return
  function loop() {
    const now = Date.now()
    let stillFading = false
    for (const n of fadingNodes) {
      if (now - n.birthTime < 300) { stillFading = true; break }
    }
    redraw()
    if (stillFading) {
      animFrameId = requestAnimationFrame(loop)
    } else {
      fadingNodes.clear()
      animFrameId = null
    }
  }
  animFrameId = requestAnimationFrame(loop)
}

function addDeltaNodes(newConceptData) {
  if (!newConceptData.length || !simulation) return

  const existingIds = new Set(nodes.map(n => n.id))
  const toAdd = newConceptData
    .filter(c => props.trendFilter === 'all' || c.trend === props.trendFilter)
    .filter(c => !existingIds.has(c.concept_name.toLowerCase()))
    .map(c => ({
      id:              c.concept_name.toLowerCase(),
      display:         toTitleCase(c.concept_name.toLowerCase()),
      composite_score: c.composite_score ?? 0,
      velocity:        c.velocity ?? 0,
      acceleration:    c.acceleration ?? 0,
      centrality:      c.centrality_score ?? c.centrality ?? null,
      trend:           c.trend ?? 'stable',
      birthTime:       null,
    }))

  if (!toAdd.length) return

  let i = 0
  batchTimer = setInterval(() => {
    const batch = toAdd.slice(i, i + 10)
    if (!batch.length) {
      clearInterval(batchTimer)
      batchTimer = null
      return
    }
    const now = Date.now()
    batch.forEach(n => { n.birthTime = now; fadingNodes.add(n) })
    nodes.push(...batch)

    // Re-derive edges from updated top-100 (covers newly promoted nodes)
    const sortedAll = [...nodes].sort((a, b) => b.composite_score - a.composite_score)
    top30Ids = new Set(sortedAll.slice(0, 30).map(n => n.id))
    links    = deriveEdgesFrom(sortedAll.slice(0, Math.min(100, sortedAll.length)), 200)
    maxLinkWeight = Math.max(...links.map(l => l.weight), 1)

    simulation.nodes(nodes)
    simulation.force('link', d3.forceLink(links).id(d => d.id).distance(60).strength(0.3))
    simulation.alpha(0.3).restart()

    updateStats()
    startFadeLoop()
    i += 10
  }, 50)
}

async function onNodeCountChange(target) {
  if (target <= nodes.length) {
    // Slider went down — trim to the top-N by composite score and rebuild
    allLoadedConcepts = allLoadedConcepts
      .slice()
      .sort((a, b) => (b.composite_score ?? 0) - (a.composite_score ?? 0))
      .slice(0, target)
    buildGraph()
    return
  }

  // Need more nodes — check cache first
  if (target <= allLoadedConcepts.length) {
    // Already fetched — add from cache progressively
    const delta = allLoadedConcepts.slice(nodes.length, target)
    addDeltaNodes(delta)
    return
  }

  // Fetch the missing range from the backend
  const from = allLoadedConcepts.length
  const limit = target - from
  try {
    const fresh = await api.getGraphConcepts(limit, from)
    allLoadedConcepts.push(...fresh)
    const delta = allLoadedConcepts.slice(nodes.length, target)
    addDeltaNodes(delta)
  } catch {
    // silently ignore network errors — slider stays where it is
  }
}

// ── Mouse interactions ─────────────────────────────────────────────────────

function findNodeAt(sx, sy) {
  const wx = (sx - currentTransform.x) / currentTransform.k
  const wy = (sy - currentTransform.y) / currentTransform.k
  for (let i = nodes.length - 1; i >= 0; i--) {
    const n = nodes[i]
    if (n.x == null) continue
    const r  = nodeRadius(n)
    const dx = n.x - wx
    const dy = n.y - wy
    if (dx * dx + dy * dy <= r * r) return n
  }
  return null
}

function onMouseMove(event) {
  const node = findNodeAt(event.offsetX, event.offsetY)
  if (node !== hoveredNode) {
    hoveredNode = node
    canvas.value.style.cursor = node ? 'pointer' : 'default'
    redraw()
  }
  if (node) {
    tooltip.value = {
      visible:      true,
      x:            event.offsetX + 14,
      y:            event.offsetY - 14,
      name:         node.display,
      composite:    Number(node.composite_score).toFixed(3),
      velocity:     Number(node.velocity).toFixed(3),
      trend:        node.trend,
      trendColor:   CANVAS_COLORS[node.trend] ?? CANVAS_COLORS.default,
    }
  } else {
    tooltip.value.visible = false
  }
}

function onClick(event) {
  // Prevent firing after pan
  if (event.defaultPrevented) return
  const node = findNodeAt(event.offsetX, event.offsetY)
  if (node) {
    selectedNodeId = node.id
    connectedIds   = getConnectedIds(node.id)
    emit('select', node)
  } else {
    selectedNodeId = null
    connectedIds   = new Set()
    emit('select', null)
  }
  redraw()
}

function onDblClick(event) {
  const node = findNodeAt(event.offsetX, event.offsetY)
  if (!node || node.x == null) return
  const targetK = Math.min(currentTransform.k * 2.5, 6)
  const targetX = canvasW / 2 - node.x * targetK
  const targetY = canvasH / 2 - node.y * targetK
  canvasSel
    .transition()
    .duration(500)
    .call(zoomBehavior.transform, d3.zoomIdentity.translate(targetX, targetY).scale(targetK))
}

// ── Public API ─────────────────────────────────────────────────────────────

function resetZoom() {
  if (canvasSel && zoomBehavior) {
    canvasSel.transition().duration(400).call(zoomBehavior.transform, d3.zoomIdentity)
    gState.zoomTransform = { x: 0, y: 0, k: 1 }
  }
}

defineExpose({ resetZoom })

// ── Lifecycle ──────────────────────────────────────────────────────────────

watch(() => props.concepts, (newConcepts) => {
  if (batchTimer) { clearInterval(batchTimer); batchTimer = null }
  allLoadedConcepts = [...newConcepts]
  buildGraph()
  // If Top N exceeds the initial fetch, delta-load the remainder
  if (props.nodeCount > allLoadedConcepts.length) {
    onNodeCountChange(props.nodeCount)
  }
}, { deep: true })

watch(() => props.nodeCount, (newVal, oldVal) => {
  if (newVal !== oldVal) onNodeCountChange(newVal)
})

watch(() => props.trendFilter, buildGraph)
watch(() => props.searchQuery, redraw)

watch(() => props.focusNodeId, (id) => {
  selectedNodeId = id ?? null
  connectedIds   = selectedNodeId ? getConnectedIds(selectedNodeId) : new Set()
  redraw()
})

function onThemeChange() {
  readCanvasColors()
  redraw()
}

onMounted(() => {
  window.addEventListener('rtt-theme-change', onThemeChange)
  allLoadedConcepts = [...props.concepts]
  buildGraph()
  if (props.nodeCount > allLoadedConcepts.length) {
    onNodeCountChange(props.nodeCount)
  }
  // Restore saved zoom transform (persists across navigation)
  const saved = gState.zoomTransform
  if (saved && (saved.x !== 0 || saved.y !== 0 || saved.k !== 1)) {
    const t = d3.zoomIdentity.translate(saved.x, saved.y).scale(saved.k)
    currentTransform = t
    if (canvasSel && zoomBehavior) canvasSel.call(zoomBehavior.transform, t)
  }

  api.getGraphStats().then(s => {
    stats.value.papersProcessed = s.papers_processed
    if (s.last_run) {
      const d = new Date(s.last_run)
      stats.value.lastRun = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: '2-digit' })
    }
  }).catch(() => {})

  canvas.value.addEventListener('mousemove', onMouseMove)
  canvas.value.addEventListener('click',     onClick)
  canvas.value.addEventListener('dblclick',  onDblClick)

  ro = new ResizeObserver(() => {
    const newW = container.value?.clientWidth  ?? 0
    const newH = container.value?.clientHeight ?? 0
    if (newW === canvasW && newH === canvasH) return
    canvasW = newW
    canvasH = newH
    canvas.value.width  = canvasW
    canvas.value.height = canvasH
    if (simulation) {
      simulation
        .force('center', d3.forceCenter(canvasW / 2, canvasH / 2).strength(0.3))
        .force('x',      d3.forceX(canvasW / 2).strength(0.08))
        .force('y',      d3.forceY(canvasH / 2).strength(0.08))
      simulation.alpha(0.2).restart()
    }
    redraw()
  })
  ro.observe(container.value)
})

onUnmounted(() => {
  window.removeEventListener('rtt-theme-change', onThemeChange)
  if (simulation)  simulation.stop()
  if (ro)          ro.disconnect()
  if (batchTimer)  clearInterval(batchTimer)
  if (animFrameId) cancelAnimationFrame(animFrameId)
  if (canvas.value) {
    canvas.value.removeEventListener('mousemove', onMouseMove)
    canvas.value.removeEventListener('click',     onClick)
    canvas.value.removeEventListener('dblclick',  onDblClick)
  }
})
</script>
