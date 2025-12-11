import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import App from './App.vue'
import router from './router'
import axios from 'axios'

axios.defaults.headers.common['ngrok-skip-browser-warning'] = 'true';

const app = createApp(App)

app.use(ElementPlus)
app.use(router)

app.mount('#app')