/**
 * frontend/src/api/client.ts — Page-agnostic API call helpers.
 *
 * All functions wrap requestJson() + the relevant adapter.
 * They return stable frontend DTOs, not raw server shapes.
 *
 * Do NOT add page-specific logic here.
 * Do NOT redesign backend API contracts from this layer.
 */
import { requestJson } from './http'
import { adaptStoreList, adaptCategoryList } from './adapters/stores'
import {
  adaptJobList,
  adaptJob,
  adaptScheduleList,
  adaptSchedule,
  adaptRunList,
  adaptRun,
} from './adapters/scheduler'
import { adaptMappingList, adaptAutoLinkResult } from './adapters/mappings'
import type { StoreSummary, CategorySummary } from '@/types/store'
import type { SchedulerJobSummary, SchedulerJobDetail, SchedulerSchedule } from '@/types/scheduler'
import type { ScrapeRunSummary } from '@/types/history'
import type { MappingRow, AutoLinkResult } from '@/types/mappings'

// ---------------------------------------------------------------------------
// Categories (sync actions)
// ---------------------------------------------------------------------------

/**
 * POST /api/admin/stores/sync — sync store list from registered adapters.
 * Admin-only; the backend returns 404 if ENABLE_ADMIN_SYNC is off.
 */
export async function syncAdminStores(signal?: AbortSignal): Promise<StoreSummary[]> {
  const data = await requestJson<{ stores: unknown[] }>(
    '/api/admin/stores/sync',
    { method: 'POST', signal },
  )
  return adaptStoreList(data.stores as Parameters<typeof adaptStoreList>[0])
}

/**
 * POST /api/stores/:storeId/categories/sync
 * Triggers category scrape and returns the updated category list.
 */
export async function syncStoreCategories(
  storeId: number,
  signal?: AbortSignal,
): Promise<CategorySummary[]> {
  const data = await requestJson<{ categories: unknown[] }>(
    `/api/stores/${storeId}/categories/sync`,
    { method: 'POST', signal },
  )
  return adaptCategoryList(data.categories as Parameters<typeof adaptCategoryList>[0])
}

/** Summary returned by POST /api/categories/:id/products/sync */
export interface ProductSyncSummary {
  products_processed: number | null
  products_created: number | null
  products_updated: number | null
  price_changes_detected: number | null
}

/**
 * POST /api/categories/:categoryId/products/sync
 * Triggers product scrape for one category and returns a processing summary.
 */
export async function syncCategoryProducts(
  categoryId: number,
  signal?: AbortSignal,
): Promise<ProductSyncSummary> {
  const data = await requestJson<{ summary: unknown }>(
    `/api/categories/${categoryId}/products/sync`,
    { method: 'POST', signal },
  )
  const s = (data.summary ?? {}) as Record<string, unknown>
  return {
    products_processed: (s.products_processed ?? s.processed ?? null) as number | null,
    products_created: (s.products_created ?? s.created ?? null) as number | null,
    products_updated: (s.products_updated ?? s.updated ?? null) as number | null,
    price_changes_detected:
      (s.price_changes_detected ?? s.price_changes ?? null) as number | null,
  }
}

/**
 * GET /api/scrape-status — returns recent runs (running-status default).
 */
export async function fetchScrapeStatus(signal?: AbortSignal): Promise<ScrapeRunSummary[]> {
  const data = await requestJson<{ runs: unknown[] }>('/api/scrape-status', { signal })
  return adaptRunList(data.runs as Parameters<typeof adaptRunList>[0])
}

// ---------------------------------------------------------------------------
// History (scrape runs)
// ---------------------------------------------------------------------------

export interface ScrapeRunsFilter {
  store_id?: number | null
  run_type?: string | null
  status?: string | null
  trigger_type?: string | null
  limit?: number
  offset?: number
}

export async function fetchScrapeRuns(
  params?: ScrapeRunsFilter,
  signal?: AbortSignal,
): Promise<ScrapeRunSummary[]> {
  const qs = params
    ? '?' +
      new URLSearchParams(
        Object.fromEntries(
          Object.entries(params)
            .filter(([, v]) => v !== undefined && v !== null && v !== '')
            .map(([k, v]) => [k, String(v)]),
        ),
      ).toString()
    : ''
  const data = await requestJson<{ runs: unknown[] }>(`/api/scrape-runs${qs}`, { signal })
  return adaptRunList(data.runs as Parameters<typeof adaptRunList>[0])
}

