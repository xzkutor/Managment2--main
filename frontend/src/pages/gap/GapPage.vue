<template>
  <div class="gap-workspace">

    <!-- ── Left rail: filters ─────────────────────── -->
    <aside class="gap-workspace-rail panel">
      <div class="gap-rail-heading">Параметри запиту</div>
      <GapFilters
        :target-stores="filters.targetStores.value"
        :reference-categories="filters.referenceCategories.value"
        :mapped-target-cats="filters.mappedTargetCats.value"
        :selected-target-store-id="filters.selectedTargetStoreId.value"
        :selected-ref-category-id="filters.selectedRefCategoryId.value"
        :selected-target-cat-ids="filters.selectedTargetCatIds.value"
        :search="filters.search.value"
        :only-available="filters.onlyAvailable.value"
        :statuses="filters.statuses"
        :ref-categories-loading="filters.refCategoriesLoading.value"
        :mapped-cats-loading="filters.mappedCatsLoading.value"
        :no-mappings-warning="filters.noMappingsWarning.value"
        :can-load="filters.canLoad.value"
        :loading="data.loading.value"
        @update:target-store="filters.setTargetStore"
        @update:ref-category="filters.setRefCategory"
        @toggle-target-cat="filters.toggleTargetCat"
        @update:search="v => { filters.search.value = v }"
        @update:only-available="v => { filters.onlyAvailable.value = v }"
        @update:status-new="v => { filters.statuses.new = v }"
        @update:status-in-progress="v => { filters.statuses.in_progress = v }"
        @update:status-done="v => { filters.statuses.done = v }"
        @load="handleLoad"
      />
    </aside>

    <!-- ── Right workspace ───────────────────────── -->
    <div class="gap-workspace-main">
      <div class="gap-workspace-main-surface">

        <!-- KPI strip + context (shown after first successful load) -->
        <GapSummary
          v-if="data.hasLoaded.value && data.result.value"
          :summary="data.result.value.summary"
          :target-store-name="targetStoreName"
          :ref-category-name="refCategoryName"
          :target-cat-count="filters.selectedTargetCatIds.value.size"
        />

        <!-- In-surface status: loading/error/empty (Commit 5) -->
        <GapStatusBanner
          :loading="data.loading.value || filters.storesLoading.value"
          :error="data.error.value ?? actions.actionError.value"
          :stores-error="filters.storesError.value"
          :is-empty="data.isEmptyAfterLoad.value"
          :has-loaded="data.hasLoaded.value"
        />

        <!-- Pre-run placeholder: before first load (Commit 3) -->
        <GapPreRunPlaceholder
          v-if="data.hasNeverLoaded.value"
          :can-load="filters.canLoad.value"
        />

        <!-- Grouped result panels (Commit 6) -->
        <template v-if="data.hasResults.value">
          <GapGroupTable
            v-for="group in data.result.value!.groups"
            :key="group.target_category?.id ?? String(Math.random())"
            :group="group"
            :ref-category-id="filters.selectedRefCategoryId.value ?? 0"
            :action-in-progress-id="actions.actionInProgressId.value"
            @action="handleAction"
          />
        </template>

      </div>
    </div>

  </div>
</template>

<script setup lang="ts">
/**
 * GapPage.vue — root Vue component for the /gap page.
 *
 * Workspace layout (Commit 2):
 *   - sticky left rail (GapFilters)
 *   - right workspace surface (placeholder, KPI strip, banners, result panels)
 *
 * Flask still owns: page shell (header/nav), CSS, <title>.
 */
import { computed, onMounted } from 'vue'
import { useGapFilters } from './composables/useGapFilters'
import { useGapData } from './composables/useGapData'
import { useGapActions } from './composables/useGapActions'
import { patchGapItemStatus } from './composables/patchGapResult'
import GapFilters from './components/GapFilters.vue'
import GapSummary from './components/GapSummary.vue'
import GapStatusBanner from './components/GapStatusBanner.vue'
import GapGroupTable from './components/GapGroupTable.vue'
import GapPreRunPlaceholder from './components/GapPreRunPlaceholder.vue'
import type { GapItemStatus } from '@/types/gap'

const filters = useGapFilters()
const data = useGapData()
const actions = useGapActions()

onMounted(() => {
  void filters.loadStores()
})

// ── Context helpers for GapSummary ────────────────────────────────────────
/** Display name of the selected target store (used in KPI context header). */
const targetStoreName = computed(() => {
  const id = filters.selectedTargetStoreId.value
  if (!id) return null
  return filters.targetStores.value.find((s) => s.id === id)?.name ?? null
})

/** Display name of the selected reference category. */
const refCategoryName = computed(() => {
  const id = filters.selectedRefCategoryId.value
  if (!id) return null
  return filters.referenceCategories.value.find((c) => c.id === id)?.name ?? null
})

// ── Handlers ──────────────────────────────────────────────────────────────

function buildBody() {
  const checkedStatuses: GapItemStatus[] = []
  if (filters.statuses.new) checkedStatuses.push('new')
  if (filters.statuses.in_progress) checkedStatuses.push('in_progress')
  if (filters.statuses.done) checkedStatuses.push('done')

  return {
    target_store_id: filters.selectedTargetStoreId.value!,
    reference_category_id: filters.selectedRefCategoryId.value!,
    target_category_ids: Array.from(filters.selectedTargetCatIds.value),
    search: filters.search.value.trim() || null,
    only_available: filters.onlyAvailable.value || null,
    statuses: checkedStatuses.length
      ? checkedStatuses
      : ['new' as GapItemStatus, 'in_progress' as GapItemStatus],
  }
}

async function handleLoad() {
  if (!filters.canLoad.value) return
  await data.loadGap(buildBody())
}

async function handleAction(refCatId: number, targetProductId: number, status: GapItemStatus) {
  const ok = await actions.setStatus(refCatId, targetProductId, status)
  if (!ok) return

  // Local patch — update item status and summary without blanking the page
  if (data.result.value) {
    const patched = patchGapItemStatus(data.result.value, targetProductId, status)
    if (patched !== data.result.value) {
      data.result.value = patched
      return
    }
  }

  // Fallback: item not found in current result — non-destructive reload
  if (data.lastBody.value) {
    await data.loadGap(data.lastBody.value)
  }
}
</script>

