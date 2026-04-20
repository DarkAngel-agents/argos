// ARGOS UI v1 - argos.js
// Pas 5 sub-pas: secret redaction defense-in-depth.
// NOT a security boundary - just a leak filter for rendered output.
// Source: prompt to specialized chat, integrated chat 5, 7 April 2026.

function redactSecrets(text) {
  if (!text || typeof text !== 'string') return text;
  const REDACTED = '••••••';
  const patterns = [
    // Anthropic API keys: sk-ant-... followed by 40+ url-safe chars
    /sk-ant-[A-Za-z0-9_-]{40,}/g,
    // OpenAI keys: sk-... 20+ chars (excludes sk-ant- already handled above)
    /sk-(?!ant-)[A-Za-z0-9]{20,}/g,
    // GitHub tokens: ghp_ (personal), ghs_ (server), gho_ (oauth), ghu_ (user), ghr_ (refresh)
    /gh[psour]_[A-Za-z0-9]{36,}/g,
    // xAI / Grok keys
    /xai-[A-Za-z0-9]{20,}/g,
    // Google API keys: AIza prefix + 35 chars
    /AIza[0-9A-Za-z_-]{35}/g,
    // AWS access key IDs
    /AKIA[0-9A-Z]{16}/g,
    // AWS secret access keys (40 char base64-ish, only when in obvious context)
    /aws_secret[_a-z]*\s*[=:]\s*['"]?[A-Za-z0-9/+=]{40}['"]?/gi,
    // JWT tokens: header.payload.signature (3 base64url segments separated by dots)
    /eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}/g,
    // Bearer tokens in HTTP-style headers
    /Bearer\s+[A-Za-z0-9_\-.=]{20,}/g,
    // Slack tokens: xoxb-, xoxp-, xoxa-, xoxr-
    /xox[baprs]-[A-Za-z0-9-]{10,}/g,
    // Stripe live/test keys
    /(?:sk|pk|rk)_(?:live|test)_[A-Za-z0-9]{24,}/g,
    // SendGrid keys
    /SG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}/g,
    // Generic password/secret/token/key/api_key assignments in code or env-style
    /(?:password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|auth[_-]?token|client[_-]?secret|private[_-]?key)\s*[:=]\s*['"]?([^\s'"]{6,})['"]?/gi,
    // Word@digits pattern: alphanumeric word followed by @ and 3+ digits, word-bounded.
    // Catches "Anything@1234" style passwords without naming any specific word.
    // Avoids matching emails (which have @domain.tld, not @digits-only).
    /\b[A-Za-z][A-Za-z0-9]{2,}@\d{3,}\b/g,
    // Private key headers (PEM format)
    /-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----/g,
    // Generic high-entropy hex strings 32+ chars (md5/sha hashes of secrets)
    /\b[a-f0-9]{32,}\b/g,
    // Generic high-entropy base64 strings 40+ chars
    /\b(?=[A-Za-z0-9+/]*[A-Z])(?=[A-Za-z0-9+/]*[a-z])(?=[A-Za-z0-9+/]*\d)[A-Za-z0-9+/]{40,}={0,2}\b/g,
  ];
  let result = text;
  for (const re of patterns) {
    result = result.replace(re, REDACTED);
  }
  return result;
}

// Make available globally for Alpine components and future chat view.
window.redactSecrets = redactSecrets;

