<template>
  <el-aside width="200px" class="sidebar">
    <div class="sidebar-header">
      <h3>ESP32-CAM</h3>
      <div class="user-info" @click="showProfileDialog = true" style="cursor: pointer;">
        <el-icon style="font-size: 20px; margin-bottom: 8px;"><User /></el-icon>
        <span>{{ user?.username }}</span>
      </div>
    </div>
    
    <el-menu :default-active="activeIndex" class="sidebar-menu">
      <el-menu-item index="1" @click="router.push('/dashboard')">
        <el-icon><HomeFilled /></el-icon>
        <span>Dashboard</span>
      </el-menu-item>
      <el-menu-item v-if="user?.is_admin" index="2" @click="router.push('/admin')">
        <el-icon><Setting /></el-icon>
        <span>User Management</span>
      </el-menu-item>
      <el-menu-item index="3" @click="handleLogout" class="logout-item">
        <el-icon><SwitchButton /></el-icon>
        <span>Logout</span>
      </el-menu-item>
    </el-menu>

    <el-dialog v-model="showProfileDialog" title="Profil Ayarları" width="400px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="140px" label-position="left">
        <el-form-item label="Kullanıcı Adı">
          <el-input v-model="user.username" disabled />
        </el-form-item>
        <el-form-item label="Mevcut Şifre" prop="currentPassword">
          <el-input v-model="form.currentPassword" type="password" show-password />
        </el-form-item>
        <el-form-item label="Yeni Şifre" prop="newPassword">
          <el-input v-model="form.newPassword" type="password" show-password />
        </el-form-item>
        <el-form-item label="Yeni Şifre Tekrar" prop="confirmPassword">
          <el-input v-model="form.confirmPassword" type="password" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showProfileDialog = false">İptal</el-button>
        <el-button type="primary" @click="changePassword" :loading="loading">Şifreyi Değiştir</el-button>
      </template>
    </el-dialog>
  </el-aside>
</template>

<script setup>
import { ref, onMounted, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { HomeFilled, Setting, SwitchButton, User } from '@element-plus/icons-vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'

defineProps({ activeIndex: { type: String, default: '1' } })

const router = useRouter()
const user = ref(null)
const showProfileDialog = ref(false)
const loading = ref(false)
const formRef = ref(null)
const form = reactive({ currentPassword: '', newPassword: '', confirmPassword: '' })

const rules = {
  currentPassword: [{ required: true, message: 'Mevcut şifre gerekli', trigger: 'blur' }],
  newPassword: [
    { required: true, message: 'Yeni şifre gerekli', trigger: 'blur' },
    { min: 6, message: 'Şifre en az 6 karakter olmalı', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, trigger: 'blur' },
    { validator: (r, v, cb) => v === form.newPassword ? cb() : cb(new Error('Şifreler eşleşmiyor')), trigger: 'blur' }
  ]
}

const changePassword = async () => {
  await formRef.value?.validate(async (valid) => {
    if (!valid) return
    loading.value = true
    try {
      await axios.post('http://localhost:5001/api/change-password', {
        current_password: form.currentPassword,
        new_password: form.newPassword
      }, { withCredentials: true })
      ElMessage.success('Şifre başarıyla değiştirildi')
      showProfileDialog.value = false
      Object.assign(form, { currentPassword: '', newPassword: '', confirmPassword: '' })
      formRef.value.resetFields()
    } catch (error) {
      ElMessage.error(error.response?.data?.error || 'Şifre değiştirme başarısız')
    } finally {
      loading.value = false
    }
  })
}

const handleLogout = async () => {
  try {
    await axios.post('http://localhost:5001/api/logout', {}, { withCredentials: true })
    localStorage.removeItem('user')
    router.push('/login')
  } catch { ElMessage.error('Logout failed') }
}

onMounted(() => {
  const userData = localStorage.getItem('user')
  if (userData) user.value = JSON.parse(userData)
})
</script>

<style scoped>
.sidebar {
  background: #001529;
  display: flex;
  flex-direction: column;
  height: 100vh;
}

.sidebar-header {
  padding: 20px;
  border-bottom: 1px solid #ffffff1a;
}

.sidebar-header h3 {
  margin: 0 0 12px 0;
  color: #fff;
  font-size: 18px;
}

.user-info {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 8px;
  border-radius: 8px;
  transition: all 0.3s;
}

.user-info:hover {
  background: #ffffff1a;
}

.user-info span {
  color: #ffffff80;
  font-size: 14px;
}

.sidebar-menu {
  flex: 1;
  border: none;
  background: transparent;
  overflow: hidden;
}

:deep(.el-menu-item) {
  color: #ffffffa6;
  height: 48px;
  line-height: 48px;
}

:deep(.el-menu-item:hover) {
  background: #ffffff1a;
  color: #fff;
}

:deep(.el-menu-item.is-active) {
  background: #1890ff;
  color: #fff;
}

.logout-item {
  position: absolute;
  bottom: 0;
  width: 100%;
  border-top: 1px solid #ffffff1a;
}

:deep(.logout-item:hover) {
  background: #ff4d4f !important;
  color: #fff !important;
}

.el-icon svg {
    height: 1em;
    width: 1em;
    color: white;
}

:deep(.el-form-item__label)::before {
  content: '' !important;
  margin-right: 0 !important;
}

:deep(.el-form-item.is-required .el-form-item__label)::after {
  content: '*';
  color: var(--el-color-danger);
  margin-left: 4px;
}
</style>
