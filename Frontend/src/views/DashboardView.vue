<template>
  <el-container class="dashboard-container">
    <AppSidebar active-index="1" />
    
    <el-container class="main-container">
      <el-header class="dashboard-header">
        <h2>Select Camera</h2>
      </el-header>
      
      <el-main>
        <div class="camera-grid">
          <el-card 
            v-for="camera in cameras" 
            :key="camera.id" 
            class="camera-card"
            shadow="hover"
            @click="selectCamera(camera)"
          >
            <template #header>
              <div class="card-header">
                <span>{{ camera.name }}</span>
                <div class="card-actions" v-if="user?.is_admin">
                  <el-button 
                    type="primary" 
                    size="small" 
                    circle
                    :icon="Edit" 
                    @click.stop="editCamera(camera)"
                  />
                  <el-button 
                    type="danger" 
                    size="small" 
                    circle
                    :icon="Delete"
                    @click.stop="deleteCamera(camera.id, camera.name)"
                  />
                </div>
              </div>
            </template>
            <div class="camera-info">
              <p><strong>IP:</strong> {{ camera.ip_address }}</p>
              <p v-if="camera.location"><strong>Location:</strong> {{ camera.location }}</p>
            </div>
            <el-button type="primary" block>View Camera</el-button>
          </el-card>
        </div>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Edit, Delete } from '@element-plus/icons-vue'
import AppSidebar from '../components/AppSidebar.vue'

const router = useRouter()
const user = ref(null)
const cameras = ref([])

const fetchCameras = async () => {
  try {
    const { data } = await axios.get('http://localhost:5001/api/cameras', { withCredentials: true })
    cameras.value = data
  } catch { ElMessage.error('Failed to load cameras') }
}

const editCamera = () => ElMessage.info('Edit functionality not available')

const deleteCamera = async (id, name) => {
  try {
    await ElMessageBox.confirm(
      id === 1 ? `Are you sure you want to delete "${name}"? This is the main camera.` : `Delete camera "${name}"?`,
      'Warning', { confirmButtonText: 'Yes, Delete', cancelButtonText: 'Cancel', type: 'warning' }
    )
    await axios.delete(`http://localhost:5001/api/cameras/${id}`, { withCredentials: true })
    ElMessage.success('Camera deleted')
    fetchCameras()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('Failed to delete camera')
  }
}

const selectCamera = (camera) => router.push({ name: 'camera', params: { id: camera.id } })

onMounted(async () => {
  const userData = localStorage.getItem('user')
  if (userData) user.value = JSON.parse(userData)
  await fetchCameras()
})
</script>

<style scoped>
.dashboard-container {
  min-height: 100vh;
  background: #e4e7ed;
}

.main-container {
  flex: 1;
}

.dashboard-header {
  background: white;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 32px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.dashboard-header h2 {
  margin: 0;
  color: #303133;
}

.camera-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 24px;
  padding: 32px;
}

.camera-card {
  cursor: pointer;
  transition: transform 0.2s;
  border: 1px solid #dcdfe6;
}

.camera-card:hover {
  transform: translateY(-4px);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-actions {
  display: flex;
  gap: 8px;
}

.camera-info {
  margin-bottom: 16px;
}

.camera-info p {
  margin: 8px 0;
  color: #606266;
}
</style>