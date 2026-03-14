import { vi } from 'vitest'
import { config } from '@vue/test-utils'

// Stub PrimeVue globally so component tests don't need to configure it
config.global.stubs = {
  Toast: true,
  ConfirmDialog: true,
}

// Suppress console.warn from Vue for missing prop warnings in stubs
vi.spyOn(console, 'warn').mockImplementation(() => {})
