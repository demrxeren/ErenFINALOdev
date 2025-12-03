<template>
  <el-aside width="200px" class="sidebar">
    <div class="sidebar-header">
      <h3>ESP32-CAM</h3>
      <div class="user-info">
        <span>{{ user?.username }}</span>
      </div>
    </div>
    
    <el-menu :default-active="activeIndex" class="sidebar-menu">
      <el-menu-item index="1" @click="navigateTo('/dashboard')">
        <el-icon><HomeFilled /></el-icon>
        <span>Dashboard</span>
      </el-menu-item>
      
      <el-menu-item v-if="user?.is_admin" index="2" @click="navigateTo('/admin')">
        <el-icon><Setting /></el-icon>
        <span>Admin</span>
      </el-menu-item>
      
      <el-menu-item index="3" @click="handleLogout" class="logout-item">
        <el-icon><SwitchButton /></el-icon>
        <span>Logout</span>
      </el-menu-item>
    </el-menu>
  </el-aside>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { HomeFilled, Setting, SwitchButton } from '@element-plus/icons-vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'

const router = useRouter()
const route = useRoute()
const user = ref(null)

const props = defineProps({ 
  activeIndex: { type: String, default: '1' } 
})

const navigateTo = (path) => {
  router.push(path)
}

const handleLogout = async () => {
  try {
    await axios.post('http://localhost:5001/api/logout', {}, {
      withCredentials: true
    })
    localStorage.removeItem('user')
    router.push('/login')
  } catch (error) {
    ElMessage.error('Logout failed')
  }
}

onMounted(() => {
  const userData = localStorage.getItem('user')
  if (userData) {
    user.value = JSON.parse(userData)
  }
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
</style>
