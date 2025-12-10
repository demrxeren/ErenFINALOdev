<template>
  <el-main class="main-layout">
    <div class="content-wrapper">
      
      <el-card class="box-card chart-card" header="Chart Area">
        <canvas ref="chartCanvas"></canvas>
      </el-card>
      
      <div class="controls-section">
        
        <el-alert
          v-if="!historyItem"
          :title="captureStatus.title"
          :type="captureStatus.type"
          :description="captureStatus.desc"
          show-icon
          :closable="false"
          style="margin-bottom: 10px;"
        />

        <el-dropdown trigger="click" @command="handleFilter" style="width: 100%;">
          <el-button type="warning" size="large" block>
            {{ filterLabel }} <el-icon class="el-icon--right"><ArrowDown /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="all">Show All</el-dropdown-item>
              <el-dropdown-item command="show-20">Show 20</el-dropdown-item>
              <el-dropdown-item command="temp-max">Highest Temp</el-dropdown-item>
              <el-dropdown-item command="temp-min">Lowest Temp</el-dropdown-item>
              <el-dropdown-item command="hum-max">Highest Humidity</el-dropdown-item>
              <el-dropdown-item command="hum-min">Lowest Humidity</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>

        <template v-if="!historyItem">
          <el-button type="success" size="large" @click="saveData" block>Save</el-button>
          <el-button type="danger" size="large" @click="clearAll" block>Clear</el-button>
          <el-button type="info" size="large" @click="$emit('open-history')" block>History</el-button>
        </template>
        <template v-else>
          <div class="history-info">
            <p>{{ historyItem.timestamp }}</p>
          </div>
        </template>
      </div>
      
      <el-card class="box-card picture-card" header="Picture Area">
        <!-- Geçmiş Modunda Photo Grid (All Photos) -->
        <div v-if="historyItem && historyPhotos.length > 0" class="history-grid">
          <div v-for="(photo, index) in historyPhotos" :key="index" class="grid-item" @click="openPhotoDialog(photo)">
            <img :src="photo.url" :alt="`Photo ${index + 1}`" />
            <div class="photo-timestamp">{{ new Date(photo.timestamp).toLocaleTimeString() }}</div>
          </div>
        </div>
        
        <!-- Normal Mod veya Tek Fotoğraf -->
        <div v-else class="image-wrapper">
          <img v-if="imgSrc" :src="imgSrc" />
          
          <div v-else class="no-photo-state">
             <el-icon size="40"><Camera /></el-icon>
             <span>{{ historyItem ? 'No Photo Saved' : 'Waiting for Auto Capture...' }}</span>
          </div>
        </div>
      </el-card>
      
      <!-- Fotoğraf Dialog -->
      <el-dialog v-model="photoDialogVisible" width="50%" :close-on-click-modal="true">
        <img v-if="selectedPhoto" :src="selectedPhoto.url" style="max-width: 100%; max-height: 70vh; width: auto; height: auto; display: block; margin: 0 auto;" />
        <template #header>
          <span>{{ selectedPhoto ? new Date(selectedPhoto.timestamp).toLocaleString() : '' }}</span>
        </template>
      </el-dialog>

    </div>
  </el-main>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, computed } from 'vue'
import Chart from 'chart.js/auto'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowDown, Camera } from '@element-plus/icons-vue'

const props = defineProps({ historyItem: Object, cameraId: { type: Number, default: 1 } })
defineEmits(['open-history'])

const chartCanvas = ref(null), photoUrl = ref(null), rawData = ref([]), filterType = ref('all'),
      capturedPhotos = ref([]), photoDialogVisible = ref(false), selectedPhoto = ref(null)
let chartInstance, intervalId, captureTimeoutId, photoErrorShown = false

