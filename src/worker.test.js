import { describe, it, expect } from 'vitest';
import { buildCookieHeader, isLoggedOut, parsePosts, matchesKeywords } from './worker.js';

const FIXTURE_HTML = `
<html><body>
<div>
  <div>
    <strong><a href="/sarah.jones">Sarah Jones</a></strong>
    <div>WTS 2 SJMB tickets £180 each dm me</div>
    <div><abbr>2 hours ago</abbr></div>
    <div><a href="/groups/123456789/permalink/987654321/?ref=m_notif">Full Story</a></div>
  </div>
  <div>
    <strong><a href="/alex.laddle">Alex Laddle</a></strong>
    <div>wtb 1 johns mb</div>
    <div><abbr>4 hours ago</abbr></div>
    <div><a href="/groups/123456789/permalink/111222333/?ref=m_notif">Full Story</a></div>
  </div>
</div>
</body></html>
`;

const LOGGED_OUT_HTML = `<html><body><div>Log In</div><div>Create New Account</div></body></html>`;

describe('buildCookieHeader', () => {
  it('builds a Cookie header string from JSON array', () => {
    const json = JSON.stringify([
      { name: 'c_user', value: '12345' },
      { name: 'xs', value: 'abc' },
    ]);
    expect(buildCookieHeader(json)).toBe('c_user=12345; xs=abc');
  });
});

describe('isLoggedOut', () => {
  it('returns true when login page indicators are present', () => {
    expect(isLoggedOut(LOGGED_OUT_HTML)).toBe(true);
  });

  it('returns false for normal group HTML', () => {
    expect(isLoggedOut(FIXTURE_HTML)).toBe(false);
  });

  it('returns false for React app HTML (staticcontentonly should not trigger)', () => {
    const reactHtml = '<html><body data-staticcontentonly="1">feed content</body></html>';
    expect(isLoggedOut(reactHtml)).toBe(false);
  });
});

describe('parsePosts', () => {
  it('returns two posts from fixture HTML', () => {
    expect(parsePosts(FIXTURE_HTML)).toHaveLength(2);
  });

  it('extracts post IDs', () => {
    const ids = parsePosts(FIXTURE_HTML).map(p => p.id);
    expect(ids).toContain('987654321');
    expect(ids).toContain('111222333');
  });

  it('extracts author from strong tag', () => {
    const authors = parsePosts(FIXTURE_HTML).map(p => p.author);
    expect(authors).toContain('Sarah Jones');
  });

  it('extracts timestamp from abbr tag', () => {
    const sarah = parsePosts(FIXTURE_HTML).find(p => p.author === 'Sarah Jones');
    expect(sarah.timestamp).toBe('2 hours ago');
  });

  it('extracts text containing post content', () => {
    const sarah = parsePosts(FIXTURE_HTML).find(p => p.author === 'Sarah Jones');
    expect(sarah.text).toContain('WTS');
    expect(sarah.text).toContain('SJMB');
  });

  it('builds full Facebook URL', () => {
    const sarah = parsePosts(FIXTURE_HTML).find(p => p.author === 'Sarah Jones');
    expect(sarah.url).toMatch(/^https:\/\/www\.facebook\.com\/groups\/\d+\/permalink\/987654321\//);
  });

  it('deduplicates posts with the same ID', () => {
    const html = FIXTURE_HTML.replace('987654321', '111222333');
    const posts = parsePosts(html);
    const ids = posts.map(p => p.id);
    expect(ids.length).toBe(new Set(ids).size);
  });

  it('returns empty array for HTML with no permalink links', () => {
    expect(parsePosts('<html><body>nothing here</body></html>')).toHaveLength(0);
  });
});

describe('matchesKeywords', () => {
  it('matches wts', () => {
    expect(matchesKeywords('WTS 2 SJMB tickets £180 each')).toBe('wts');
  });

  it('matches sjmb', () => {
    expect(matchesKeywords('Anyone want SJMB? Selling')).toBe('sjmb');
  });

  it('matches selling', () => {
    expect(matchesKeywords("selling my ticket, can't go anymore")).toBe('selling');
  });

  it("matches john's mb", () => {
    expect(matchesKeywords("john's mb ticket for sale")).toBe("john's mb");
  });

  it('excludes WTB-only posts', () => {
    expect(matchesKeywords('WTB 1 johns mb please')).toBeNull();
  });

  it('includes WTB post that also has sell intent', () => {
    expect(matchesKeywords('wtb or wts sjmb ticket')).toBe('wts');
  });

  it('returns null for unrelated posts', () => {
    expect(matchesKeywords('Anyone going to Pembroke May Ball?')).toBeNull();
  });

  it('returns first matching keyword (wts beats sjmb)', () => {
    expect(matchesKeywords('WTS SJMB ticket')).toBe('wts');
  });
});
