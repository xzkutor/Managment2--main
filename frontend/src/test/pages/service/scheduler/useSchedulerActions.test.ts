import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref } from 'vue'
import { useSchedulerActions } from '@/pages/service/scheduler/composables/useSchedulerActions'
import type { SchedulerReadModel } from '@/pages/service/scheduler/composables/useSchedulerReadModel'

// ---------------------------------------------------------------------------
// Mock API client
// ---------------------------------------------------------------------------

vi.mock('@/api/client', () => ({
  createSchedulerJob: vi.fn(),
  updateSchedulerJob: vi.fn(),
  enqueueJobRun: vi.fn(),
  upsertJobSchedule: vi.fn(),
  fetchSchedulerRuns: vi.fn(),
  fetchSchedulerJobDetail: vi.fn(),
  fetchSchedulerJobs: vi.fn(),
}))

import * as client from '@/api/client'
import { ApiError } from '@/api/errors'

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const makeJob = (overrides = {}) => ({
  id: 1,
  source_key: 'hockeyworld',
  runner_type: 'store_category_sync' as const,
  params_json: { store_id: 3 },
  enabled: true,
  priority: 0,
  allow_overlap: false,
  timeout_sec: null,
  max_retries: 0,
  retry_backoff_sec: 60,
  concurrency_key: null,
  next_run_at: null,
  last_run_at: null,
  created_at: null,
  updated_at: null,
  ...overrides,
})

const makeSchedule = (overrides = {}) => ({
  id: 10,
  job_id: 1,
  schedule_type: 'interval' as const,
  cron_expr: null,
  interval_sec: 3600,
  timezone: 'UTC',
  jitter_sec: 0,
  misfire_policy: 'skip' as const,
  enabled: true,
  created_at: null,
  updated_at: null,
  ...overrides,
})

const makeRun = (id = 99) => ({
  id,
  store_id: null,
  store: null,
  job_id: 1,
  run_type: 'store_category_sync',
  trigger_type: 'manual',
  status: 'success',
  attempt: 1,
  queued_at: null,
  started_at: '2026-01-01T12:00:00Z',
  finished_at: '2026-01-01T12:00:30Z',
  worker_id: null,
  categories_processed: 0,
  products_processed: 0,
  products_created: 0,
  products_updated: 0,
  price_changes_detected: 0,
  error_message: null,
  metadata_json: null,
  checkpoint_out_json: null,
  retryable: false,
  retry_of_run_id: null,
  retry_processed: false,
  retry_exhausted: false,
})

/** Build a minimal SchedulerReadModel double */
function makeModel(overrides: Partial<SchedulerReadModel> = {}): SchedulerReadModel {
  return {
    jobs: ref([makeJob()]),
    selectedJobId: ref(1),
    selectedJob: ref(makeJob()),
    selectedSchedules: ref([makeSchedule()]),
    selectedRuns: ref([]),
    loadingJobs: ref(false),
    loadingDetail: ref(false),
    errorJobs: ref(null),
    errorDetail: ref(null),
    activate: vi.fn(),
    selectJob: vi.fn(),
    refresh: vi.fn(),
    ...overrides,
  }
}

beforeEach(() => {
  vi.clearAllMocks()
})

// ---------------------------------------------------------------------------
// runNow
// ---------------------------------------------------------------------------

describe('useSchedulerActions — runNow', () => {
  it('sets success status and refreshes runs on success', async () => {
    const newRun = makeRun(100)
    vi.mocked(client.enqueueJobRun).mockResolvedValueOnce(newRun)
    vi.mocked(client.fetchSchedulerRuns).mockResolvedValueOnce([newRun])

    const model = makeModel()
    const actions = useSchedulerActions(model)

    await actions.runNow(1)

    expect(actions.runNowStatus.value.kind).toBe('success')
    expect(client.enqueueJobRun).toHaveBeenCalledWith(1)
    expect(client.fetchSchedulerRuns).toHaveBeenCalledWith(1, { limit: 20 })
    expect(model.selectedRuns.value).toEqual([newRun])
  })

  it('sets conflict status when ApiError.isConflict is true', async () => {
    const conflictErr = new ApiError(409, 'Conflict', 'Job already running')
    vi.mocked(client.enqueueJobRun).mockRejectedValueOnce(conflictErr)
    vi.mocked(client.fetchSchedulerRuns).mockResolvedValue([])

    const model = makeModel()
    const actions = useSchedulerActions(model)

    await actions.runNow(1)

    expect(actions.runNowStatus.value.kind).toBe('conflict')
    expect(actions.runNowStatus.value.message).toContain('allow_overlap')
  })

  it('sets error status for generic errors', async () => {
    vi.mocked(client.enqueueJobRun).mockRejectedValueOnce(new Error('network timeout'))
    vi.mocked(client.fetchSchedulerRuns).mockResolvedValue([])

    const model = makeModel()
    const actions = useSchedulerActions(model)

    await actions.runNow(1)

    expect(actions.runNowStatus.value.kind).toBe('error')
    expect(actions.runNowStatus.value.message).toContain('network timeout')
  })

  it('clearRunNowStatus resets to idle', async () => {
    vi.mocked(client.enqueueJobRun).mockRejectedValueOnce(new Error('err'))
    vi.mocked(client.fetchSchedulerRuns).mockResolvedValue([])

    const model = makeModel()
    const actions = useSchedulerActions(model)
    await actions.runNow(1)
    expect(actions.runNowStatus.value.kind).not.toBe('idle')

    actions.clearRunNowStatus()
    expect(actions.runNowStatus.value.kind).toBe('idle')
  })

  it('is idempotent: ignores second call while first is pending', async () => {
    let resolveRun!: (v: ReturnType<typeof makeRun>) => void
    const pending = new Promise<ReturnType<typeof makeRun>>((res) => { resolveRun = res })
    vi.mocked(client.enqueueJobRun).mockReturnValueOnce(pending)
    vi.mocked(client.fetchSchedulerRuns).mockResolvedValue([])

    const model = makeModel()
    const actions = useSchedulerActions(model)

    const first = actions.runNow(1)
    actions.runNow(1) // should be ignored
    resolveRun(makeRun())
    await first

    expect(client.enqueueJobRun).toHaveBeenCalledTimes(1)
  })
})