const openPhotoDialog = (photo) => { selectedPhoto.value = photo; photoDialogVisible.value = true }
const imgSrc = computed(() => props.historyItem?.photo_image || photoUrl.value)
const historyPhotos = computed(() => props.historyItem?.photos?.length ? props.historyItem.photos : [])
const filterLabel = computed(() => ({ 'temp-max': 'Highest Temp', 'temp-min': 'Lowest Temp', 'hum-max': 'Highest Humidity', 'hum-min': 'Lowest Humidity', 'show-20': 'Show 20', 'all': 'Show All' }[filterType.value] || 'Show All'))
const currentTemp = computed(() => rawData.value.length ? rawData.value[rawData.value.length - 1].temperature : 0)
const captureStatus = computed(() => {
  const t = currentTemp.value
  return t >= 28 ? { title: 'ALARM', type: 'error', desc: 'Live Video Stream Active' } :
         t >= 24 ? { title: 'High Alert', type: 'warning', desc: 'Capture: Every 10s' } :
         t >= 20 ? { title: 'Attention', type: 'info', desc: 'Capture: Every 20s' } :
         { title: 'Normal', type: 'success', desc: 'Capture: Every 30s' }
})

const manageAutoCapture = async () => {
  if (props.historyItem) return
  const temp = currentTemp.value

  if (temp >= 28) {
    if (!photoUrl.value?.includes('/stream')) {
      try {
        const { data } = await axios.get('http://localhost:5001/api/cameras', { withCredentials: true })
        const cam = data.find(c => c.id === props.cameraId)
        if (cam) {
          let baseUrl = cam.ip_address.startsWith('http') ? cam.ip_address : `http://${cam.ip_address}`
          photoUrl.value = `${baseUrl}/stream`
        }
      } catch (e) { console.error("Kamera IP'si alınamadı:", e) }
    }
    clearTimeout(captureTimeoutId)
    captureTimeoutId = setTimeout(manageAutoCapture, 3000)
    return
  }

  if (photoUrl.value?.includes('/stream')) photoUrl.value = null
  await getLatestPhoto()
  clearTimeout(captureTimeoutId)
  captureTimeoutId = setTimeout(manageAutoCapture, 5000)
}

const handleFilter = (cmd) => { filterType.value = cmd; renderChart() }

const renderChart = () => {
  if (!chartInstance) return
  if (!rawData.value.length) {
    chartInstance.data.labels = []
    chartInstance.data.datasets[0].data = []
    chartInstance.data.datasets[1].data = []
    chartInstance.update()
    return
  }

  let show = []
  const data = [...rawData.value]

  if (filterType.value === 'show-20') {
    show = data.slice(-20)
  } else if (filterType.value !== 'all') {
    const comp = { 'temp-max': (a,b) => a.temperature > b.temperature, 'temp-min': (a,b) => a.temperature < b.temperature,
                   'hum-max': (a,b) => a.humidity > b.humidity, 'hum-min': (a,b) => a.humidity < b.humidity }[filterType.value]
    const idx = data.reduce((best, cur, i, arr) => comp(cur, arr[best]) ? i : best, 0)
    show = data.slice(Math.max(0, idx - 2), Math.min(data.length, idx + 3))
  } else show = data

  chartInstance.data.labels = show.map(d => new Date(d.timestamp).toLocaleTimeString())
  chartInstance.data.datasets[0].data = show.map(d => d.temperature)
  chartInstance.data.datasets[1].data = show.map(d => d.humidity)
  chartInstance.update()
}

const fetchData = async () => {
  if (props.historyItem || !chartInstance) return
  try {
    const { data } = await axios.get('http://localhost:5001/api/data', { params: { camera_id: props.cameraId }, withCredentials: true })
    if (!data || !Array.isArray(data)) return

    if (!rawData.value.length) rawData.value = data
    else {
      const lastId = rawData.value[rawData.value.length - 1].id
      const newData = data.filter(i => i.id > lastId)
      if (newData.length) rawData.value.push(...newData)
    }
    renderChart()
  } catch (e) { console.error("Veri çekme hatası:", e) }
}

const getLatestPhoto = async () => {
  try {
    const { data } = await axios.get('http://localhost:5001/api/photos', { params: { camera_id: props.cameraId }, withCredentials: true })
    if (data[0]?.url && photoUrl.value !== data[0].url) {
      photoUrl.value = data[0].url
      capturedPhotos.value.push({ url: data[0].url, timestamp: new Date().toISOString() })
    }
    photoErrorShown = false
  } catch (e) { if (!photoErrorShown) { console.warn('⚠ Camera device not available'); photoErrorShown = true } }
}

