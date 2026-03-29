<template>
  <div class="manual-picker">
    <details class="picker-details">
      <summary class="picker-summary">🔍 Вибрати вручну…</summary>
      <div class="picker-body">
        <!-- Include rejected toggle -->
        <label style="display:flex;align-items:center;gap:6px;font-size:0.82rem;color:var(--muted);margin-bottom:6px;">
          <input
            type="checkbox"
            :checked="picker.includeRejected.value"
            @change="picker.setIncludeRejected(($event.target as HTMLInputElement).checked)"
          />
          Показати відхилені
        </label>

        <!-- Search input -->
        <input
          type="text"
          class="picker-search"
          placeholder="Пошук за назвою…"
          :value="picker.search.value"
          @input="picker.onSearchInput(($event.target as HTMLInputElement).value)"
        />

        <!-- Results select -->
        <select class="picker-select" size="5" v-model="selectedProductId">
          <option value="" disabled>
            <template v-if="picker.isSearching.value">Завантаження…</template>
            <template v-else-if="picker.searchError.value">Помилка: {{ picker.searchError.value }}</template>
            <template v-else-if="!picker.search.value || picker.search.value.length < 2">— введіть мінімум 2 символи —</template>
            <template v-else-if="!picker.products.value.length">— нічого не знайдено —</template>
            <template v-else>— оберіть —</template>
          </option>
          <option
            v-for="p in picker.products.value"
            :key="p.id"
            :value="p.id"
          >{{ eligibleLabel(p) }}</option>
        </select>

        <!-- Confirm button -->
        <button
          class="btn btn-sm"
          style="margin-top:6px;"
          :disabled="!selectedProductId || isConfirming"
          @click="onConfirm"
        >
          {{ isConfirming ? '…' : '✔ Підтвердити вибір' }}
        </button>
      </div>
    </details>
  </div>
</template>

<script setup lang="ts">
/**
 * ManualPicker.vue — debounced eligible-target-product search widget.
 *
 * Emits 'pick' with the selected target product id.
 * Parent is responsible for calling makeDecision and refreshing results.
 */
import { ref } from 'vue'
import { useManualPicker } from '../composables/useManualPicker'
import { eligibleProductLabel } from './shared/format'
import type { EligibleProduct } from '../types'

interface Props {
  refProductId: number
  targetCategoryIds: number[]
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'pick', targetProductId: number): void
}>()

const picker = useManualPicker(
  () => props.refProductId,
  () => props.targetCategoryIds,
)

const selectedProductId = ref<number | ''>('')
const isConfirming = ref(false)

function eligibleLabel(p: EligibleProduct): string {
  return eligibleProductLabel(p)
}

async function onConfirm() {
  if (!selectedProductId.value) return
  isConfirming.value = true
  try {
    emit('pick', Number(selectedProductId.value))
    selectedProductId.value = ''
  } finally {
    isConfirming.value = false
  }
}
</script>

