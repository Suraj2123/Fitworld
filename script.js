const foodForm = document.querySelector('#food-form');
const foodName = document.querySelector('#food-name');
const foodCalories = document.querySelector('#food-calories');
const foodList = document.querySelector('#food-list');
const emptyMessage = document.querySelector('#food-empty');
const calorieTotal = document.querySelector('#calorie-total');
let totalCalories = 0;

// A name made only of spaces should not count as a food.
foodName.addEventListener('input', function () {
  foodName.setCustomValidity('');
});

foodForm.addEventListener('submit', function (event) {
  event.preventDefault(); // Keep the browser from reloading the page.
  const name = foodName.value.trim();
  const calories = Number(foodCalories.value);

  if (name === '') {
    foodName.setCustomValidity('Enter a food name.');
    foodName.reportValidity();
    return;
  }

  // Use textContent so a food name is displayed as text, not HTML.
  const entry = document.createElement('li');
  entry.textContent = `${name} — ${calories} kcal`;
  foodList.appendChild(entry);

  totalCalories += calories;
  calorieTotal.textContent = totalCalories;
  emptyMessage.hidden = true;
  foodForm.reset();
  foodName.focus();
});
