import { PagefindUI } from '@pagefind/default-ui';
import '@pagefind/default-ui/css/ui.css';

type SearchTranslations = Record<string, string>;

const ERASE_SVG = `<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" focusable="false"><path fill="currentColor" d="M16.24 3.56a2 2 0 0 1 2.83 0l1.37 1.37a2 2 0 0 1 0 2.83L10.3 18.9a2 2 0 0 1-.94.52l-4.2 1a1 1 0 0 1-1.2-1.2l1-4.2a2 2 0 0 1 .52-.94L16.24 3.56Zm1.41 1.42-1.4-1.41-9.6 9.6-.5 2.1 2.1-.5 9.4-9.79ZM4 20h10v2H4v-2Z"/></svg>`;

export function initSiteSearch(opts: {
  translations: SearchTranslations;
  closeLabel: string;
  eraseLabel: string;
}): void {
  const ui = new PagefindUI({
    element: '#search',
    showSubResults: false,
    showImages: false,
    resetStyles: false,
    pageSize: 100,
    excerptLength: 18,
    translations: opts.translations,
  });

  const root = document.querySelector<HTMLElement>('.site-search');
  if (!root) return;

  const getInput = () =>
    root.querySelector<HTMLInputElement>('.pagefind-ui__search-input');
  const getClear = () =>
    root.querySelector<HTMLButtonElement>('.pagefind-ui__search-clear');

  const clearSearch = () => {
    const clearBtn = getClear();
    if (clearBtn) {
      clearBtn.click();
      return;
    }
    ui.triggerSearch('');
    const input = getInput();
    if (input) {
      input.value = '';
      input.dispatchEvent(new Event('input', { bubbles: true }));
      input.blur();
    }
  };

  const mountActions = () => {
    if (root.querySelector('.site-search-actions')) return true;
    const clearBtn = getClear();
    if (!clearBtn) return false;

    clearBtn.setAttribute('aria-label', opts.closeLabel);
    clearBtn.setAttribute('title', opts.closeLabel);
    clearBtn.textContent = '';

    const wrap = document.createElement('div');
    wrap.className = 'site-search-actions';

    const erase = document.createElement('button');
    erase.type = 'button';
    erase.className = 'site-search-erase';
    erase.setAttribute('aria-label', opts.eraseLabel);
    erase.setAttribute('title', opts.eraseLabel);
    erase.innerHTML = ERASE_SVG;
    erase.addEventListener('click', (event) => {
      event.preventDefault();
      event.stopPropagation();
      clearSearch();
    });

    clearBtn.replaceWith(wrap);
    wrap.append(erase, clearBtn);

    const syncVisibility = () => {
      const hasValue = Boolean(getInput()?.value.trim());
      wrap.classList.toggle('is-empty', !hasValue);
    };

    getInput()?.addEventListener('input', syncVisibility);
    clearBtn.addEventListener('click', () => {
      queueMicrotask(syncVisibility);
    });
    syncVisibility();
    return true;
  };

  // Pagefind mounts async — retry briefly until clear button exists.
  let tries = 0;
  const timer = window.setInterval(() => {
    tries += 1;
    if (mountActions() || tries > 40) window.clearInterval(timer);
  }, 50);

  document.addEventListener('pointerdown', (event) => {
    const target = event.target;
    if (!(target instanceof Node)) return;
    if (root.contains(target)) return;
    if (!getInput()?.value.trim()) return;
    clearSearch();
  });
}
