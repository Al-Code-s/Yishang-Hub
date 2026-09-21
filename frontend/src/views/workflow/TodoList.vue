<template>
  <div class="ys-page">
    <div class="ys-page__header">
      <div>
        <h2 class="ys-page__title">我的待办</h2>
        <p class="ys-page__description">
          只显示当前轮到你审批的单据。审批与出入库是两个独立动作，通过审批不会直接改变库存。
        </p>
      </div>
      <el-button @click="load" :loading="loading">刷新</el-button>
    </div>

    <el-alert v-if="errorMessage" type="error" :closable="false" show-icon :title="errorMessage" />

    <el-table v-loading="loading" :data="rows" border stripe size="small">
      <el-table-column prop="biz_no" label="单号" width="140" />
      <el-table-column prop="title" label="申请事项" min-width="200" />
      <el-table-column prop="applicant_name" label="申请人" width="110" />
      <el-table-column prop="current_step_name" label="当前节点" width="140" />
      <el-table-column label="金额" width="120">
        <template #default="{ row }">{{ formatAmount(row.amount) }}</template>
      </el-table-column>
      <el-table-column label="提交时间" width="170">
        <template #default="{ row }">{{ formatDateTime(row.submitted_at) }}</template>
      </el-table-column>
      <el-table-column prop="status_display" label="状态" width="100" />
      <el-table-column label="操作" width="220" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="open(row)">查看</el-button>
          <el-button
            v-if="row.can_approve"
            link
            type="success"
            size="small"
            @click="openDecision(row, 'approve')"
          >
            通过
          </el-button>
          <el-button
            v-if="row.can_approve"
            link
            type="danger"
            size="small"
            @click="openDecision(row, 'reject')"
          >
            驳回
          </el-button>
        </template>
      </el-table-column>
      <template #empty>
        <el-empty description="当前没有待办事项" />
      </template>
    </el-table>

    <div class="ys-pagination">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        background
        @current-change="load"
      />
    </div>

    <approval-detail-drawer v-model="detailVisible" :instance-id="currentId" @changed="load" />

    <el-dialog
      v-model="decisionVisible"
      :title="decision === 'approve' ? '审批通过' : '审批驳回'"
      width="480px"
      :close-on-click-modal="false"
    >
      <el-alert v-if="decisionError" type="error" :closable="false" show-icon :title="decisionError" />
      <el-form label-width="80px">
        <el-form-item label="审批意见" :required="decision === 'reject'">
          <el-input
            v-model="decisionComment"
            type="textarea"
            :rows="3"
            :placeholder="decision === 'reject' ? '驳回必须填写理由' : '可选'"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="decisionVisible = false">取消</el-button>
        <el-button
          :type="decision === 'approve' ? 'primary' : 'danger'"
          :loading="submitting"
          @click="submitDecision"
        >
          确认{{ decision === 'approve' ? '通过' : '驳回' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'

import ApprovalDetailDrawer from '@/components/ApprovalDetailDrawer.vue'
import { ApiError } from '@/api/http'
import { workflowApi } from '@/api/modules'
import type { ApprovalInstance } from '@/types/models'
import { formatAmount } from '@/utils/decimal'
import { formatDateTime } from '@/utils/format'

const rows = ref<ApprovalInstance[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const errorMessage = ref('')

const detailVisible = ref(false)
const currentId = ref<number | null>(null)

const decisionVisible = ref(false)
const decision = ref<'approve' | 'reject'>('approve')
const decisionComment = ref('')
const decisionError = ref('')
const submitting = ref(false)
const decisionTarget = ref<number | null>(null)

async function load(): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  try {
    const result = await workflowApi.todo({ page: page.value, page_size: pageSize.value })
    rows.value = result.results
    total.value = result.count
  } catch (error) {
    rows.value = []
    total.value = 0
    errorMessage.value = error instanceof ApiError ? error.message : '加载待办失败'
  } finally {
    loading.value = false
  }
}

function open(row: ApprovalInstance): void {
  currentId.value = row.id
  detailVisible.value = true
}

function openDecision(row: ApprovalInstance, action: 'approve' | 'reject'): void {
  decision.value = action
  decisionComment.value = ''
  decisionError.value = ''
  decisionTarget.value = row.id
  decisionVisible.value = true
}

async function submitDecision(): Promise<void> {
  if (decisionTarget.value === null) {
    return
  }
  if (decision.value === 'reject' && !decisionComment.value.trim()) {
    decisionError.value = '驳回必须填写审批意见'
    return
  }
  submitting.value = true
  decisionError.value = ''
  try {
    if (decision.value === 'approve') {
      await workflowApi.approve(decisionTarget.value, decisionComment.value)
    } else {
      await workflowApi.reject(decisionTarget.value, decisionComment.value)
    }
    ElMessage.success(decision.value === 'approve' ? '已通过' : '已驳回')
    decisionVisible.value = false
    await load()
  } catch (error) {
    decisionError.value = error instanceof ApiError ? error.message : '操作失败'
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  void load()
})
</script>