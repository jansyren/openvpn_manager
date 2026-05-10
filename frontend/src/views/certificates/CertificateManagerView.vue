<template>
  <div>
    <div class="page-header">
      <h1 class="page-title">Certificate Manager</h1>
    </div>

    <Message v-if="!ctx.selectedInstanceId" severity="info" :closable="false" style="margin-bottom:1rem">
      Select a server and VPN instance in the header bar to view certificates.
    </Message>

    <DataTable :value="certificates" :loading="loading" striped-rows :row-class="rowClass">
      <template #empty>{{ ctx.selectedInstanceId ? 'No certificates found.' : 'Select a VPN instance first.' }}</template>
      <Column field="common_name" header="Common Name" />
      <Column header="Type">
        <template #body="{ data }">
          <Tag :value="data.cert_type" :severity="certTypeSeverity(data.cert_type)" />
        </template>
      </Column>
      <Column field="serial" header="Serial">
        <template #body="{ data }">
          <span class="serial">{{ data.serial?.slice(0, 16) }}{{ data.serial?.length > 16 ? '…' : '' }}</span>
        </template>
      </Column>
      <Column header="Not Before">
        <template #body="{ data }">{{ formatDate(data.not_before) }}</template>
      </Column>
      <Column header="Expires">
        <template #body="{ data }">
          <span :class="{ 'text-expired': isExpired(data.not_after), 'text-expiring': isExpiringSoon(data.not_after) }">
            {{ formatDate(data.not_after) }}
          </span>
        </template>
      </Column>
      <Column header="Status">
        <template #body="{ data }">
          <Tag :value="data.is_revoked ? 'Revoked' : 'Valid'" :severity="data.is_revoked ? 'danger' : 'success'" />
        </template>
      </Column>
      <Column header="Actions" style="width: 9rem">
        <template #body="{ data }">
          <Button
            icon="pi pi-refresh"
            severity="info"
            text
            rounded
            v-tooltip="'Renew'"
            :disabled="data.cert_type === 'ca'"
            @click="openRenewDialog(data)"
          />
          <Button
            icon="pi pi-ban"
            severity="warn"
            text
            rounded
            v-tooltip="'Revoke'"
            :disabled="data.is_revoked"
            @click="openRevokeDialog(data)"
          />
        </template>
      </Column>
    </DataTable>

    <!-- Revoke Dialog -->
    <Dialog v-model:visible="revokeDialogVisible" header="Revoke Certificate" modal style="width: 440px">
      <p>Revoke certificate for <strong>{{ revokeTarget?.common_name }}</strong>?</p>
      <div class="field">
        <label>Reason</label>
        <Select
          v-model="revokeReason"
          :options="revokeReasons"
          class="w-full"
          placeholder="unspecified"
        />
      </div>
      <div class="field">
        <label>CA Passphrase (optional)</label>
        <InputText v-model="revokePassphrase" type="password" class="w-full" placeholder="Required to update the CRL on the server" />
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" @click="revokeDialogVisible = false" />
        <Button label="Revoke" severity="warn" :loading="revoking" @click="doRevoke" />
      </template>
    </Dialog>

    <!-- Renew Dialog -->
    <Dialog v-model:visible="renewDialogVisible" header="Renew Certificate" modal style="width: 420px">
      <p>Issue a new certificate for <strong>{{ renewTarget?.common_name }}</strong> with a fresh expiry date.</p>
      <div class="field">
        <label>CA Passphrase *</label>
        <InputText v-model="renewPassphrase" type="password" class="w-full" />
      </div>
      <div class="field">
        <label>Expire Days</label>
        <InputNumber v-model="renewExpireDays" class="w-full" :min="1" :max="9999" />
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" @click="renewDialogVisible = false" />
        <Button label="Renew" severity="info" :loading="renewing" @click="doRenew" />
      </template>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { useToast } from 'primevue/usetoast'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import Dialog from 'primevue/dialog'
import Select from 'primevue/select'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import Message from 'primevue/message'
import { useContextStore } from '@/stores/context'
import { certificatesApi } from '@/api/certificates'
import type { CertificateRead } from '@/types'

const toast = useToast()
const ctx = useContextStore()

