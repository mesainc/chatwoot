<script setup>
import { useAttrs } from 'vue';

const attrs = useAttrs();
const logoPath = '/mesa/mark.svg';
</script>

<template>
  <img v-bind="attrs" :src="logoPath" alt="Mesa" />
</template>
