import { createApp } from 'vue'
import { createPinia } from 'pinia'

// Self-hosted fonts: Vite bundles the files under /assets/. Each stylesheet declares every subset
// with a unicode-range, so a browser downloads only what a page uses; index.html preloads the
// latin files. The serif italic is for quoted text (the `note` style).
import '@fontsource-variable/source-sans-3/wght.css'
import '@fontsource-variable/source-serif-4/wght.css'
import '@fontsource-variable/source-serif-4/wght-italic.css'
import './styles/main.css'
import App from './App.vue'

createApp(App).use(createPinia()).mount('#app')
