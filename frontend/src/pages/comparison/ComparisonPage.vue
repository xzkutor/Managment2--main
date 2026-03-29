<template>
  <div class="cw-workspace">

    <!-- ── Left sticky control rail ─────────────────────────────── -->
    <ComparisonControlRail
      :target-stores="page.targetStores.value"
      :target-store-id="page.targetStoreId.value"
      :categories="page.referenceCategories.value"
      :loading-categories="page.isLoadingRefCategories.value"
      :active-category-id="page.referenceCategoryId.value"
      :can-compare="page.canCompare.value"
      :comparing="page.isComparing.value"
      :status-text="page.storesError.value ?? page.pageStatus.value"
      @update:target-store="page.setTargetStore"
      @select-category="page.selectRefCategory"
      @compare="page.compare"
    />

    <!-- ── Right main workspace ──────────────────────────────────── -->
    <div class="cw-main">

      <!-- KPI summary / status bar -->
      <ComparisonSummaryBar
        :result="page.comparisonResult.value"
        :comparing="page.isComparing.value"
        :error-text="page.comparisonError.value ?? page.decisionError.value"
        :reference-category="page.currentReferenceCategory.value"
        :target-store="page.selectedTargetStore.value"
      />

      <!-- ── Review workspace ──────────────────────────────────── -->
      <div v-if="page.hasReviewContent.value" class="cw-review-workspace">

        <!-- Auto suggestions — collapsed by default -->
        <ComparisonCollapsibleSection
          v-if="page.reviewCounts.value.autoSuggestions > 0"
          title="🔍 Авто-пропозиції"
          :count="page.reviewCounts.value.autoSuggestions"
          :expanded="page.sectionExpanded.value.autoSuggestions"
          badge-class="badge-heuristic"
          @toggle="page.toggleSection('autoSuggestions')"
        >
          <AutoSuggestionsTable
            :suggestions="page.autoSuggestions.value"
            :decision-in-progress-key="page.decisionInProgressKey.value"
            @decision="page.makeDecision"
          />
        </ComparisonCollapsibleSection>

        <!-- Candidate groups — collapsed by default -->
        <ComparisonCollapsibleSection
          v-if="page.reviewCounts.value.candidateGroups > 0"
          title="🔎 Потребують вибору"
          :count="page.reviewCounts.value.candidateGroups"
          :expanded="page.sectionExpanded.value.candidateGroups"
          badge-class="badge-ambig"
          @toggle="page.toggleSection('candidateGroups')"
        >
          <CandidateGroups
            :groups="page.comparisonResult.value!.candidate_groups"
            :decision-in-progress-key="page.decisionInProgressKey.value"
            @decision="page.makeDecision"
            @open-picker="onOpenPicker"
          />
        </ComparisonCollapsibleSection>

        <!-- Reference-only — collapsed by default -->
        <ComparisonCollapsibleSection
          v-if="page.reviewCounts.value.referenceOnly > 0"
          title="📋 Тільки в референсі"
          :count="page.reviewCounts.value.referenceOnly"
          :expanded="page.sectionExpanded.value.referenceOnly"
          badge-class="badge-ref"
          @toggle="page.toggleSection('referenceOnly')"
        >
          <ReferenceOnlySection
            :items="page.comparisonResult.value!.reference_only"
            @open-picker="onOpenPicker"
          />
        </ComparisonCollapsibleSection>

        <!-- Target-only (secondary, collapsed) -->
        <TargetOnlySection
          :items="page.comparisonResult.value?.target_only ?? []"
        />
      </div>

      <!-- Empty state -->
      <div
        v-else-if="page.hasCompared.value && !page.isComparing.value && !page.comparisonError.value"
        class="empty-state"
        style="margin-top:40px;"
      >
        <div class="empty-state-icon">✅</div>
        <div class="empty-state-title">Все зіставлено!</div>
        <div class="empty-state-body">Немає товарів для перегляду в обраних категоріях.</div>
      </div>

    </div>

    <!-- ── Shared manual picker drawer ──────────────────────────── -->
    <ManualPickerDrawer
      :open="drawer.isOpen.value"
      :ref-product="drawer.drawerRefProduct.value"
      :target-category-ids="drawer.drawerTargetCategoryIds.value"
      @close="drawer.closeDrawer"
      @pick="onDrawerPick"
    />

  </div>
</template>

<script setup lang="ts">
/**
 * ComparisonPage.vue — two-column operator workspace (RFC-016 v2).
 *
 * Layout: left sticky rail + right review workspace.
 * Three primary sections (auto-suggestions, candidates, ref-only) are collapsed by default.
 * One shared ManualPickerDrawer handles all manual matching.
 */
import { onMounted } from 'vue'
import { useComparisonPage }     from './composables/useComparisonPage'
import { useManualPickerDrawer } from './composables/useManualPickerDrawer'
import type { ComparisonProduct } from './types'

import ComparisonControlRail        from './components/ComparisonControlRail.vue'
import ComparisonSummaryBar         from './components/ComparisonSummaryBar.vue'
import ComparisonCollapsibleSection from './components/ComparisonCollapsibleSection.vue'
import AutoSuggestionsTable         from './components/AutoSuggestionsTable.vue'
import CandidateGroups              from './components/CandidateGroups.vue'
import ReferenceOnlySection         from './components/ReferenceOnlySection.vue'
import TargetOnlySection            from './components/TargetOnlySection.vue'
import ManualPickerDrawer           from './components/ManualPickerDrawer.vue'

const page   = useComparisonPage()
const drawer = useManualPickerDrawer()

onMounted(() => { void page.loadStores() })

function onOpenPicker(refProduct: ComparisonProduct): void {
  drawer.openDrawer(refProduct, Array.from(page.selectedTargetCategoryIds.value))
}

async function onDrawerPick(tgtProductId: number): Promise<void> {
  const refProduct = drawer.drawerRefProduct.value
  if (!refProduct?.id) return
  drawer.closeDrawer()
  await page.makeDecision(refProduct.id, tgtProductId, 'confirmed')
}
</script>

