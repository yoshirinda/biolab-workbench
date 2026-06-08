// Shared BioLab UI helpers for the five-workflow workbench.
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach((element) => {
    if (window.bootstrap?.Tooltip) {
      new window.bootstrap.Tooltip(element);
    }
  });
});