// ---------------------------------------------------------------------------
// toggleEnabled
// ---------------------------------------------------------------------------

describe('useSchedulerActions — toggleEnabled', () => {
  it('patches enabled flag in list and selectedJob', async () => {
    const updated = makeJob({ enabled: false })
    vi.mocked(client.updateSchedulerJob).mockResolvedValueOnce(updated)

    const model = makeModel()
    const actions = useSchedulerActions(model)

    await actions.toggleEnabled(makeJob({ enabled: true }))

    expect(client.updateSchedulerJob).toHaveBeenCalledWith(1, { enabled: false })
    expect(model.jobs.value[0].enabled).toBe(false)
    expect(model.selectedJob.value?.enabled).toBe(false)
  })

  it('silently ignores errors (state stays consistent)', async () => {
    vi.mocked(client.updateSchedulerJob).mockRejectedValueOnce(new Error('server error'))

    const model = makeModel()
    const originalEnabled = model.jobs.value[0].enabled
    const actions = useSchedulerActions(model)

    await actions.toggleEnabled(makeJob({ enabled: true }))

    // State must not have changed on error
    expect(model.jobs.value[0].enabled).toBe(originalEnabled)
  })
})

// ---------------------------------------------------------------------------
// createJob
// ---------------------------------------------------------------------------

describe('useSchedulerActions — createJob', () => {
  it('appends new job to list and selects it without full jobs reload', async () => {
    const newJob = makeJob({ id: 7, source_key: 'newshop' })
    vi.mocked(client.createSchedulerJob).mockResolvedValueOnce(newJob)
    vi.mocked(client.fetchSchedulerJobDetail).mockResolvedValueOnce({
      job: newJob,
      schedules: [],
    })

    const model = makeModel()
    const initialJobCount = model.jobs.value.length
    const actions = useSchedulerActions(model)

    const form = {
      source_key: 'newshop',
      runner_type: 'all_stores_category_sync' as const,
      store_id: '',
      category_id: '',
      enabled: true,
      allow_overlap: false,
      priority: 0,
      max_retries: 0,
      retry_backoff_sec: 60,
      timeout_sec: '',
      concurrency_key: '',
      extra_params_json: '',
    }

    const result = await actions.createJob(form)

    expect(result).not.toBeNull()
    expect(model.selectedJobId.value).toBe(7)
    // New job appended — full fetchSchedulerJobs NOT called
    expect(client.fetchSchedulerJobs).not.toHaveBeenCalled()
    expect(model.jobs.value).toHaveLength(initialJobCount + 1)
    expect(model.jobs.value[model.jobs.value.length - 1].source_key).toBe('newshop')
    // Runs cleared for new job (no history yet)
    expect(model.selectedRuns.value).toHaveLength(0)
  })

  it('returns null and sets error when source_key is missing', async () => {
    const model = makeModel()
    const actions = useSchedulerActions(model)

    const form = {
      source_key: '  ',
      runner_type: 'all_stores_category_sync' as const,
      store_id: '',
      category_id: '',
      enabled: true,
      allow_overlap: false,
      priority: 0,
      max_retries: 0,
      retry_backoff_sec: 60,
      timeout_sec: '',
      concurrency_key: '',
      extra_params_json: '',
    }

    const result = await actions.createJob(form)

    expect(result).toBeNull()
    expect(actions.jobFormError.value).toBeTruthy()
  })

  it('returns null and sets error when extra_params_json is invalid JSON', async () => {
    const model = makeModel()
    const actions = useSchedulerActions(model)

    const form = {
      source_key: 'shop',
      runner_type: 'all_stores_category_sync' as const,
      store_id: '',
      category_id: '',
      enabled: true,
      allow_overlap: false,
      priority: 0,
      max_retries: 0,
      retry_backoff_sec: 60,
      timeout_sec: '',
      concurrency_key: '',
      extra_params_json: '{bad json}',
    }

    const result = await actions.createJob(form)

    expect(result).toBeNull()
    expect(actions.jobFormError.value).toContain('JSON')
  })
})

