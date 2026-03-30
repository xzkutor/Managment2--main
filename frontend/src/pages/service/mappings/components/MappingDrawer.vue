<template>
  <!--
    MappingDrawer.vue — right-side drawer for create/edit mapping (Commits 04, 05).

    Replaces the modal MappingDialog.
    Form fields: reference category, target store (defaults from service context),
    target category. match_type and confidence are intentionally excluded.
  -->
  <DrawerShell
    :open="open"
    :title="mode === 'create' ? 'Новий мапінг' : 'Редагувати мапінг'"
    @close="$emit('close')"
  >
    <form id="mapping-drawer-form" autocomplete="off" @submit.prevent="onSubmit">

      <!-- Reference category -->
      <div class="form-group">
        <label for="mdr-ref-cat">Категорія (reference)</label>
        <select
          id="mdr-ref-cat"
          v-model="form.reference_category_id"
          required
          :disabled="mode === 'edit'"
        >
          <option value="">— оберіть категорію —</option>
          <option v-for="c in refCategories" :key="c.id" :value="String(c.id)">
            {{ c.name }}
          </option>
        </select>
      </div>

      <!-- Target store (disabled on edit; defaults from service context on create) -->
      <div class="form-group">
        <label for="mdr-tgt-store">Цільовий магазин</label>
        <select
          id="mdr-tgt-store"
          v-model="form.target_store_id"
          :disabled="mode === 'edit'"
          @change="onTargetStoreChange"
        >
          <option value="">— оберіть магазин —</option>
          <option v-for="s in targetStores" :key="s.id" :value="String(s.id)">
            {{ s.name }}
          </option>
        </select>
        <p v-if="mode === 'edit'" class="field-help">
          Пара категорій незмінна при редагуванні.
        </p>
      </div>

      <!-- Target category (populated after target store chosen) -->
      <div class="form-group">
        <label for="mdr-tgt-cat">Категорія (target)</label>
        <select
          id="mdr-tgt-cat"
          v-model="form.target_category_id"
          required
          :disabled="mode === 'edit' || loadingTargetCats"
        >
          <option value="">
            {{ loadingTargetCats ? 'Завантаження…' : '— оберіть категорію —' }}
          </option>
          <option v-for="c in localTargetCats" :key="c.id" :value="String(c.id)">
            {{ c.name }}
          </option>
        </select>
      </div>

      <p v-if="errorMsg" class="field-error" style="margin-top: 10px;">{{ errorMsg }}</p>
    </form>

    <template #footer>
      <button class="btn-ghost" type="button" @click="$emit('close')">Скасувати</button>
      <button
        class="btn"
        type="submit"
        form="mapping-drawer-form"
        :disabled="pending"
      >
        {{ pending ? 'Збереження…' : 'Зберегти' }}
      </button>
    </template>
  </DrawerShell>
</template>

<script setup lang="ts">
/**
 * MappingDrawer.vue — simplified right-side drawer for mapping create/edit.
 *
 * Fields: reference category, target store, target category.
 * Removed: match_type, confidence (not needed for operator workflow).
 * Target store defaults to the current service context target store on create.
 */
import { ref, watch } from 'vue'
import DrawerShell from '@/components/base/DrawerShell.vue'
import { fetchCategoriesForStore } from '@/api/client'
import type { StoreSummary, CategorySummary } from '@/types/store'
import type { MappingRow, DrawerFormModel } from '@/types/mappings'

interface Props {
  open: boolean
  mode: 'create' | 'edit'
  mapping?: MappingRow | null
  refCategories: CategorySummary[]
  /** All non-reference stores; target category is populated after selection. */
  targetStores: StoreSummary[]
  /** Pre-selected target store id (from service context or toolbar). */
  defaultTargetStoreId?: number | null
  /** Already-loaded categories for the default target store. */
  defaultTargetCategories?: CategorySummary[]
  pending?: boolean
  errorMsg?: string | null
}

const props = withDefaults(defineProps<Props>(), {
  mapping: null,
  defaultTargetStoreId: null,
  defaultTargetCategories: () => [],
  pending: false,
  errorMsg: null,
})

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'submit', form: DrawerFormModel): void
}>()

function emptyForm(): DrawerFormModel {
  return {
    reference_category_id: '',
    target_store_id: props.defaultTargetStoreId ? String(props.defaultTargetStoreId) : '',
    target_category_id: '',
  }
}

const form = ref<DrawerFormModel>(emptyForm())
const localTargetCats = ref<CategorySummary[]>([...props.defaultTargetCategories])
const loadingTargetCats = ref(false)

// Load categories for the target store when it changes in the form
async function onTargetStoreChange() {
  const storeId = form.value.target_store_id ? Number(form.value.target_store_id) : null
  form.value.target_category_id = ''
  if (!storeId) { localTargetCats.value = []; return }
  loadingTargetCats.value = true
  try {
    localTargetCats.value = await fetchCategoriesForStore(storeId)
  } catch {
    localTargetCats.value = []
  } finally {
    loadingTargetCats.value = false
  }
}

// Reset/populate form when drawer opens
watch(() => props.open, async (isOpen) => {
  if (!isOpen) return
  if (props.mode === 'edit' && props.mapping) {
    form.value = {
      reference_category_id: String(props.mapping.reference_category_id),
      target_store_id: props.mapping.target_store_id ? String(props.mapping.target_store_id) : '',
      target_category_id: String(props.mapping.target_category_id),
    }
    // Load target cats for the edit mapping's store
    if (props.mapping.target_store_id) {
      loadingTargetCats.value = true
      try {
        localTargetCats.value = await fetchCategoriesForStore(props.mapping.target_store_id)
      } catch {
        localTargetCats.value = []
      } finally {
        loadingTargetCats.value = false
      }
    }
  } else {
    form.value = emptyForm()
    // Default target categories from the provided list
    localTargetCats.value = [...props.defaultTargetCategories]
  }
})

function onSubmit() {
  if (!form.value.reference_category_id || !form.value.target_category_id) return
  emit('submit', { ...form.value })
}
</script>

