import { createPinia } from 'pinia'
import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import zhCn from 'element-plus/es/locale/lang/zh-cn'

import App from './App.vue'
import router from './router'
import './assets/styles/base.css'
import './assets/styles/theme.css'

const pinia = createPinia()
const app = createApp(App)

app
  .use(pinia)
  .use(router)
  .use(ElementPlus, { locale: zhCn })

import { useThemeStore } from './stores/theme'

useThemeStore(pinia).initialize()
app.mount('#app')
