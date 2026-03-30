<template>
  <!--
    MappingsTab.vue — two-column workspace (Commit 4).

    Left rail: store selectors + primary action buttons + auto-link summary.
    Right workspace: error banners, loading/empty/table states.
    Dialog is Vue-owned via Teleport (unchanged).
  -->
  <div class="sc-section">
    <div class="sc-section-header">
      <h2 class="sc-section-title">Мапінги категорій</h2>
    </div>

    <div class="sc-inner-workspace">

      <!-- ── Left rail: store controls + actions ─────────── -->
      <aside class="sc-inner-rail panel">
        <div class="sc-inner-rail-heading">Магазини</div>

        <!-- Reference store -->
        <div class="form-group">
          <label for="mapp-ref-store">Reference store</label>
          <select
            id="mapp-ref-store"
            :value="state.refStoreId.value ?? ''"
            @change="onRefChange"
          >
            <option value="">— оберіть —</option>
            <option v-for="s in state.stores.value" :key="s.id" :value="s.id">
              {{ s.name }}{{ s.is_reference ? ' ★' : '' }}
            </option>
          </select>
        </div>

        <!-- Target store -->
        <div class="form-group">
          <label for="mapp-tgt-store">Target store</label>
          <select
            id="mapp-tgt-store"
            :value="state.targetStoreId.value ?? ''"
            @change="onTargetChange"
          >
            <option value="">— оберіть —</option>
            <option v-for="s in state.stores.value" :key="s.id" :value="s.id">
              {{ s.name }}{{ s.is_reference ? ' ★' : '' }}
            </option>
          </select>
        </div>

        <!-- Actions -->
        <div class="sc-rail-actions">
          <button
            class="btn sc-rail-btn-full"
            type="button"
            :disabled="!bothSelected"
            @click="onCreateClick"
          >
            + Створити мапінг
          </button>
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

        <!-- Auto-link summary (inside rail) -->
        <div
          v-if="state.autoLinkSummary.value"
          :class="['status-block', state.autoLinkSummary.value.summary.created > 0 ? 'success' : 'info']"
          style="margin-top: 14px; font-size: 0.85rem;"
          role="status"
        >
          Створено {{ state.autoLinkSummary.value.summary.created }},
          існувало {{ state.autoLinkSummary.value.summary.skipped_existing }},
          без норм. {{ state.autoLinkSummary.value.summary.skipped_no_norm }}.
          <button
            class="btn-ghost btn-sm"
            style="float: right; margin-top: -2px;"
            type="button"
            aria-label="Закрити"
            @click="state.clearAutoLinkSummary"
          >✕</button>
        </div>
      </aside>

      <!-- ── Right workspace: results ────────────────────── -->
      <div class="sc-inner-main">

        <!-- Error banner -->
        <div
          v-if="state.error.value"
          class="status-block error"
          style="margin-bottom: 12px;"
          role="alert"
        >
          ⚠ {{ state.error.value }}
        </div>

        <!-- No stores selected -->
        <div v-if="!bothSelected" class="empty-state">
          <div class="empty-state-icon">🔗</div>
          <p class="empty-state-title">Оберіть магазини</p>
          <p class="empty-state-body">
            Виберіть reference і target магазини в лівій панелі для відображення мапінгів.
          </p>
        </div>

        <!-- Loading -->
        <div v-else-if="state.loading.value" class="empty-state">
          <div class="empty-state-icon" aria-live="polite">⏳</div>
          <p class="empty-state-title">Завантаження мапінгів…</p>
        </div>

        <!-- Empty -->
        <div v-else-if="state.mappings.value.length === 0" class="empty-state">
          <div class="empty-state-icon">🗂</div>
          <p class="empty-state-title">Немає мапінгів</p>
          <p class="empty-state-body">
            Натисніть «+ Створити мапінг» або «⚡ Авто-маппінг» у лівій панелі.
          </p>
        </div>

        <!-- Mappings table -->
        <MappingsTable
          v-else
          :mappings="state.mappings.value"
          :deleting-ids="state.deletingIds.value"
          @edit="state.openEditDialog"
          @delete="state.deleteMappingById"
        />
      </div>
    </div>

    <!-- Dialog (Vue-owned via Teleport) -->
    <MappingDialog
      :open="state.dialogOpen.value"
      :mode="state.dialogMode.value"
      :mapping="state.dialogMapping.value"
      :ref-categories="state.refCategories.value"
      :target-categories="state.targetCategories.value"
      :pending="state.submitPending.value"
      :error-msg="state.submitError.value"
      @close="state.closeDialog"
      @submit="state.submitDialog"
    />
  </div>
</template>

<script setup lang="ts">
/**
 * MappingsTab.vue — two-column workspace layout (Commit 4).
 *
 * Store selectors and primary actions live in the left rail (sc-inner-rail).
 * Results table, status, and empty states live in the right workspace (sc-inner-main).
 * All existing actions (create, edit, delete, auto-link) are preserved.
 */
import { computed } from 'vue'
import { useMappingsTab } from './composables/useMappingsTab'
import MappingsTable from './components/MappingsTable.vue'
import MappingDialog from './components/MappingDialog.vue'

const state = useMappingsTab()

const bothSelected = computed(() => !!state.refStoreId.value && !!state.targetStoreId.value)

function onRefChange(event: Event) {
  const val = (event.target as HTMLSelectElement).value
  state.setRefStore(val ? Number(val) : null)
}

function onTargetChange(event: Event) {
  const val = (event.target as HTMLSelectElement).value
  state.setTargetStore(val ? Number(val) : null)
}

async function onCreateClick() {
  if (!bothSelected.value) return
  await state.openCreateDialog()
}
</script>

