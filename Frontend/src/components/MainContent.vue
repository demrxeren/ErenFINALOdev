<template>
  <el-main class="main-layout">
    <div class="content-wrapper">
      <el-card class="box-card chart-card" header="Chart Area">
        <canvas ref="chartCanvas"></canvas>
      </el-card>
      
      <div class="controls-section" v-if="!historyItem">
        <el-button type="primary" size="large" @click="takePhoto" block>Take Photo</el-button>
        <el-button type="success" size="large" @click="saveData" block>Save</el-button>
        <el-button type="danger" size="large" @click="clearAll" block>Clear</el-button>
        <el-button type="info" size="large" @click="$emit('open-history')" block>History</el-button>
      </div>
      <div v-else class="controls-section">
        <div class="history-info">
          <p>{{ historyItem.timestamp }}</p>
        </div>
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

// Props: geçmiş verisi görüntüleniyorsa historyItem objesi gelir
const props = defineProps({ 
  historyItem: Object,
  cameraId: {
    type: Number,
    default: 1
  }
})

defineEmits(['open-history'])

// chartCanvas: grafik çizim alanı referansı, photoUrl: çekilen fotoğraf URL'i
const chartCanvas = ref(null), photoUrl = ref(null)

// chartInstance: Chart.js grafik nesnesi, intervalId: periyodik veri çekme zamanlayıcısı
let chartInstance, intervalId

// imgSrc: gösterilecek resim kaynağını belirler (geçmiş verisi veya yeni çekilen fotoğraf)
const imgSrc = computed(() => props.historyItem?.photo_image || photoUrl.value)

// Grafik verilerini günceller - data verilirse kullanır, yoksa sıfırlar
const updateChart = (data) => {
  if (!chartInstance) return
  if (data) {
    chartInstance.data = data
  } else {
    chartInstance.data.labels = []
    chartInstance.data.datasets.forEach(ds => ds.data = [])
  }
  chartInstance.update()
}

// historyItem değiştiğinde: geçmiş veri varsa göster, yoksa canlı veri akışını başlat
watch(() => props.historyItem, (item) => {
  clearInterval(intervalId)
  if (item?.sensor_data) {
    updateChart(item.sensor_data)
  } else {
    updateChart()
    fetchData()
    intervalId = setInterval(fetchData, 3000)
  }
})

// Backend'den fotoğraf çeker ve gösterir
const takePhoto = async () => {
  try {
    const response = await axios.get('http://localhost:5001/api/photos', {
      params: { camera_id: props.cameraId },
      withCredentials: true
    })
    photoUrl.value = response.data[0].url
    ElMessage.success('Photo taken!')
  } catch { ElMessage.error('Failed to take photo') }
}

// Mevcut grafik ve fotoğrafı geçmiş olarak veritabanına kaydeder
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

// Backend'den sensör verilerini (sıcaklık/nem) çeker ve grafiği günceller
const fetchData = async () => {
  if (props.historyItem || !chartInstance) return
  try {
    const response = await axios.get('http://localhost:5001/api/data', {
      params: { camera_id: props.cameraId },
      withCredentials: true
    })
    const data = response.data
    chartInstance.data.labels = data.map(d => new Date(d.timestamp).toLocaleTimeString())
    chartInstance.data.datasets[0].data = data.map(d => d.temperature)
    chartInstance.data.datasets[1].data = data.map(d => d.humidity)
    chartInstance.update()
  } catch {}
}

// Tüm verileri siler (kullanıcıdan onay ister)
const clearAll = async () => {
  try {
    await ElMessageBox.confirm('Clear all data?', 'Warning', { confirmButtonText: 'Yes', cancelButtonText: 'No', type: 'warning' })
    await axios.delete('http://localhost:5001/api/data', {
      params: { camera_id: props.cameraId },
      withCredentials: true
    })
    photoUrl.value = null
    updateChart()
    ElMessage.success('Cleared')
  } catch {}
}

// Bileşen yüklendiğinde: Chart.js grafiğini oluşturur ve 3 saniyede bir veri günceller
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

// Bileşen kaldırıldığında: zamanlayıcıyı ve grafik nesnesini temizler
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
</style>