<template>
  <!--
    ServiceCategoriesTab.vue — single-workspace category management (Commit 3).

    Replaces the old dual-pane (reference + target) layout with one coherent
    workspace: compact control area (store selector + sync actions) at the top,
    scrape status widget below, and one dominant category table surface.
    The operator picks any store from the unified selector.
  -->
  <div class="sc-section">

    <!-- ── Section header ──────────────────────────────────── -->
    <div class="sc-section-header">
      <h2 class="sc-section-title">Категорії та скрапінг</h2>
      <div class="sc-section-actions" v-if="state.enableAdminSync.value">
        <button
          class="btn-ghost btn-sm"
          type="button"
          :disabled="state.storeSyncLoading.value"
          @click="state.triggerStoreSync"
        >
          {{ state.storeSyncLoading.value ? '⏳ Синхронізація…' : 'Синхронізувати магазини' }}
        </button>
        <span
          v-if="state.storeSyncStatus.value"
          :class="['status-pill', `status-${state.storeSyncStatus.value.kind}`]"
        >
          {{ state.storeSyncStatus.value.text }}
        </span>
      </div>
    </div>

    <!-- ── Compact control bar: store + sync ───────────────── -->
    <div class="panel sc-cat-controls">
      <div class="sc-cat-controls-row">
        <div class="form-group sc-cat-store-group">
          <label for="cat-store-select">Магазин</label>
          <select
            id="cat-store-select"
            :value="state.refPane.storeId.value ?? ''"
            @change="onStoreChange"
          >
            <option value="">— оберіть магазин —</option>
            <option v-for="s in state.stores.value" :key="s.id" :value="s.id">
              {{ s.name }}{{ s.is_reference ? ' (ref)' : '' }}
            </option>
          </select>
        </div>
        <div class="sc-cat-sync-group">
          <button
            class="btn"
            type="button"
            :disabled="!state.refPane.storeId.value || state.refPane.syncLoading.value"
            @click="state.refPane.triggerSync"
          >
            {{ state.refPane.syncLoading.value ? '⏳ Синхронізація…' : 'Синхронізувати категорії' }}
          </button>
          <span
            v-if="state.refPane.statusText.value && state.refPane.statusText.value !== 'Очікування'"
            :class="['status-pill', `status-${state.refPane.statusKind.value}`]"
          >
            {{ state.refPane.statusText.value }}
          </span>
        </div>
      </div>
    </div>

    <!-- ── Scrape status: compact widget ───────────────────── -->
    <ScrapeStatusList :runs="state.scrapeRuns.value" />

    <!-- ── Category table: dominant surface ────────────────── -->
    <div class="panel">
      <CategoryTable
        :categories="state.refPane.categories.value"
        :loading="state.refPane.loading.value"
        :sync-products-loading-id="state.refPane.syncProductsLoadingId.value"
        @sync-products="state.refPane.triggerProductSync"
      />
    </div>

  </div>
</template>

<script setup lang="ts">
/**
 * ServiceCategoriesTab.vue — single-workspace category view (Commit 3).
 *
 * Collapses the dual-pane layout into one coherent workspace.
 * Uses refPane from useServiceCategories as the single active pane;
 * the store selector allows picking any store (reference or target).
 */
import { useServiceCategories } from './composables/useServiceCategories'
import ScrapeStatusList from './components/ScrapeStatusList.vue'
import CategoryTable from './components/CategoryTable.vue'

const state = useServiceCategories()

function onStoreChange(event: Event) {
  const val = (event.target as HTMLSelectElement).value
  state.refPane.setStore(val ? Number(val) : null)
}
</script>

<style scoped>
.sc-cat-controls {
  margin-bottom: 16px;
  padding: 16px 20px;
}

.sc-cat-controls-row {
  display: flex;
  align-items: flex-end;
  gap: 16px;
  flex-wrap: wrap;
}

.sc-cat-store-group {
  flex: 1;
  min-width: 200px;
  margin-bottom: 0;
}

.sc-cat-sync-group {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  padding-bottom: 1px;
}
</style>
