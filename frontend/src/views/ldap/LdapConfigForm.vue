<template>
  <div class="form-body">
    <div class="field">
      <label>Name *</label>
      <InputText v-model="model.name" class="w-full" placeholder="Corporate AD" />
    </div>
    <div class="field">
      <label>Server URL *</label>
      <InputText v-model="model.server_url" class="w-full" placeholder="ldap://dc.example.com:389" />
      <small class="hint">Use ldaps:// for LDAPS. Port 389 for LDAP, 636 for LDAPS.</small>
    </div>
    <div class="field">
      <label>Backup Server URL</label>
      <InputText v-model="model.server_url_backup" class="w-full" placeholder="ldap://dc2.example.com:389" />
    </div>
    <div class="field">
      <label>Bind DN *</label>
      <InputText v-model="model.bind_dn" class="w-full" placeholder="CN=svc-vpn,OU=ServiceAccounts,DC=example,DC=com" />
    </div>
    <div class="field">
      <label>{{ isCreate ? 'Bind Password *' : 'Bind Password (leave blank to keep current)' }}</label>
      <InputText v-model="model.bind_password" type="password" class="w-full" />
    </div>
    <div class="field">
      <label>User Search Base *</label>
      <InputText v-model="model.user_search_base" class="w-full" placeholder="OU=Users,DC=example,DC=com" />
    </div>
    <div class="field">
      <label>User Filter</label>
      <InputText v-model="model.user_filter" class="w-full" placeholder="(objectClass=person)" />
      <small class="hint">LDAP filter to scope user lookups. Default: (objectClass=person)</small>
    </div>
    <div class="field">
      <label>Username Attribute</label>
      <InputText v-model="model.username_attr" class="w-full" placeholder="sAMAccountName" />
      <small class="hint">Attribute containing the login username. Use <code>sAMAccountName</code> for AD, <code>uid</code> for OpenLDAP.</small>
    </div>
    <div class="field">
      <label>Group Search Base</label>
      <InputText v-model="model.group_search_base" class="w-full" placeholder="OU=Groups,DC=example,DC=com" />
      <small class="hint">Used for explicit group member searches. Leave blank to use memberOf attribute only.</small>
    </div>
    <div class="field">
      <label>Group Member Attribute</label>
      <InputText v-model="model.group_member_attr" class="w-full" placeholder="member" />
      <small class="hint">Attribute on the group entry listing its members. Use <code>member</code> for AD (group sync). User→group lookups use <code>memberOf</code> (configured in the auth plugin).</small>
    </div>
    <div class="field field-inline">
      <Checkbox v-model="model.use_tls" :binary="true" input-id="use-tls" />
      <label for="use-tls">Use STARTTLS (upgrade plain LDAP connection to TLS)</label>
    </div>
    <div class="field field-inline">
      <Checkbox v-model="model.tls_verify_cert" :binary="true" input-id="tls-verify" />
      <label for="tls-verify">Verify TLS certificate</label>
    </div>
    <div class="field">
      <label>CA Certificate (PEM) — for self-signed certs</label>
      <Textarea v-model="model.ca_cert_pem" rows="4" class="w-full mono" placeholder="-----BEGIN CERTIFICATE-----&#10;...&#10;-----END CERTIFICATE-----" />
    </div>
    <div class="field field-inline">
      <Checkbox v-model="model.is_active" :binary="true" input-id="is-active" />
      <label for="is-active">Active (used for JIT user provisioning)</label>
    </div>
  </div>
</template>

<script setup lang="ts">
import InputText from 'primevue/inputtext'
import Checkbox from 'primevue/checkbox'
import Textarea from 'primevue/textarea'

defineProps<{ isCreate: boolean }>()

const model = defineModel<{
  name: string
  server_url: string
  server_url_backup: string
  bind_dn: string
  bind_password: string
  user_search_base: string
  user_filter: string
  username_attr: string
  group_search_base: string
  group_member_attr: string
  use_tls: boolean
  tls_verify_cert: boolean
  ca_cert_pem: string
  is_active: boolean
}>({ required: true })
</script>

<style scoped>
.form-body {
  display: flex;
  flex-direction: column;
  gap: 0;
}
.field {
  margin-bottom: 1rem;
}
.field label {
  display: block;
  margin-bottom: 0.3rem;
  font-weight: 600;
  font-size: 0.875rem;
}
.field-inline {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.field-inline label {
  margin: 0;
  cursor: pointer;
}
.hint {
  font-size: 0.75rem;
  color: var(--p-surface-400);
  margin-top: 0.2rem;
  display: block;
}
.w-full {
  width: 100%;
}
.mono {
  font-family: monospace;
  font-size: 0.8rem;
}
</style>
