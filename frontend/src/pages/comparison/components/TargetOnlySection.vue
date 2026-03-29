<template>
  <div class="cw-secondary-section">
    <div class="cw-section">
      <details>
        <summary style="cursor:pointer;list-style:none;display:flex;align-items:center;gap:8px;">
          <h3 class="cw-section-title" style="margin:0;">
            📦 Тільки в цільовому
            <span class="badge badge-tgt">{{ items.length }}</span>
          </h3>
          <span class="muted" style="font-size:0.8rem;">(розгорнути)</span>
        </summary>

        <div style="margin-top:12px;">
          <p v-if="!items.length" class="muted">Немає товарів тільки в цільовому.</p>
          <table v-else>
            <thead>
              <tr><th>Назва</th><th>Ціна</th><th>Категорія</th></tr>
            </thead>
            <tbody>
              <tr
                v-for="item in items"
                :key="item.target_product?.id ?? String(Math.random())"
              >
                <td><ProductLink :product="item.target_product" /></td>
                <td class="muted">{{ formatPrice(item.target_product) }}</td>
                <td><CatBadge :cat="item.target_category" /></td>
              </tr>
            </tbody>
          </table>
        </div>
      </details>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * TargetOnlySection.vue — compact secondary section for target-only items (RFC-016, Commit 7).
 * Demoted to collapsed-by-default to reduce visual weight vs. the main review workflow.
 */
import type { TargetOnlyItem } from '../types'
import ProductLink from './shared/ProductLink.vue'
import CatBadge    from './shared/CatBadge.vue'
import { formatPrice } from './shared/format'

interface Props { items: TargetOnlyItem[] }
withDefaults(defineProps<Props>(), { items: () => [] })
</script>
