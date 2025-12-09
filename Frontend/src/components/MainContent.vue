<template>
  <el-main class="main-layout">
    <div class="content-wrapper">
      
      <el-card class="box-card chart-card" header="Chart Area">
        <canvas ref="chartCanvas"></canvas>
      </el-card>
      
      <div class="controls-section">
        <el-dropdown trigger="click" @command="handleFilter" style="width: 100%;">
          <el-button type="warning" size="large" block>
            {{ filterLabel }} <el-icon class="el-icon--right"><ArrowDown /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="all">Show All</el-dropdown-item>
              <el-dropdown-item command="temp-max">Highest Temp</el-dropdown-item>
              <el-dropdown-item command="temp-min">Lowest Temp</el-dropdown-item>
              <el-dropdown-item command="hum-max">Highest Humidity</el-dropdown-item>
              <el-dropdown-item command="hum-min">Lowest Humidity</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>

        <template v-if="!historyItem">
          <el-button type="primary" size="large" @click="takePhoto" block>Take Photo</el-button>
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
        <img v-if="imgSrc" :src="imgSrc" />
        <span v-else>{{ historyItem ? 'No Photo Saved' : 'Camera Feed' }}</span>
      </el-card>

    </div>
  </el-main>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, computed } from 'vue'
import Chart from 'chart.js/auto'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowDown } from '@element-plus/icons-vue'

const props = defineProps({ historyItem: Object, cameraId: { type: Number, default: 1 } })
defineEmits(['open-history'])

const chartCanvas = ref(null), photoUrl = ref(null), rawData = ref([]), filterType = ref('all')
let chartInstance, intervalId

const imgSrc = computed(() => props.historyItem?.photo_image || photoUrl.value)
const filterLabel = computed(() => {
  const labels = {
    'temp-max': 'Highest Temp',
    'temp-min': 'Lowest Temp',
    'hum-max': 'Highest Humidity',
    'hum-min': 'Lowest Humidity',
    'all': 'Show All'
  }
  return labels[filterType.value] || 'Show All'
})

const handleFilter = (command) => {
  filterType.value = command
  renderChart()
}

const renderChart = () => {
  if (!chartInstance) return
  
  // Tüm veriyi kopyala
  const allData = [...rawData.value]
  let dataToShow = []
  
  // Veri yoksa işlem yapma
  if (allData.length === 0) return

  if (filterType.value !== 'all') {
    // FİLTRELEME MODU: Tüm hafızadaki veriyi tara
    let targetIndex = 0
    
    if (filterType.value === 'temp-max') {
      targetIndex = allData.reduce((bestIdx, current, idx, arr) => 
        current.temperature > arr[bestIdx].temperature ? idx : bestIdx, 0)
    } else if (filterType.value === 'temp-min') {
      targetIndex = allData.reduce((bestIdx, current, idx, arr) => 
        current.temperature < arr[bestIdx].temperature ? idx : bestIdx, 0)
    } else if (filterType.value === 'hum-max') {
      targetIndex = allData.reduce((bestIdx, current, idx, arr) => 
        current.humidity > arr[bestIdx].humidity ? idx : bestIdx, 0)
    } else if (filterType.value === 'hum-min') {
      targetIndex = allData.reduce((bestIdx, current, idx, arr) => 
        current.humidity < arr[bestIdx].humidity ? idx : bestIdx, 0)
    }
    
    // Bulunan değerin bağlamını göstermek için öncesinden ve sonrasından 2'şer veri al
    const start = Math.max(0, targetIndex - 2)
    const end = Math.min(allData.length, targetIndex + 3)
    dataToShow = allData.slice(start, end)
  } else {
    // NORMAL MOD (Show All): Sadece en son gelen 20 veriyi göster
    dataToShow = allData.slice(-20)
  }
  
  chartInstance.data.labels = dataToShow.map(d => {
    const date = new Date(d.timestamp)
    return isNaN(date.getTime()) ? d.timestamp : date.toLocaleTimeString()
  })
  chartInstance.data.datasets[0].data = dataToShow.map(d => d.temperature)
  chartInstance.data.datasets[1].data = dataToShow.map(d => d.humidity)
  chartInstance.update()
}

// Veri Çekme Fonksiyonu (Düzeltilmiş - Append Mantığı)
const fetchData = async () => {
  if (props.historyItem || !chartInstance) return
  try {
    const { data } = await axios.get('http://localhost:5001/api/data', {
      params: { camera_id: props.cameraId }, 
      withCredentials: true
    })
    
    if (rawData.value.length === 0) {
      // İlk yükleme: gelen veriyi direkt al
      rawData.value = data
    } else {
      // Sonraki yüklemeler: Sadece YENİ olanları ekle
      const lastId = rawData.value[rawData.value.length - 1].id
      
      // Gelen pakette, elimizdeki son ID'den daha büyük ID'ye sahip olanları filtrele
      const newItems = data.filter(item => item.id > lastId)
      
      // Eğer yeni veri varsa listeye ekle
      if (newItems.length > 0) {
        rawData.value.push(...newItems)
      }
    }
    
    renderChart()
  } catch (error) {
    console.error("Veri çekme hatası:", error)
  }
}

const takePhoto = async () => {
  try {
    const { data } = await axios.get('http://localhost:5001/api/photos', {
      params: { camera_id: props.cameraId }, withCredentials: true
    })
    photoUrl.value = data[0].url
    ElMessage.success('Photo taken!')
  } catch { ElMessage.error('Failed to take photo') }
}

const saveData = async () => {
  if (!chartInstance) return
  try {
    await axios.post('http://localhost:5001/api/save-history', {
      camera_id: props.cameraId, 
      chartImage: chartInstance.toBase64Image(),
      photoUrl: photoUrl.value, 
      sensorData: { labels: chartInstance.data.labels, datasets: chartInstance.data.datasets }
    }, { withCredentials: true })
    ElMessage.success('Saved!')
  } catch { ElMessage.error('Failed to save') }
}

const clearAll = async () => {
  try {
    await ElMessageBox.confirm('Clear all data?', 'Warning', { confirmButtonText: 'Yes', cancelButtonText: 'No', type: 'warning' })
    await axios.delete('http://localhost:5001/api/data', { params: { camera_id: props.cameraId }, withCredentials: true })
    photoUrl.value = null
    rawData.value = []
    renderChart()
    ElMessage.success('Cleared')
  } catch {}
}

watch(() => props.historyItem, (item) => {
  clearInterval(intervalId)
  if (item?.sensor_data) {
    const { labels = [], datasets = [] } = item.sensor_data
    rawData.value = labels.map((lbl, i) => ({
      timestamp: lbl, temperature: datasets[0]?.data[i], humidity: datasets[1]?.data[i]
    }))
    filterType.value = 'all'
    renderChart()
  } else {
    rawData.value = []
    filterType.value = 'all'
    renderChart()
    fetchData()
    intervalId = setInterval(fetchData, 3000)
  }
})

onMounted(() => {
  if (props.historyItem) return
  chartInstance = new Chart(chartCanvas.value.getContext('2d'), {
    type: 'line',
    data: { labels: [], datasets: [
      { label: 'Temp', data: [], borderColor: 'orange', tension: 0.1 },
      { label: 'Humidity', data: [], borderColor: 'lightblue', tension: 0.1 }
    ]},
    options: { responsive: true, maintainAspectRatio: false }
  })
  fetchData()
  intervalId = setInterval(fetchData, 3000)
})

onUnmounted(() => {
  clearInterval(intervalId)
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
  width: 150px;
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

canvas, img { 
  max-width: 100%; 
  max-height: 100%;
  object-fit: contain;
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