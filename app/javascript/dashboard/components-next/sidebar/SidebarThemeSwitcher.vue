<script setup>
import { useI18n } from 'vue-i18n';
import { useAppearanceHotKeys } from 'dashboard/composables/commands/useAppearanceHotKeys';
import { colorScheme } from 'dashboard/helper/themeHelper';
import Button from 'next/button/Button.vue';

defineProps({
  isCollapsed: { type: Boolean, default: false },
});

const { t } = useI18n();
const { themeOptions, setAppearance } = useAppearanceHotKeys();
const themeIcons = {
  light: 'i-lucide-sun',
  dark: 'i-lucide-moon',
  auto: 'i-lucide-monitor',
};
</script>

<template>
  <div
    class="flex w-full items-center gap-2"
    :class="isCollapsed ? 'flex-col' : 'justify-between'"
  >
    <span v-if="!isCollapsed" class="text-xs text-n-slate-11 truncate">
      {{ t('COMMAND_BAR.SECTIONS.APPEARANCE') }}
    </span>
    <div
      role="group"
      :aria-label="t('SIDEBAR_ITEMS.APPEARANCE')"
      class="flex flex-shrink-0 gap-0.5 rounded-lg bg-n-alpha-1 p-0.5"
      :class="{ 'flex-col': isCollapsed }"
    >
      <Button
        v-for="theme in themeOptions"
        :key="theme.key"
        :icon="themeIcons[theme.key]"
        :title="theme.label"
        :aria-label="theme.label"
        :aria-pressed="colorScheme === theme.key"
        color="slate"
        variant="ghost"
        size="sm"
        class="!size-7"
        :class="{ '!bg-n-alpha-2 !text-n-slate-12': colorScheme === theme.key }"
        @click="setAppearance(theme.key)"
      />
    </div>
  </div>
</template>
