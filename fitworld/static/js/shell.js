import { $, api, session, showError } from "./client.js";

document
  .querySelectorAll("[data-close]")
  .forEach((button) =>
    button.addEventListener("click", () => button.closest("dialog").close("cancel")),
  );
$("#app-signout").addEventListener("click", async () => {
  const button = $("#app-signout");
  button.disabled = true;
  try {
    await session;
    await api("logout", "POST", {});
    try {
      Object.keys(sessionStorage)
        .filter((key) => key.startsWith("fitworld:meal-draft:"))
        .forEach((key) => sessionStorage.removeItem(key));
    } catch {
      /* Signing out must also work when browser storage is unavailable. */
    }
    window.location.replace("/?login=1");
  } catch (error) {
    showError(error);
    button.disabled = false;
  }
});
session.catch((error) => showError(error));
