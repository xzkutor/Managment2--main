<template>
  <!--
    MatchesPage.vue — /matches workspace layout.
    Three zones: left filter rail · top search+KPI header · main results panel.
    All state is owned by useMatchesPage(); no local component state here.
  -->
  <div class="mw-workspace">

    <!-- ── Left filter rail ──────────────────────────────────── -->
    <aside class="mw-rail panel">
      <MatchesFilters
        :reference-stores="state.referenceStores.value"
        :target-stores="state.targetStores.value"
        :reference-categories="state.referenceCategories.value"
        :target-categories="state.targetCategories.value"
        :filters="state.filters"
        :loading="state.isLoadingRows.value"
        :active-filters-count="state.activeFiltersCount.value"
        @update:reference-store="state.setReferenceStore"
        @update:target-store="state.setTargetStore"
        @update:reference-category-id="id => { state.filters.referenceCategoryId = id }"
        @update:target-category-id="id => { state.filters.targetCategoryId = id }"
        @update:status="s => { state.filters.status = s }"
        @load="state.loadMappings"
      />
    </aside>

    <!-- ── Right content area ────────────────────────────────── -->
    <div class="mw-content">

      <!-- Top workspace header: search bar + KPI summary -->
      <div class="mw-header panel">
        <div class="mw-search-bar">
          <label for="mwSearchInput" class="sr-only">Пошук за назвою</label>
          <input
            id="mwSearchInput"
            type="text"
            class="mw-search-input"
            :value="state.filters.search"
            placeholder="Пошук за назвою (напр. Bauer Vapor…)"
            @input="e => { state.filters.search = (e.target as HTMLInputElement).value }"
            @keydown.enter="state.loadMappings()"
          />
          <button
            class="btn"
            type="button"
            :disabled="state.isLoadingRows.value"
            @click="state.loadMappings()"
          >
            {{ state.isLoadingRows.value ? 'Завантаження…' : 'Показати' }}
          </button>
        </div>
        <MatchesSummary
          v-if="state.hasLoaded.value"
          :total="state.kpiTotal.value"
          :confirmed="state.kpiConfirmed.value"
          :rejected="state.kpiRejected.value"
        />
      </div>

      <!-- Results panel — loading/error/empty + table -->
      <div class="mw-results panel">

        <!-- ── Status block ────────────────────────── -->
        <div
          v-if="state.isBootstrapping.value || state.isLoadingRows.value"
          class="status-block info mw-results-status"
          role="status"
          aria-live="polite"
        >
          <span class="spinner" aria-hidden="true"></span> Завантаження…
        </div>
        <div
          v-else-if="state.errorMessage.value"
          class="status-block error mw-results-status"
          role="alert"
        >
          {{ state.errorMessage.value }}
        </div>
        <div
          v-else-if="state.infoMessage.value && !state.hasRows.value"
          class="status-block info mw-results-status"
          role="status"
          aria-live="polite"
        >
          {{ state.infoMessage.value }}
        </div>

        <!-- ── Results table ────────────────────────── -->
        <MatchesTable
          v-if="state.hasRows.value"
          :rows="state.rows.value"
          :deleting-id="state.isDeletingId.value"
          @delete="state.deleteRow"
        />

      </div>
    </div>

  </div>
</template>

<script setup lang="ts">
/**
 * MatchesPage.vue — root Vue component for the /matches workspace page.
 *
 * Layout: three-zone workspace (left filter rail · top search+KPI header ·
 * main results panel). All page state is owned by useMatchesPage().
 *
 * Flask owns: page shell (sidebar/nav), CSS includes, <title>.
 */
import { useMatchesPage } from './composables/useMatchesPage'
import MatchesFilters from './components/MatchesFilters.vue'
import MatchesSummary from './components/MatchesSummary.vue'
import MatchesTable from './components/MatchesTable.vue'

const state = useMatchesPage()
</script>
