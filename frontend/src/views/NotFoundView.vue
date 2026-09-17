<template>
  <el-result icon="info" title="页面不存在" sub-title="该地址没有对应的功能页面，或当前角色没有访问权限。">
    <template #extra>
      <el-button type="primary" @click="goHome">返回工作台</el-button>
    </template>
  </el-result>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()

function goHome(): void {
  void router.push('/')
}
</script>