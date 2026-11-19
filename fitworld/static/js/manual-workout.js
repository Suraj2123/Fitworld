import { $, notify } from "./client.js";

export function initManualWorkout() {
  const form = $("#workout-form");
  let editing = null;
  function reset() {
    editing = null;
    form.reset();
    form.dataset.submitLabel = "Add workout";
    form.querySelector('[type="submit"]').textContent = "Add workout";
    $("#cancel-workout-edit").hidden = true;
    $("#workout-edit-status").textContent = "";
    form.querySelector(".form-error").hidden = true;
    form.dispatchEvent(new Event("workout:draft"));
  }
  $("#cancel-workout-edit").addEventListener("click", reset);
  form.querySelector('[type="reset"]').addEventListener("click", (event) => {
    event.preventDefault();
    reset();
  });
  return {
    editing: () => editing,
    reset,
    edit(workout) {
      if (form.dataset.busy === "true") return;
      if (
        editing ||
        [...form.querySelectorAll("input, textarea")].some((input) => input.value) ||
        form.elements.status.value !== "completed"
      ) {
        notify("Save or clear your current workout before editing another.");
        return;
      }
      editing = { id: workout.id, date: workout.performed_on };
      for (const key of ["workout_name", "status", "estimated_calories", "notes"])
        form.elements[key].value = workout[key] ?? "";
      form.elements.duration_minutes.value = workout.duration_seconds / 60;
      form.dataset.submitLabel = "Save workout changes";
      form.querySelector('[type="submit"]').textContent = form.dataset.submitLabel;
      $("#cancel-workout-edit").hidden = false;
      $("#workout-edit-status").textContent =
        `Editing ${workout.workout_name} from ${workout.performed_on}. Changes stay on that date.`;
      form.querySelector("details").open = true;
      form.dispatchEvent(new Event("workout:draft"));
      form.elements.workout_name.focus();
    },
  };
}
