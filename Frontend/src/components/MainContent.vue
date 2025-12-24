<template>
  <el-main class="main-layout">
    <div class="content-wrapper">
      <el-card class="box-card chart-card" header="Chart Area">
        <canvas ref="chartCanvas"></canvas>
      </el-card>

      <div class="controls-section">
        <el-alert v-if="!historyItem" :title="captureStatus.title" :type="captureStatus.type"
          :description="captureStatus.desc" show-icon :closable="false" style="margin-bottom: 10px;" />

        <div class="hour-range-filter">
          <div class="hour-inputs">
            <div class="time-group" v-for="(cfg, key) in {start: {label: 'Start Time:', hour: startHour, minute: startMinute}, end: {label: 'End Time:', hour: endHour, minute: endMinute}}" :key="key">
              <label>{{ cfg.label }}</label>
              <div class="time-inputs">
                <div class="input-wrapper">
                  <span class="time-label">Hour:</span>
                  <el-input-number v-model="cfg.hour" :min="0" :max="23" size="small" @change="renderChart" />
                </div>
                <div class="input-wrapper">
                  <span class="time-label">Minute:</span>
                  <el-input-number v-model="cfg.minute" :min="0" :max="59" size="small" @change="renderChart" />
                </div>
              </div>
            </div>
          </div>
        </div>

        <el-dropdown trigger="click" @command="handleFilter" style="width: 100%;">
          <el-button type="warning" size="large" block>
            {{ filterLabels[filterType] || 'Show All' }} <el-icon class="el-icon--right"><ArrowDown /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item v-for="(label, cmd) in filterLabels" :key="cmd" :command="cmd">{{ label }}</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>

        <template v-if="!historyItem">
          <el-button type="success" size="large" @click="saveData" block>Save</el-button>
          <el-button type="danger" size="large" @click="clearAll" block>Clear</el-button>
          <el-button type="info" size="large" @click="$emit('open-history')" block>History</el-button>
        </template>
        <template v-else>
          <div class="history-info"><p>{{ historyItem.timestamp }}</p></div>
        </template>
      </div>

      <el-card class="box-card picture-card" header="Picture Area">
        <div v-if="historyPhotos.length > 0" class="history-grid">
          <div v-for="(photo, index) in historyPhotos" :key="index" class="grid-item" @click="selectedPhoto = photo; photoDialogVisible = true">
            <img :src="photo.url" :alt="`Photo ${index + 1}`" />
            <div class="photo-timestamp">{{ new Date(photo.timestamp).toLocaleTimeString() }}</div>
          </div>
        </div>
        <div v-else class="image-wrapper">
          <div class="no-photo-state">
            <el-icon size="40"><Camera /></el-icon>
            <span>{{ historyItem ? 'No Photo Saved' : 'No photos in selected time range' }}</span>
          </div>
        </div>
      </el-card>

      <el-dialog v-model="photoDialogVisible" width="50%" :close-on-click-modal="true">
        <img v-if="selectedPhoto" :src="selectedPhoto.url" style="max-width: 100%; max-height: 70vh; width: auto; height: auto; display: block; margin: 0 auto;" />
        <template #header><span>{{ selectedPhoto ? new Date(selectedPhoto.timestamp).toLocaleString() : '' }}</span></template>
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
import { startCapture, getPhotos, clearPhotos, setCurrentTemp } from '../services/photoService'

const props = defineProps({ historyItem: Object, cameraId: { type: Number, default: 1 } })
const emit = defineEmits(['open-history', 'show-history-with-data'])

const chartCanvas = ref(null), rawData = ref([]), filterType = ref('all'),
  photoDialogVisible = ref(false), selectedPhoto = ref(null),
  startHour = ref(0), startMinute = ref(0), endHour = ref(23), endMinute = ref(59)
let chartInstance, intervalId

const filterLabels = { 'all': 'Show All', 'show-20': 'Show 20', 'temp-max': 'Highest Temp', 'temp-min': 'Lowest Temp', 'hum-max': 'Highest Humidity', 'hum-min': 'Lowest Humidity' }

const filterByTimeRange = (items, getTimestamp) => {
  const startTime = startHour.value * 60 + startMinute.value
  const endTime = endHour.value * 60 + endMinute.value
  return items.filter(item => {
    const d = new Date(getTimestamp(item))
    const t = d.getHours() * 60 + d.getMinutes()
    return t >= startTime && t < endTime
  })
}

const historyPhotos = computed(() => {
  let photos = props.historyItem?.photos?.length ? props.historyItem.photos : (!props.historyItem ? getPhotos(props.cameraId) : [])
  return filterByTimeRange(photos, p => p.timestamp).sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))
})

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
  setCurrentTemp(props.cameraId, currentTemp.value)
}

const handleFilter = (cmd) => { filterType.value = cmd; renderChart() }

const renderChart = () => {
  if (!chartInstance || !rawData.value.length) {
    if (chartInstance) { chartInstance.data.labels = []; chartInstance.data.datasets.forEach(ds => ds.data = []); chartInstance.update() }
    return
  }
  let data = filterByTimeRange([...rawData.value], d => d.timestamp), show = []
  if (filterType.value === 'show-20') show = data.slice(-20)
  else if (filterType.value !== 'all') {
    const comp = { 'temp-max': (a, b) => a.temperature > b.temperature, 'temp-min': (a, b) => a.temperature < b.temperature,
      'hum-max': (a, b) => a.humidity > b.humidity, 'hum-min': (a, b) => a.humidity < b.humidity }[filterType.value]
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
    if (!data?.length) return
    if (!rawData.value.length) rawData.value = data
    else {
      const lastId = rawData.value[rawData.value.length - 1].id
      const newData = data.filter(i => i.id > lastId)
      if (newData.length) rawData.value.push(...newData)
    }
    renderChart()
  } catch {}
}

