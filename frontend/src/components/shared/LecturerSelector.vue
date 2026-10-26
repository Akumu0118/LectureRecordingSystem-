<script setup>
defineProps({ id: { type: String, required: true }, modelValue: { type: String, default: '' }, lecturers: { type: Array, default: () => [] }, selected: { type: Object, default: null }, disabled: Boolean, label: { type: String, default: 'Lecturer' }, placeholder: { type: String, default: 'Select a registered lecturer' } })
const emit = defineEmits(['update:modelValue', 'select'])
function change(event) { emit('update:modelValue', event.target.value); emit('select') }
</script>
<template>
  <div class="field">
    <label class="field-label" :for="id">
      {{ label }}
    </label>
    <select :id="id" :value="modelValue" :disabled="disabled" @change="change">
      <option value="">
        {{ placeholder }}
      </option>
      <option v-if="selected && !lecturers.some(item => item.id === selected.id)" :value="selected.id">
        {{ selected.name }}
      </option>
      <option v-for="lecturer in lecturers" :key="lecturer.id" :value="lecturer.id">
        {{ lecturer.name }}{{ lecturer.department ? ` - ${lecturer.department}` : '' }}
      </option>
    </select>
  </div>
</template>
