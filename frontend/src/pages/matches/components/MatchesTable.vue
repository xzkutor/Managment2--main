<template>
  <div class="mw-table-panel">
    <div class="mw-table-toolbar">
      <span class="mw-table-count" v-if="rows.length">
        {{ rows.length }} {{ rowsLabel(rows.length) }}
      </span>
    </div>
    <div class="table-wrapper mw-table-scroll">
      <table>
        <thead>
          <tr>
            <th>Референс (товар)</th>
            <th class="col-price">Ціна</th>
            <th>Цільовий (товар)</th>
            <th class="col-price">Ціна</th>
            <th class="col-status">Статус</th>
            <th class="col-score">Score</th>
            <th class="col-date">Оновлено</th>
            <th class="col-action">Дії</th>
          </tr>
        </thead>
        <tbody>
          <MatchesTableRow
            v-for="row in rows"
            :key="row.id"
            :row="row"
            :is-deleting-id="deletingId"
            @delete="emit('delete', $event)"
          />
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * MatchesTable.vue — results panel table for the /matches workspace.
 * Wraps the header/body structure; delegates row rendering to MatchesTableRow.
 */
import MatchesTableRow from './MatchesTableRow.vue'
import type { ProductMappingRow } from '@/types/matches'

interface Props {
  rows: ProductMappingRow[]
  deletingId: number | null
}

withDefaults(defineProps<Props>(), {
  deletingId: null,
})

const emit = defineEmits<{
  (e: 'delete', mappingId: number): void
}>()

function rowsLabel(n: number): string {
  if (n === 1) return 'збіг'
  if (n >= 2 && n <= 4) return 'збіги'
  return 'збігів'
}
</script>

<style scoped>
.mw-table-panel { display: flex; flex-direction: column; }
.mw-table-toolbar {
  display: flex;
  align-items: center;
  padding: 10px 16px;
  border-bottom: 1px solid var(--border);
  min-height: 42px;
}
.mw-table-count {
  font-size: 0.82rem;
  color: var(--muted);
  font-weight: 600;
}
.mw-table-scroll {
  max-height: calc(100vh - 300px);
  overflow-y: auto;
}
.col-price  { width: 110px; white-space: nowrap; }
.col-status { width: 140px; }
.col-score  { width: 76px; text-align: center; }
.col-date   { width: 100px; white-space: nowrap; }
.col-action { width: 90px; text-align: center; }
</style>
