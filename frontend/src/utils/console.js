/**
 * Frontend Console Utility for TiO.
 * Provides a matching "indicator" style for browser console logs.
 */
const Console = {
  // Styles for browser console
  styles: {
    info: 'color: #3b82f6; font-weight: bold;',
    success: 'color: #22c55e; font-weight: bold;',
    warning: 'color: #eab308; font-weight: bold;',
    error: 'color: #ef4444; font-weight: bold;',
    critical: 'color: #a855f7; font-weight: bold;',
    stage: 'color: #06b6d4; font-weight: bold; background: #083344; padding: 1px 4px; border-radius: 2px;',
    prefix: 'color: #71717a; font-family: monospace;'
  },

  _log(level, style, message, stage = null) {
    const time = new Date().toLocaleTimeString();
    const prefix = `[${level}]${stage ? `[${stage.toUpperCase()}]` : ''}`;
    console.log(
      `%c[${time}] %c${prefix.padEnd(20)} %c${message}`,
      this.styles.prefix,
      style,
      'color: inherit;'
    );
  },

  info(message, stage = null) {
    this._log('INFO', this.styles.info, message, stage);
  },

  success(message, stage = null) {
    this._log('SUCCESS', this.styles.success, message, stage);
  },

  warning(message, stage = null) {
    this._log('WARNING', this.styles.warning, message, stage);
  },

  error(message, stage = null) {
    this._log('ERROR', this.styles.error, message, stage);
  },

  critical(message, stage = null) {
    this._log('CRITICAL', this.styles.critical, message, stage);
  },

  stage(stageName, message = "") {
    const time = new Date().toLocaleTimeString();
    const prefix = `[${stageName.toUpperCase()}]`;
    console.log(
      `%c[${time}] %c${prefix.padEnd(20)} %c${message}`,
      this.styles.prefix,
      this.styles.stage,
      'font-weight: bold;'
    );
  }
};

export default Console;
