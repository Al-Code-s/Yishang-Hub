<template>
  <el-drawer v-model="visible" title="审批详情" size="620px">
    <el-alert v-if="errorMessage" type="error" :closable="false" show-icon :title="errorMessage" />

    <template v-if="instance">
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="单号">{{ instance.biz_no }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ instance.status_display }}</el-descriptions-item>
        <el-descriptions-item label="申请事项" :span="2">{{ instance.title }}</el-descriptions-item>
        <el-descriptions-item label="申请人">{{ instance.applicant_name }}</el-descriptions-item>
        <el-descriptions-item label="金额">{{ formatAmount(instance.amount, 4) }}</el-descriptions-item>
        <el-descriptions-item label="审批模板">{{ instance.template_name }}</el-descriptions-item>
        <el-descriptions-item label="模板版本">v{{ instance.template_version }}</el-descriptions-item>
        <el-descriptions-item label="提交时间">
          {{ formatDateTime(instance.submitted_at) }}
        </el-descriptions-item>
        <el-descriptions-item label="结束时间">
          {{ formatDateTime(instance.finished_at) }}
        </el-descriptions-item>
      </el-descriptions>

      <h4 class="ys-section-title">审批节点</h4>
      <el-steps direction="vertical" :active="activeStep">
        <el-step
          v-for="step in instance.steps"
          :key="step.id"
          :title="`${step.seq}. ${step.name}`"
          :status="stepStatus(step.status)"
        >
          <template #description>
            <div class="ys-muted">
              审批人：{{ step.approver_role_name || step.assigned_user_name || '未指定' }}
              <span v-if="step.decided_by_name">· 处理人 {{ step.decided_by_name }}</span>
              <span v-if="step.decided_at">· {{ formatDateTime(step.decided_at) }}</span>
            </div>
            <div v-if="step.comment" class="ys-step-comment">意见：{{ step.comment }}</div>
          </template>
        </el-step>
      </el-steps>

      <h4 class="ys-section-title">操作轨迹</h4>
      <el-timeline>
        <el-timeline-item
          v-for="log in instance.logs"
          :key="log.id"
          :timestamp="formatDateTime(log.created_at)"
        >
          {{ log.actor_name }} {{ log.action_display }}
          <div v-if="log.comment" class="ys-muted">{{ log.comment }}</div>
        </el-timeline-item>
      </el-timeline>

      <div class="ys-toolbar">
        <el-input v-model="newComment" placeholder="补充审批意见" style="width: 320px" />
        <el-button :loading="commenting" @click="submitComment">提交意见</el-button>
        <el-button v-if="instance.can_withdraw" type="warning" plain @click="withdraw">撤回</el-button>
      </div>

      <p class="ys-muted">
        单据版本 v{{ instance.version }} · 数据更新时间 {{ formatDateTime(instance.updated_at) }}
      </p>
    </template>

    <el-empty v-else-if="!loading" description="未加载到审批详情" />
  </el-drawer>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

import { ApiError } from '@/api/http'
import { workflowApi } from '@/api/modules'
import type { ApprovalInstance } from '@/types/models'
import { formatAmount } from '@/utils/decimal'
import { formatDateTime } from '@/utils/format'

const props = defineProps<{ modelValue: boolean; instanceId: number | null }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean]; changed: [] }>()

const visible = ref(props.modelValue)
const instance = ref<ApprovalInstance | null>(null)
const loading = ref(false)
const errorMessage = ref('')
const newComment = ref('')
const commenting = ref(false)

watch(
  () => props.modelValue,
  async (value) => {
    visible.value = value
    if (value && props.instanceId) {
      await load()
    }
  },
)

watch(
  () => props.instanceId,
  async (value) => {
    if (value && props.modelValue) {
      await load()
    }
  },
)

watch(visible, (value) => emit('update:modelValue', value))

const activeStep = computed(() => {
  if (!instance.value) {
    return 0
  }
  const index = instance.value.steps.findIndex((step) => step.seq === instance.value?.current_seq)
  return index < 0 ? instance.value.steps.length : index
})

function stepStatus(status: string): 'wait' | 'process' | 'finish' | 'error' | 'success' {
  if (status === 'approved') {
    return 'success'
  }
  if (status === 'rejected') {
    return 'error'
  }
  if (status === 'pending') {
    return 'process'
  }
  if (status === 'cancelled' || status === 'skipped') {
    return 'wait'
  }
  return 'wait'
}

async function load(): Promise<void> {
  if (!props.instanceId) {
    return
  }
  loading.value = true
  errorMessage.value = ''
  try {
    instance.value = await workflowApi.detail(props.instanceId)
  } catch (error) {
    instance.value = null
    errorMessage.value = error instanceof ApiError ? error.message : '加载审批详情失败'
  } finally {
    loading.value = false
  }
}

async function submitComment(): Promise<void> {
  if (!props.instanceId || !newComment.value.trim()) {
    ElMessage.warning('请输入意见内容')
    return
  }
  commenting.value = true
  try {
    await workflowApi.comment(props.instanceId, newComment.value)
    newComment.value = ''
    await load()
    ElMessage.success('已提交意见')
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : '提交失败')
  } finally {
    commenting.value = false
  }
}

async function withdraw(): Promise<void> {
  if (!props.instanceId) {
    return
  }
  try {
    await workflowApi.withdraw(props.instanceId, '申请人撤回')
    await load()
    emit('changed')
    ElMessage.success('已撤回')
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : '撤回失败')
  }
}
</script>

<style scoped>
.ys-section-title {
  margin: 20px 0 12px;
  font-size: 14px;
  color: var(--ys-navy-900);
}

.ys-step-comment {
  color: var(--ys-gray-700);
}
</style>