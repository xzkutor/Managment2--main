<template>
  <div class="sc-section">

    <!-- ── Section header (aligned with service console) ─────── -->
    <div class="sc-section-header" style="margin-bottom: 20px;">
      <h2 class="sc-section-title">Планувальник задач</h2>
      <div class="sc-section-actions">
        <button
          class="btn-ghost btn-sm"
          type="button"
          :disabled="model.loadingJobs.value"
          title="Оновити список задач"
          @click="handleRefresh"
        >↺ Оновити</button>
        <button
          class="btn btn-sm"
          type="button"
          @click="openCreateJob"
        >+ Нова задача</button>
      </div>
    </div>

    <!-- ── Two-column layout: jobs list + detail ──────────────── -->
    <div class="scheduler-layout">

      <!-- Left: jobs list panel -->
      <div class="scheduler-jobs-panel panel">
        <SchedulerJobsList
          :jobs="model.jobs.value"
          :selected-job-id="model.selectedJobId.value"
          :loading="model.loadingJobs.value"
          :error="model.errorJobs.value"
          @select="model.selectJob"
        />
      </div>

      <!-- Right: detail panel -->
      <div class="scheduler-detail-panel">

        <!-- No selection -->
        <div v-if="!model.selectedJobId.value && !model.loadingJobs.value" class="empty-state">
          <div class="empty-state-icon">⏱</div>
          <p class="empty-state-title">Оберіть задачу</p>
          <p class="empty-state-body">Оберіть задачу зі списку ліворуч, щоб переглянути деталі.</p>
        </div>

        <!-- Loading detail -->
        <div v-else-if="model.loadingDetail.value" class="empty-state">
          <div class="empty-state-icon" aria-live="polite">⏳</div>
          <p class="empty-state-title">Завантаження…</p>
        </div>

        <!-- Error loading detail -->
        <div v-else-if="model.errorDetail.value" class="status-block error" style="margin: 0;">
          ⚠ {{ model.errorDetail.value.message }}
        </div>

        <!-- Job detail -->
        <template v-else-if="model.selectedJob.value">

          <!-- Header with action buttons -->
          <div class="panel-header" style="margin-bottom: 16px; flex-wrap: wrap; gap: 8px;">
            <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
              <span class="sch-job-title">{{ model.selectedJob.value.source_key }}</span>
              <span
                :class="['sch-badge', model.selectedJob.value.enabled ? 'sch-badge-enabled' : 'sch-badge-disabled']"
              >
                {{ model.selectedJob.value.enabled ? 'enabled' : 'disabled' }}
              </span>
            </div>
            <div class="panel-actions" style="flex-shrink: 0;">
              <button
                class="btn-ghost btn-sm"
                type="button"
                :disabled="actions.togglePending.value"
                :title="model.selectedJob.value.enabled ? 'Вимкнути задачу' : 'Увімкнути задачу'"
                @click="handleToggle"
              >
                {{ model.selectedJob.value.enabled ? '⏸ Вимкнути' : '▶ Увімкнути' }}
              </button>
              <button
                class="btn btn-sm"
                type="button"
                :disabled="actions.runNowPending.value"
                title="Запустити зараз"
                @click="handleRunNow"
              >
                {{ actions.runNowPending.value ? '⏳ Запуск…' : '▶ Run now' }}
              </button>
              <button
                class="btn-ghost btn-sm"
                type="button"
                @click="openEditJob"
              >✎ Редагувати</button>
              <button
                class="btn-ghost btn-sm"
                type="button"
                @click="openEditSchedule"
              >🗓 Розклад</button>
              <button
                class="btn-ghost btn-sm"
                type="button"
                :disabled="actions.runsRefreshPending.value"
                title="Оновити запуски"
                @click="handleRunsRefresh"
              >↺ Runs</button>
            </div>
          </div>

          <!-- Run-now status feedback -->
          <SchedulerRunNowStatus
            :status="actions.runNowStatus.value"
            @clear="actions.clearRunNowStatus"
          />

          <!-- Job fields -->
          <SchedulerJobDetail :job="model.selectedJob.value" />

          <!-- Schedule card -->
          <SchedulerScheduleCard :schedules="model.selectedSchedules.value" />

          <!-- Recent runs -->
          <SchedulerRunsTable :runs="model.selectedRuns.value" />

        </template>
      </div>
    </div>

    <!-- ── Job create/edit dialog ─────────────────────────── -->
    <SchedulerJobFormDialog
      :open="jobDialogOpen"
      :mode="jobDialogMode"
      :job="jobDialogMode === 'edit' ? model.selectedJob.value : null"
      :pending="actions.jobFormPending.value"
      :error-msg="actions.jobFormError.value"
      @close="jobDialogOpen = false"
      @submit="handleJobSubmit"
    />

    <!-- ── Schedule create/edit dialog ───────────────────── -->
    <SchedulerScheduleFormDialog
      :open="schedDialogOpen"
      :schedule="primarySchedule"
      :pending="actions.schedulePending.value"
      :error-msg="actions.scheduleError.value"
      @close="schedDialogOpen = false"
      @submit="handleScheduleSubmit"
    />

  </div>
