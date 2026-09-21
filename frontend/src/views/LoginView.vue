<template>
  <div class="ys-login">
    <!-- 纯 CSS 装饰层（网格 + 光斑），不引入任何外链资源，离线可用 -->
    <div class="ys-login__aurora" aria-hidden="true" />

    <div class="ys-login__shell">
      <!-- 品牌区：窄屏隐藏，避免小屏被横向挤压；对应地卡片里显示紧凑版品牌 -->
      <section class="ys-login__intro">
        <div class="ys-login__brand">
          <span class="ys-login__mark" aria-hidden="true">意</span>
          <span class="ys-login__brand-text">
            <strong>意尚智造</strong>
            <em>集成平台</em>
          </span>
        </div>

        <h1 class="ys-login__headline">服饰企业一体化经营管理平台</h1>
        <!-- 单行书写：模板里换行会被压缩成一个空格，紧跟在中文标点后会留下多余空隙 -->
        <p class="ys-login__slogan">从面料采购、款式建码到库存出入库与销售发货，日常业务都在同一个平台上流转，不用在多个系统之间来回切换。</p>

        <ul class="ys-login__features">
          <li v-for="item in features" :key="item.title">
            <el-icon class="ys-login__feature-icon"><component :is="item.icon" /></el-icon>
            <span class="ys-login__feature-text">
              <b>{{ item.title }}</b>
              <i>{{ item.desc }}</i>
            </span>
          </li>
        </ul>
      </section>

      <section class="ys-login__card">
        <header class="ys-login__card-head">
          <div class="ys-login__brand ys-login__brand--compact">
            <span class="ys-login__mark" aria-hidden="true">意</span>
            <span class="ys-login__brand-text">
              <strong>意尚智造</strong>
              <em>集成平台</em>
            </span>
          </div>
          <h2>账号登录</h2>
          <p>请使用系统管理员分配的账号登录</p>
        </header>

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
              ref="usernameRef"
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

        <p class="ys-login__hint">
          连续登录失败会被锁定账号，忘记密码请联系系统管理员重置。
        </p>
        <p class="ys-login__copyright">© {{ year }} 意尚智造 · 仅供公司内部使用</p>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref, type Component } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { CircleCheck, Files, Key, Lock, ShoppingCart, User } from '@element-plus/icons-vue'
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
const usernameRef = ref<{ focus: () => void }>()
const submitting = ref(false)
const errorMessage = ref('')
const form = reactive({ username: '', password: '' })
const year = new Date().getFullYear()

/**
 * 左侧要点：面向使用者的业务价值描述——讲清平台能帮各个岗位做什么。
 * 表述避免开发视角的术语（如权限分层、数据表字段名等）；
 * 同时只陈述平台已具备的能力，不列举尚未实施的模块，避免登录页变成技术说明或虚假宣传。
 */
const features: { title: string; desc: string; icon: Component }[] = [
  { title: '一套账号，权限分明', desc: '按岗位分配可用功能与数据范围', icon: Key },
  { title: '基础资料统一维护', desc: '面料、辅料、款式、颜色尺码一处建档', icon: Files },
  { title: '采购到销售全程贯通', desc: '到货、入库、出库、发货连续流转', icon: ShoppingCart },
  { title: '单据与审批全程留痕', desc: '谁在何时提交、审批、修改随时可查', icon: CircleCheck },
]

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

// 打开登录页即聚焦账号输入框，键盘用户可以直接开始输入
onMounted(() => {
  usernameRef.value?.focus()
})
</script>

<style scoped>
/* 登录页样式全部收在本组件内（页面级视觉，不与业务页面共用），
   全局样式表只保留设计令牌。 */

