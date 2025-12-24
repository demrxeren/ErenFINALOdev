<template>
  <el-container class="h-screen">
    <AppSidebar active-index="1" />
    <el-container class="main-layout">
      <el-header class="camera-header">
        <div class="header-left">
          <el-button @click="selectedHistoryItem ? selectedHistoryItem = null : router.push('/dashboard')" circle type="primary">
            <el-icon><ArrowLeft /></el-icon>
          </el-button>
          <h2>{{ camera?.name }}</h2>
        </div>
      </el-header>
      <el-container>
        <MainContent :history-item="selectedHistoryItem" :camera-id="cameraId" @open-history="showHistoryDrawer = true" @show-history-with-data="selectedHistoryItem = $event" />
      </el-container>
      <HistoryDrawer v-model:visible="showHistoryDrawer" :camera-id="cameraId" @select-item="(item) => { selectedHistoryItem = item; showHistoryDrawer = false }" />
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import AppSidebar from '../components/AppSidebar.vue'
import MainContent from '../components/MainContent.vue'
import HistoryDrawer from '../components/HistoryDrawer.vue'
import { ElMessage } from 'element-plus'
import { ArrowLeft } from '@element-plus/icons-vue'

const route = useRoute(), router = useRouter(),
      cameraId = ref(parseInt(route.params.id)), camera = ref(null),
      showHistoryDrawer = ref(false), selectedHistoryItem = ref(null)

onMounted(async () => {
  try {
    const { data } = await axios.get('http://localhost:5001/api/cameras', { withCredentials: true })
    camera.value = data.find(c => c.id === cameraId.value)
  } catch { ElMessage.error('Failed to load camera') }
})
</script>

<style scoped>
.h-screen { height: 100vh; background: #e4e7ed; }
.main-layout { flex: 1; display: flex; flex-direction: column; }
.camera-header { background: white; display: flex; align-items: center; justify-content: space-between; padding: 0 24px; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1); }
.header-left { display: flex; align-items: center; gap: 16px; }
.camera-header h2 { margin: 0; color: #303133; }
</style>
