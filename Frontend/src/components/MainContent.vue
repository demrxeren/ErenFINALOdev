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
        <div class="image-wrapper">
          <img v-if="imgSrc" :src="imgSrc" />
          
          <div v-else class="no-photo-state">
             <el-icon size="40"><Camera /></el-icon>
             <span>{{ historyItem ? 'No Photo Saved' : 'Waiting for Auto Capture...' }}</span>
          </div>
        </div>
      </el-card>

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

const chartCanvas = ref(null), photoUrl = ref(null), rawData = ref([]), filterType = ref('all')
let chartInstance, intervalId, captureTimeoutId

// Görüntü Kaynağı (Stream veya Fotoğraf)
const imgSrc = computed(() => props.historyItem?.photo_image || photoUrl.value)

const filterLabel = computed(() => ({
  'temp-max': 'Highest Temp', 'temp-min': 'Lowest Temp',
  'hum-max': 'Highest Humidity', 'hum-min': 'Lowest Humidity', 
  'show-20': 'Show 20', 'all': 'Show All'
}[filterType.value] || 'Show All'))

// Son sıcaklık verisi
const currentTemp = computed(() => {
  if (!rawData.value || rawData.value.length === 0) return 0
  return rawData.value[rawData.value.length - 1].temperature
})

// Durum Paneli Metinleri
const captureStatus = computed(() => {
  const t = currentTemp.value
  if (t >= 24) return { title: 'ALARM', type: 'error', desc: 'Live Video Stream Active' }
  if (t >= 22) return { title: 'High Alert', type: 'warning', desc: 'Capture: Every 5s' }
  if (t >= 20) return { title: 'Attention', type: 'info', desc: 'Capture: Every 10s' }
  return { title: 'Normal', type: 'success', desc: 'Capture: Every 30s' }
})

// === OTOMATİK ÇEKİM VE VIDEO YÖNETİMİ ===
const manageAutoCapture = async () => {
  if (props.historyItem) return // Geçmiş modundaysak dur

  const temp = currentTemp.value

  // --- VIDEO MODU (>= 24°C) ---
  if (temp >= 24) {
    if (!photoUrl.value || !photoUrl.value.includes('/stream')) {
       try {
         const { data } = await axios.get('http://localhost:5001/api/cameras', { withCredentials: true })
         const cam = data.find(c => c.id === props.cameraId)
         if (cam) {
             let baseUrl = cam.ip_address
             if (!baseUrl.startsWith('http')) baseUrl = `http://${baseUrl}`
             photoUrl.value = `${baseUrl}/stream` 
         }
       } catch (e) { 
         console.error("Kamera IP'si alınamadı:", e) 
       }
    }
    
    clearTimeout(captureTimeoutId)
    captureTimeoutId = setTimeout(manageAutoCapture, 3000) 
    return
  } 

  // --- FOTOĞRAF MODU (< 24°C) ---
  if (photoUrl.value && photoUrl.value.includes('/stream')) {
      photoUrl.value = null 
  }

  await takePhoto()

  let nextInterval = 30000 
  
  if (temp >= 22) {
    nextInterval = 5000 
  } else if (temp >= 20) {
    nextInterval = 10000 
  }

  clearTimeout(captureTimeoutId)
  captureTimeoutId = setTimeout(manageAutoCapture, nextInterval)
}

const handleFilter = (cmd) => { filterType.value = cmd; renderChart() }

