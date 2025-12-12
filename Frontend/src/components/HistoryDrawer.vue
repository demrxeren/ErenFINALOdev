<template>
  <el-drawer :model-value="visible" @update:model-value="$emit('update:visible', $event)" title="Recent History"
    size="300px" @open="fetchHistory">
    <el-timeline v-if="items.length">
      <el-timeline-item v-for="item in items" :key="item.id" :timestamp="item.timestamp" placement="top">
        <el-card shadow="hover" :body-style="{ padding: '10px', position: 'relative' }"
          @click="$emit('select-item', item)">
          <el-button type="danger" :icon="Delete" circle size="small" class="delete-btn"
            @click.stop="deleteHistory(item.id)" />
          <div class="history-images">
            <div class="img-box"><span>Chart</span><el-image :src="`${SB}${item.chart_image}`"
                fit="cover" class="history-img" /></div>
            <div class="img-box" v-if="item.photo_image"><span>Photo</span><el-image :src="resolvePhoto(item.photo_image)" fit="cover"
              class="history-img" /></div>
          </div>
        </el-card>
      </el-timeline-item>
    </el-timeline>
    <el-empty v-else description="No history found" />
  </el-drawer>
</template>

<script setup>
import { ref } from 'vue'
import axios from 'axios'
import { Delete } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

const props = defineProps({ visible: Boolean, cameraId: Number })
defineEmits(['update:visible', 'select-item'])
const items = ref([])
const SB = 'http://localhost:5001'

const resolvePhoto = (url) => url ? (url.startsWith('/') ? `${SB}${url}` : url) : ''

const fetchHistory = async () => {
  try { 
    const { data } = await axios.get(`${SB}/api/history`, {
      params: props.cameraId ? { camera_id: props.cameraId } : {}, withCredentials: true })
    items.value = data
  } catch { }
}

const deleteHistory = async (id) => {
  try {
    await ElMessageBox.confirm('Delete?', 'Warning', 
      { confirmButtonText: 'Yes', cancelButtonText: 'No', type: 'warning' })
    await axios.delete(`${SB}/api/history/${id}`, { withCredentials: true })
    ElMessage.success('Deleted'); fetchHistory()
  } catch { }
}
</script>

<style scoped>
.history-card {
  cursor: pointer;
  position: relative;
}

.delete-btn {
  position: absolute;
  top: 5px;
  right: 5px;
  z-index: 10;
}

.history-images {
  display: flex;
  gap: 5px;
  margin-top: 5px;
}

.img-box {
  flex: 1;
  text-align: center;
  font-size: 10px;
  color: #666;
}

.history-img {
  width: 100%;
  height: 60px;
  border-radius: 4px;
  display: block;
}
</style>

<style>
.history-drawer .el-drawer__header {
  border-bottom: 1px solid #dcdfe6;
  margin-bottom: 0;
  padding-bottom: 20px;
}

.history-images {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.img-box {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.img-box span {
  font-size: 0.8rem;
  color: #666;
  font-weight: bold;
}

.history-img {
  width: 100%;
  height: 100px;
  border-radius: 4px;
  border: 1px solid #eee;
}

.history-card {
  cursor: pointer;
  transition: transform 0.2s;
}

.history-card:hover {
  transform: scale(1.02);
}

.delete-btn {
  position: absolute;
  top: 5px;
  right: 5px;
  z-index: 10;
}
</style>
