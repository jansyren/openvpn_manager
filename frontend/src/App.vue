<template>
  <RouterView />
  <Toast position="top-right" />
  <ConfirmDialog />
</template>

<script setup lang="ts">
import Toast from 'primevue/toast'
import ConfirmDialog from 'primevue/confirmdialog'
import { onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useRouter } from 'vue-router'

const authStore = useAuthStore()
const router = useRouter()

// Listen for forced logout events (e.g. refresh token expired)
onMounted(() => {
  window.addEventListener('auth:logout', () => {
    authStore.logout().then(() => router.push({ name: 'login' }))
  })
})
</script>