// ---------------------------------------------------------------------------
// updateJob
// ---------------------------------------------------------------------------

describe('useSchedulerActions — updateJob', () => {
  it('patches jobs list badge and selectedJob in-place without fetching runs', async () => {
    const updatedJob = makeJob({ source_key: 'updated' })
    vi.mocked(client.updateSchedulerJob).mockResolvedValueOnce(updatedJob)

    const model = makeModel()
    const originalRuns = [makeRun(50)]
    model.selectedRuns.value = originalRuns
    const actions = useSchedulerActions(model)

    const form = {
      source_key: 'updated',
      runner_type: 'store_category_sync' as const,
      store_id: '3',
      category_id: '',
      enabled: true,
      allow_overlap: false,
      priority: 0,
      max_retries: 0,
      retry_backoff_sec: 60,
      timeout_sec: '',
      concurrency_key: '',
      extra_params_json: '',
    }

    const result = await actions.updateJob(1, form)

    expect(result).not.toBeNull()
    expect(model.jobs.value[0].source_key).toBe('updated')
    expect(model.selectedJob.value?.source_key).toBe('updated')
    // Runs must NOT be reloaded on a simple job update
    expect(client.fetchSchedulerRuns).not.toHaveBeenCalled()
    expect(model.selectedRuns.value).toEqual(originalRuns)
    // Full detail fetch also not needed
    expect(client.fetchSchedulerJobDetail).not.toHaveBeenCalled()
  })
})

// ---------------------------------------------------------------------------
// upsertSchedule
// ---------------------------------------------------------------------------

describe('useSchedulerActions — upsertSchedule', () => {
  it('returns null and sets error when interval_sec missing for interval schedule', async () => {
    const model = makeModel()
    const actions = useSchedulerActions(model)

    const result = await actions.upsertSchedule(1, {
      schedule_type: 'interval',
      interval_sec: '',
      cron_expr: '',
      timezone: 'UTC',
      jitter_sec: 0,
      misfire_policy: 'skip',
      enabled: true,
    })

    expect(result).toBeNull()
    expect(actions.scheduleError.value).toBeTruthy()
  })

  it('returns null and sets error when cron_expr empty for cron schedule', async () => {
    const model = makeModel()
    const actions = useSchedulerActions(model)

    const result = await actions.upsertSchedule(1, {
      schedule_type: 'cron',
      interval_sec: '',
      cron_expr: '  ',
      timezone: 'UTC',
      jitter_sec: 0,
      misfire_policy: 'skip',
      enabled: true,
    })

    expect(result).toBeNull()
    expect(actions.scheduleError.value).toBeTruthy()
  })

  it('calls upsertJobSchedule and patches selectedSchedules locally without full detail reload', async () => {
    const schedule = makeSchedule()
    vi.mocked(client.upsertJobSchedule).mockResolvedValueOnce(schedule)

    const model = makeModel({ selectedSchedules: ref([makeSchedule()]) })
    const actions = useSchedulerActions(model)

    const result = await actions.upsertSchedule(1, {
      schedule_type: 'interval',
      interval_sec: '3600',
      cron_expr: '',
      timezone: 'UTC',
      jitter_sec: 0,
      misfire_policy: 'skip',
      enabled: true,
    })

    expect(result).not.toBeNull()
    expect(client.upsertJobSchedule).toHaveBeenCalledWith(1, expect.objectContaining({
      schedule_type: 'interval',
      interval_sec: 3600,
    }))
    // Full detail reload must NOT happen
    expect(client.fetchSchedulerJobDetail).not.toHaveBeenCalled()
    // Schedule patched in-place
    expect(model.selectedSchedules.value).toHaveLength(1)
    expect(model.selectedSchedules.value[0]).toEqual(schedule)
  })
})

// ---------------------------------------------------------------------------
// refreshRuns
// ---------------------------------------------------------------------------

describe('useSchedulerActions — refreshRuns', () => {
  it('updates selectedRuns without touching selectedJob', async () => {
    const runs = [makeRun(1), makeRun(2)]
    vi.mocked(client.fetchSchedulerRuns).mockResolvedValueOnce(runs)

    const model = makeModel()
    const originalJob = model.selectedJob.value
    const actions = useSchedulerActions(model)

    await actions.refreshRuns(1)

    expect(model.selectedRuns.value).toEqual(runs)
    expect(model.selectedJob.value).toBe(originalJob) // reference unchanged
  })

  it('silently swallows errors (runs table stays stale)', async () => {
    vi.mocked(client.fetchSchedulerRuns).mockRejectedValueOnce(new Error('network'))

    const model = makeModel({ selectedRuns: ref([makeRun()]) })
    const actions = useSchedulerActions(model)

    await actions.refreshRuns(1)

    // No throw; runs unchanged
    expect(model.selectedRuns.value).toHaveLength(1)
  })
})

