import { ref } from 'vue'
import axios from 'axios'

const photosByCamera = ref({}), captureStateByCamera = ref({}), timeouts = {}
let photoErrorShown = false

export const getPhotos = (cameraId) => photosByCamera.value[cameraId] || []
export const clearPhotos = (cameraId) => { if (photosByCamera.value[cameraId]) photosByCamera.value[cameraId] = [] }
const getCurrentTemp = (cameraId) => captureStateByCamera.value[cameraId]?.currentTemp || 22

const getLatestPhoto = async (cameraId) => {
  try {
    const { data } = await axios.get('http://localhost:5001/api/photos', { params: { camera_id: cameraId }, withCredentials: true })
    if (data[0]?.url) {
      const ps = captureStateByCamera.value[cameraId]
      if (ps.url !== data[0].url) {
        ps.url = data[0].url
        ps.lastTimestamp = new Date().toISOString()
        photosByCamera.value[cameraId].push({ url: data[0].url, timestamp: ps.lastTimestamp })
      }
    }
    photoErrorShown = false
  } catch { if (!photoErrorShown) { console.warn('⚠ Camera device not available'); photoErrorShown = true } }
}

const manageAutoCapture = async (cameraId) => {
  const temp = getCurrentTemp(cameraId)
  if (temp >= 28) {
    try {
      const { data } = await axios.get('http://localhost:5001/api/cameras', { withCredentials: true })
      const cam = data.find(c => c.id === cameraId)
      if (cam) {
        const sUrl = `${cam.ip_address.startsWith('http') ? cam.ip_address : `http://${cam.ip_address}`}/stream`
        if (captureStateByCamera.value[cameraId]?.url !== sUrl) captureStateByCamera.value[cameraId].url = sUrl
      }
    } catch { }
    if (timeouts[cameraId]) clearTimeout(timeouts[cameraId])
    timeouts[cameraId] = setTimeout(() => manageAutoCapture(cameraId), 3000)
    return
  }
  await getLatestPhoto(cameraId)
  if (timeouts[cameraId]) clearTimeout(timeouts[cameraId])
  timeouts[cameraId] = setTimeout(() => manageAutoCapture(cameraId), temp >= 24 ? 10000 : temp >= 20 ? 20000 : 30000)
}

export const startCapture = (cameraId) => {
  if (!photosByCamera.value[cameraId]) {
    photosByCamera.value[cameraId] = []
    captureStateByCamera.value[cameraId] = { url: null, lastTimestamp: null }
  }
  manageAutoCapture(cameraId)
}

export const stopCapture = (cameraId) => { if (timeouts[cameraId]) { clearTimeout(timeouts[cameraId]); delete timeouts[cameraId] } }
export const setCurrentTemp = (cameraId, temp) => {
  if (!captureStateByCamera.value[cameraId]) captureStateByCamera.value[cameraId] = {}
  captureStateByCamera.value[cameraId].currentTemp = temp
}
export const stopAllCaptures = () => Object.keys(timeouts).forEach(cId => stopCapture(parseInt(cId)))
