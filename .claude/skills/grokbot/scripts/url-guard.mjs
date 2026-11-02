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
