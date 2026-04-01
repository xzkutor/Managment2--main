<template>
  <div class="table-wrapper">
    <table>
      <thead>
        <tr>
          <th>Категорія (ref)</th>
          <th>Категорія (target)</th>
          <th>Дії</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="m in mappings" :key="m.id">
          <td>{{ m.reference_category_name || String(m.reference_category_id) }}</td>
          <td>{{ m.target_category_name || String(m.target_category_id) }}</td>
          <td class="actions-cell">
            <button
              class="btn-ghost btn-sm"
              type="button"
              @click="$emit('edit', m)"
            >Редагувати</button>
            <button
              class="btn-ghost btn-sm btn-danger"
              type="button"
              :disabled="deletingIds.has(m.id)"
              @click="onDelete(m.id)"
            >
              {{ deletingIds.has(m.id) ? '⏳…' : 'Видалити' }}
            </button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup lang="ts">
import type { MappingRow } from '@/types/mappings'

interface Props {
  mappings: MappingRow[]
  deletingIds: Set<number>
}

defineProps<Props>()

const emit = defineEmits<{
  (e: 'edit', mapping: MappingRow): void
  (e: 'delete', mappingId: number): void
}>()

function onDelete(id: number) {
  if (window.confirm('Видалити цей мапінг?')) {
    emit('delete', id)
  }
}
</script>

<style scoped>
.actions-cell {
  white-space: nowrap;
}
.btn-danger {
  color: #dc2626;
}
.btn-danger:not(:disabled):hover {
  background: #fee2e2;
}
</style>
