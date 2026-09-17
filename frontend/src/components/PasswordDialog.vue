<template>
  <el-dialog v-model="visible" title="修改密码" width="440px" :close-on-click-modal="false">
    <el-form ref="formRef" :model="form" :rules="rules" label-width="96px">
      <el-form-item label="当前密码" prop="old_password">
        <el-input v-model="form.old_password" type="password" show-password autocomplete="current-password" />
      </el-form-item>
      <el-form-item label="新密码" prop="new_password">
        <el-input v-model="form.new_password" type="password" show-password autocomplete="new-password" />
      </el-form-item>
      <el-form-item label="确认新密码" prop="confirm">
        <el-input v-model="form.confirm" type="password" show-password autocomplete="new-password" />
      </el-form-item>
    </el-form>
    <el-alert
      type="info"
      :closable="false"
      title="密码要求"
      description="修改成功后，其它设备上的登录状态会立即失效。"
    />
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submit">确认修改</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'

import { ApiError } from '@/api/http'
import { identityApi } from '@/api/identity'
import { useAuthStore } from '@/stores/auth'

const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()

const auth = useAuthStore()
const visible = ref(props.modelValue)
const submitting = ref(false)
const formRef = ref<FormInstance>()
const form = reactive({ old_password: '', new_password: '', confirm: '' })

const rules: FormRules = {
  old_password: [{ required: true, message: '请输入当前密码', trigger: 'blur' }],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 10, message: '新密码至少 10 位', trigger: 'blur' },
  ],
  confirm: [
    {
      validator: (_rule, value, callback) => {
        if (value !== form.new_password) {
          callback(new Error('两次输入的密码不一致'))
          return
        }
        callback()
      },
      trigger: 'blur',
    },
  ],
}

watch(
  () => props.modelValue,
  (value) => {
    visible.value = value
    if (value) {
      form.old_password = ''
      form.new_password = ''
      form.confirm = ''
    }
  },
)

watch(visible, (value) => emit('update:modelValue', value))

async function submit(): Promise<void> {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) {
    return
  }
  submitting.value = true
  try {
    await identityApi.changePassword(form.old_password, form.new_password)
    ElMessage.success('密码修改成功，其它设备的登录状态已失效。')
    visible.value = false
    await auth.fetchSession()
  } catch (error) {
    if (error instanceof ApiError) {
      ElMessage.error(error.fieldErrorMessage || error.message)
    } else {
      ElMessage.error('修改失败')
    }
  } finally {
    submitting.value = false
  }
}
</script>