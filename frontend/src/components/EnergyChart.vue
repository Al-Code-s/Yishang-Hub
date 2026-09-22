<template>
  <div ref="host" class="ys-chart" :style="{ height: height + 'px' }" />
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { BarChart, LineChart, PieChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TitleComponent, TooltipComponent } from 'echarts/components'
import * as echarts from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'

/**
 * 轻量 ECharts 包装：只负责实例生命周期与自适应，图表内容由父组件传入 option。
 *
 * 按需注册图表与组件，避免把整个 echarts 打进包体。
 */
echarts.use([
  BarChart,
  LineChart,
  PieChart,
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
  CanvasRenderer,
])

const props = withDefaults(defineProps<{ option: Record<string, unknown>; height?: number }>(), {
  height: 320,
})

const host = ref<HTMLDivElement>()
let chart: ReturnType<typeof echarts.init> | null = null

function render(): void {
  if (!host.value) {
    return
  }
  if (!chart) {
    chart = echarts.init(host.value)
  }
  chart.setOption(props.option, true)
}

function resize(): void {
  chart?.resize()
}

onMounted(() => {
  render()
  window.addEventListener('resize', resize)
})

watch(() => props.option, render, { deep: true })

onBeforeUnmount(() => {
  window.removeEventListener('resize', resize)
  chart?.dispose()
  chart = null
})
</script>

<style scoped>
.ys-chart {
  width: 100%;
}
</style>
