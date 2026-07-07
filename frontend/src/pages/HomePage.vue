<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import StatusBadge from '@/components/StatusBadge.vue'
import { useAppStore } from '@/stores/app'

type DomainKey = 'safety' | 'maintenance'
type RightGroupKey = 'business' | 'capability'
type RightTabKey = 'credential' | 'analysis' | 'iot'

const appStore = useAppStore()
const activeDomain = ref<DomainKey>('safety')
const timeDimension = ref('月维度')
const currentDate = ref('2026-05')
const currentCategory = ref('全部')
const activeRightGroup = ref<RightGroupKey>('capability')
const activeRightTab = ref<RightTabKey>('credential')

const domainPanels = {
  safety: {
    title: '本质安全',
    filter: '告警与隐患',
    metrics: [
      { label: '告警总数', value: '27', unit: '条', trend: '较上月 -12%', tone: 'warning' },
      { label: '待处理隐患', value: '2', unit: '项', trend: '较上月 -1', tone: 'danger' },
      { label: '高等级未闭环', value: '1', unit: '条', trend: '需跟进', tone: 'danger' },
      { label: '工单闭环率', value: '88.7', unit: '%', trend: '较上月 +4.2%', tone: 'success' },
    ],
    ranks: [
      { name: '河北新奥能源', value: '7条' },
      { name: '广东新奥能源', value: '5条' },
      { name: '福建新奥能源', value: '3条' },
      { name: '湖南新奥能源', value: '2条' },
    ],
  },
  maintenance: {
    title: '设备运维',
    filter: '设备检维修',
    metrics: [
      { label: '缺陷总数', value: '0', unit: '条', trend: '环比上期 -', tone: 'success' },
      { label: '缺陷处置率', value: '0', unit: '%', trend: '环比上期 -', tone: 'neutral' },
      { label: '缺陷未处置', value: '0', unit: '条', trend: '环比上期 -', tone: 'success' },
      { label: '超期未处置', value: '0', unit: '条', trend: '环比上期 -', tone: 'success' },
    ],
    ranks: [
      { name: '河北新奥能源', value: '0条' },
      { name: '广东新奥能源', value: '0条' },
      { name: '福建新奥能源', value: '0条' },
      { name: '湖南新奥能源', value: '0条' },
    ],
  },
}

const topIndicators = [
  { label: '安全运行', value: '1272', unit: '天' },
  { label: '项目总数', value: '0', unit: '个' },
  { label: '在线企业', value: '5384', unit: '家' },
]

const mapPoints = [
  { label: '华北', value: '58', x: 18, y: 28, tone: 'normal' },
  { label: '华东集群', value: '5384', x: 48, y: 64, tone: 'active' },
  { label: '华南', value: '126', x: 55, y: 72, tone: 'success' },
  { label: '西南', value: '42', x: 37, y: 66, tone: 'warning' },
]

const rightTabsByGroup: Record<RightGroupKey, { key: RightTabKey; label: string }[]> = {
  business: [
    { key: 'credential', label: '经营指标' },
    { key: 'analysis', label: '客户分析' },
    { key: 'iot', label: '履约改善' },
  ],
  capability: [
    { key: 'credential', label: '人员持证' },
    { key: 'analysis', label: '人效分析' },
    { key: 'iot', label: '物联接入' },
  ],
}