// === chatView() global function (extracted from chat-view.html) ===
function chatView() {
  return {
    convId: null,
    messages: [],
    draft: '',
    loading: true,
    sending: false,
    pendingSpinner: false,

    init() {
      const idStr = this.$el.getAttribute('data-conv-id');
      if (idStr) this.convId = parseInt(idStr);
      if (!this.convId) {
        console.error('[chat-view] no conv id on root element');
        this.loading = false;
        return;
      }
      this.loadMessages().then(() => this.checkPending());
      this.startSSE();
      // Cleanup SSE on element removal (Alpine destroy hook)
      this.$el._chatViewCleanup = () => this.stopSSE();
    },

    startSSE() {
      if (this._sse) return;
      try {
        this._sse = new EventSource('/api/stream/activity');
        this._sse.addEventListener('chat_message', (ev) => {
          try {
            const data = JSON.parse(ev.data);
            // Filter on this conversation only
            if (data.conversation_id !== this.convId) return;
            // Debounce refetch (max once per 500ms)
            if (this._refetchTimer) return;
            this._refetchTimer = setTimeout(() => {
              this._refetchTimer = null;
              this.loadMessages().then(() => {
                // If we got an assistant message, clear pending spinner
                const hasAssistant = this.messages.some(m => m.role === 'assistant');
                if (hasAssistant) this.pendingSpinner = false;
              });
            }, 500);
          } catch (e) {
            console.warn('[chat-view] sse parse fail:', e);
          }
        });
        this._sse.addEventListener('error', (e) => {
          console.warn('[chat-view] sse error, browser will auto-reconnect');
        });
      } catch (e) {
        console.error('[chat-view] sse init failed:', e);
      }
    },

    stopSSE() {
      if (this._sse) {
        this._sse.close();
        this._sse = null;
      }
      if (this._refetchTimer) {
        clearTimeout(this._refetchTimer);
        this._refetchTimer = null;
      }
    },

    async checkPending() {
      try {
        const r = await fetch(`/api/conversations/${this.convId}/pending`);
        if (!r.ok) return;
        const data = await r.json();
        if (data.pending) {
          // User message exists with pending=TRUE in DB - LLM still working
          // Append optimistic user row if not already in messages list
          const alreadyShown = this.messages.some(m => m.role === 'user' && m.content === data.content);
          if (!alreadyShown) {
            this.messages.push({
              id: 'pending-' + Date.now(),
              role: 'user',
              content: data.content,
              created_at: new Date().toISOString()
            });
          }
          this.pendingSpinner = true;
          this.$nextTick(() => this.scrollBottom());
        }
      } catch (e) {
        console.warn('[chat-view] pending check failed:', e);
      }
    },

    async loadMessages() {
      this.loading = true;
      try {
        const r = await fetch(`/api/conversations/${this.convId}/messages`);
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        this.messages = await r.json();
        this.$nextTick(() => this.scrollBottom());
      } catch (e) {
        console.error('[chat-view] load failed:', e);
      } finally {
        this.loading = false;
      }
    },

    async refresh() {
      this.pendingSpinner = false;
      await this.loadMessages();
      await this.checkPending();
    },

    async send() {
      const content = this.draft.trim();
      if (!content || this.sending) {
        return;
      }
      this.sending = true;
      this.pendingSpinner = true;
      // Optimistic append user msg
      this.messages.push({
        id: 'tmp-' + Date.now(),
        role: 'user',
        content: content,
        created_at: new Date().toISOString()
      });
      this.draft = '';
      this.$nextTick(() => this.scrollBottom());
      try {
        const r = await fetch('/api/messages', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ conversation_id: this.convId, content: content })
        });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        // Refetch authoritative list
        await this.loadMessages();
      } catch (e) {
        console.error('[chat-view] send failed:', e);
        alert('Eroare la trimitere: ' + e.message);
      } finally {
        this.sending = false;
        this.pendingSpinner = false;
      }
    },

    scrollBottom() {
      const c = this.$refs.msgContainer;
      if (c) c.scrollTop = c.scrollHeight;
    },

    renderMd(text) {
      if (!text) return '';
      // Apply secret redaction first (defense-in-depth)
      let s = (window.redactSecrets ? window.redactSecrets(text) : text);
      // HTML escape
      s = s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
           .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
      // Code blocks ```lang\ncode``` (must be before inline code)
      s = s.replace(/```(\w*)\n([\s\S]*?)```/g, (m, lang, code) =>
        '<pre class="md-code"><code>' + code.replace(/\n$/, '') + '</code></pre>');
      // Inline code `x`
      s = s.replace(/`([^`\n]+)`/g, '<code class="md-inline">$1</code>');
      // Bold **x**
      s = s.replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>');
      // Italic *x* (avoid matching ** already handled)
      s = s.replace(/(?<!\*)\*([^*\n]+)\*(?!\*)/g, '<em>$1</em>');
      // Links [text](url)
      s = s.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
      // Line breaks: preserve double newlines as paragraph breaks, single as <br>
      s = s.replace(/\n\n+/g, '</p><p>');
      s = s.replace(/\n/g, '<br>');
      s = '<p>' + s + '</p>';
      return s;
    },

    formatTs(ts) {
      if (!ts) return '';
      try {
        const d = new Date(ts);
        return d.toLocaleTimeString('ro-RO', { hour: '2-digit', minute: '2-digit' });
      } catch { return ''; }
    }
  };
}
// === END chatView ===
