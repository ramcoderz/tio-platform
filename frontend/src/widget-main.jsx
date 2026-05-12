import React from 'react';
import ReactDOM from 'react-dom/client';
import ChatWidget from './components/ChatWidget';
import './styles.css'; // Global styles for base animations and scrollbars

/**
 * TiO Embeddable Widget Entry Point
 * 
 * Usage:
 * <script src="https://your-tio-instance.com/widget.js"></script>
 * <script>
 *   window.initTiO({
 *     chatbotId: 1,
 *     title: 'Support AI',
 *     accentColor: '#00C6FF'
 *   });
 * </script>
 */

const initTiO = (config = {}) => {
  // Prevent double initialization
  if (document.getElementById('tio-widget-root')) return;

  const container = document.createElement('div');
  container.id = 'tio-widget-root';
  document.body.appendChild(container);

  const root = ReactDOM.createRoot(container);
  root.render(
    <React.StrictMode>
      <ChatWidget 
        chatbotId={config.chatbotId}
        domain={config.domain || 'general'}
        title={config.title || 'TiO Assistant'}
        apiBase={config.apiBase || window.location.origin}
        accentColor={config.accentColor || '#00C6FF'}
      />
    </React.StrictMode>
  );
};

// Expose to window for global access
window.initTiO = initTiO;

// Auto-init if data attributes are present on the script tag
const currentScript = document.currentScript;
if (currentScript) {
  const chatbotId = currentScript.getAttribute('data-chatbot-id');
  if (chatbotId) {
    initTiO({
      chatbotId: parseInt(chatbotId),
      title: currentScript.getAttribute('data-title'),
      accentColor: currentScript.getAttribute('data-accent'),
    });
  }
}
