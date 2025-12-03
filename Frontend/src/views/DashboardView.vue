<template>
  <el-container class="dashboard-container">
    <AppSidebar active-index="1" />
    
    <el-container class="main-container">
      <el-header class="dashboard-header">
        <h2>Select Camera</h2>
        <el-button 
          v-if="user?.is_admin" 
          type="primary" 
          @click="showCameraDialog = true"
        >
          <el-icon><Plus /></el-icon>
          Add New Camera
        </el-button>
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
                    v-if="camera.id !== 1"
                    type="primary" 
                    size="small" 
                    circle
                    icon="Edit"
                    @click.stop="editCamera(camera)"
                  />
                  <el-button 
                    v-if="camera.id !== 1"
                    type="danger" 
                    size="small" 
                    circle
                    icon="Delete"
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

      <!-- Camera Management Dialog -->
      <el-dialog v-model="showCameraDialog" :title="editMode ? 'Edit Camera' : 'Add New Camera'" width="500px">
        <el-form :model="cameraForm" ref="cameraFormRef" :rules="cameraRules">
          <el-form-item label="Camera Name" prop="name">
            <el-input v-model="cameraForm.name" placeholder="e.g. Front Door" />
          </el-form-item>
          <el-form-item label="IP Address" prop="ip_address">
            <el-input v-model="cameraForm.ip_address" placeholder="http://192.168.1.100" />
          </el-form-item>
          <el-form-item label="Location">
            <el-input v-model="cameraForm.location" placeholder="e.g. Building A, Floor 1" />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="cancelEdit">Cancel</el-button>
          <el-button type="primary" @click="saveCamera">{{ editMode ? 'Update' : 'Add' }}</el-button>
        </template>
      </el-dialog>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import AppSidebar from '../components/AppSidebar.vue'

const router = useRouter()
const user = ref(null)
const cameras = ref([])
const showCameraDialog = ref(false)
const cameraFormRef = ref(null)
const editMode = ref(false)
const editingCameraId = ref(null)

const cameraForm = reactive({
  name: '',
  ip_address: '',
  location: ''
})

const cameraRules = {
  name: [{ required: true, message: 'Camera name is required', trigger: 'blur' }],
  ip_address: [{ required: true, message: 'IP address is required', trigger: 'blur' }]
}

const fetchCameras = async () => {
  try {
    const response = await axios.get('http://localhost:5001/api/cameras', {
      withCredentials: true
    })
    cameras.value = response.data
  } catch (error) {
    ElMessage.error('Failed to load cameras')
  }
}

const editCamera = (camera) => {
  editMode.value = true
  editingCameraId.value = camera.id
  cameraForm.name = camera.name
  cameraForm.ip_address = camera.ip_address
  cameraForm.location = camera.location || ''
  showCameraDialog.value = true
}

const cancelEdit = () => {
  showCameraDialog.value = false
  editMode.value = false
  editingCameraId.value = null
  cameraForm.name = ''
  cameraForm.ip_address = ''
  cameraForm.location = ''
}

const saveCamera = async () => {
  if (!cameraFormRef.value) return
  
  await cameraFormRef.value.validate(async (valid) => {
    if (!valid) return
    
    try {
      if (editMode.value) {
        await axios.put(`http://localhost:5001/api/cameras/${editingCameraId.value}`, cameraForm, {
          withCredentials: true
        })
        ElMessage.success('Camera updated successfully')
      } else {
        await axios.post('http://localhost:5001/api/cameras', cameraForm, {
          withCredentials: true
        })
        ElMessage.success('Camera added successfully')
      }
      cancelEdit()
      fetchCameras()
    } catch (error) {
      ElMessage.error(editMode.value ? 'Failed to update camera' : 'Failed to add camera')
    }
  })
}

const deleteCamera = async (id, name) => {
  try {
    const message = id === 1 
      ? `Are you sure you want to delete "${name}"? This is the main camera and deleting it may affect system functionality.`
      : `Delete camera "${name}"?`
    
    await ElMessageBox.confirm(message, 'Warning', {
      confirmButtonText: 'Yes, Delete',
      cancelButtonText: 'Cancel',
      type: 'warning',
      dangerouslyUseHTMLString: false
    })
    await axios.delete(`http://localhost:5001/api/cameras/${id}`, {
      withCredentials: true
    })
    ElMessage.success('Camera deleted')
    fetchCameras()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('Failed to delete camera')
    }
  }
}

const selectCamera = (camera) => {
  router.push({ name: 'camera', params: { id: camera.id } })
}

onMounted(async () => {
  const userData = localStorage.getItem('user')
  if (userData) {
    user.value = JSON.parse(userData)
  }
  
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
