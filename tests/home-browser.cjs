const { chromium } = require('playwright');
const assert = require('node:assert/strict');
(async () => {
 const browser = await chromium.launch({channel:'chrome',headless:true});
 const context = await browser.newContext({viewport:{width:1440,height:1000}});
 const page = await context.newPage();
 const errors=[]; page.on('pageerror',e=>errors.push(e.message));
 const base='http://127.0.0.1:5057';
 async function write(path,data,method='POST') {
  const session=await (await context.request.get(base+'/api/session')).json();
  const r=await context.request.fetch(base+'/api/'+path,{method,data,headers:{'X-CSRF-Token':session.csrf_token}});
  assert(r.ok(),await r.text());
 }
 await write('register',{display_name:'Home Demo',email:`demo${Date.now()}@example.com`,password:'test-only-long-password'});
 await write('onboarding/profile',{age:25,weight:70,unit_system:'metric',experience_level:'beginner',current_workouts_per_week:0},'PUT');
 await write('onboarding/preferences',{primary_goal:'build_strength',training_location:'home',target_days_per_week:3,session_minutes:30},'PUT');
 await write('onboarding/complete',{});
 await page.goto(base+'/home?date=2026-01-05');
 await page.waitForSelector('#today-stats:not([aria-busy])');
 await page.locator('#meal-name').fill('Breakfast');
 async function food(row,name,servings,calories) {
  await row.locator('[data-field=food_name]').fill(name);
  await row.locator('[data-field=serving_description]').fill('cup');
  await row.locator('[data-field=servings]').fill(servings);
  await row.locator('[data-field=calories_per_serving]').fill(calories);
 }
 await food(page.locator('.meal-item').nth(0),'Oats','2','150');
 await page.locator('#add-meal-item').click();
 await food(page.locator('.meal-item').nth(1),'Milk','0.5','100');
 assert((await page.locator('#meal-preview').innerText()).includes('350 kcal'));
 await page.locator('#food-form [type=submit]').click();
 await page.waitForFunction(()=>document.querySelector('#calorie-total').textContent==='350');
 await page.reload();
 await page.waitForFunction(()=>document.querySelector('#calorie-total').textContent==='350');
 await page.getByRole('button',{name:'Use Breakfast as a new meal',exact:true}).click();
 assert.equal(await page.locator('.meal-item').count(),2);
 await page.locator('#next-day').click();
 await page.waitForFunction(()=>document.querySelector('#calorie-total').textContent==='0');
 await page.locator('.meal-item').first().locator('[data-field=servings]').fill('1');
 await page.locator('#food-form [type=submit]').click();
 await page.waitForFunction(()=>document.querySelector('#calorie-total').textContent==='200');
 await page.locator('#workout-name').fill('Evening walk');
 await page.locator('#workout-minutes').fill('25');
 await page.locator('#workout-form summary').click();
 await page.locator('#manual-notes').fill('A steady pace around the park.');
 await page.locator('#manual-calories').fill('90');
 await page.locator('#workout-form [type=submit]').click();
 await page.waitForFunction(()=>document.querySelector('#workout-total').textContent==='25');
 assert((await page.locator('#today-workouts').innerText()).includes('A steady pace'));
 // Reuse must not overwrite an existing draft.
 await page.locator('.meal-item [data-field=food_name]').fill('Unsaved snack');
 await page.getByRole('button',{name:'Use Breakfast as a new meal',exact:true}).click();
 assert.equal(await page.locator('.meal-item [data-field=food_name]').inputValue(),'Unsaved snack');
 await page.locator('#clear-meal').click();
 await page.getByRole('button',{name:'Use Breakfast as a new meal',exact:true}).click();
 // Remove first row; labels and focus must still work with the remaining row.
 await page.locator('.meal-item').first().getByRole('button',{name:'Remove food 1 from draft'}).click();
 assert.equal(await page.locator('.meal-item').count(),1);
 await page.locator('#jump-food').click();
 assert.equal(await page.locator('.meal-item input').first().evaluate(e=>e===document.activeElement),true);
 await page.locator('#clear-meal').click();
 // Rejected saves must preserve the draft and restore controls.
 await food(page.locator('.meal-item').first(),'Preserved snack','1','80');
 await page.route('**/api/activity/meals', route => route.fulfill({status:422,contentType:'application/json',body:JSON.stringify({error:'Test validation rejection'})}));
 await page.locator('#food-form [type=submit]').click();
 await page.waitForSelector('#food-form .form-error:not([hidden])');
 assert.equal(await page.locator('.meal-item [data-field=food_name]').inputValue(),'Preserved snack');
 assert.equal(await page.locator('#add-meal-item').isEnabled(),true);
 await page.unroute('**/api/activity/meals');
 await page.locator('#clear-meal').click();
 await page.locator('#food-heading').click();
 await page.waitForTimeout(5100);
 await page.evaluate(()=>window.scrollTo(0,0));
 await page.screenshot({path:'/tmp/fitworld-home-desktop.png',fullPage:true});
 await page.setViewportSize({width:390,height:844});
 await page.screenshot({path:'/tmp/fitworld-home-mobile.png',fullPage:true});
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Mobile overflow');
 await page.locator('#today-button').click();
 assert.equal(await page.locator('#next-day').isDisabled(),true);
 assert.deepEqual(errors,[]);
 console.log('PASS: multi-food save, persistence, reuse across dates, draft protection, workout details, removal/focus, mobile layout, today navigation; no JS errors.');
 await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