export async function fetchScrapeRunDetail(
  runId: number,
  signal?: AbortSignal,
): Promise<ScrapeRunSummary> {
  const data = await requestJson<{ run: unknown }>(`/api/scrape-runs/${runId}`, { signal })
  return adaptRun(data.run as Parameters<typeof adaptRun>[0])
}

// ---------------------------------------------------------------------------
// Stores
// ---------------------------------------------------------------------------

export async function fetchStores(signal?: AbortSignal): Promise<StoreSummary[]> {
  const data = await requestJson<{ stores: unknown[] }>('/api/stores', { signal })
  return adaptStoreList(data.stores as Parameters<typeof adaptStoreList>[0])
}

export async function fetchCategoriesForStore(
  storeId: number,
  signal?: AbortSignal,
): Promise<CategorySummary[]> {
  const data = await requestJson<{ categories: unknown[] }>(
    `/api/stores/${storeId}/categories`,
    { signal },
  )
  return adaptCategoryList(data.categories as Parameters<typeof adaptCategoryList>[0])
}

// ---------------------------------------------------------------------------
// Scheduler jobs
// ---------------------------------------------------------------------------

export async function fetchSchedulerJobs(
  params?: { enabled?: boolean; runner_type?: string; limit?: number; offset?: number },
  signal?: AbortSignal,
): Promise<SchedulerJobSummary[]> {
  const qs = params ? '?' + new URLSearchParams(
    Object.fromEntries(
      Object.entries(params)
        .filter(([, v]) => v !== undefined)
        .map(([k, v]) => [k, String(v)]),
    ),
  ).toString() : ''
  const data = await requestJson<{ jobs: unknown[] }>(
    `/api/admin/scrape/jobs${qs}`,
    { signal },
  )
  return adaptJobList(data.jobs as Parameters<typeof adaptJobList>[0])
}

export async function fetchSchedulerJobDetail(
  jobId: number,
  signal?: AbortSignal,
): Promise<{ job: SchedulerJobDetail; schedules: SchedulerSchedule[] }> {
  const data = await requestJson<{ job: unknown; schedules: unknown[] }>(
    `/api/admin/scrape/jobs/${jobId}`,
    { signal },
  )
  return {
    job: adaptJob(data.job as Parameters<typeof adaptJob>[0]),
    schedules: adaptScheduleList(data.schedules as Parameters<typeof adaptScheduleList>[0]),
  }
}

export async function updateSchedulerJob(
  jobId: number,
  patch: Partial<Pick<
    SchedulerJobSummary,
    'enabled' | 'priority' | 'allow_overlap' | 'timeout_sec' |
    'max_retries' | 'retry_backoff_sec' | 'concurrency_key' | 'params_json'
  >>,
  signal?: AbortSignal,
): Promise<SchedulerJobDetail> {
  const data = await requestJson<{ job: unknown }>(
    `/api/admin/scrape/jobs/${jobId}`,
    { method: 'PATCH', body: patch, signal },
  )
  return adaptJob(data.job as Parameters<typeof adaptJob>[0])
}

export async function enqueueJobRun(
  jobId: number,
  signal?: AbortSignal,
): Promise<ScrapeRunSummary> {
  const data = await requestJson<{ run: unknown }>(
    `/api/admin/scrape/jobs/${jobId}/run`,
    { method: 'POST', signal },
  )
  return adaptRun(data.run as Parameters<typeof adaptRun>[0])
}

// ---------------------------------------------------------------------------
// Scheduler runs
// ---------------------------------------------------------------------------

export async function fetchSchedulerRuns(
  jobId: number,
  params?: { status?: string; limit?: number; offset?: number },
  signal?: AbortSignal,
): Promise<ScrapeRunSummary[]> {
  const qs = params ? '?' + new URLSearchParams(
    Object.fromEntries(
      Object.entries(params)
        .filter(([, v]) => v !== undefined)
        .map(([k, v]) => [k, String(v)]),
    ),
  ).toString() : ''
  const data = await requestJson<{ runs: unknown[] }>(
    `/api/admin/scrape/jobs/${jobId}/runs${qs}`,
    { signal },
  )
  return adaptRunList(data.runs as Parameters<typeof adaptRunList>[0])
}

