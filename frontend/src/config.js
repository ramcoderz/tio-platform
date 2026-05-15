/**
 * TiO Frontend Configuration
 * Centralizes host and port resolution to ensure the frontend always 
 * points to the correct backend API and WebSocket server.
 */

const getBaseConfig = () => {
  const isDev = import.meta.env.DEV;
  const protocol = window.location.protocol;
  
  // 1. Determine API Base
  let apiBase = import.meta.env.VITE_API_URL;
  if (!apiBase) {
    // Auto-detect based on current host
    const host = isDev && window.location.port === '5173'
      ? window.location.hostname + ':8000'
      : window.location.host;
    apiBase = `${protocol}//${host}`;
  }

  // 2. Determine WebSocket Base
  let wsBase = import.meta.env.VITE_WS_URL;
  if (!wsBase) {
    const wsProtocol = protocol === 'https:' ? 'wss:' : 'ws:';
    const host = apiBase.replace(/^https?:\/\//, '');
    wsBase = `${wsProtocol}//${host}`;
  }

  return {
    isDev,
    apiBase,
    wsBase
  };
};

export const config = getBaseConfig();
