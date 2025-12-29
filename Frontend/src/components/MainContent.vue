<template>
  <el-main class="main-layout">
    <div class="content-wrapper">

      <el-card class="box-card chart-card" header="Chart Area">
        <canvas ref="chartCanvas"></canvas>
      </el-card>

      <div class="controls-section">

        <el-alert v-if="!historyItem" :title="captureStatus.title" :type="captureStatus.type"
          :description="captureStatus.desc" show-icon :closable="false" style="margin-bottom: 10px;" />

        <div class="date-time-filter">
          <div class="date-time-inputs">
            <div class="time-group">
              <label>Start Date & Time:</label>
              <el-date-picker v-model="startDateTime" type="datetime" placeholder="Select start date & time"
                size="small" format="DD/MM/YYYY HH:mm" value-format="YYYY-MM-DD HH:mm:ss" @change="renderChart" />
            </div>
            <div class="time-group">
              <label>End Date & Time:</label>
              <el-date-picker v-model="endDateTime" type="datetime" placeholder="Select end date & time" size="small"
                format="DD/MM/YYYY HH:mm" value-format="YYYY-MM-DD HH:mm:ss" @change="renderChart" />
            </div>
          </div>
        </div>

        <el-dropdown trigger="click" @command="handleFilter" style="width: 100%;">
          <el-button type="warning" size="large" block>
            {{ filterLabel }} <el-icon class="el-icon--right">
              <ArrowDown />
            </el-icon>
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
            <p>{{ formatDate(historyItem.timestamp) }}</p>
          </div>
        </template>
      </div>

      <el-card class="box-card picture-card" :class="{ 'is-streaming': photoUrl?.includes('/stream') }">
        <template #header>
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <span>Picture Area</span>
            <el-tag v-if="photoUrl?.includes('/stream')" type="danger" effect="dark" size="small">LIVE STREAM</el-tag>
          </div>
        </template>

        <div v-if="photoUrl?.includes('/stream')" class="stream-container">
          <img :src="photoUrl" class="stream-image" />
        </div>

        <div v-else-if="historyPhotos.length > 0" class="history-grid">
          <div v-for="(photo, index) in historyPhotos" :key="index" class="grid-item" @click="openPhotoDialog(photo)">
            <img :src="photo.url" :alt="`Photo ${index + 1}`" />
            <div class="photo-timestamp">{{ formatDate(photo.timestamp) }}</div>
          </div>
        </div>

        <div v-else class="image-wrapper">
          <div class="no-photo-state">
            <el-icon size="40">
              <Camera />
            </el-icon>
            <span>{{ historyItem ? 'No Photo Saved' : 'No photos in selected time range' }}</span>
          </div>
        </div>
      </el-card>

      <el-dialog v-model="photoDialogVisible" width="50%" :close-on-click-modal="true">
        <img v-if="selectedPhoto" :src="selectedPhoto.url"
          style="max-width: 100%; max-height: 70vh; width: auto; height: auto; display: block; margin: 0 auto;" />
        <template #header>
          <span>{{ selectedPhoto ? formatDate(selectedPhoto.timestamp) : '' }}</span>
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
import { startCapture, stopCapture, getPhotos, clearPhotos, setCurrentTemp, getCaptureState } from '../services/photoService'

const props = defineProps({ historyItem: Object, cameraId: { type: Number, default: 1 } })
const emit = defineEmits(['open-history', 'show-history-with-data'])

const chartCanvas = ref(null), rawData = ref([]), filterType = ref('all'),
  photoDialogVisible = ref(false), selectedPhoto = ref(null)

// Initialize date range to today (start of day to end of day)
const getDefaultStartDate = () => {
  const d = new Date()
  d.setHours(0, 0, 0, 0)
  return d
}
const getDefaultEndDate = () => {
  const d = new Date()
  d.setHours(23, 59, 59, 999)
  return d
}
const startDateTime = ref(getDefaultStartDate())
const endDateTime = ref(getDefaultEndDate())
let chartInstance, intervalId, photoErrorShown = false

