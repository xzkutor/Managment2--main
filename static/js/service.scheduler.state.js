/* service.scheduler.state.js — Scheduler UI state and runner specs */
'use strict';

// ── Runner metadata map ───────────────────────────────────────────────

const RUNNER_SPECS = {
    store_category_sync: {
        label: 'Синхронізація категорій магазину',
        requiresStore: true, requiresCategory: false,
        storeHelp: 'Магазин, категорії якого синхронізувати',
        paramsStoreKey: 'store_id', paramsCatKey: null,
    },
    category_product_sync: {
        label: 'Синхронізація товарів категорії',
        requiresStore: true, requiresCategory: true,
        storeHelp: 'Магазин, що містить категорію',
        categoryHelp: 'Категорія для синхронізації товарів',
        paramsStoreKey: 'store_id', paramsCatKey: 'category_id',
    },
    all_stores_category_sync: {
        label: 'Синхронізація категорій всіх магазинів',
        requiresStore: false, requiresCategory: false,
        paramsStoreKey: null, paramsCatKey: null,
    },
};

function getRunnerUiSpec(rt) {
    return RUNNER_SPECS[rt] || { label: rt, requiresStore: false, requiresCategory: false, paramsStoreKey: null, paramsCatKey: null };
}
function runnerRequiresStore(rt)    { return !!getRunnerUiSpec(rt).requiresStore; }
function runnerRequiresCategory(rt) { return !!getRunnerUiSpec(rt).requiresCategory; }

// ── In-memory scheduler UI state ──────────────────────────────────────

const schState = {
    jobs: [], selectedJobId: null, selectedJob: null,
    selectedSchedule: null, jobModalMode: 'create',
    refData: { stores: null, categories: {}, loadingStores: false, loadingCats: {} },
};