const certificates = ref<CertificateRead[]>([])
const loading = ref(false)

const revokeDialogVisible = ref(false)
const revokeTarget = ref<CertificateRead | null>(null)
const revokeReason = ref('unspecified')
const revokePassphrase = ref('')
const revoking = ref(false)

const renewDialogVisible = ref(false)
const renewTarget = ref<CertificateRead | null>(null)
const renewPassphrase = ref('')
const renewExpireDays = ref(825)
const renewing = ref(false)

const revokeReasons = [
  'unspecified',
  'keyCompromise',
  'CACompromise',
  'affiliationChanged',
  'superseded',
  'cessationOfOperation',
  'certificateHold',
]

watch(
  () => ctx.selectedInstanceId,
  async (id) => {
    certificates.value = []
    if (id) await loadCertificates()
  },
)

function certTypeSeverity(type: string): string {
  if (type === 'ca') return 'warn'
  if (type === 'server') return 'info'
  return 'success'
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '—'
  return new Date(dateStr).toLocaleDateString()
}

function isExpired(dateStr: string | null): boolean {
  if (!dateStr) return false
  return new Date(dateStr) < new Date()
}

function isExpiringSoon(dateStr: string | null): boolean {
  if (!dateStr) return false
  const d = new Date(dateStr)
  const soon = new Date()
  soon.setDate(soon.getDate() + 30)
  return d >= new Date() && d < soon
}

function rowClass(data: CertificateRead): string {
  if (isExpired(data.not_after) && !data.is_revoked) return 'row-expired'
  return ''
}

async function loadCertificates() {
  if (!ctx.selectedInstanceId) { certificates.value = []; return }
  loading.value = true
  try {
    certificates.value = await certificatesApi.list(ctx.selectedInstanceId)
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to load certificates', life: 4000 })
  } finally {
    loading.value = false
  }
}

function openRevokeDialog(cert: CertificateRead) {
  revokeTarget.value = cert
  revokeReason.value = 'unspecified'
  revokePassphrase.value = ''
  revokeDialogVisible.value = true
}

async function doRevoke() {
  if (!revokeTarget.value) return
  revoking.value = true
  try {
    await certificatesApi.revoke(revokeTarget.value.id, revokeReason.value, revokePassphrase.value || undefined)
    toast.add({ severity: 'success', summary: 'Revoked', detail: 'Certificate revoked.', life: 3000 })
    revokeDialogVisible.value = false
    await loadCertificates()
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to revoke', life: 4000 })
  } finally {
    revoking.value = false
  }
}

function openRenewDialog(cert: CertificateRead) {
  renewTarget.value = cert
  renewPassphrase.value = ''
  renewExpireDays.value = 825
  renewDialogVisible.value = true
}

async function doRenew() {
  if (!renewTarget.value || !renewPassphrase.value) {
    toast.add({ severity: 'warn', summary: 'Validation', detail: 'CA passphrase is required.', life: 3000 })
    return
  }
  renewing.value = true
  try {
    const result = await certificatesApi.renew(renewTarget.value.id, renewPassphrase.value, renewExpireDays.value)
    toast.add({ severity: 'success', summary: 'Renewed', detail: `Certificate renewed. New serial: ${result.serial}`, life: 5000 })
    renewDialogVisible.value = false
    await loadCertificates()
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to renew', life: 4000 })
  } finally {
    renewing.value = false
  }
}

onMounted(async () => {
  if (ctx.selectedInstanceId) await loadCertificates()
})
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1.5rem;
}
.page-title {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 700;
}
.field {
  margin-bottom: 1rem;
}
.field label {
  display: block;
  margin-bottom: 0.35rem;
  font-weight: 600;
  font-size: 0.875rem;
}
.w-full {
  width: 100%;
}
.text-expired {
  color: var(--p-red-500);
  font-weight: 600;
}
.text-expiring {
  color: var(--p-orange-500);
  font-weight: 600;
}
.serial {
  font-family: monospace;
  font-size: 0.8rem;
}
</style>

<style>
.row-expired td {
  background: color-mix(in srgb, var(--p-red-500) 8%, transparent) !important;
}
</style>
