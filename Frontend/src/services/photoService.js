import { ref } from 'vue'
import axios from 'axios'

const photosByCamera = ref({})
const captureStateByCamera = ref({})
const intervals = {}
const timeouts = {}
let photoErrorShown = false

const getLocalTimestamp = () => {
  const d = new Date()
  const pad = (n) => n.toString().padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

export const initPhotoCapture = (cameraId) => {
  if (!photosByCamera.value[cameraId]) {
    photosByCamera.value[cameraId] = []
    captureStateByCamera.value[cameraId] = { url: null, lastTimestamp: null }
  }
}

export const getPhotos = (cameraId) => photosByCamera.value[cameraId] || []
export const getCaptureState = (cameraId) => {
  initPhotoCapture(cameraId)
  return captureStateByCamera.value[cameraId]
}

export const clearPhotos = (cameraId) => {
  if (photosByCamera.value[cameraId]) {
    photosByCamera.value[cameraId] = []
  }
}

const getCurrentTemp = (cameraId) => captureStateByCamera.value[cameraId]?.currentTemp ?? 0

const getLatestPhoto = async (cameraId) => {
  try {
    const { data } = await axios.get('http://localhost:5001/api/photos', {
      params: { camera_id: cameraId },
      withCredentials: true
    })
    if (data[0]?.url) {
      const ps = captureStateByCamera.value[cameraId]
      if (ps.url !== data[0].url) {
        captureStateByCamera.value[cameraId] = {
          ...ps,
          url: data[0].url,
          lastTimestamp: getLocalTimestamp()
        }
        photosByCamera.value[cameraId].push({
          url: data[0].url,
          timestamp: captureStateByCamera.value[cameraId].lastTimestamp
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
        captureStateByCamera.value[cameraId] = {
          ...captureStateByCamera.value[cameraId],
          url: sUrl
        }
      }
    }
  } catch (e) {
    console.error(`Failed to setup stream for camera ${cameraId}:`, e)
  }
}

const manageAutoCapture = async (cameraId) => {
  const temp = getCurrentTemp(cameraId)
  if (temp >= 22) {
    await setupStreamIfNeeded(cameraId)
    if (timeouts[cameraId]) clearTimeout(timeouts[cameraId])
    timeouts[cameraId] = setTimeout(() => manageAutoCapture(cameraId), 3000)
    return
  }
  await getLatestPhoto(cameraId)
  if (timeouts[cameraId]) clearTimeout(timeouts[cameraId])
  let iv = 40000
  if (temp >= 20) iv = 10000
  else if (temp >= 18) iv = 20000
  else if (temp >= 16) iv = 30000

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
    captureStateByCamera.value[cameraId] = { currentTemp: temp }
  } else {
    const oldTemp = captureStateByCamera.value[cameraId].currentTemp
    captureStateByCamera.value[cameraId].currentTemp = temp

    // If we just crossed the threshold, trigger immediate update
    if ((oldTemp < 22 && temp >= 22) || (oldTemp >= 22 && temp < 22)) {
      if (timeouts[cameraId]) {
        clearTimeout(timeouts[cameraId])
        manageAutoCapture(cameraId)
      }
    }
  }
}

export const stopAllCaptures = () => {
  Object.keys(intervals).forEach(cId => stopCapture(parseInt(cId)))
  Object.keys(timeouts).forEach(cId => stopCapture(parseInt(cId)))
}
