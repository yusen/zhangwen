export const FIRST_START_QUERY_PARAMETER = 'firstStart';

export function readFirstStartQuery(locationLike = {}) {
  const parameters = new URLSearchParams(String(locationLike.search || ''));
  const present = parameters.has(FIRST_START_QUERY_PARAMETER);
  const requested = parameters.get(FIRST_START_QUERY_PARAMETER) === '1';
  if (!present) {
    return { present: false, requested: false, cleanUrl: '' };
  }

  parameters.delete(FIRST_START_QUERY_PARAMETER);
  const query = parameters.toString();
  return {
    present: true,
    requested,
    cleanUrl: (locationLike.pathname || '/')
      + (query ? '?' + query : '')
      + (locationLike.hash || ''),
  };
}

export function shouldOpenModelSourceOnFirstStart({ requested = false, llmStatus = '' } = {}) {
  return requested && llmStatus === 'not_configured';
}
