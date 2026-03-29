<template>
  <div class="vue-island">
    <!-- Toolbar: store selectors + action buttons -->
    <MappingsToolbar
      :stores="state.stores.value"
      :ref-store-id="state.refStoreId.value"
      :target-store-id="state.targetStoreId.value"
      :auto-link-busy="state.autoLinkPending.value"
      @update:ref-store-id="state.setRefStore"
      @update:target-store-id="state.setTargetStore"
      @create="onCreateClick"
      @auto-link="state.triggerAutoLink"
    />

    <!-- Auto-link summary banner -->
    <div
      v-if="state.autoLinkSummary.value"
      :class="['status-block', state.autoLinkSummary.value.summary.created > 0 ? 'success' : 'info']"
      style="margin-bottom: 12px;"
      role="status"
    >
      Авто-маппінг завершено: створено {{ state.autoLinkSummary.value.summary.created }},
      вже існувало {{ state.autoLinkSummary.value.summary.skipped_existing }},
      без нормалізації {{ state.autoLinkSummary.value.summary.skipped_no_norm }}.
      <button
        class="btn-ghost btn-sm"
        style="float: right; margin-top: -2px;"
        type="button"
        aria-label="Закрити"
        @click="state.clearAutoLinkSummary"
      >✕</button>
    </div>

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
    <div v-if="!bothSelected" class="status-block info" style="margin-top: 8px;">
      Виберіть обидва магазини для відображення мапінгів.
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
      <p class="empty-state-body">Натисніть «+ Створити мапінг» або «⚡ Авто-маппінг за назвою».</p>
    </div>

    <!-- Mappings table -->
    <MappingsTable
      v-else
      :mappings="state.mappings.value"
      :deleting-ids="state.deletingIds.value"
      @edit="state.openEditDialog"
      @delete="state.deleteMappingById"
    />

    <!-- Create / Edit dialog (Vue-owned via Teleport) -->
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
 * MappingsTab.vue — root component for the Mappings tab Vue island.
 *
 * Mounted by frontend/src/entries/service.ts on #service-mappings-root.
 * Owns all Mappings flows: load, create, edit, delete, auto-link.
 */
import { computed } from 'vue'
import { useMappingsTab } from './composables/useMappingsTab'
import MappingsToolbar from './components/MappingsToolbar.vue'
import MappingsTable from './components/MappingsTable.vue'
import MappingDialog from './components/MappingDialog.vue'

const state = useMappingsTab()

const bothSelected = computed(() => !!state.refStoreId.value && !!state.targetStoreId.value)

async function onCreateClick() {
  if (!bothSelected.value) return
  await state.openCreateDialog()
}
</script>

