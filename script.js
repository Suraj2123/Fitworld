// Food logging flow: read inputs -> add a list item -> update total -> reset form.
// querySelector finds an HTML element. The # means we are selecting by its ID.
// const keeps each reference fixed; we can still change the element it refers to.
const foodForm = document.querySelector('#food-form');
const foodName = document.querySelector('#food-name');
const foodCalories = document.querySelector('#food-calories');
const foodList = document.querySelector('#food-list');
const emptyMessage = document.querySelector('#food-empty');
const calorieTotal = document.querySelector('#calorie-total');
// let allows this number to change when food is added. It lives only in page memory.
// No database or browser storage is used, so refreshing clears entries and the total.
let totalCalories = 0;

// Clear any custom name error when the user edits the input. An empty string
// removes the error so the browser will allow another valid submission attempt.
foodName.addEventListener('input', function () {
  foodName.setCustomValidity('');
});

// Listen on the form so clicking Add food or pressing Enter can submit it.
// Normal browser validation (required, min, step) happens before this event.
foodForm.addEventListener('submit', function (event) {
  event.preventDefault(); // Keep the browser from reloading the page.
  // Input values are strings. trim removes leading/trailing spaces from the name.
  const name = foodName.value.trim();
  // Number converts the calorie string so 150 + 100 becomes 250, not "150100".
  const calories = Number(foodCalories.value);

  // required catches an empty field, but spaces can pass it. Check the trimmed name,
  // display an error, and return early so no entry or calories are added.
  if (name === '') {
    foodName.setCustomValidity('Enter a food name.');
    foodName.reportValidity();
    return;
  }

  // Create a list item in memory, give it text, then append it to the visible list.
  // Backticks and ${...} insert values into the string. textContent displays names
  // as plain text, even if someone enters characters that look like HTML.
  const entry = document.createElement('li');
  entry.textContent = `${name} — ${calories} kcal`;
  // Each entry gets its own button and click handler. The handler remembers
  // this entry and its calories (a closure), even after the submit handler finishes.
  const removeButton = document.createElement('button');
  removeButton.type = 'button'; // This action should never submit a form.
  removeButton.className = 'remove-entry';
  removeButton.textContent = 'Remove';
  removeButton.setAttribute('aria-label', `Remove ${name}, ${calories} kcal`);
  removeButton.addEventListener('click', function () {
    entry.remove(); // Remove only the list item associated with this button.
    totalCalories -= calories;
    calorieTotal.textContent = totalCalories;
    // hidden is false when the list is empty, revealing the original message.
    emptyMessage.hidden = foodList.children.length > 0;
    // The clicked button no longer exists; put keyboard focus on a useful control.
    foodName.focus();
  });
  entry.appendChild(removeButton);
  foodList.appendChild(entry);

  // += adds the new calories to the previous total. Update the displayed number
  // separately: changing a JavaScript variable does not automatically change HTML.
  totalCalories += calories;
  calorieTotal.textContent = totalCalories;
  // There is now at least one entry, so the empty-state message no longer applies.
  emptyMessage.hidden = true;
  // Clear only the form inputs (not the list or total), then move the cursor back
  // to the name field to make entering the next food easier.
  foodForm.reset();
  foodName.focus();
});

// Workout logging uses its own elements and total so it cannot change the food log.
// Keeping this flow similar to food logging makes both handlers easy to compare.
const workoutForm = document.querySelector('#workout-form');
const workoutName = document.querySelector('#workout-name');
const workoutMinutes = document.querySelector('#workout-minutes');
const workoutList = document.querySelector('#workout-list');
const workoutEmpty = document.querySelector('#workout-empty');
const workoutTotal = document.querySelector('#workout-total');
let totalMinutes = 0;

// Remove a previous whitespace-only name error when the user starts correcting it.
workoutName.addEventListener('input', function () {
  workoutName.setCustomValidity('');
});

workoutForm.addEventListener('submit', function (event) {
  event.preventDefault(); // Update this page instead of navigating or reloading.
  const name = workoutName.value.trim();
  const minutes = Number(workoutMinutes.value);

  // The browser checks required/min/step; this extra check rejects names of only spaces.
  if (name === '') {
    workoutName.setCustomValidity('Enter a workout name.');
    workoutName.reportValidity();
    return;
  }

  // textContent treats the entered workout name as text rather than executable HTML.
  const entry = document.createElement('li');
  entry.textContent = `${name} — ${minutes} min`;
  // Each entry gets its own button and click handler. The handler remembers
  // this entry and its minutes (a closure), even after the submit handler finishes.
  const removeButton = document.createElement('button');
  removeButton.type = 'button'; // This action should never submit a form.
  removeButton.className = 'remove-entry';
  removeButton.textContent = 'Remove';
  removeButton.setAttribute('aria-label', `Remove ${name}, ${minutes} min`);
  removeButton.addEventListener('click', function () {
    entry.remove(); // Remove only the list item associated with this button.
    totalMinutes -= minutes;
    workoutTotal.textContent = totalMinutes;
    // hidden is false when the list is empty, revealing the original message.
    workoutEmpty.hidden = workoutList.children.length > 0;
    // The clicked button no longer exists; put keyboard focus on a useful control.
    workoutName.focus();
  });
  entry.appendChild(removeButton);
  workoutList.appendChild(entry);

  // Accumulate the duration, then copy the updated number into the visible total.
  // This variable and the list disappear on refresh, just like the food log.
  totalMinutes += minutes;
  workoutTotal.textContent = totalMinutes;
  workoutEmpty.hidden = true;

  // Prepare the form for another entry without clearing the recorded workouts.
  workoutForm.reset();
  workoutName.focus();
});
