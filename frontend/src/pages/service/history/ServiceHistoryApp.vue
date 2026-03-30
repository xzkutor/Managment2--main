<template>
  <!--
    ServiceHistoryApp.vue — filter rail + result workspace (Commit 5).

    Left rail: four filter selects + refresh action.
    Right workspace: status banner, history table, pagination, run-details dialog.
    Layout aligns with /matches and /gap workspace patterns.
  -->
  <div class="sc-section">
    <div class="sc-section-header">
      <h2 class="sc-section-title">Історія скрапінгу</h2>
    </div>

    <div class="sc-inner-workspace">

      <!-- ── Left rail: filters ───────────────────────────── -->
      <aside class="sc-inner-rail panel">
        <div class="sc-inner-rail-heading">Фільтри</div>

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

        <div class="sc-rail-actions">
          <button
            class="btn-ghost sc-rail-btn-full"
            type="button"
            :disabled="state.loading.value"
            @click="state.reload"
          >
            ↺ Оновити
          </button>
        </div>
      </aside>

      <!-- ── Right workspace: results ─────────────────────── -->
      <div class="sc-inner-main">

        <!-- Loading banner -->
        <div
          v-if="state.loading.value"
          class="status-block info"
          style="margin-bottom: 14px;"
          role="status"
          aria-live="polite"
        >
          ⏳ Завантаження…
        </div>

        <!-- Error banner -->
        <div
          v-else-if="state.error.value"
          class="status-block error"
          style="margin-bottom: 14px;"
          role="alert"
        >
          ⚠ {{ state.error.value }}
        </div>

        <!-- Record count -->
        <div
          v-else
          class="status-block info"
          style="margin-bottom: 14px;"
          role="status"
        >
          Записів на сторінці: {{ state.runs.value.length }}
        </div>

        <!-- Runs table -->
        <HistoryTable
          :runs="state.runs.value"
          @details="state.openDetails"
        />

        <!-- Pagination (footer of results panel) -->
        <HistoryPagination
          :page="state.page.value"
          :page-size="state.pageSize.value"
          :item-count="state.runs.value.length"
          :disabled="state.loading.value"
          @prev="state.prevPage"
          @next="state.nextPage"
        />
      </div>
    </div>

    <!-- Run details dialog (Vue-owned via Teleport) -->
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
 * ServiceHistoryApp.vue — filter rail + result workspace (Commit 5).
 *
 * Filters live in the left rail (HistoryFilters + refresh button).
 * Table, pagination, and status live in the right workspace.
 * Dialog and data flow are unchanged.
 */
import { useServiceHistory } from './composables/useServiceHistory'
import HistoryFilters from './components/HistoryFilters.vue'
import HistoryTable from './components/HistoryTable.vue'
import HistoryPagination from './components/HistoryPagination.vue'
import RunDetailsDialog from './components/RunDetailsDialog.vue'

const state = useServiceHistory()
</script>

