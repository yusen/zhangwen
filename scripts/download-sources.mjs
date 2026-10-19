// Install-process settings only; never write npm/pip user configuration.
import { devNull } from 'node:os';
import { resolve } from 'node:path';

export function dependencyNetwork(globalConfig = resolve(import.meta.dirname, '../.runtime/npm-empty-global.conf')) {
  return {
    env: {
      PIP_CONFIG_FILE: devNull,
      PIP_INDEX_URL: 'https://pypi.tuna.tsinghua.edu.cn/simple',
      PIP_EXTRA_INDEX_URL: '', PIP_TRUSTED_HOST: '',
      npm_config_registry: 'https://registry.npmmirror.com',
      npm_config_replace_registry_host: 'always',
      npm_config_userconfig: devNull, npm_config_globalconfig: globalConfig,
      npm_config_update_notifier: 'false', npm_config_maxsockets: '5',
      npm_config_fetch_retries: '3', npm_config_fetch_retry_mintimeout: '2000',
      npm_config_fetch_retry_maxtimeout: '20000',
    },
    npmArgs: ['--registry=https://registry.npmmirror.com', '--replace-registry-host=always'],
  };
}

export function equivalentRegistryUrl(left, right) {
  if (left === right) return true;
  try {
    const a = new URL(left), b = new URL(right);
    const allowed = new Set(['registry.npmjs.org', 'registry.npmmirror.com']);
    return [a, b].every(u => u.protocol === 'https:' && allowed.has(u.host) && !u.username && !u.password)
      && a.pathname === b.pathname && a.search === b.search && a.hash === b.hash;
  } catch { return false; }
}
