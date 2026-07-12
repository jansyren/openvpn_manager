<template>
  <div class="page-header">
    <h1 class="page-title">{{ title }}</h1>
    <div class="page-header-actions">
      <slot />
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{ title: string }>()
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
.page-header-actions {
  display: flex;
  gap: 0.5rem;
}
</style>
