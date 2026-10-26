<script setup>
import LecturerSelector from '../shared/LecturerSelector.vue'
import ListPagination from '../shared/ListPagination.vue'
import ConfirmAction from '../shared/ConfirmAction.vue'
const props = defineProps({ workspace: { type: Object, required: true } })
const w = props.workspace
</script>
<template>
  <section class="card lecturer-management" aria-labelledby="lecturer-heading" :aria-busy="w.referenceBusy">
    <div class="section-heading">
      <div>
        <p class="eyebrow">
          Step 1
        </p>
        <h2 id="lecturer-heading">
          Your lecturer
        </h2>
      </div>
      <button class="btn compact" :disabled="w.captureLocked" @click="w.refreshLecturers">
        Refresh
      </button>
    </div>
    <LecturerSelector
      id="registered-lecturer"
      v-model="w.selectedLecturerId"
      :lecturers="w.lecturers"
      :selected="w.selectedLecturer"
      :disabled="w.captureLocked"
      label="Registered lecturer"
      placeholder="Register a new lecturer"
      @select="w.selectLecturer"
      />
    <ListPagination
      :offset="w.lecturerOffset"
      :total="w.lecturerTotal"
      :count="w.lecturers.length"
      :busy="w.captureLocked"
      label="lecturers"
      @change="w.changeLecturerPage"
      />
    <div v-if="w.selectedLecturer" class="lecturer-profile">
      <span class="profile-initial" aria-hidden="true">{{ w.selectedLecturer.name.trim().charAt(0) }}</span>
      <div><p class="eyebrow">Saved profile</p><h3>{{ w.selectedLecturer.name }}</h3><p class="muted">{{ w.selectedLecturer.department || 'No department specified' }}</p></div>
    </div>
    <details class="profile-editor" :open="!w.selectedLecturerId">
      <summary>{{ w.selectedLecturerId ? 'Edit lecturer details' : 'Register a lecturer' }}</summary>
      <form class="inset-form" @submit.prevent="w.saveLecturer">
        <h3>
          {{ w.selectedLecturerId ? 'Lecturer information' : 'Register a lecturer' }}
        </h3>
        <div class="field">
          <label for="lecturer-name" class="field-label">
            Lecturer name
            <span class="required-label">
              (required)
            </span>
          </label>
          <input
            id="lecturer-name"
            v-model="w.lecturerName"
            required
            maxlength="200"
            autocomplete="off"
            placeholder="e.g. Dr. Santos"
            :disabled="w.captureLocked"
            />
        </div>
        <div class="field">
          <label for="lecturer-department" class="field-label">
            Department
            <span class="muted">
              (optional)
            </span>
          </label>
          <input
            id="lecturer-department"
            v-model="w.lecturerDepartment"
            maxlength="200"
            autocomplete="off"
            placeholder="e.g. Computer Engineering"
            :disabled="w.captureLocked"
            />
        </div>
        <div class="actions">
          <button class="btn primary" type="submit" :disabled="w.captureLocked || !w.lecturerName.trim()">
            {{ w.referenceBusy ? 'Working...' : w.selectedLecturerId ? 'Save lecturer' : 'Register lecturer' }}
          </button>
        </div>
      </form>
    </details>
    <div class="profile-danger">
      <button
        v-if="w.selectedLecturerId"
        id="delete-lecturer"
        class="btn text-danger"
        type="button"
        :disabled="w.captureLocked"
        @click="w.lecturerDeleteCandidate = w.selectedLecturerId">
        Delete lecturer
      </button>
    </div>
    <ConfirmAction
      v-if="w.selectedLecturerId && w.lecturerDeleteCandidate === w.selectedLecturerId"
      title="Delete this lecturer?"
      description="Only lecturers without saved reference samples or recordings can be deleted."
      confirm-label="Delete lecturer"
      :busy="w.captureLocked"
      return-focus="delete-lecturer"
      @confirm="w.deleteLecturer"
      @cancel="w.lecturerDeleteCandidate = null"
      />
    <p class="muted helper">
      Your selection is restored when you return. Saved references belong to this lecturer.
    </p>
  </section>
</template>