const saveData = async () => {
  if (!chartInstance) return
  try {
    const { data: response } = await axios.post('http://localhost:5001/api/save-history', {
      camera_id: props.cameraId, chartImage: chartInstance.toBase64Image(),
      photoUrl: null, sensorData: rawData.value, photos: getPhotos(props.cameraId)
    }, { withCredentials: true })
    ElMessage.success('Saved!')
    await new Promise(r => setTimeout(r, 500))
    if (response.id) {
      const { data: historyData } = await axios.get('http://localhost:5001/api/history', { params: { camera_id: props.cameraId }, withCredentials: true })
      const savedItem = historyData.find(item => item.id === response.id)
      if (savedItem) emit('show-history-with-data', savedItem)
    }
  } catch { ElMessage.error('Failed to save') }
}

const clearAll = async () => {
  try {
    await ElMessageBox.confirm('Clear all data?', 'Warning', { confirmButtonText: 'Yes', cancelButtonText: 'No', type: 'warning' })
    await axios.delete('http://localhost:5001/api/data', { params: { camera_id: props.cameraId }, withCredentials: true })
    rawData.value = []; clearPhotos(props.cameraId); renderChart()
    ElMessage.success('Cleared')
  } catch {}
}

watch(() => props.historyItem, (item) => {
  clearInterval(intervalId)
  startHour.value = 0; startMinute.value = 0; endHour.value = 23; endMinute.value = 59
  if (item?.sensor_data) { rawData.value = Array.isArray(item.sensor_data) ? item.sensor_data : []; filterType.value = 'all'; renderChart() }
  else { rawData.value = []; filterType.value = 'all'; renderChart(); fetchData(); intervalId = setInterval(fetchData, 3000); manageAutoCapture() }
})

watch([() => startHour.value, () => startMinute.value, () => endHour.value, () => endMinute.value], renderChart)

onMounted(() => {
  chartInstance = new Chart(chartCanvas.value.getContext('2d'), {
    type: 'line', data: { labels: [], datasets: [
      { label: 'Temp', data: [], borderColor: 'orange', tension: 0.1 },
      { label: 'Humidity', data: [], borderColor: 'lightblue', tension: 0.1 }
    ]}, options: { responsive: true, maintainAspectRatio: false }
  })
  if (props.historyItem) return
  startCapture(props.cameraId)
  fetchData(); intervalId = setInterval(fetchData, 3000); manageAutoCapture()
})

onUnmounted(() => { clearInterval(intervalId); chartInstance?.destroy() })
</script>

<style scoped>
.main-layout { flex: 1; display: flex; align-items: center; padding: 20px; }
.content-wrapper { display: flex; width: 100%; height: 600px; gap: 20px; align-items: stretch; }
.box-card { flex: 1; display: flex; flex-direction: column; }
.controls-section { width: 200px; display: flex; flex-direction: column; gap: 16px; justify-content: center; }
.controls-section .el-button, .controls-section .el-dropdown { margin: 0; width: 100%; }
.controls-section :deep(.el-dropdown .el-button) { width: 100%; }
.hour-range-filter { background: white; padding: 12px; border-radius: 4px; border: 1px solid #dcdfe6; }
.hour-inputs { display: flex; flex-direction: column; gap: 12px; }
.time-group { display: flex; flex-direction: column; gap: 6px; }
.time-group label { font-size: 12px; color: #606266; font-weight: 600; }
.time-inputs { display: flex; gap: 6px; width: 100%; }
.input-wrapper { flex: 1; display: flex; flex-direction: column; gap: 3px; }
.time-label { font-size: 11px; color: #909399; }
.input-wrapper :deep(.el-input-number) { width: 100%; }
.history-info { text-align: center; padding: 20px; background: white; border-radius: 4px; color: #909399; }
.history-info p { margin: 0; font-size: 14px; }
.picture-card { flex: 1; min-height: 0; }
.picture-card :deep(.el-card__body) { height: 100%; overflow: hidden; padding: 0; }
.image-wrapper { width: 100%; height: 100%; display: flex; justify-content: center; align-items: center; overflow: hidden; background-color: #f5f7fa; }
.image-wrapper img { max-width: 100%; max-height: 100%; object-fit: contain; }
.history-grid { width: 100%; height: 100%; display: grid; grid-template-columns: repeat(3, 1fr); grid-auto-rows: 150px; gap: 8px; padding: 8px; overflow-y: auto; background-color: #f5f7fa; align-content: start; }
.grid-item { width: 100%; height: 100%; overflow: hidden; border-radius: 4px; border: 1px solid #dcdfe6; background-color: white; cursor: pointer; position: relative; transition: transform 0.2s, box-shadow 0.2s; }
.grid-item:hover { transform: scale(1.05); box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15); z-index: 1; }
.grid-item img { width: 100%; height: 100%; object-fit: cover; }
.photo-timestamp { position: absolute; bottom: 0; left: 0; right: 0; background: rgba(0, 0, 0, 0.7); color: white; padding: 4px; font-size: 10px; text-align: center; }
.no-photo-state { display: flex; flex-direction: column; align-items: center; color: #909399; gap: 10px; }
span { color: #909399; font-size: 1.2rem; }
:deep(.el-card__body) { flex: 1; display: flex; flex-direction: column; justify-content: center; align-items: center; padding: 20px; }
:deep(.el-card__header) { text-align: center; font-weight: bold; padding: 10px; }
</style>