.ys-login {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100%;
  padding: 32px 24px;
  overflow: hidden;
  background:
    radial-gradient(1200px 620px at 10% 6%, rgba(43, 124, 233, 0.45), transparent 62%),
    radial-gradient(900px 520px at 92% 94%, rgba(22, 104, 220, 0.34), transparent 64%),
    linear-gradient(135deg, #0b2545 0%, #12395f 52%, #1b4c7e 100%);
}

.ys-login__aurora {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.05) 1px, transparent 1px);
  background-size: 56px 56px;
  -webkit-mask-image: radial-gradient(circle at 32% 28%, #000 0%, transparent 76%);
  mask-image: radial-gradient(circle at 32% 28%, #000 0%, transparent 76%);
  pointer-events: none;
}

.ys-login__shell {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 420px;
  gap: 56px;
  align-items: center;
  width: min(1080px, 100%);
}

/* ---------- 左侧品牌区 ---------- */
.ys-login__intro {
  color: #fff;
}

.ys-login__brand {
  display: flex;
  align-items: center;
  gap: 12px;
}

.ys-login__mark {
  display: grid;
  place-items: center;
  width: 46px;
  height: 46px;
  border-radius: 13px;
  background: linear-gradient(135deg, #2b7ce9, #6cb4ff);
  color: #fff;
  font-size: 21px;
  font-weight: 700;
  box-shadow: 0 10px 24px rgba(4, 22, 46, 0.5);
}

.ys-login__brand-text {
  display: flex;
  flex-direction: column;
  line-height: 1.25;
}

.ys-login__brand-text strong {
  font-size: 18px;
  font-weight: 600;
  letter-spacing: 0.06em;
}

.ys-login__brand-text em {
  font-size: 11px;
  font-style: normal;
  letter-spacing: 0.24em;
  opacity: 0.72;
}

.ys-login__headline {
  margin: 34px 0 0;
  font-size: 30px;
  font-weight: 600;
  line-height: 1.35;
  letter-spacing: 0.01em;
}

.ys-login__slogan {
  margin: 14px 0 0;
  max-width: 460px;
  font-size: 13px;
  line-height: 1.9;
  color: rgba(226, 238, 255, 0.74);
}

.ys-login__features {
  margin: 32px 0 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 16px;
}

.ys-login__features li {
  display: flex;
  align-items: center;
  gap: 12px;
}

.ys-login__feature-icon {
  flex: none;
  width: 34px;
  height: 34px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.14);
  color: #9ec9ff;
  font-size: 17px;
}

.ys-login__feature-text {
  display: flex;
  flex-direction: column;
  line-height: 1.5;
}

.ys-login__feature-text b {
  font-size: 13.5px;
  font-weight: 600;
  color: #fff;
}

.ys-login__feature-text i {
  font-size: 12px;
  font-style: normal;
  color: rgba(214, 231, 252, 0.64);
}

/* ---------- 右侧登录卡片 ---------- */
.ys-login__card {
  width: 100%;
  padding: 34px 34px 22px;
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 30px 70px rgba(3, 15, 32, 0.5);
}

.ys-login__card-head {
  margin-bottom: 22px;
}

.ys-login__card-head h2 {
  margin: 0;
  font-size: 21px;
  font-weight: 600;
  letter-spacing: 0.02em;
  color: var(--ys-navy-900);
}

.ys-login__card-head p {
  margin: 8px 0 0;
  font-size: 12.5px;
  color: var(--ys-gray-500);
}

/* 紧凑品牌只在窄屏出现（宽屏由左侧品牌区承担） */
.ys-login__brand--compact {
  display: none;
  margin-bottom: 18px;
}

.ys-login__brand--compact .ys-login__mark {
  width: 40px;
  height: 40px;
  border-radius: 11px;
  font-size: 18px;
}

.ys-login__brand--compact .ys-login__brand-text strong {
  color: var(--ys-navy-900);
}

.ys-login__brand--compact .ys-login__brand-text em {
  color: var(--ys-gray-500);
  opacity: 1;
}

.ys-login__error {
  margin-bottom: 16px;
}

/* 表单控件：与卡片圆角、留白统一 */
.ys-login__card :deep(.el-form-item) {
  margin-bottom: 18px;
}

.ys-login__card :deep(.el-form-item__label) {
  padding-bottom: 4px;
  font-size: 13px;
  font-weight: 600;
  color: var(--ys-gray-700);
}

.ys-login__card :deep(.el-input__wrapper) {
  padding: 4px 12px;
  border-radius: 10px;
  box-shadow: 0 0 0 1px var(--ys-gray-200) inset;
  transition: box-shadow 0.18s ease;
}

.ys-login__card :deep(.el-input__wrapper:hover) {
  box-shadow: 0 0 0 1px var(--ys-gray-300) inset;
}

.ys-login__card :deep(.el-input__wrapper.is-focus) {
  box-shadow:
    0 0 0 1px var(--ys-blue-600) inset,
    0 0 0 4px rgba(22, 104, 220, 0.12);
}

.ys-login__submit {
  width: 100%;
  height: 44px;
  margin-top: 6px;
  font-size: 15px;
  letter-spacing: 0.22em;
  text-indent: 0.22em;
  border: none;
  background: linear-gradient(135deg, #1668dc, #2b7ce9);
  box-shadow: 0 10px 22px rgba(22, 104, 220, 0.3);
}

.ys-login__submit:hover {
  background: linear-gradient(135deg, #1253b0, #1668dc);
  box-shadow: 0 12px 26px rgba(22, 104, 220, 0.38);
}

.ys-login__hint {
  margin: 18px 0 0;
  font-size: 12px;
  line-height: 1.7;
  text-align: center;
  color: var(--ys-gray-500);
}

.ys-login__copyright {
  margin: 14px 0 0;
  padding-top: 14px;
  border-top: 1px solid var(--ys-gray-100);
  font-size: 11.5px;
  text-align: center;
  color: var(--ys-gray-500);
}

/* ---------- 响应式 ---------- */
@media (max-width: 960px) {
  .ys-login__shell {
    grid-template-columns: minmax(0, 1fr);
    gap: 0;
    width: min(440px, 100%);
  }

  .ys-login__intro {
    display: none;
  }

  .ys-login__brand--compact {
    display: flex;
  }
}

@media (max-width: 480px) {
  .ys-login {
    padding: 20px 16px;
  }

  .ys-login__card {
    padding: 26px 22px 18px;
    border-radius: 14px;
  }

  .ys-login__card-head h2 {
    font-size: 19px;
  }
}

/* 尊重系统「减少动态效果」设置 */
@media (prefers-reduced-motion: no-preference) {
  .ys-login__shell {
    animation: ys-login-rise 0.5s cubic-bezier(0.22, 0.61, 0.36, 1) both;
  }

  @keyframes ys-login-rise {
    from {
      opacity: 0;
      transform: translateY(14px);
    }
    to {
      opacity: 1;
      transform: none;
    }
  }
}
</style>
