export interface ParsedRoute {
  portal: 'landing' | 'admin' | 'user' | 'ceremony';
  electionId?: string;
  section?: string;
  ceremonyToken?: string;
  rawPath: string;
}

export function parseRoute(pathname: string): ParsedRoute {
  const clean = pathname.split('?')[0].split('#')[0] || '/';

  if (clean === '/') {
    return { portal: 'landing', rawPath: clean };
  }

  if (clean.startsWith('/ceremony')) {
    const parts = clean.split('/').filter(Boolean);
    const token = parts.length > 1 ? parts[1] : undefined;
    return { portal: 'ceremony', ceremonyToken: token, rawPath: clean };
  }

  if (clean.startsWith('/admin')) {
    // Check /admin/e/:electionId/:section?
    const adminE = clean.match(/^\/admin\/e\/([^/]+)(?:\/([^/]+))?/);
    if (adminE) {
      return {
        portal: 'admin',
        electionId: adminE[1],
        section: adminE[2] || 'overview',
        rawPath: clean,
      };
    }
    // Check /admin/:section?
    const adminSec = clean.match(/^\/admin(?:\/([^/]+))?/);
    return {
      portal: 'admin',
      section: adminSec && adminSec[1] ? adminSec[1] : 'overview',
      rawPath: clean,
    };
  }

  if (clean.startsWith('/user') || clean === '/register' || clean === '/vote' || clean === '/audit') {
    if (clean === '/user/login') {
      return { portal: 'user', section: 'login', rawPath: clean };
    }
    if (clean === '/user/register' || clean === '/register') {
      return { portal: 'user', section: 'register', rawPath: clean };
    }
    // Check /user/e/:electionId/:section?
    const userE = clean.match(/^\/user\/e\/([^/]+)(?:\/([^/]+))?/);
    if (userE) {
      return {
        portal: 'user',
        electionId: userE[1],
        section: userE[2] || 'overview',
        rawPath: clean,
      };
    }
    // Check /user/:section? or legacy shortcuts
    const sec = clean === '/vote' ? 'vote' : clean === '/audit' ? 'audit' : clean.replace('/user/', '') || 'overview';
    return {
      portal: 'user',
      section: sec,
      rawPath: clean,
    };
  }

  return { portal: 'landing', rawPath: clean };
}
