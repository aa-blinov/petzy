// Sets the theme class before the first paint, so a dark-theme user
// doesn't see a white flash. A file, not an inline script, so the page's
// Content-Security-Policy can forbid inline scripts altogether.
(function () {
  try {
    var theme = localStorage.getItem('theme') || 'system';
    var root = document.documentElement;
    var isDark = theme === 'dark' || (theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);
    if (isDark) {
      root.setAttribute('data-prefers-color-scheme', 'dark');
      root.classList.add('dark');
    } else {
      root.setAttribute('data-prefers-color-scheme', 'light');
      root.classList.remove('dark');
    }
  } catch (e) { }
})();
  
