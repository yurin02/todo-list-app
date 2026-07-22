document.addEventListener("click", (event) => {
  const button = event.target.closest("[data-toggle-content]");
  if (!button) return;
  const wrap = button.previousElementSibling;
  const expanded = wrap.classList.toggle("is-expanded");
  button.textContent = expanded ? "閉じる" : "続きを読む";
});