const saveData = async () => {
  if (!chartInstance) return
  try {
    await axios.post('http://localhost:5001/api/save-history', {
      camera_id: props.cameraId, chartImage: chartInstance.toBase64Image(),
      photoUrl: photoUrl.value, sensorData: rawData.value, photos: capturedPhotos.value
    }, { withCredentials: true })
    ElMessage.success('Saved!')
  } catch { ElMessage.error('Failed to save') }
}

const clearAll = async () => {
  try {
    await ElMessageBox.confirm('Clear all data?', 'Warning', { confirmButtonText: 'Yes', cancelButtonText: 'No', type: 'warning' })
    await axios.delete('http://localhost:5001/api/data', { params: { camera_id: props.cameraId }, withCredentials: true })
    photoUrl.value = null; rawData.value = []; capturedPhotos.value = []; renderChart()
    ElMessage.success('Cleared')
  } catch {}
}

watch(() => props.historyItem, (item) => {
  clearInterval(intervalId); clearTimeout(captureTimeoutId)
  if (item?.sensor_data) {
    rawData.value = Array.isArray(item.sensor_data) ? item.sensor_data : []
    filterType.value = 'all'; renderChart()
  } else {
    rawData.value = []; filterType.value = 'all'; renderChart()
    fetchData(); intervalId = setInterval(fetchData, 3000); manageAutoCapture()
  }
})

onMounted(() => {
  chartInstance = new Chart(chartCanvas.value.getContext('2d'), {
    type: 'line', data: { labels: [], datasets: [
      { label: 'Temp', data: [], borderColor: 'orange', tension: 0.1 },
      { label: 'Humidity', data: [], borderColor: 'lightblue', tension: 0.1 }
    ]}, options: { responsive: true, maintainAspectRatio: false }
  })
  if (props.historyItem) return
  fetchData(); intervalId = setInterval(fetchData, 3000); manageAutoCapture()
})

onUnmounted(() => { clearInterval(intervalId); clearTimeout(captureTimeoutId); chartInstance?.destroy() })
</script>

<style scoped>
.main-layout { 
  flex: 1;
  display: flex; 
  align-items: center; 
  padding: 20px; 
}

.content-wrapper { 
  display: flex; 
  width: 100%; 
  height: 600px; 
  gap: 20px; 
  align-items: stretch;
}

.box-card { 
  flex: 1; 
  display: flex; 
  flex-direction: column; 
}

.chart-card {
  flex: 1;
}

.controls-section { 
  width: 200px;
  display: flex; 
  flex-direction: column;
  gap: 16px;
  justify-content: center;
}

.controls-section .el-button {
  margin: 0;
}

.history-info {
  text-align: center;
  padding: 20px;
  background: white;
  border-radius: 4px;
  color: #909399;
}

.history-info p {
  margin: 0;
  font-size: 14px;
}

.picture-card {
  flex: 1;
}

.image-wrapper {
  width: 100%;
  height: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
  overflow: hidden;
  background-color: #f5f7fa;
}

.image-wrapper img { 
  max-width: 100%; 
  max-height: 100%;
  object-fit: contain;
}

.history-grid {
  width: 100%;
  height: 100%;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  grid-auto-rows: minmax(150px, 1fr);
  gap: 8px;
  padding: 8px;
  overflow-y: auto;
  background-color: #f5f7fa;
  align-content: start;
}

.grid-item {
  width: 100%;
  height: 100%;
  overflow: hidden;
  border-radius: 4px;
  border: 1px solid #dcdfe6;
  background-color: white;
  cursor: pointer;
  position: relative;
  transition: transform 0.2s, box-shadow 0.2s;
}

.grid-item:hover {
  transform: scale(1.05);
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
  z-index: 1;
}

.grid-item img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.photo-timestamp {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  background: rgba(0, 0, 0, 0.7);
  color: white;
  padding: 4px;
  font-size: 10px;
  text-align: center;
}

.no-photo-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  color: #909399;
  gap: 10px;
}

span { 
  color: #909399; 
  font-size: 1.2rem; 
}

:deep(.el-card__body) { 
  flex: 1; 
  display: flex; 
  flex-direction: column;
  justify-content: center; 
  align-items: center; 
  padding: 20px; 
}

:deep(.el-card__header) { 
  text-align: center; 
  font-weight: bold; 
  padding: 10px; 
}
.controls-section .el-dropdown {
  width: 100%;
}

.controls-section :deep(.el-dropdown .el-button) {
  width: 100%;
}
</style>