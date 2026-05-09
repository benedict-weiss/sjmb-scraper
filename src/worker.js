import { parse } from 'node-html-parser';

const GROUP_ID = '257070261826425';
const MAX_SEEN = 500;

const KEYWORDS = [
  'wts',
  "st john's may ball",
  "john's may ball",
  'johns may ball',
  "john's mb",
  'johns mb',
  'johns ball',
  'sjmb',
  'ticket available',
  'for sale',
  'selling',
];

const SELL_INTENT = ['wts', 'selling', 'for sale', 'ticket available'];

export function buildCookieHeader(cookiesJson) {
  const cookies = JSON.parse(cookiesJson);
  return cookies.map(c => `${c.name}=${c.value}`).join('; ');
}

export function isLoggedOut(html) {
  const lower = html.toLowerCase();
  return lower.includes('log in') && lower.includes('create new account');
}

export function parsePosts(html) {
  const root = parse(html);
  const posts = [];
  const seenIds = new Set();

  for (const link of root.querySelectorAll('a[href*="/permalink/"]')) {
    const href = link.getAttribute('href') || '';
    const m = href.match(/\/permalink\/(\d+)\//);
    if (!m) continue;
    const postId = m[1];
    if (seenIds.has(postId)) continue;
    seenIds.add(postId);

    let container = link.parentNode;
    for (let i = 0; i < 6; i++) {
      if (!container) break;
      if (container.querySelector('strong')) break;
      container = container.parentNode;
    }
    if (!container) continue;

    const authorEl = container.querySelector('strong');
    const author = authorEl ? authorEl.text.trim() : 'Unknown';
    const abbrEl = container.querySelector('abbr');
    const timestamp = abbrEl ? abbrEl.text.trim() : '';
    const text = container.text.replace(/\s+/g, ' ').trim();
    const url = `https://www.facebook.com/groups/${GROUP_ID}/permalink/${postId}/`;

    posts.push({ id: postId, author, text, timestamp, url });
  }

  return posts;
}

export function matchesKeywords(text) {
  const lower = text.toLowerCase();
  const hasWtb = /\bwtb\b/.test(lower);
  const hasSellIntent = SELL_INTENT.some(si => lower.includes(si));
  if (hasWtb && !hasSellIntent) return null;
  for (const kw of KEYWORDS) {
    if (lower.includes(kw)) return kw;
  }
  return null;
}

export { GROUP_ID, MAX_SEEN };
