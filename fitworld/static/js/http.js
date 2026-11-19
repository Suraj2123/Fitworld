// Shared transport only. Importing this module makes no request or UI change.
let csrfToken = "";

export class ApiError extends Error {
  constructor(message, status, fields = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.fields = fields;
  }
}

export async function request(path, method = "GET", data) {
  const response = await fetch(`/api/${path}`, {
    method,
    credentials: "same-origin",
    signal: AbortSignal.timeout(15000),
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    body: data === undefined ? undefined : JSON.stringify(data),
  });
  let result;
  try {
    result = await response.json();
  } catch {
    throw new ApiError(
      "We couldn’t read the response. Refresh and check your saved details before trying again.",
      response.status,
    );
  }
  if (!response.ok)
    throw new ApiError(
      result.error || "The request could not be completed.",
      response.status,
      result.fields || {},
    );
  if (result.csrf_token) csrfToken = result.csrf_token;
  return result;
}
