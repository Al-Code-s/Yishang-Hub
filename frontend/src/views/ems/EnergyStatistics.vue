<template>
  <energy-statistics-panel title="能耗统计" description="按计量点（电能分项）、区域、部门、设备或日/月/年维度聚合用量与费用。费用按发生日期套用对应介质与尖峰平谷时段的单价折算；没有维护单价的介质会在上方提示，不会用默认价凑数。" />
</template>

<script setup lang="ts">
import EnergyStatisticsPanel from '@/components/EnergyStatisticsPanel.vue'
</script>
