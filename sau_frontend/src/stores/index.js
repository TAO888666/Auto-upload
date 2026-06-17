import { createPinia } from 'pinia'
import { useUserStore } from './user'
import { useAccountStore } from './account'
import { useAppStore } from './app'
import { usePublishTaskStore } from './publishTask'

const pinia = createPinia()

export default pinia
export { useUserStore, useAccountStore, useAppStore, usePublishTaskStore }