export async function createSchedulerJob(
  payload: {
    source_key: string
    runner_type: string
    params_json?: Record<string, unknown> | null
    enabled?: boolean
    priority?: number
    allow_overlap?: boolean
    timeout_sec?: number | null
    max_retries?: number
    retry_backoff_sec?: number
    concurrency_key?: string | null
  },
  signal?: AbortSignal,
): Promise<SchedulerJobDetail> {
  const data = await requestJson<{ job: unknown }>(
    '/api/admin/scrape/jobs',
    { method: 'POST', body: payload, signal },
  )
  return adaptJob(data.job as Parameters<typeof adaptJob>[0])
}

// ---------------------------------------------------------------------------
// Scheduler schedule
// ---------------------------------------------------------------------------

export async function upsertJobSchedule(
  jobId: number,
  payload: Partial<Omit<SchedulerSchedule, 'id' | 'job_id' | 'created_at' | 'updated_at'>>,
  signal?: AbortSignal,
): Promise<SchedulerSchedule> {
  const data = await requestJson<{ schedule: unknown }>(
    `/api/admin/scrape/jobs/${jobId}/schedule`,
    { method: 'PUT', body: payload, signal },
  )
  return adaptSchedule(data.schedule as Parameters<typeof adaptSchedule>[0])
}

// ---------------------------------------------------------------------------
// Category mappings
// ---------------------------------------------------------------------------

export async function fetchCategoryMappings(
  referenceStoreId: number,
  targetStoreId: number,
  signal?: AbortSignal,
): Promise<MappingRow[]> {
  const data = await requestJson<{ mappings: unknown[] }>(
    `/api/category-mappings?reference_store_id=${referenceStoreId}&target_store_id=${targetStoreId}`,
    { signal },
  )
  return adaptMappingList(data.mappings as Parameters<typeof adaptMappingList>[0])
}

export async function createCategoryMapping(
  payload: {
    reference_category_id: number
    target_category_id: number
    match_type?: string | null
    confidence?: number | null
  },
  signal?: AbortSignal,
): Promise<MappingRow[]> {
  const data = await requestJson<{ mappings: unknown[] }>(
    '/api/category-mappings',
    { method: 'POST', body: payload, signal },
  )
  return adaptMappingList(data.mappings as Parameters<typeof adaptMappingList>[0])
}

export async function updateCategoryMapping(
  mappingId: number,
  payload: { match_type?: string | null; confidence?: number | null },
  referenceStoreId: number,
  targetStoreId: number,
  signal?: AbortSignal,
): Promise<MappingRow[]> {
  const data = await requestJson<{ mappings: unknown[] }>(
    `/api/category-mappings/${mappingId}?reference_store_id=${referenceStoreId}&target_store_id=${targetStoreId}`,
    { method: 'PUT', body: payload, signal },
  )
  return adaptMappingList(data.mappings as Parameters<typeof adaptMappingList>[0])
}

export async function deleteCategoryMapping(
  mappingId: number,
  referenceStoreId: number,
  targetStoreId: number,
  signal?: AbortSignal,
): Promise<MappingRow[]> {
  const data = await requestJson<{ mappings: unknown[] }>(
    `/api/category-mappings/${mappingId}?reference_store_id=${referenceStoreId}&target_store_id=${targetStoreId}`,
    { method: 'DELETE', signal },
  )
  return adaptMappingList(data.mappings as Parameters<typeof adaptMappingList>[0])
}

export async function autoLinkCategoryMappings(
  referenceStoreId: number,
  targetStoreId: number,
  signal?: AbortSignal,
): Promise<AutoLinkResult> {
  const data = await requestJson<{ summary: unknown; mappings: unknown[] }>(
    '/api/category-mappings/auto-link',
    {
      method: 'POST',
      body: { reference_store_id: referenceStoreId, target_store_id: targetStoreId },
      signal,
    },
  )
  return adaptAutoLinkResult(data as Parameters<typeof adaptAutoLinkResult>[0])
}

