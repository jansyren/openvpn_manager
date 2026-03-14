<template>
  <div class="login-wrapper">
    <div class="login-card">
      <h1 class="title">OpenVPN Manager</h1>
      <p class="subtitle">Sign in to continue</p>

      <form @submit.prevent="handleLogin" novalidate>
        <div class="field">
          <label for="username">Username</label>
          <InputText
            id="username"
            v-model="form.username"
            autocomplete="username"
            :disabled="loading"
            class="w-full"
          />
        </div>

        <div class="field">
          <label for="password">Password</label>
          <Password
            id="password"
            v-model="form.password"
            :feedback="false"
            toggle-mask
            autocomplete="current-password"
            :disabled="loading"
            input-class="w-full"
          />
        </div>

        <Message v-if="errorMessage" severity="error" :closable="false">{{ errorMessage }}</Message>

        <Button
          type="submit"
          label="Sign In"
          icon="pi pi-sign-in"
          :loading="loading"
          class="w-full mt-3"
        />
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import InputText from 'primevue/inputtext'
import Password from 'primevue/password'
import Button from 'primevue/button'
import Message from 'primevue/message'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const router = useRouter()
const route = useRoute()

const form = ref({ username: '', password: '' })
const loading = ref(false)
const errorMessage = ref<string | null>(null)

async function handleLogin(): Promise<void> {
  errorMessage.value = null
  if (!form.value.username || !form.value.password) {
    errorMessage.value = 'Username and password are required'
    return
  }

  loading.value = true
  try {
    await authStore.login(form.value.username, form.value.password)
    const redirect = (route.query.redirect as string) || '/'
    router.push(redirect)
  } catch (e: unknown) {
    const err = e as { detail?: string; status?: number }
    if (err.status === 401) {
      errorMessage.value = 'Invalid username or password'
    } else if (err.detail?.includes('locked')) {
      errorMessage.value = 'Account is temporarily locked. Please try again later.'
    } else {
      errorMessage.value = err.detail ?? 'Login failed'
    }
  } finally {
    loading.value = false
    form.value.password = ''
  }
}
</script>

<style scoped>
.login-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: var(--p-surface-100);
}

.login-card {
  background: white;
  border-radius: 12px;
  padding: 2.5rem;
  width: 100%;
  max-width: 400px;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.08);
}

.title {
  font-size: 1.5rem;
  font-weight: 700;
  margin: 0 0 0.25rem;
}

.subtitle {
  color: var(--p-surface-500);
  margin: 0 0 1.5rem;
}

.field {
  margin-bottom: 1rem;
}

.field label {
  display: block;
  font-size: 0.875rem;
  font-weight: 500;
  margin-bottom: 0.375rem;
}
</style>
