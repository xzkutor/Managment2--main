<template>
  <!--
    ServiceCategoriesTab.vue — single-workspace category management.
    Commit 02: target-store only selector, top-centred control block.
    Commit 03: writes current target store to service context.
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

    <!-- ── Top-centred control block ───────────────────────── -->
    <div class="sc-cat-top-panel panel">
      <div class="sc-cat-top-row">
        <!-- Target store selector (reference stores excluded) -->
        <div class="form-group sc-cat-store-group">
          <label for="cat-store-select">Цільовий магазин</label>
          <select
            id="cat-store-select"
            :value="state.targetPane.storeId.value ?? ''"
            @change="onStoreChange"
          >
            <option value="">— оберіть цільовий магазин —</option>
            <option
              v-for="s in targetStores"
              :key="s.id"
              :value="s.id"
            >
              {{ s.name }}
            </option>
          </select>
        </div>

        <div class="sc-cat-sync-group">
          <button
            class="btn"
            type="button"
            :disabled="!state.targetPane.storeId.value || state.targetPane.syncLoading.value"
            @click="state.targetPane.triggerSync"
          >
            {{ state.targetPane.syncLoading.value ? '⏳ Синхронізація…' : 'Синхронізувати категорії' }}
          </button>
          <span
            v-if="state.targetPane.statusText.value && state.targetPane.statusText.value !== 'Очікування'"
            :class="['status-pill', `status-${state.targetPane.statusKind.value}`]"
          >
            {{ state.targetPane.statusText.value }}
          </span>
        </div>
      </div>
    </div>

    <!-- ── Scrape status: compact widget ───────────────────── -->
    <ScrapeStatusList :runs="state.scrapeRuns.value" />

    <!-- ── Category table: dominant surface ────────────────── -->
    <div class="panel">
      <CategoryTable
        :categories="state.targetPane.categories.value"
        :loading="state.targetPane.loading.value"
        :sync-products-loading-id="state.targetPane.syncProductsLoadingId.value"
        @sync-products="state.targetPane.triggerProductSync"
      />
    </div>

  </div>
</template>

<script setup lang="ts">
/**
 * ServiceCategoriesTab.vue — single-workspace category view.
 *
 * Shows only target (non-reference) stores so the operator cannot
 * accidentally mutate the reference catalogue.
 * Writes the selected target store to useServiceContext so Mappings
 * can default its target-store selection.
 */
import { computed } from 'vue'
import { useServiceCategories } from './composables/useServiceCategories'
import { useServiceContext } from '../composables/useServiceContext'
import ScrapeStatusList from './components/ScrapeStatusList.vue'
import CategoryTable from './components/CategoryTable.vue'

const state = useServiceCategories()
const ctx = useServiceContext()

/** Only show target (non-reference) stores in the selector. */
const targetStores = computed(() => state.stores.value.filter((s) => !s.is_reference))

function onStoreChange(event: Event) {
  const val = (event.target as HTMLSelectElement).value
  const id = val ? Number(val) : null
  state.targetPane.setStore(id)
  ctx.setTargetStore(id)
}
</script>

<style scoped>
.sc-cat-top-panel {
  margin-bottom: 16px;
  padding: 18px 24px;
}

.sc-cat-top-row {
  display: flex;
  align-items: flex-end;
  gap: 16px;
  flex-wrap: wrap;
  max-width: 760px;
  margin: 0 auto;
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
