import assert from "node:assert/strict";
import test from "node:test";

let instance = 0;
const transport = () => import(`../../fitworld/static/js/http.js?test=${++instance}`);
const json = (data, status = 200) => new Response(JSON.stringify(data), { status });

test("importing the transport does not start requests or require a browser DOM", async (context) => {
  const fetch = context.mock.method(globalThis, "fetch", async () => json({}));
  await transport();
  assert.equal(fetch.mock.callCount(), 0);
});

test("successful session changes rotate the CSRF token for later writes", async (context) => {
  const calls = [];
  context.mock.method(globalThis, "fetch", async (url, options) => {
    calls.push({ url, options });
    return json(
      calls.length === 1 ? { csrf_token: "before-login" } : { csrf_token: "after-login" },
    );
  });
  const { request } = await transport();
  await request("session");
  await request("login", "POST", { email: "test@example.com", password: "test-password" });
  await request("activity/workouts", "POST", { workout_name: "Walk" });
  assert.equal(calls[1].options.headers["X-CSRF-Token"], "before-login");
  assert.equal(calls[2].options.headers["X-CSRF-Token"], "after-login");
  assert.equal(calls[1].options.credentials, "same-origin");
  assert.deepEqual(JSON.parse(calls[2].options.body), { workout_name: "Walk" });
});

test("validation failures expose their status and field errors without a UI policy", async (context) => {
  context.mock.method(globalThis, "fetch", async () =>
    json({ error: "Check your details.", fields: { age: "Use a whole number." } }, 422),
  );
  const { request, ApiError } = await transport();
  await assert.rejects(request("onboarding/profile", "PUT", {}), (error) => {
    assert.ok(error instanceof ApiError);
    assert.equal(error.status, 422);
    assert.deepEqual(error.fields, { age: "Use a whole number." });
    return true;
  });
});

test("a non-JSON server error has a useful message", async (context) => {
  context.mock.method(
    globalThis,
    "fetch",
    async () => new Response("<html>Server error</html>", { status: 500 }),
  );
  const { request } = await transport();
  await assert.rejects(
    request("activity"),
    (error) => error.status === 500 && error.message.includes("Refresh and check"),
  );
});

test("a failed write is attempted once, so a timeout cannot silently duplicate activity", async (context) => {
  const fetch = context.mock.method(globalThis, "fetch", async () => {
    throw new DOMException("Timed out", "TimeoutError");
  });
  const { request } = await transport();
  await assert.rejects(request("activity/meals", "POST", {}), { name: "TimeoutError" });
  assert.equal(fetch.mock.callCount(), 1);
});
