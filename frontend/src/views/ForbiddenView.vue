<template>
  <el-result icon="warning" title="没有访问权限" sub-title="当前账号的角色未获得该功能的授权，请联系系统管理员。">
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