import { ref } from 'vue'
import axios from 'axios'

const photosByCamera = ref({})
const captureStateByCamera = ref({})
const intervals = {}
const timeouts = {}
let photoErrorShown = false

export const initPhotoCapture = (cameraId) => {
  if (!photosByCamera.value[cameraId]) {
    photosByCamera.value[cameraId] = []
    captureStateByCamera.value[cameraId] = { url: null, lastTimestamp: null }
  }
}

export const getPhotos = (cameraId) => photosByCamera.value[cameraId] || []

export const clearPhotos = (cameraId) => {
  if (photosByCamera.value[cameraId]) {
    photosByCamera.value[cameraId] = []
  }
}

const getCurrentTemp = (cameraId) => captureStateByCamera.value[cameraId]?.currentTemp || 22

const getLatestPhoto = async (cameraId) => {
  try {
    const { data } = await axios.get('http://localhost:5001/api/photos', {
      params: { camera_id: cameraId },
      withCredentials: true
    })
    if (data[0]?.url) {
      const ps = captureStateByCamera.value[cameraId]
      if (ps.url !== data[0].url) {
        ps.url = data[0].url
        ps.lastTimestamp = new Date().toISOString()
        photosByCamera.value[cameraId].push({
          url: data[0].url,
          timestamp: ps.lastTimestamp
        })
      }
    }
    photoErrorShown = false
  } catch (e) {
    if (!photoErrorShown) {
      console.warn('⚠ Camera device not available or no photos')
      photoErrorShown = true
    }
  }
}

const setupStreamIfNeeded = async (cameraId) => {
  try {
    const { data } = await axios.get('http://localhost:5001/api/cameras', {
      withCredentials: true
    })
    const cam = data.find(c => c.id === cameraId)
    if (cam) {
      const bUrl = cam.ip_address.startsWith('http') ? cam.ip_address : `http://${cam.ip_address}`
      const sUrl = `${bUrl}/stream`
      if (captureStateByCamera.value[cameraId]?.url !== sUrl) {
        captureStateByCamera.value[cameraId].url = sUrl
      }
    }
  } catch (e) {
    console.error(`Failed to setup stream for camera ${cameraId}:`, e)
  }
}

const manageAutoCapture = async (cameraId) => {
  const temp = getCurrentTemp(cameraId)
  if (temp >= 28) {
    await setupStreamIfNeeded(cameraId)
    if (timeouts[cameraId]) clearTimeout(timeouts[cameraId])
    timeouts[cameraId] = setTimeout(() => manageAutoCapture(cameraId), 3000)
    return
  }
  await getLatestPhoto(cameraId)
  if (timeouts[cameraId]) clearTimeout(timeouts[cameraId])
  let iv = 30000
  if (temp >= 24) iv = 10000
  if (temp >= 20) iv = 20000
  timeouts[cameraId] = setTimeout(() => manageAutoCapture(cameraId), iv)
}

export const startCapture = (cameraId) => {
  initPhotoCapture(cameraId)
  manageAutoCapture(cameraId)
  console.log(`🎥 Background photo capture started for camera ${cameraId}`)
}

export const stopCapture = (cameraId) => {
  if (intervals[cameraId]) {
    clearInterval(intervals[cameraId])
    delete intervals[cameraId]
  }
  if (timeouts[cameraId]) {
    clearTimeout(timeouts[cameraId])
    delete timeouts[cameraId]
  }
  console.log(`⏹️ Background photo capture stopped for camera ${cameraId}`)
}

export const setCurrentTemp = (cameraId, temp) => {
  if (!captureStateByCamera.value[cameraId]) {
    captureStateByCamera.value[cameraId] = {}
  }
  captureStateByCamera.value[cameraId].currentTemp = temp
}

export const stopAllCaptures = () => {
  Object.keys(intervals).forEach(cId => stopCapture(parseInt(cId)))
  Object.keys(timeouts).forEach(cId => stopCapture(parseInt(cId)))
}