// === GÜNCELLENEN KISIM BURASI ===
const renderChart = () => {
  if (!chartInstance || !rawData.value.length) return
  let data = [...rawData.value], show = []
  
  if (filterType.value === 'show-20') {
    show = data.slice(-20) // Sadece son 20 veriyi göster
  } else if (filterType.value !== 'all') {
    const comp = { 'temp-max': (a,b) => a.temperature > b.temperature, 'temp-min': (a,b) => a.temperature < b.temperature,
                   'hum-max': (a,b) => a.humidity > b.humidity, 'hum-min': (a,b) => a.humidity < b.humidity }[filterType.value]
    const idx = data.reduce((best, cur, i, arr) => comp(cur, arr[best]) ? i : best, 0)
    show = data.slice(Math.max(0, idx - 2), Math.min(data.length, idx + 3))
  } else {
    show = data // ARTIK TÜM VERİYİ GÖSTERİYOR (Dilimleme kaldırıldı)
  }
  
  chartInstance.data.labels = show.map(d => new Date(d.timestamp).toLocaleTimeString())
  chartInstance.data.datasets[0].data = show.map(d => d.temperature)
  chartInstance.data.datasets[1].data = show.map(d => d.humidity)
  chartInstance.update()
}

const fetchData = async () => {
  if (props.historyItem || !chartInstance) return
  try {
    const { data } = await axios.get('http://localhost:5001/api/data', 
      { params: { camera_id: props.cameraId }, withCredentials: true })
    if (!rawData.value.length) rawData.value = data
    else {
      const lastId = rawData.value[rawData.value.length - 1].id
      rawData.value.push(...data.filter(i => i.id > lastId))
    }
    renderChart()
  } catch (e) { console.error("Veri çekme hatası:", e) }
}

const takePhoto = async () => {
  try {
    const { data } = await axios.get('http://localhost:5001/api/photos',
      { params: { camera_id: props.cameraId }, withCredentials: true })
    if(data[0]?.url) photoUrl.value = data[0].url
  } catch { 
    console.error('Auto capture failed') 
  }
}

const saveData = async () => {
  if (!chartInstance) return
  try {
    await axios.post('http://localhost:5001/api/save-history', {
      camera_id: props.cameraId, chartImage: chartInstance.toBase64Image(),
      photoUrl: photoUrl.value, sensorData: { labels: chartInstance.data.labels, datasets: chartInstance.data.datasets }
    }, { withCredentials: true })
    ElMessage.success('Saved!')
  } catch { ElMessage.error('Failed to save') }
}

const clearAll = async () => {
  try {
    await ElMessageBox.confirm('Clear all data?', 'Warning', 
      { confirmButtonText: 'Yes', cancelButtonText: 'No', type: 'warning' })
    await axios.delete('http://localhost:5001/api/data', 
      { params: { camera_id: props.cameraId }, withCredentials: true })
    photoUrl.value = null; rawData.value = []; renderChart()
    ElMessage.success('Cleared')
  } catch {}
}

watch(() => props.historyItem, (item) => {
  clearInterval(intervalId)
  clearTimeout(captureTimeoutId)

  if (item?.sensor_data) {
    // Geçmiş Modu
    const { labels = [], datasets = [] } = item.sensor_data
    rawData.value = labels.map((lbl, i) => ({ timestamp: lbl, 
      temperature: datasets[0]?.data[i], humidity: datasets[1]?.data[i] }))
    filterType.value = 'all'; renderChart()
  } else {
    // Canlı Mod
    rawData.value = []; filterType.value = 'all'; renderChart()
    
    fetchData(); 
    intervalId = setInterval(fetchData, 3000)
    manageAutoCapture() 
  }
})

onMounted(() => {
  if (props.historyItem) return
  chartInstance = new Chart(chartCanvas.value.getContext('2d'), {
    type: 'line',
    data: { labels: [], datasets: [
      { label: 'Temp', data: [], borderColor: 'orange', tension: 0.1 },
      { label: 'Humidity', data: [], borderColor: 'lightblue', tension: 0.1 }
    ]}, options: { responsive: true, maintainAspectRatio: false }
  })
  
  fetchData(); 
  intervalId = setInterval(fetchData, 3000)
  manageAutoCapture()
})

onUnmounted(() => { 
  clearInterval(intervalId); 
  clearTimeout(captureTimeoutId);
  chartInstance?.destroy() 
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