const STORAGE_KEY = 'theme';

export type Theme = 'light' | 'dark';

export function applyTheme(theme: Theme) {
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem(STORAGE_KEY, theme);
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) {
    meta.setAttribute('content', theme === 'dark' ? '#0f1115' : '#0b5fff');
  }
  const btn = document.getElementById('theme-toggle');
  if (btn) {
    const label =
      theme === 'dark'
        ? (btn.dataset.labelLight ?? 'Switch to light mode')
        : (btn.dataset.labelDark ?? 'Switch to dark mode');
    btn.setAttribute('aria-label', label);
    btn.setAttribute('title', label);
  }
}

export function initThemeToggle() {
  const btn = document.getElementById('theme-toggle');
  if (!btn) return;

  btn.addEventListener('click', () => {
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    applyTheme(isDark ? 'light' : 'dark');
  });
}

initThemeToggle();

const initial = document.documentElement.getAttribute('data-theme');
if (initial === 'light' || initial === 'dark') {
  applyTheme(initial);
}
