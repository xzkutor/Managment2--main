<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="cw-drawer-overlay"
      role="dialog"
      aria-modal="true"
      aria-label="Ручний пошук товару"
      @keydown.esc="emit('close')"
      @click.self="emit('close')"
    >
      <div class="cw-drawer-panel">

        <!-- Header -->
        <div class="cw-drawer-header">
          <div class="cw-drawer-title">
            🔍 Вибір вручну
            <div v-if="refProduct" class="cw-drawer-subtitle">{{ refProduct.name }}</div>
          </div>
          <button
            class="cw-drawer-close"
            aria-label="Закрити"
            @click="emit('close')"
          >✕</button>
        </div>

        <!-- Body -->
        <div class="cw-drawer-body">

          <!-- Include-rejected toggle -->
          <label class="checkbox-row">
            <input
              type="checkbox"
              :checked="picker.includeRejected.value"
              @change="picker.setIncludeRejected(($event.target as HTMLInputElement).checked)"
            />
            <span style="font-size:0.85rem;">Показати відхилені</span>
          </label>

          <!-- Search input -->
          <input
            ref="searchInput"
            type="text"
            class="picker-search"
            placeholder="Пошук за назвою (мін. 2 символи)…"
            :value="picker.search.value"
            style="width:100%;"
            @input="picker.onSearchInput(($event.target as HTMLInputElement).value)"
          />

          <!-- Search results -->
          <div v-if="picker.isSearching.value" class="muted" style="padding:6px 0;font-size:0.88rem;">
            <span class="spinner" />Завантаження…
          </div>
          <div v-else-if="picker.searchError.value" class="status-block error">
            {{ picker.searchError.value }}
          </div>
          <div
            v-else-if="picker.search.value.trim().length < 2"
            class="muted"
            style="font-size:0.85rem;padding:6px 0;"
          >
            Введіть мінімум 2 символи для пошуку
          </div>
          <div
            v-else-if="!picker.products.value.length"
            class="muted"
            style="font-size:0.85rem;padding:6px 0;"
          >
            Нічого не знайдено
          </div>
          <div v-else class="select-list" style="max-height:320px;overflow-y:auto;">
            <div
              v-for="p in picker.products.value"
              :key="p.id"
              class="select-list-item"
              :class="{ active: selectedId === p.id }"
              role="button"
              tabindex="0"
              @click="selectedId = p.id"
              @keydown.enter="selectedId = p.id"
              @keydown.space.prevent="selectedId = p.id"
            >
              {{ eligibleLabel(p) }}
            </div>
          </div>

          <!-- Confirm action -->
          <div style="margin-top:4px;">
            <button
              class="btn"
              style="width:100%;"
              :disabled="!selectedId || isConfirming"
              @click="onConfirm"
            >
              <span v-if="isConfirming"><span class="spinner" />Зберігаємо…</span>
              <span v-else>✔ Підтвердити вибір</span>
            </button>
          </div>

        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
/**
 * ManualPickerDrawer.vue — Shared page-level right-side drawer for manual product matching.
 *
 * One instance lives on ComparisonPage. Opens when any candidate group card or
 * reference-only item emits 'open-picker'. Replaces inline ManualPicker instances
 * inside CandidateGroupCard and ReferenceOnlySection (RFC-016, Commit 5).
 *
 * Emits:
 *   'close'  — drawer should be closed
 *   'pick'   — operator confirmed a target product id
 */
import { ref, watch, nextTick } from 'vue'
import { useManualPicker } from '../composables/useManualPicker'
import { eligibleProductLabel } from './shared/format'
import type { ComparisonProduct, EligibleProduct } from '../types'

interface Props {
  open:              boolean
  refProduct:        ComparisonProduct | null
  targetCategoryIds: number[]
}
const props = withDefaults(defineProps<Props>(), {
  open:              false,
  refProduct:        null,
  targetCategoryIds: () => [],
})

const emit = defineEmits<{
  (e: 'close'):                   void
  (e: 'pick', targetId: number):  void
}>()

// Picker state — uses getter so it reads the current refProduct id reactively
const picker = useManualPicker(
  () => props.refProduct?.id ?? 0,
  () => props.targetCategoryIds,
)

const selectedId   = ref<number | null>(null)
const isConfirming = ref(false)
const searchInput  = ref<HTMLInputElement | null>(null)

// Reset state whenever drawer opens with a (possibly different) product
watch(
  () => props.open,
  async (nowOpen) => {
    if (nowOpen) {
      picker.reset()
      selectedId.value = null
      await nextTick()
      searchInput.value?.focus()
    }
  },
)

function eligibleLabel(p: EligibleProduct): string {
  return eligibleProductLabel(p)
}

async function onConfirm() {
  if (!selectedId.value) return
  isConfirming.value = true
  try {
    emit('pick', selectedId.value)
    selectedId.value = null
  } finally {
    isConfirming.value = false
  }
}
</script>

