// URL guard for the grokbot transport, in its own module so tests import the SHIPPED
// logic rather than a copy of it. Importing grok_chrome.mjs would run the transport.
export const isBotUrl = (u) => {
  try {
    const t = new URL(u);
    return t.origin === 'https://grok.com' && /^\/bot\/[\w-]+$/.test(t.pathname);
  } catch {
    return false;
  }
};

// The landing page must be the REQUESTED bot path, exactly. A prefix or origin-only check
// accepts a redirect to /bot/other or /bot/<id>/settings and would print that page as the
// conversation.
export const landedOnRequested = (requested, landedHref) => {
  try {
    const l = new URL(landedHref);
    return l.origin === 'https://grok.com' && l.pathname === new URL(requested).pathname;
  } catch {
    return false;
  }
};

// The list mode may open the grok.com home page or a bot page, nothing else.
export const isAllowedListUrl = (u) => {
  if (isBotUrl(u)) return true;
  try {
    const t = new URL(u);
    return t.origin === 'https://grok.com' && (t.pathname === '/' || t.pathname === '');
  } catch {
    return false;
  }
};

// A link found anywhere on an allowed page is NOT proof of account ownership: a bot
// message can render a link to another bot. `list` therefore extracts only from the
// account's bot navigation, and reports results as candidates rather than as a resolved
// inventory. These are the selectors it scopes to.
export const BOT_NAV_SELECTORS = ['nav a[href*="/bot/"]', '[role="navigation"] a[href*="/bot/"]'];
