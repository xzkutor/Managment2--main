<template>
  <!--
    MappingsTab.vue — top filter block + dominant results table (Commits 02, 06).
    Commit 01 (fixup): onCreateClick no longer depends on useServiceContext.
    Commit 02 (fixup): inner left rail replaced with horizontal top filter bar.
    Commit 04 (fixup): ref store is visually secondary; copy aligned with new layout.
  -->
  <div class="sc-section">
    <div class="sc-section-header">
      <h2 class="sc-section-title">Мапінги категорій</h2>
      <div class="sc-section-actions">
        <button
          class="btn btn-sm"
          type="button"
          :disabled="!bothSelected"
          @click="onCreateClick"
        >+ Новий мапінг</button>
      </div>
    </div>

    <!-- ── Top filter block ─────────────────────────────────── -->
    <div class="sc-mapp-filter-bar panel">
      <div class="sc-mapp-filter-row">

        <!-- Reference store (secondary context) -->
        <div class="form-group sc-mapp-form-group--secondary">
          <label for="mapp-ref-store" class="label-muted">Reference store</label>
          <select
            id="mapp-ref-store"
            :value="state.refStoreId.value ?? ''"
            @change="onRefChange"
          >
            <option value="">— оберіть —</option>
            <option v-for="s in refStores" :key="s.id" :value="s.id">{{ s.name }}</option>
          </select>
        </div>

        <!-- Target store (primary) -->
        <div class="form-group sc-mapp-form-group">
          <label for="mapp-tgt-store">Цільовий магазин</label>
          <select
            id="mapp-tgt-store"
            :value="state.targetStoreId.value ?? ''"
            @change="onTargetChange"
          >
            <option value="">— оберіть цільовий магазин —</option>
            <option v-for="s in targetStores" :key="s.id" :value="s.id">{{ s.name }}</option>
          </select>
        </div>

        <!-- Actions -->
        <div class="sc-mapp-filter-actions">
          <button
            class="btn-ghost"
            type="button"
            :disabled="!bothSelected || state.autoLinkPending.value"
            title="Авто-маппінг за нормалізованою назвою"
            @click="state.triggerAutoLink"
          >
            {{ state.autoLinkPending.value ? '⏳ Авто-маппінг…' : '⚡ Авто-маппінг' }}
          </button>
        </div>
      </div>

      <!-- Auto-link summary -->
      <div
        v-if="state.autoLinkSummary.value"
        :class="['status-block', state.autoLinkSummary.value.summary.created > 0 ? 'success' : 'info']"
        style="margin-top: 12px; font-size: 0.84rem;"
        role="status"
      >
        Створено {{ state.autoLinkSummary.value.summary.created }},
        існувало {{ state.autoLinkSummary.value.summary.skipped_existing }},
        без норм. {{ state.autoLinkSummary.value.summary.skipped_no_norm }}.
        <button
          class="btn-ghost btn-sm"
          style="float: right;"
          type="button"
          aria-label="Закрити"
          @click="state.clearAutoLinkSummary"
        >✕</button>
      </div>
    </div>

    <!-- ── Error banner ─────────────────────────────────────── -->
    <div v-if="state.error.value" class="status-block error" style="margin-bottom:12px;" role="alert">
      ⚠ {{ state.error.value }}
    </div>

    <!-- ── Results surface ──────────────────────────────────── -->
    <div v-if="!bothSelected" class="empty-state">
      <div class="empty-state-icon">🔗</div>
      <p class="empty-state-title">Оберіть магазини</p>
      <p class="empty-state-body">Виберіть reference і цільовий магазин для відображення та керування мапінгами.</p>
    </div>
    <div v-else-if="state.loading.value" class="empty-state">
      <div class="empty-state-icon" aria-live="polite">⏳</div>
      <p class="empty-state-title">Завантаження…</p>
    </div>
    <div v-else-if="state.mappings.value.length === 0" class="empty-state">
      <div class="empty-state-icon">🗂</div>
      <p class="empty-state-title">Немає мапінгів</p>
      <p class="empty-state-body">Натисніть «+ Новий мапінг» або «⚡ Авто-маппінг».</p>
    </div>
    <MappingsTable
      v-else
      :mappings="state.mappings.value"
      :deleting-ids="state.deletingIds.value"
      @edit="state.openEditDrawer"
      @delete="state.deleteMappingById"
    />

    <!-- Right-side drawer -->
    <MappingDrawer
      :open="state.drawerOpen.value"
      :mode="state.drawerMode.value"
      :mapping="state.drawerMapping.value"
      :ref-categories="state.refCategories.value"
      :target-stores="targetStores"
      :default-target-store-id="state.targetStoreId.value"
      :default-target-categories="state.targetCategories.value"
      :pending="state.submitPending.value"
      :error-msg="state.submitError.value"
      @close="state.closeDrawer"
      @submit="state.submitDrawer"
    />
  </div>
</template>

<script setup lang="ts">
/**
 * MappingsTab.vue — top filter block + drawer + results table.
 *
 * Layout: section header → top filter bar (store selectors + auto-link)
 *         → empty/loading/error state → MappingsTable → MappingDrawer.
 *
 * Drawer defaults: target store and already-loaded target categories come
 * from the current Mappings page state (state.targetStoreId / targetCategories).
 * No dependency on useServiceContext for drawer defaulting.
 */
import { computed } from 'vue'
import { useMappingsTab } from './composables/useMappingsTab'
import MappingsTable from './components/MappingsTable.vue'
import MappingDrawer from './components/MappingDrawer.vue'

const state = useMappingsTab()

const bothSelected = computed(() => !!state.refStoreId.value && !!state.targetStoreId.value)
const refStores    = computed(() => state.stores.value.filter((s) =>  s.is_reference))
const targetStores = computed(() => state.stores.value.filter((s) => !s.is_reference))

function onRefChange(event: Event) {
  const val = (event.target as HTMLSelectElement).value
  void state.setRefStore(val ? Number(val) : null)
}

function onTargetChange(event: Event) {
  const val = (event.target as HTMLSelectElement).value
  void state.setTargetStore(val ? Number(val) : null)
}

async function onCreateClick() {
  if (!bothSelected.value) return
  // Drawer defaults target store from the current Mappings page state (state.targetStoreId).
  // No cross-section service context is consulted.
  await state.openCreateDrawer()
}
</script>

<style scoped>
.label-muted {
  color: var(--muted);
}

.sc-mapp-form-group--secondary select {
  opacity: 0.85;
}
</style>
