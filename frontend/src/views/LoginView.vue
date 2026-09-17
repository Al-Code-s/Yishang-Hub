<template>
  <div class="ys-login">
    <div class="ys-login__card">
      <div class="ys-login__brand">
        <h1>意尚智造集成平台</h1>
        <p>服饰企业统一业务平台</p>
      </div>

      <el-alert
        v-if="errorMessage"
        type="error"
        :closable="false"
        show-icon
        :title="errorMessage"
        class="ys-login__error"
      />

      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent>
        <el-form-item label="账号" prop="username">
          <el-input
            v-model="form.username"
            size="large"
            placeholder="请输入用户名或手机号"
            autocomplete="username"
            :prefix-icon="User"
            @keyup.enter="submit"
          />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            size="large"
            type="password"
            show-password
            placeholder="请输入密码"
            autocomplete="current-password"
            :prefix-icon="Lock"
            @keyup.enter="submit"
          />
        </el-form-item>
        <el-button
          type="primary"
          size="large"
          class="ys-login__submit"
          :loading="submitting"
          @click="submit"
        >
          登录
        </el-button>
      </el-form>

      <p class="ys-muted ys-login__hint">
        连续登录失败会被锁定账号，忘记密码请联系系统管理员重置。
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Lock, User } from '@element-plus/icons-vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'

import { ApiError } from '@/api/http'
import { identityApi } from '@/api/identity'
import { useAuthStore } from '@/stores/auth'
import { useTabsStore } from '@/stores/tabs'

const auth = useAuthStore()
const tabs = useTabsStore()
const route = useRoute()
const router = useRouter()

const formRef = ref<FormInstance>()
const submitting = ref(false)
const errorMessage = ref('')
const form = reactive({ username: '', password: '' })

const rules: FormRules = {
  username: [{ required: true, message: '请输入账号', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function submit(): Promise<void> {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) {
    return
  }
  submitting.value = true
  errorMessage.value = ''
  try {
    // 先取 CSRF Cookie，再登录；登录接口本身也做 CSRF 校验
    await identityApi.csrf()
    await auth.login(form.username.trim(), form.password)
    tabs.reset()
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
    await router.replace(redirect)
    ElMessage.success('登录成功')
  } catch (error) {
    if (error instanceof ApiError) {
      errorMessage.value = error.message
    } else {
      errorMessage.value = '登录失败，请稍后再试'
    }
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.ys-login__error {
  margin-bottom: 12px;
}

.ys-login__submit {
  width: 100%;
}

.ys-login__hint {
  margin: 16px 0 0;
  text-align: center;
}
</style>