const photoUrl = computed(() => getCaptureState(props.cameraId)?.url)

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  if (isNaN(d.getTime())) return dateStr
  const pad = (n) => n.toString().padStart(2, '0')
  return `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.${d.getFullYear()} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

const openPhotoDialog = (photo) => { selectedPhoto.value = photo; photoDialogVisible.value = true }
const historyPhotos = computed(() => {
  let photos = []

  // Get start and end as Date objects
  const start = startDateTime.value ? new Date(startDateTime.value) : null
  const end = endDateTime.value ? new Date(endDateTime.value) : null

  // History modunda history item'daki photos
  if (props.historyItem?.photos?.length) {
    photos = props.historyItem.photos.filter(photo => {
      const photoDate = new Date(photo.timestamp)
      if (start && photoDate < start) return false
      if (end && photoDate > end) return false
      return true
    })
  }

  // Live modunda captured photos (now from service)
  if (!props.historyItem) {
    const servicePhotos = getPhotos(props.cameraId)
    photos = servicePhotos.filter(photo => {
      const photoDate = new Date(photo.timestamp)
      if (start && photoDate < start) return false
      if (end && photoDate > end) return false
      return true
    })
  }

  // En yeni fotoğraflar en üstte olacak şekilde sırala
  return photos.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))
})
const filterLabel = computed(() => ({ 'temp-max': 'Highest Temp', 'temp-min': 'Lowest Temp', 'hum-max': 'Highest Humidity', 'hum-min': 'Lowest Humidity', 'show-20': 'Show 20', 'all': 'Show All' }[filterType.value] || 'Show All'))
const currentTemp = computed(() => rawData.value.length ? rawData.value[rawData.value.length - 1].temperature : 0)
const captureStatus = computed(() => {
  const t = currentTemp.value
  return t >= 26 ? { title: 'ALARM', type: 'error', desc: 'Live Video Stream Active' } :
    t >= 24 ? { title: 'Attention', type: 'warning', desc: 'Capture: Every 10s' } :
      t >= 22 ? { title: 'Normal', type: 'info', desc: 'Capture: Every 20s' } :
        { title: 'Cool', type: 'success', desc: 'Capture: Every 30s' }
})



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
  let data = [...rawData.value]

  // Get start and end as Date objects
  const start = startDateTime.value ? new Date(startDateTime.value) : null
  const end = endDateTime.value ? new Date(endDateTime.value) : null

  // Apply date-time range filter
  data = data.filter(d => {
    const dataDate = new Date(d.timestamp)
    if (start && dataDate < start) return false
    if (end && dataDate > end) return false
    return true
  })

  if (filterType.value === 'show-20') {
    show = data.slice(-20)
  } else if (filterType.value !== 'all') {
    const comp = {
      'temp-max': (a, b) => a.temperature > b.temperature, 'temp-min': (a, b) => a.temperature < b.temperature,
      'hum-max': (a, b) => a.humidity > b.humidity, 'hum-min': (a, b) => a.humidity < b.humidity
    }[filterType.value]
    const idx = data.reduce((best, cur, i, arr) => comp(cur, arr[best]) ? i : best, 0)
    show = data.slice(Math.max(0, idx - 2), Math.min(data.length, idx + 3))
  } else show = data

  chartInstance.data.labels = show.map(d => formatDate(d.timestamp))
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
    setCurrentTemp(props.cameraId, currentTemp.value)
    renderChart()
  } catch (e) { console.error("Veri çekme hatası:", e) }
}

const getLatestPhoto = async () => {
  // Photo capture is now handled by the background service
  // This method is kept for compatibility but does nothing
}

const saveData = async () => {
  if (!chartInstance) return
  try {
    const response = await axios.post('http://localhost:5001/api/save-history', {
      camera_id: props.cameraId, chartImage: chartInstance.toBase64Image(),
      photoUrl: photoUrl.value, sensorData: rawData.value, photos: getPhotos(props.cameraId)
    }, { withCredentials: true })
    ElMessage.success('Saved!')
    // After save, show the history with the saved data
    await new Promise(resolve => setTimeout(resolve, 500))
    const historyId = response.data.id
    if (historyId) {
      // Fetch the newly saved history item
      const { data: historyData } = await axios.get('http://localhost:5001/api/history', {
        params: { camera_id: props.cameraId }, withCredentials: true
      })
      const savedItem = historyData.find(item => item.id === historyId)
      if (savedItem) {
        // Emit event to parent to show this history item
        emit('show-history-with-data', savedItem)
      }
    }
  } catch (e) {
    console.error('Save error:', e)
    ElMessage.error('Failed to save')
  }
}

const clearAll = async () => {
  try {
    await ElMessageBox.confirm('Clear all data?', 'Warning', { confirmButtonText: 'Yes', cancelButtonText: 'No', type: 'warning' })
    await axios.delete('http://localhost:5001/api/data', { params: { camera_id: props.cameraId }, withCredentials: true })
    rawData.value = []; clearPhotos(props.cameraId); renderChart()
    ElMessage.success('Cleared')
  } catch { }
}

watch(() => props.historyItem, (item) => {
  clearInterval(intervalId)
  // Reset date range to today
  startDateTime.value = getDefaultStartDate()
  endDateTime.value = getDefaultEndDate()
  if (item?.sensor_data) {
    rawData.value = Array.isArray(item.sensor_data) ? item.sensor_data : []
    filterType.value = 'all'; renderChart()
  } else {
    rawData.value = []; filterType.value = 'all'; renderChart()
    fetchData(); intervalId = setInterval(fetchData, 3000)
  }
})

watch([() => startDateTime.value, () => endDateTime.value], () => {
  // Update chart and photos when date range changes
  renderChart()
})

onMounted(() => {
  chartInstance = new Chart(chartCanvas.value.getContext('2d'), {
    type: 'line', data: {
      labels: [], datasets: [
        { label: 'Temp', data: [], borderColor: 'orange', tension: 0.1 },
        { label: 'Humidity', data: [], borderColor: 'lightblue', tension: 0.1 }
      ]
    }, options: { responsive: true, maintainAspectRatio: false }
  })
  if (props.historyItem) return

  // Start background capture for this camera
  startCapture(props.cameraId)

  fetchData(); intervalId = setInterval(fetchData, 3000)
})

onUnmounted(() => {
  clearInterval(intervalId)
  chartInstance?.destroy()
  // Note: Don't stop capture here - let it continue in background
})
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

.date-range-filter {
  width: 100%;
}

.date-range-filter :deep(.el-input__wrapper) {
  padding: 2px 8px;
}

.date-range-filter :deep(.el-input) {
  font-size: 12px;
}

.date-time-filter {
  background: white;
  padding: 12px;
  border-radius: 4px;
  border: 1px solid #dcdfe6;
}

.date-time-inputs {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.time-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.time-group label {
  font-size: 12px;
  color: #606266;
  font-weight: 600;
}

.date-time-filter :deep(.el-date-editor) {
  width: 100% !important;
}

.date-time-filter :deep(.el-input__wrapper) {
  padding: 4px 8px;
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
  min-height: 0;
}

.picture-card :deep(.el-card__body) {
  height: 100%;
  overflow: hidden;
  padding: 0;
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

.stream-container {
  width: 100%;
  height: 300px;
  background: #fff;
  display: flex;
  justify-content: center;
  align-items: center;
  overflow: hidden;
  border-bottom: 2px solid #dcdfe6;
}

.stream-image {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  transform: scale(1.2);
  transition: transform 0.3s ease;
}

.history-grid {
  width: 100%;
  height: 100%;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  grid-auto-rows: 150px;
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
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
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