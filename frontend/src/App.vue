<script setup lang="ts">
import { RouterView } from 'vue-router'
import { useRoute } from 'vue-router'

import DefaultLayout from '@/layouts/DefaultLayout.vue'
import PlatformLayout from '@/layouts/PlatformLayout.vue'

const route = useRoute()
</script>

<template>
  <PlatformLayout v-if="route.meta.platform">
    <RouterView />
  </PlatformLayout>
  <DefaultLayout v-else>
    <RouterView />
  </DefaultLayout>
</template>
