<template>
  <!--
    ServiceHistoryApp.vue — history section with top filter bar (Commit 07).
    Filters render horizontally above the table (no left rail).
    Table is the primary workspace surface.
  -->
  <div class="sc-section">
    <div class="sc-section-header">
      <h2 class="sc-section-title">Історія скрапінгу</h2>
      <div class="sc-section-actions">
        <button
          class="btn-ghost btn-sm"
          type="button"
          :disabled="state.loading.value"
          @click="state.reload"
        >↺ Оновити</button>
      </div>
    </div>

    <!-- Top horizontal filter bar -->
    <div class="sc-hist-filter-bar panel">
      <HistoryFilters
        :stores="state.stores.value"
        :store-id="state.filters.storeId"
        :run-type="state.filters.runType"
        :status="state.filters.status"
        :trigger-type="state.filters.triggerType"
        @update:store-id="v => state.setFilter('storeId', v)"
        @update:run-type="v => state.setFilter('runType', v)"
        @update:status="v => state.setFilter('status', v)"
        @update:trigger-type="v => state.setFilter('triggerType', v)"
      />
    </div>

    <!-- Status banner -->
    <div
      v-if="state.loading.value"
      class="status-block info"
      style="margin-bottom: 14px;"
      role="status"
      aria-live="polite"
    >⏳ Завантаження…</div>
    <div
      v-else-if="state.error.value"
      class="status-block error"
      style="margin-bottom: 14px;"
      role="alert"
    >⚠ {{ state.error.value }}</div>
    <div
      v-else
      class="status-block info"
      style="margin-bottom: 14px;"
      role="status"
    >Записів на сторінці: {{ state.runs.value.length }}</div>

    <!-- Results table: full width, dominant surface -->
    <HistoryTable :runs="state.runs.value" @details="state.openDetails" />

    <!-- Pagination under table -->
    <HistoryPagination
      :page="state.page.value"
      :page-size="state.pageSize.value"
      :item-count="state.runs.value.length"
      :disabled="state.loading.value"
      @prev="state.prevPage"
      @next="state.nextPage"
    />

    <!-- Run details dialog -->
    <RunDetailsDialog
      :open="state.detailRunId.value !== null"
      :run="state.detailRun.value"
      :loading="state.detailLoading.value"
      :error="state.detailError.value"
      @close="state.closeDetails"
    />
  </div>
</template>

<script setup lang="ts">
/**
 * ServiceHistoryApp.vue — horizontal top filter bar + full-width table (Commit 07).
 * Removes the left-rail filter layout introduced in the previous pass.
 */
import { useServiceHistory } from './composables/useServiceHistory'
import HistoryFilters from './components/HistoryFilters.vue'
import HistoryTable from './components/HistoryTable.vue'
import HistoryPagination from './components/HistoryPagination.vue'
import RunDetailsDialog from './components/RunDetailsDialog.vue'

const state = useServiceHistory()
</script>

<style scoped>
.sc-hist-filter-bar {
  padding: 14px 20px;
  margin-bottom: 16px;
}
</style>
