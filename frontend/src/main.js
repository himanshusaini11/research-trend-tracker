import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './style.css'
import './styles/modernist.css'  // new design system, scoped under .modernist — inert until a view opts in
import './composables/useTheme'  // runs module-level _apply() on every page load

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')