const rightTabData: Record<RightGroupKey, Record<RightTabKey, {
  title: string
  value: string
  target: string
  diagnosis: string
  rows: { name: string; value: string; width: number }[]
}>> = {
  business: {
    credential: {
      title: '经营改善完成率',
      value: '86.4%',
      target: '较上月 +3.2%',
      diagnosis: '经营改善事项整体推进稳定，华东与华南区域贡献较高。',
      rows: [
        { name: '河北新奥能源', value: '91.2%', width: 86 },
        { name: '广东新奥能源', value: '88.6%', width: 80 },
        { name: '福建新奥能源', value: '83.4%', width: 70 },
        { name: '湖南新奥能源', value: '79.8%', width: 62 },
      ],
    },
    analysis: {
      title: '客户满意度',
      value: '92.3%',
      target: '较上月 +1.8%',
      diagnosis: '客户满意度整体处于较好水平，需重点关注低评分企业的服务响应。',
      rows: [
        { name: '华东运营区', value: '95.1%', width: 90 },
        { name: '华南运营区', value: '93.4%', width: 84 },
        { name: '华北运营区', value: '89.7%', width: 72 },
        { name: '西南运营区', value: '86.5%', width: 64 },
      ],
    },
    iot: {
      title: '合同履约率',
      value: '95.1%',
      target: '较上月 +2.1%',
      diagnosis: '合同履约率稳定提升，个别低履约区域需跟进交付节点。',
      rows: [
        { name: '能源托管项目', value: '97.2%', width: 92 },
        { name: '设备维保项目', value: '95.8%', width: 86 },
        { name: '安全整改项目', value: '92.4%', width: 76 },
        { name: '数字化接入项目', value: '90.5%', width: 68 },
      ],
    },
  },
  capability: {
    credential: {
      title: '人员持证上岗率',
      value: '30.81%',
      target: '达标值100%',
      diagnosis: '系统监测到人员持证上岗率 30.81%，其中 13 个企业未达标。',
      rows: [
        { name: '广西新奥能源', value: '1.72%', width: 12 },
        { name: '浙江新奥能源', value: '13.02%', width: 34 },
        { name: '福建新奥能源', value: '16.96%', width: 44 },
        { name: '江苏新奥能源', value: '27.71%', width: 72 },
      ],
    },
    analysis: {
      title: '人均处理工单',
      value: '18.6',
      target: '较上月 +2.4',
      diagnosis: '华东、华南区域处理效率较高，华北区域仍有排队工单需要关注。',
      rows: [
        { name: '华东运营区', value: '24.8', width: 78 },
        { name: '华南运营区', value: '21.3', width: 68 },
        { name: '华北运营区', value: '13.9', width: 44 },
        { name: '西南运营区', value: '11.2', width: 36 },
      ],
    },
    iot: {
      title: '设备在线率',
      value: '96.2%',
      target: '较上月 +1.1%',
      diagnosis: '核心采集设备整体在线稳定，少量站点存在夜间离线波动。',
      rows: [
        { name: '燃气站控设备', value: '98.4%', width: 90 },
        { name: '安防感知设备', value: '95.7%', width: 76 },
        { name: '能耗采集设备', value: '94.1%', width: 70 },
        { name: '边缘网关', value: '92.8%', width: 64 },
      ],
    },
  },
}

const leftPanel = computed(() => domainPanels[activeDomain.value])
const rightTabs = computed(() => rightTabsByGroup[activeRightGroup.value])
const rightPanel = computed(() => rightTabData[activeRightGroup.value][activeRightTab.value])
const leftActiveTabLabel = computed(() => leftPanel.value.title)
const rightActiveTabLabel = computed(() => {
  return rightTabs.value.find((tab) => tab.key === activeRightTab.value)?.label || rightPanel.value.title
})

const healthTone = computed(() => {
  if (appStore.apiStatus === 'online') {
    return 'success'
  }

  if (appStore.apiStatus === 'offline') {
    return 'danger'
  }

  if (appStore.apiStatus === 'checking') {
    return 'info'
  }

  return 'warning'
})

const healthLabel = computed(() => {
  if (appStore.apiStatus === 'online') {
    return '后端在线'
  }

  if (appStore.apiStatus === 'offline') {
    return '后端未连接'
  }

  if (appStore.apiStatus === 'checking') {
    return '检测中'
  }

  return '等待检测'
})

