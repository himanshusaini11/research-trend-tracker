<template>
  <div ref="container" class="consensus-chart" />
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import * as d3 from 'd3'

const props = defineProps({
  rounds: { type: Array, required: true },
  width:  { type: Number, default: 420 },
  height: { type: Number, default: 200 },
})

const container = ref(null)

function render() {
  if (!container.value || !props.rounds.length) return

  const margin = { top: 16, right: 24, bottom: 32, left: 44 }
  const innerW  = props.width  - margin.left - margin.right
  const innerH  = props.height - margin.top  - margin.bottom

  d3.select(container.value).selectAll('*').remove()

  const svg = d3.select(container.value)
    .append('svg')
    .attr('width',  props.width)
    .attr('height', props.height)
    .append('g')
    .attr('transform', `translate(${margin.left},${margin.top})`)

  const x = d3.scaleLinear()
    .domain([1, Math.max(props.rounds.length, 2)])
    .range([0, innerW])

  const y = d3.scaleLinear()
    .domain([0, 1])
    .range([innerH, 0])

  // Gridlines
  svg.append('g')
    .attr('class', 'grid')
    .call(
      d3.axisLeft(y)
        .ticks(4)
        .tickSize(-innerW)
        .tickFormat('')
    )
    .call(g => g.select('.domain').remove())
    .call(g => g.selectAll('line').attr('stroke', 'rgba(255,255,255,0.07)'))

  // Consensus line (blue)
  const lineConsensus = d3.line()
    .x(d => x(d.round_number))
    .y(d => y(d.consensus_score))
    .curve(d3.curveMonotoneX)

  svg.append('path')
    .datum(props.rounds)
    .attr('fill', 'none')
    .attr('stroke', '#3b82f6')
    .attr('stroke-width', 2)
    .attr('d', lineConsensus)

  // Consensus dots
  svg.selectAll('.dot-consensus')
    .data(props.rounds)
    .join('circle')
    .attr('class', 'dot-consensus')
    .attr('cx', d => x(d.round_number))
    .attr('cy', d => y(d.consensus_score))
    .attr('r', 4)
    .attr('fill', '#3b82f6')

  // Opinion shift line (amber, dashed)
  const lineShift = d3.line()
    .x(d => x(d.round_number))
    .y(d => y(d.opinion_shift))
    .curve(d3.curveMonotoneX)

  svg.append('path')
    .datum(props.rounds)
    .attr('fill', 'none')
    .attr('stroke', '#f59e0b')
    .attr('stroke-width', 1.5)
    .attr('stroke-dasharray', '4 3')
    .attr('d', lineShift)

  // Axes
  svg.append('g')
    .attr('transform', `translate(0,${innerH})`)
    .call(
      d3.axisBottom(x)
        .ticks(props.rounds.length)
        .tickFormat(d => `R${d}`)
    )
    .call(g => g.select('.domain').attr('stroke', 'rgba(255,255,255,0.2)'))
    .call(g => g.selectAll('text').attr('fill', 'rgba(255,255,255,0.5)').attr('font-size', 11))
    .call(g => g.selectAll('line').attr('stroke', 'rgba(255,255,255,0.2)'))

  svg.append('g')
    .call(
      d3.axisLeft(y)
        .ticks(4)
        .tickFormat(d3.format('.0%'))
    )
    .call(g => g.select('.domain').attr('stroke', 'rgba(255,255,255,0.2)'))
    .call(g => g.selectAll('text').attr('fill', 'rgba(255,255,255,0.5)').attr('font-size', 11))
    .call(g => g.selectAll('line').attr('stroke', 'rgba(255,255,255,0.2)'))

  // Legend
  const legend = svg.append('g').attr('transform', `translate(${innerW - 120}, 0)`)
  legend.append('line').attr('x1', 0).attr('x2', 14).attr('y1', 6).attr('y2', 6)
    .attr('stroke', '#3b82f6').attr('stroke-width', 2)
  legend.append('text').attr('x', 18).attr('y', 10)
    .attr('fill', 'rgba(255,255,255,0.5)').attr('font-size', 10).text('consensus')
  legend.append('line').attr('x1', 0).attr('x2', 14).attr('y1', 22).attr('y2', 22)
    .attr('stroke', '#f59e0b').attr('stroke-width', 1.5).attr('stroke-dasharray', '4 3')
  legend.append('text').attr('x', 18).attr('y', 26)
    .attr('fill', 'rgba(255,255,255,0.5)').attr('font-size', 10).text('shift')
}

onMounted(render)
watch(() => props.rounds, render, { deep: true })
</script>

<style scoped>
.consensus-chart {
  overflow: visible;
}
</style>
