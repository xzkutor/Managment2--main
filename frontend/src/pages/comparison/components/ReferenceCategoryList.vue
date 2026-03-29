<template>
  <div>
    <p v-if="loading" class="muted">Завантаження…</p>
    <p v-else-if="!categories.length" class="muted">
      Немає категорій. Синхронізуйте на сервісній сторінці.
    </p>
    <div
      v-for="cat in categories"
      :key="cat.id"
      class="category-item"
      :class="{ active: activeCategoryId === cat.id }"
      role="button"
      tabindex="0"
      @click="emit('select', cat.id)"
      @keydown.enter="emit('select', cat.id)"
      @keydown.space.prevent="emit('select', cat.id)"
    >
      {{ cat.name }}
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * ReferenceCategoryList.vue — clickable list of reference categories.
 * Emits 'select' with the category id when clicked.
 */
import type { CategorySummary } from '@/types/store'

interface Props {
  categories: CategorySummary[]
  activeCategoryId: number | null
  loading: boolean
}
withDefaults(defineProps<Props>(), {
  categories: () => [],
  activeCategoryId: null,
  loading: false,
})

const emit = defineEmits<{
  (e: 'select', id: number): void
}>()
</script>