const systemDetails = computed(() => [
  { label: 'Database', value: appStore.health?.database || '-' },
  { label: 'Redis', value: appStore.health?.redis || '-' },
  { label: 'LLM', value: appStore.health?.llm || '-' },
])

function switchRightGroup(group: RightGroupKey) {
  activeRightGroup.value = group
  activeRightTab.value = 'credential'
}

onMounted(() => {
  void appStore.checkHealth()
})
</script>

<template>
  <div class="home-dashboard">
    <section class="dashboard-grid" aria-label="智能运营中心总览">
      <aside class="side-panel side-panel--left">
        <div class="domain-tabs" role="tablist" aria-label="运营领域">
          <button
            v-for="(panel, key) in domainPanels"
            :key="key"
            :class="['domain-tab', { 'domain-tab--active': activeDomain === key }]"
            type="button"
            @click="activeDomain = key"
          >
            {{ panel.title }}
          </button>
        </div>

        <div class="filter-row">
          <button class="select-button" type="button">月维度</button>
          <button class="select-button select-button--wide" type="button">2026-05</button>
        </div>

        <div class="selector-stack">
          <button class="selector-button" type="button">{{ leftPanel.filter }}</button>
          <button class="selector-button" type="button">全部企业</button>
        </div>

        <section class="metric-box" aria-label="左侧关键指标">
          <article
            v-for="item in leftPanel.metrics"
            :key="item.label"
            :class="['metric-row', `metric-row--${item.tone}`]"
          >
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}<small>{{ item.unit }}</small></strong>
            <em>{{ item.trend }}</em>
          </article>
        </section>

        <section class="rank-block" aria-label="企业排行">
          <h2>{{ leftPanel.metrics[0].label }}</h2>
          <ol class="rank-list">
            <li v-for="(item, index) in leftPanel.ranks" :key="item.name">
              <span>{{ index + 1 }}</span>
              <b>{{ item.name }}</b>
              <em>{{ item.value }}</em>
            </li>
          </ol>
        </section>

        <section class="trend-block" aria-label="趋势图">
          <h2>{{ leftPanel.metrics[0].label }}</h2>
          <div class="trend-chart">
            <span style="height: 18%"></span>
            <span style="height: 48%"></span>
            <span style="height: 30%"></span>
            <span style="height: 64%"></span>
            <span style="height: 24%"></span>
          </div>
          <div class="chart-axis">
            <span>2026-05-01</span>
            <span>2026-05-04</span>
          </div>
        </section>

        <RouterLink
          class="ai-analysis-btn"
          :to="{
            path: '/operation',
            query: {
              domain: activeDomain,
              active_tab: leftActiveTabLabel,
              time_dimension: timeDimension,
              date: currentDate,
              category: currentCategory,
            },
          }"
        >
          AI 智能分析
        </RouterLink>
      </aside>

      <main class="map-stage">
        <div class="map-topbar">
          <div class="indicator-strip">
            <div v-for="item in topIndicators" :key="item.label" class="top-indicator">
              <span>{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
              <em>{{ item.unit }}</em>
            </div>
          </div>

          <div class="map-actions">
            <input aria-label="企业筛选" placeholder="全部" />
            <RouterLink
              class="mode-button mode-button--active"
              :to="{
                path: '/operation',
                query: {
                  domain: 'safety',
                  active_tab: '本质安全',
                  time_dimension: timeDimension,
                  date: currentDate,
                  category: currentCategory,
                },
              }"
            >
              分析
            </RouterLink>
          </div>
        </div>

        <section class="map-canvas" aria-label="运营地图态势">
          <div class="map-water"></div>
          <div class="map-land map-land--eurasia"></div>
          <div class="map-land map-land--america"></div>
          <div class="map-land map-land--australia"></div>
          <div class="map-region">亚洲</div>
          <div class="map-region map-region--europe">欧洲</div>
          <div class="map-region map-region--pacific">太平洋</div>

          <div
            v-for="point in mapPoints"
            :key="point.label"
            :class="['map-point', `map-point--${point.tone}`]"
            :style="{ left: `${point.x}%`, top: `${point.y}%` }"
          >
            <strong>{{ point.value }}</strong>
            <span>{{ point.label }}</span>
          </div>
        </section>

        <div class="map-statusbar">
          <StatusBadge :tone="healthTone" :label="healthLabel" />
          <div class="system-list">
            <span v-for="item in systemDetails" :key="item.label">
              {{ item.label }}：<b>{{ item.value }}</b>
            </span>
          </div>
        </div>
      </main>

      <aside class="side-panel side-panel--right">
        <div class="right-title">
          <button
            :class="['title-tab', { 'title-tab--active': activeRightGroup === 'business' }]"
            type="button"
            @click="switchRightGroup('business')"
          >
            经营改善
          </button>
          <button
            :class="['title-tab', { 'title-tab--active': activeRightGroup === 'capability' }]"
            type="button"
            @click="switchRightGroup('capability')"
          >
            能力提升
          </button>
        </div>

        <div class="right-tabs" role="tablist" aria-label="能力提升维度">
          <button
            v-for="tab in rightTabs"
            :key="tab.key"
            :class="['right-tab', { 'right-tab--active': activeRightTab === tab.key }]"
            type="button"
            @click="activeRightTab = tab.key"
          >
            {{ tab.label }}
          </button>
        </div>

        <section class="diagnosis-card" aria-label="诊断指标">
          <div class="diagnosis-main">
            <span>{{ rightPanel.title }}</span>
            <strong>{{ rightPanel.value }}</strong>
            <em>{{ rightPanel.target }}</em>
          </div>
          <p>{{ rightPanel.diagnosis }}</p>
        </section>

        <section class="right-rank" aria-label="能力排行">
          <h2>{{ rightPanel.title }}</h2>
          <ol>
            <li v-for="(row, index) in rightPanel.rows" :key="row.name">
              <span class="rank-num">{{ index + 1 }}</span>
              <div class="rank-main">
                <div>
                  <b>{{ row.name }}</b>
                  <em>{{ row.value }}</em>
                </div>
                <span class="rank-bar">
                  <i :style="{ width: `${row.width}%` }"></i>
                </span>
              </div>
            </li>
          </ol>
        </section>

        <section class="bar-card" aria-label="月度柱状图">
          <h2>{{ rightPanel.title }}</h2>
          <div class="bar-chart">
            <span style="height: 22%"></span>
            <span style="height: 16%"></span>
            <span style="height: 86%"></span>
            <span style="height: 32%"></span>
            <span style="height: 82%"></span>
          </div>
          <div class="chart-axis">
            <span>2025-07</span>
            <span>2025-10</span>
          </div>
        </section>

        <RouterLink
          class="ai-analysis-btn ai-analysis-btn--right"
          :to="{
            path: '/operation',
            query: {
              domain: activeRightGroup,
              active_tab: rightActiveTabLabel,
              tab: activeRightTab,
              time_dimension: timeDimension,
              date: currentDate,
            },
          }"
        >
          AI 智能分析
        </RouterLink>
      </aside>
    </section>
  </div>
