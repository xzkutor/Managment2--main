<template>
  <!--
    MappingsTab.vue — left rail + right workspace (Commits 04, 06).
    Commit 04: create/edit via right-side MappingDrawer (replaces modal).
    Commit 06: compact rail, dominant results table.
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

    <div class="sc-inner-workspace">

      <!-- ── Left rail: store selectors + auto-link ───────── -->
      <aside class="sc-inner-rail panel">
        <div class="sc-inner-rail-heading">Магазини</div>

        <div class="form-group">
          <label for="mapp-ref-store">Reference store</label>
          <select
            id="mapp-ref-store"
            :value="state.refStoreId.value ?? ''"
            @change="onRefChange"
          >
            <option value="">— оберіть —</option>
            <option v-for="s in refStores" :key="s.id" :value="s.id">
              {{ s.name }}
            </option>
          </select>
        </div>

        <div class="form-group">
          <label for="mapp-tgt-store">Target store</label>
          <select
            id="mapp-tgt-store"
            :value="state.targetStoreId.value ?? ''"
            @change="onTargetChange"
          >
            <option value="">— оберіть —</option>
            <option v-for="s in targetStores" :key="s.id" :value="s.id">
              {{ s.name }}
            </option>
          </select>
        </div>

        <div class="sc-rail-actions">
          <button
            class="btn-ghost sc-rail-btn-full"
            type="button"
            :disabled="!bothSelected || state.autoLinkPending.value"
            title="Авто-маппінг за нормалізованою назвою"
            @click="state.triggerAutoLink"
          >
            {{ state.autoLinkPending.value ? '⏳ Авто-маппінг…' : '⚡ Авто-маппінг' }}
          </button>
        </div>

        <!-- Auto-link summary -->
        <div
          v-if="state.autoLinkSummary.value"
          :class="['status-block', state.autoLinkSummary.value.summary.created > 0 ? 'success' : 'info']"
          style="margin-top: 14px; font-size: 0.84rem;"
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
      </aside>

      <!-- ── Right workspace: dominant results table ─────── -->
      <div class="sc-inner-main">
        <div v-if="state.error.value" class="status-block error" style="margin-bottom:12px;" role="alert">
          ⚠ {{ state.error.value }}
        </div>

        <div v-if="!bothSelected" class="empty-state">
          <div class="empty-state-icon">🔗</div>
          <p class="empty-state-title">Оберіть магазини</p>
          <p class="empty-state-body">Виберіть reference і target магазини для відображення мапінгів.</p>
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
      </div>
    </div>

    <!-- Right-side drawer (replaces modal) -->
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
import { computed } from 'vue'
import { useMappingsTab } from './composables/useMappingsTab'
import { useServiceContext } from '../composables/useServiceContext'
import MappingsTable from './components/MappingsTable.vue'
import MappingDrawer from './components/MappingDrawer.vue'

const state = useMappingsTab()
const ctx = useServiceContext()

const bothSelected = computed(() => !!state.refStoreId.value && !!state.targetStoreId.value)

/** Only reference stores in the ref selector. */
const refStores = computed(() => state.stores.value.filter((s) => s.is_reference))
/** Only non-reference stores in the target selector. */
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
  // Seed target store from service context if not yet selected
  if (!state.targetStoreId.value && ctx.currentTargetStoreId.value) {
    await state.setTargetStore(ctx.currentTargetStoreId.value)
  }
  await state.openCreateDrawer()
}
</script>