</template>

<script setup lang="ts">
/**
 * SchedulerApp.vue — service console scheduler section (Commit 6).
 *
 * Visual alignment: wrapped in sc-section with sc-section-header.
 * Functional behaviour unchanged: create/edit job, toggle, run-now,
 * edit schedule, refresh runs.
 */
import { ref, computed, onMounted } from 'vue'
import { useSchedulerReadModel } from './composables/useSchedulerReadModel'
import { useSchedulerActions } from './composables/useSchedulerActions'
import type { JobFormState, ScheduleFormState } from './composables/formModels'
import SchedulerJobsList from './components/SchedulerJobsList.vue'
import SchedulerJobDetail from './components/SchedulerJobDetail.vue'
import SchedulerScheduleCard from './components/SchedulerScheduleCard.vue'
import SchedulerRunsTable from './components/SchedulerRunsTable.vue'
import SchedulerRunNowStatus from './components/SchedulerRunNowStatus.vue'
import SchedulerJobFormDialog from './components/SchedulerJobFormDialog.vue'
import SchedulerScheduleFormDialog from './components/SchedulerScheduleFormDialog.vue'

const model = useSchedulerReadModel()
const actions = useSchedulerActions(model)

// ── Dialog state ──────────────────────────────────────────────────────────

const jobDialogOpen = ref(false)
const jobDialogMode = ref<'create' | 'edit'>('create')
const schedDialogOpen = ref(false)

// Primary schedule (first enabled, or first) — passed to schedule dialog as seed
const primarySchedule = computed(() => {
  const schedules = model.selectedSchedules.value
  if (!schedules.length) return null
  return schedules.find((s) => s.enabled) ?? schedules[0]
})

// ── Action handlers ───────────────────────────────────────────────────────

function openCreateJob() {
  jobDialogMode.value = 'create'
  jobDialogOpen.value = true
}

function openEditJob() {
  if (!model.selectedJob.value) return
  jobDialogMode.value = 'edit'
  jobDialogOpen.value = true
}

function openEditSchedule() {
  schedDialogOpen.value = true
}

async function handleRefresh() {
  await model.refresh()
}

async function handleToggle() {
  if (!model.selectedJob.value) return
  await actions.toggleEnabled(model.selectedJob.value)
}

async function handleRunNow() {
  if (!model.selectedJob.value) return
  await actions.runNow(model.selectedJob.value.id)
}

async function handleRunsRefresh() {
  if (!model.selectedJob.value) return
  await actions.refreshRuns(model.selectedJob.value.id)
}

async function handleJobSubmit(form: JobFormState) {
  if (jobDialogMode.value === 'create') {
    const job = await actions.createJob(form)
    if (job) jobDialogOpen.value = false
  } else {
    if (!model.selectedJob.value) return
    const job = await actions.updateJob(model.selectedJob.value.id, form)
    if (job) jobDialogOpen.value = false
  }
}

async function handleScheduleSubmit(form: ScheduleFormState) {
  if (!model.selectedJob.value) return
  const result = await actions.upsertSchedule(model.selectedJob.value.id, form)
  if (result) schedDialogOpen.value = false
}

// ── Lifecycle ─────────────────────────────────────────────────────────────

defineExpose({ activate: model.activate })

onMounted(() => {
  model.activate()
})
</script>