</template>

<style scoped>
.home-dashboard {
  color: #1c2b3f;
}

.dashboard-grid {
  display: grid;
  gap: 18px;
  grid-template-columns: 380px minmax(520px, 1fr) 380px;
  min-height: calc(100vh - 112px);
}

.side-panel,
.map-stage {
  background: #ffffff;
  border: 1px solid #dbe8f5;
  border-radius: 8px;
  box-shadow: 0 12px 28px rgba(24, 70, 128, 0.08);
}

.side-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
  height: calc(100vh - 112px);
  overflow: hidden;
  padding: 20px 20px 76px;
  position: relative;
}

.ai-analysis-btn {
  align-items: center;
  background: linear-gradient(135deg, #3730a3, #6366f1);
  border: none;
  border-radius: 8px;
  color: #ffffff;
  cursor: pointer;
  display: flex;
  font-size: 14px;
  font-weight: 800;
  justify-content: center;
  left: 20px;
  min-height: 40px;
  padding: 0 16px;
  position: absolute;
  right: 20px;
  bottom: 12px;
  text-decoration: none;
  transition: opacity 0.15s;
  box-shadow: 0 10px 22px rgba(79, 70, 229, 0.28);
}

.ai-analysis-btn:hover {
  opacity: 0.9;
}

.domain-tabs,
.right-title,
.right-tabs {
  display: grid;
  gap: 0;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.right-tabs {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.domain-tab,
.title-tab,
.right-tab {
  background: #ffffff;
  border: none;
  border-bottom: 2px solid transparent;
  color: #42566f;
  cursor: pointer;
  font-size: 16px;
  font-weight: 800;
  min-height: 42px;
}

.right-tab {
  border: 1px solid #d6e4f2;
  font-size: 14px;
  min-height: 34px;
}

.domain-tab--active,
.title-tab--active {
  border-bottom-color: #168cff;
  color: #0d7de8;
}

.right-tab--active {
  background: #168cff;
  border-color: #168cff;
  color: #ffffff;
}

.filter-row,
.selector-stack {
  display: grid;
  gap: 12px;
  grid-template-columns: 90px 1fr;
}

.selector-stack {
  grid-template-columns: 1fr 1fr;
}

.select-button,
.selector-button,
.mode-button {
  align-items: center;
  background: #f7fbff;
  border: 1px solid #d8e5f2;
  border-radius: 6px;
  color: #2f4258;
  display: inline-flex;
  font-size: 14px;
  font-weight: 700;
  justify-content: center;
  min-height: 34px;
  text-decoration: none;
}

.selector-button {
  background: #edf5fc;
  border: none;
}

.metric-box {
  border: 1px solid #1388ff;
  border-radius: 6px;
  padding: 12px;
}

.metric-row {
  align-items: center;
  background: #f8fbff;
  border: 1px solid #d9e5f0;
  display: grid;
  gap: 8px;
  grid-template-columns: 1fr auto 86px;
  min-height: 40px;
  padding: 0 12px;
}

.metric-row + .metric-row {
  margin-top: 10px;
}

.metric-row span {
  color: #53667c;
  font-size: 14px;
}

.metric-row strong {
  color: #12243a;
  font-size: 18px;
}

.metric-row small {
  font-size: 13px;
  margin-left: 2px;
}

.metric-row em,
.diagnosis-main em,
.rank-list em,
.rank-main em {
  color: #8a9aac;
  font-style: normal;
  font-size: 12px;
}

.metric-row--danger {
  background: #fff7f3;
}

.metric-row--warning {
  background: #fffaf0;
}

.metric-row--success {
  background: #f1fbf6;
}

.rank-block h2,
.trend-block h2,
.right-rank h2,
.bar-card h2 {
  color: #1a2c40;
  font-size: 15px;
  margin: 0 0 12px;
}

.rank-list,
.right-rank ol {
  list-style: none;
  margin: 0;
  padding: 0;
}

.rank-list li {
  align-items: center;
  display: grid;
  gap: 10px;
  grid-template-columns: 24px 1fr auto;
  min-height: 38px;
}

.rank-list span,
.rank-num {
  align-items: center;
  background: #248ef2;
  border-radius: 50%;
  color: #ffffff;
  display: inline-flex;
  font-size: 13px;
  font-weight: 800;
  height: 22px;
  justify-content: center;
  width: 22px;
}

.rank-list b,
.rank-main b {
  color: #51667d;
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.trend-block,
.bar-card {
  margin-top: auto;
}

.trend-chart,
.bar-chart {
  align-items: end;
  border-bottom: 1px solid #d8e4f0;
  border-left: 1px solid #e4edf6;
  display: flex;
  gap: 22px;
  height: 150px;
  padding: 12px 22px 0;
}

.trend-chart span,
.bar-chart span {
  background: linear-gradient(180deg, #1692ff, #28d2b0);
  border-radius: 4px 4px 0 0;
  display: block;
  width: 18px;
}

.chart-axis {
  color: #9aaabc;
  display: flex;
  font-size: 12px;
  justify-content: space-between;
  padding: 8px 10px 0;
}

.map-stage {
  display: grid;
  grid-template-rows: auto 1fr auto;
  overflow: hidden;
}

.map-topbar,
.map-statusbar {
  align-items: center;
  background: #ffffff;
  display: flex;
  gap: 16px;
  justify-content: space-between;
  min-height: 56px;
  padding: 10px 16px;
}

.indicator-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.top-indicator {
  align-items: center;
  display: inline-flex;
  gap: 8px;
}

.top-indicator span {
  color: #127fe4;
  font-size: 13px;
  font-weight: 800;
}

.top-indicator strong {
  background: #d6edff;
  border-radius: 6px;
  color: #167dde;
  font-size: 28px;
  line-height: 1;
  min-width: 34px;
  padding: 4px 6px;
  text-align: center;
}

.top-indicator em {
  color: #167dde;
  font-style: normal;
  font-size: 13px;
  font-weight: 800;
}

.map-actions {
  align-items: center;
  display: flex;
  gap: 8px;
}

.map-actions input {
  border: 1px solid #d8e5f2;
  border-radius: 6px;
  color: #4a6078;
  height: 34px;
  min-width: 170px;
  padding: 0 12px;
}

.mode-button {
  min-width: 72px;
}

.mode-button--active {
  background: #1592ff;
  border-color: #1592ff;
  color: #ffffff;
}

.map-canvas {
  background:
    linear-gradient(rgba(255, 255, 255, 0.5) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.5) 1px, transparent 1px),
    #a9c9eb;
  background-size: 120px 120px, 120px 120px, auto;
  min-height: 620px;
  overflow: hidden;
  position: relative;
}

.map-water {
  background: linear-gradient(180deg, rgba(244, 250, 255, 0.85), rgba(169, 201, 235, 0.12));
  height: 34%;
  left: 0;
  position: absolute;
  top: 0;
  width: 100%;
}

.map-land {
  background: #eef6ff;
  border: 1px solid rgba(119, 160, 210, 0.28);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.48);
  position: absolute;
}

.map-land--eurasia {
  border-radius: 48% 52% 42% 58%;
  clip-path: polygon(
    0 52%,
    9% 36%,
    28% 27%,
    40% 8%,
    58% 15%,
    68% 30%,
    86% 28%,
    100% 44%,
    82% 66%,
    64% 61%,
    52% 78%,
    31% 68%,
    18% 76%
  );
  height: 44%;
  left: 7%;
  top: 30%;
  width: 72%;
}

.map-land--america {
  border-radius: 62% 38% 48% 52%;
  clip-path: polygon(38% 0, 76% 11%, 92% 36%, 72% 64%, 84% 94%, 49% 86%, 28% 62%, 12% 34%);
  height: 46%;
  right: -4%;
  top: 28%;
  width: 24%;
}

.map-land--australia {
  border-radius: 42% 58% 55% 45%;
  height: 9%;
  left: 62%;
  top: 76%;
  transform: rotate(-8deg);
  width: 16%;
}

.map-region {
  color: #102c4f;
  font-size: 24px;
  font-weight: 700;
  left: 38%;
  position: absolute;
  top: 53%;
}

.map-region--europe {
  font-size: 18px;
  left: 14%;
  top: 50%;
}

.map-region--pacific {
  color: #0c65b0;
  font-size: 14px;
  left: 74%;
  top: 68%;
}

.map-point {
  align-items: center;
  background: #ffffff;
  border: 2px solid #158bff;
  border-radius: 999px;
  color: #1483ef;
  display: inline-flex;
  flex-direction: column;
  height: 54px;
  justify-content: center;
  position: absolute;
  transform: translate(-50%, -50%);
  width: 54px;
}

.map-point strong {
  font-size: 18px;
  line-height: 1;
}

.map-point span {
  color: #0f5598;
  font-size: 12px;
  left: 50%;
  position: absolute;
  top: 58px;
  transform: translateX(-50%);
  white-space: nowrap;
}

.map-point--active {
  height: 64px;
  width: 64px;
}

.map-point--active strong {
  font-size: 20px;
}

.map-point--success {
  border-color: #22b98a;
  color: #0f9f76;
}

.map-point--warning {
  border-color: #f59e0b;
  color: #d97706;
}

.map-statusbar {
  border-top: 1px solid #dbe8f5;
}

.system-list {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  justify-content: flex-end;
}

.system-list span {
  color: #66788d;
  font-size: 13px;
}

.system-list b {
  color: #1b2e43;
}

.right-title {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.diagnosis-card {
  background: #eef8ff;
  border: 1px solid #91caff;
  border-radius: 6px;
  padding: 14px;
}

.diagnosis-main {
  align-items: center;
  background: #ffffff;
  border: 1px solid #148cff;
  display: grid;
  gap: 10px;
  grid-template-columns: 1fr auto 90px;
  min-height: 42px;
  padding: 0 10px;
}

.diagnosis-main span {
  color: #60748b;
  font-size: 14px;
}

.diagnosis-main strong {
  color: #1f2f43;
  font-size: 18px;
}

.diagnosis-card p {
  color: #314b65;
  font-size: 14px;
  line-height: 1.8;
  margin: 14px 0 0;
}

.right-rank ol {
  display: grid;
  gap: 14px;
}

.right-rank li {
  align-items: center;
  display: grid;
  gap: 10px;
  grid-template-columns: 24px 1fr;
}

.rank-main {
  min-width: 0;
}

.rank-main div {
  align-items: center;
  display: flex;
  gap: 10px;
  justify-content: space-between;
}

.rank-bar {
  background: #edf3f8;
  border-radius: 999px;
  display: block;
  height: 6px;
  margin-top: 7px;
  overflow: hidden;
}

.rank-bar i {
  background: linear-gradient(90deg, #28d7b0, #1592ff);
  display: block;
  height: 100%;
}

.bar-card {
  border-top: 1px solid #e3edf7;
  padding-top: 16px;
}

@media (max-width: 1360px) {
  .dashboard-grid {
    grid-template-columns: 340px minmax(460px, 1fr);
  }

  .side-panel--right {
    grid-column: 1 / -1;
  }
}

@media (max-width: 980px) {
  .dashboard-grid {
    grid-template-columns: 1fr;
  }

  .side-panel {
    height: auto;
    min-height: 620px;
  }

  .map-canvas {
    min-height: 500px;
  }

  .map-topbar,
  .map-statusbar {
    align-items: flex-start;
    flex-direction: column;
  }

  .map-actions,
  .system-list {
    justify-content: flex-start;
    width: 100%;
  }
}

@media (max-width: 620px) {
  .side-panel {
    padding: 16px 16px 72px;
    min-height: 560px;
  }

  .ai-analysis-btn {
    left: 16px;
    right: 16px;
  }

  .filter-row,
  .selector-stack,
  .diagnosis-main {
    grid-template-columns: 1fr;
  }

  .map-actions {
    align-items: stretch;
    flex-direction: column;
  }

  .map-actions input,
  .mode-button {
    width: 100%;
  }

  .metric-row {
    align-items: flex-start;
    grid-template-columns: 1fr;
    padding: 10px 12px;
  }

  .top-indicator strong {
    font-size: 22px;
  }
}
</style>
