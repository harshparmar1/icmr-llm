/**
 * ICMR-STW 3D Conversational Symptom & Clinical Workflow Chatbot
 * Client-side Controller & 3D Spatial Interactions
 */

document.addEventListener('DOMContentLoaded', () => {
  // Elements
  const chatMessages = document.getElementById('chatMessages');
  const chatForm = document.getElementById('chatForm');
  const messageInput = document.getElementById('messageInput');
  const vitalsInput = document.getElementById('vitalsInput');
  const sendBtn = document.getElementById('sendBtn');
  const typingIndicator = document.getElementById('typingIndicator');
  const clearChatBtn = document.getElementById('clearChatBtn');
  const historyBtn = document.getElementById('historyBtn');
  const historyModal = document.getElementById('historyModal');
  const closeModalBtn = document.getElementById('closeModalBtn');
  const historyList = document.getElementById('historyList');
  const presetChips = document.querySelectorAll('.preset-chip-btn');

  // Conversational state
  let conversationHistory = [];

  init();

  function init() {
    setupInputHandling();
    setupPresetChips();
    setupHistoryModal();
  }

  // Auto-resizing textarea and keyboard shortcuts
  function setupInputHandling() {
    messageInput.addEventListener('input', () => {
      messageInput.style.height = 'auto';
      messageInput.style.height = Math.min(messageInput.scrollHeight, 120) + 'px';
    });

    messageInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        chatForm.dispatchEvent(new Event('submit'));
      }
    });

    chatForm.addEventListener('submit', handleChatSubmit);

    clearChatBtn.addEventListener('click', () => {
      conversationHistory = [];
      const rows = chatMessages.querySelectorAll('.message-row');
      rows.forEach((row, idx) => {
        if (idx > 0) row.remove(); // keep welcome message
      });
      showToast('Conversation reset.');
    });
  }

  // Preset symptom chips
  function setupPresetChips() {
    presetChips.forEach(chip => {
      chip.addEventListener('click', () => {
        const query = chip.getAttribute('data-query');
        const vitals = chip.getAttribute('data-vitals');

        messageInput.value = query;
        if (vitals && vitalsInput) {
          vitalsInput.value = vitals;
        }
        messageInput.style.height = 'auto';
        messageInput.style.height = Math.min(messageInput.scrollHeight, 120) + 'px';
        messageInput.focus();

        // Trigger submit
        chatForm.dispatchEvent(new Event('submit'));
      });
    });
  }

  // Submit message to /api/chat
  async function handleChatSubmit(e) {
    e.preventDefault();
    const text = messageInput.value.trim();
    if (!text) return;

    const vitals = vitalsInput ? vitalsInput.value.trim() : null;

    // 1. Append user message
    appendUserMessage(text);
    messageInput.value = '';
    messageInput.style.height = 'auto';

    // 2. Loading state
    sendBtn.disabled = true;
    typingIndicator.classList.add('active');
    scrollToBottom();

    try {
      const payload = {
        message: text,
        history: conversationHistory.slice(-6),
        patient_vitals: vitals || null
      };

      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to process inquiry.');
      }

      const data = await res.json();

      // Record turns
      conversationHistory.push({ role: 'user', content: text });
      conversationHistory.push({ role: 'assistant', content: data.reply });

      // 3. Render Assistant Response
      appendAssistantMessage(data);
    } catch (err) {
      console.error(err);
      appendErrorMessage(err.message);
      showToast(`Error: ${err.message}`);
    } finally {
      typingIndicator.classList.remove('active');
      sendBtn.disabled = false;
      scrollToBottom();
    }
  }

  // Render User Message
  function appendUserMessage(text) {
    const row = document.createElement('div');
    row.className = 'message-row user';
    row.innerHTML = `
      <div class="bubble-avatar user">
        <i class="fa-solid fa-user"></i>
      </div>
      <div class="bubble-content">
        <div class="bubble-user-card">
          ${escapeHtml(text)}
        </div>
      </div>
    `;
    chatMessages.appendChild(row);
    scrollToBottom();
  }

  // Render Assistant Message with 3D Workflow Cards
  function appendAssistantMessage(data) {
    const row = document.createElement('div');
    row.className = 'message-row ai';

    // Determine Urgency Badge
    const urgency = (data.urgency_level || 'ROUTINE').toUpperCase();
    let urgencyBadgeClass = 'urgency-routine';
    let urgencyIcon = 'fa-circle-check';
    if (urgency === 'EMERGENCY') {
      urgencyBadgeClass = 'urgency-emergency';
      urgencyIcon = 'fa-triangle-exclamation';
    } else if (urgency === 'URGENT') {
      urgencyBadgeClass = 'urgency-urgent';
      urgencyIcon = 'fa-clock';
    }

    // Immediate actions pills
    let actionsHtml = '';
    if (data.immediate_actions && data.immediate_actions.length > 0) {
      actionsHtml = `
        <div class="immediate-actions-row">
          ${data.immediate_actions.map(act => `
            <span class="action-pill"><i class="fa-solid fa-hand-holding-medical"></i> ${renderMarkdown(act)}</span>
          `).join('')}
        </div>
      `;
    }

    // Red Flags Box
    let redFlagsHtml = '';
    if (data.red_flags && data.red_flags.length > 0) {
      redFlagsHtml = `
        <div class="red-flags-card">
          <div class="red-flags-title">
            <i class="fa-solid fa-circle-exclamation"></i> Critical Red Flag Warning Signs
          </div>
          <ul>
            ${data.red_flags.map(rf => `<li>${renderMarkdown(rf)}</li>`).join('')}
          </ul>
        </div>
      `;
    }

    // Step-by-Step ICMR Workflow Accordion
    let workflowHtml = '';
    if (data.workflow_steps && data.workflow_steps.length > 0) {
      workflowHtml = `
        <div class="workflow-accordion">
          <div class="accordion-title">
            <i class="fa-solid fa-route"></i> ICMR Standard Treatment Workflow Stages
          </div>
          <div class="workflow-cards-container">
            ${data.workflow_steps.map(s => {
              const phaseClass = getPhaseClass(s.phase);
              return `
                <div class="workflow-stage-3d">
                  <div class="stage-num-badge">${s.step_number}</div>
                  <div class="stage-body">
                    <div class="stage-meta">
                      <span class="phase-tag ${phaseClass}">${escapeHtml(s.phase || 'Management')}</span>
                      <span class="stage-page"><i class="fa-solid fa-book-open"></i> ICMR Page ${s.page_reference || 1}</span>
                    </div>
                    <div class="stage-title">${renderInlineMarkdown(s.title)}</div>
                    <div class="stage-desc">${formatClinicalText(s.description)}</div>
                  </div>
                </div>
              `;
            }).join('')}
          </div>
        </div>
      `;
    }

    // Authoritative Citations Footer
    let citationsCount = data.evidence ? data.evidence.length : 0;
    let stwTitle = data.relevant_stw && data.relevant_stw !== 'None' ? data.relevant_stw : 'ICMR Standard Treatment Workflow';

    row.innerHTML = `
      <div class="bubble-avatar ai">
        <i class="fa-solid fa-brain"></i>
      </div>
      <div class="bubble-content">
        <div class="bubble-ai-card">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <span class="urgency-badge-3d ${urgencyBadgeClass}">
              <i class="fa-solid ${urgencyIcon}"></i> Triage: ${urgency}
            </span>
            <span style="font-size: 0.72rem; color: var(--text-muted);">
              <i class="fa-solid fa-shield-virus"></i> ${escapeHtml(data.condition_matched || 'Clinical Guideline')}
            </span>
          </div>

          <div class="guidance-text">
            ${renderMarkdown(data.reply)}
          </div>

          ${actionsHtml}
          ${redFlagsHtml}
          ${workflowHtml}

          <div class="citations-footer">
            <div class="guideline-source-link">
              Source: <strong>${escapeHtml(stwTitle)}</strong> (${citationsCount} evidence excerpts)
            </div>
            <button type="button" class="btn-copy-bubble copy-btn">
              <i class="fa-regular fa-copy"></i> Copy Plan
            </button>
          </div>
        </div>
      </div>
    `;

    // Copy event listener
    const copyBtn = row.querySelector('.copy-btn');
    if (copyBtn) {
      copyBtn.addEventListener('click', () => {
        copyWorkflowReport(data);
      });
    }

    chatMessages.appendChild(row);
    scrollToBottom();
  }

  // Error Bubble
  function appendErrorMessage(errorText) {
    const row = document.createElement('div');
    row.className = 'message-row ai';
    row.innerHTML = `
      <div class="bubble-avatar ai" style="border-color: var(--crimson-alert);">
        <i class="fa-solid fa-triangle-exclamation" style="color: var(--crimson-alert);"></i>
      </div>
      <div class="bubble-content">
        <div class="bubble-ai-card" style="border-color: rgba(239, 68, 68, 0.3);">
          <span class="urgency-badge-3d urgency-emergency">
            <i class="fa-solid fa-triangle-exclamation"></i> System Advisory
          </span>
          <div class="guidance-text" style="color: #fca5a5;">
            An error occurred while synthesizing guidance: ${escapeHtml(errorText)}. Please try again or rephrase your symptoms.
          </div>
        </div>
      </div>
    `;
    chatMessages.appendChild(row);
    scrollToBottom();
  }

  function getPhaseClass(phase) {
    if (!phase) return 'phase-management';
    const lower = phase.toLowerCase();
    if (lower.includes('lifestyle') || lower.includes('non-pharm')) return 'phase-lifestyle';
    if (lower.includes('assess')) return 'phase-assessment';
    if (lower.includes('investig')) return 'phase-investigation';
    if (lower.includes('manage') || lower.includes('treat')) return 'phase-management';
    if (lower.includes('refer')) return 'phase-referral';
    if (lower.includes('follow')) return 'phase-followup';
    return 'phase-management';
  }

  function flattenAnyText(val) {
    if (val === null || val === undefined) return '';
    if (typeof val === 'string') {
      const trimmed = val.trim();
      if (trimmed.startsWith('{') && trimmed.endsWith('}')) {
        try {
          const parsed = JSON.parse(trimmed);
          return flattenAnyText(parsed);
        } catch (e) {}
      }
      return trimmed;
    }
    if (typeof val === 'object') {
      if (Array.isArray(val)) {
        return val.map(x => flattenAnyText(x)).filter(Boolean).join('\n• ');
      }
      // Pattern: message + explanation
      if (val.message && val.explanation) {
        const msg = flattenAnyText(val.message);
        const exp = flattenAnyText(val.explanation);
        return exp ? `${msg}\n\n${exp}` : msg;
      }
      // Pattern: action + reason
      if (val.action && val.reason) {
        const act = flattenAnyText(val.action);
        const rsn = flattenAnyText(val.reason);
        return rsn ? `${act} (Note: ${rsn})` : act;
      }
      // Pattern: test/symptom + purpose
      if ((val.test || val.symptom) && val.purpose) {
        const item = flattenAnyText(val.test || val.symptom);
        const purp = flattenAnyText(val.purpose);
        return purp ? `${item}: ${purp}` : item;
      }
      // General object
      const parts = [];
      for (const [k, v] of Object.entries(val)) {
        const label = k.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
        const flatV = flattenAnyText(v);
        if (flatV) {
          parts.push(`${label}: ${flatV}`);
        }
      }
      return parts.join('\n\n');
    }
    return String(val);
  }

  function renderInlineMarkdown(str) {
    if (!str) return '';
    let safe = escapeHtml(flattenAnyText(str));
    // Convert **bold** to <strong>bold</strong>
    safe = safe.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    // Convert *italic* to <em>italic</em>
    safe = safe.replace(/\*([^*\n]+)\*/g, '<em>$1</em>');
    // Convert `code` to <code>code</code>
    safe = safe.replace(/`([^`]+)`/g, '<code>$1</code>');
    return safe;
  }

  function formatClinicalText(rawText) {
    if (!rawText) return '';

    let text = flattenAnyText(rawText);

    // Check if text already has line breaks with list markers
    const rawLines = text.split('\n').map(l => l.trim()).filter(Boolean);
    const hasListMarkers = rawLines.some(l => /^[•\-\*]|\d+\./.test(l));

    if (hasListMarkers) {
      const listItems = rawLines.map(l => {
        const clean = l.replace(/^[•\-\*]\s*|^\d+\.\s*/, '');
        return `<li><span class="clinical-bullet-icon"><i class="fa-solid fa-circle-check"></i></span><span>${renderInlineMarkdown(clean)}</span></li>`;
      }).join('');
      return `<ul class="clinical-step-list">${listItems}</ul>`;
    }

    // Check for colon introducing a list of recommendations
    // e.g. 'Concurrent with medication, reinforce these ICMR-recommended lifestyle changes to improve BP control: Limit salt to <5g/day, engage in 30 minutes...'
    const colonIdx = text.indexOf(':');
    if (colonIdx !== -1 && colonIdx < text.length - 25) {
      const prefix = text.slice(0, colonIdx + 1).trim();
      const body = text.slice(colonIdx + 1).trim();

      // Split on commas followed by actions, or periods followed by uppercase
      // Note: use `;\s+` so entity semicolons are never split
      const rawItems = body
        .split(/,\s*(?:and\s+)?|\.\s+(?=[A-Z])|;\s+/)
        .map(t => t.trim().replace(/\.$/, ''))
        .filter(t => t.length > 3);

      if (rawItems.length >= 2) {
        const listItems = rawItems.map(it => {
          const clean = it.charAt(0).toUpperCase() + it.slice(1);
          return `<li><span class="clinical-bullet-icon"><i class="fa-solid fa-circle-check"></i></span><span>${renderInlineMarkdown(clean)}.</span></li>`;
        }).join('');
        return `<p class="clinical-lead">${renderInlineMarkdown(prefix)}</p><ul class="clinical-step-list">${listItems}</ul>`;
      }
    }

    // Check if multiple sentences describe distinct clinical actions
    const sentences = text
      .split(/\.\s+(?=[A-Z])/)
      .map(s => s.trim())
      .filter(Boolean);

    if (sentences.length >= 2 && text.length > 110) {
      const listItems = sentences.map(s => {
        const clean = s.replace(/\.$/, '');
        return `<li><span class="clinical-bullet-icon"><i class="fa-solid fa-circle-check"></i></span><span>${renderInlineMarkdown(clean)}.</span></li>`;
      }).join('');
      return `<ul class="clinical-step-list">${listItems}</ul>`;
    }

    return `<p class="clinical-text">${renderInlineMarkdown(text)}</p>`;
  }

  function renderMarkdown(rawText) {
    if (!rawText) return '';
    const text = flattenAnyText(rawText);

    // If text has list lines
    const paragraphs = text.split(/\n\n+/);
    return paragraphs.map(p => {
      const lines = p.split('\n').map(l => l.trim()).filter(Boolean);
      const isList = lines.some(l => /^[•\-\*]|\d+\./.test(l));
      if (isList) {
        return '<ul class="clinical-step-list">' + lines.map(l => {
          const clean = l.replace(/^[•\-\*]\s*|^\d+\.\s*/, '');
          return `<li><span class="clinical-bullet-icon"><i class="fa-solid fa-circle-check"></i></span><span>${renderInlineMarkdown(clean)}</span></li>`;
        }).join('') + '</ul>';
      }
      return `<p style="margin-bottom: 8px; line-height: 1.65;">${renderInlineMarkdown(p)}</p>`;
    }).join('');
  }

  function copyWorkflowReport(data) {
    let report = `🏥 ICMR CLINICAL WORKFLOW REPORT\n`;
    report += `==============================================\n`;
    report += `Triage Urgency:  ${data.urgency_level || 'ROUTINE'}\n`;
    report += `Condition:       ${data.condition_matched || 'N/A'} (${data.specialty || 'General'})\n`;
    report += `Guideline STW:   ${data.relevant_stw || 'ICMR STW'}\n\n`;
    report += `CLINICAL GUIDANCE:\n${flattenAnyText(data.reply)}\n\n`;

    if (data.immediate_actions && data.immediate_actions.length > 0) {
      report += `IMMEDIATE ACTIONS:\n`;
      data.immediate_actions.forEach(a => report += `• ${flattenAnyText(a)}\n`);
      report += `\n`;
    }

    if (data.red_flags && data.red_flags.length > 0) {
      report += `⚠️ CRITICAL RED FLAGS:\n`;
      data.red_flags.forEach(rf => report += `* ${flattenAnyText(rf)}\n`);
      report += `\n`;
    }

    if (data.workflow_steps && data.workflow_steps.length > 0) {
      report += `STEP-BY-STEP WORKFLOW:\n`;
      data.workflow_steps.forEach(s => {
        report += `[Step ${s.step_number}] ${s.phase} (Page ${s.page_reference}): ${flattenAnyText(s.title)}\n`;
        report += `Action: ${flattenAnyText(s.description)}\n\n`;
      });
    }

    report += `DISCLAIMER: ${data.safety_notice || 'Consult a qualified healthcare professional.'}\n`;

    navigator.clipboard.writeText(report);
    showToast('Clinical workflow plan copied to clipboard!');
  }

  function setupHistoryModal() {
    historyBtn.addEventListener('click', async () => {
      historyModal.classList.add('active');
      historyList.innerHTML = '<p style="text-align: center; color: var(--text-secondary); padding: 20px;"><i class="fa-solid fa-spinner fa-spin"></i> Loading Supabase logs...</p>';

      try {
        const res = await fetch('/api/recent?limit=12');
        if (!res.ok) throw new Error('Could not retrieve audit history.');
        const items = await res.json();

        if (items.length === 0) {
          historyList.innerHTML = '<p style="text-align: center; color: var(--text-muted); padding: 20px;">No audit queries recorded yet.</p>';
          return;
        }

        historyList.innerHTML = '';
        items.forEach(it => {
          const card = document.createElement('div');
          card.className = 'history-card';
          const dStr = it.created_at ? new Date(it.created_at).toLocaleString() : 'Recent';
          card.innerHTML = `
            <div style="font-weight: 500; font-size: 0.88rem; color: var(--text-primary); margin-bottom: 4px;">
              ${escapeHtml(it.query)}
            </div>
            <div style="display: flex; justify-content: space-between; font-size: 0.74rem; color: var(--text-muted);">
              <span><i class="fa-solid fa-microchip"></i> ${it.llm_provider || 'mistral'} (${it.latency_ms}ms)</span>
              <span><i class="fa-regular fa-clock"></i> ${dStr}</span>
            </div>
          `;
          card.addEventListener('click', () => {
            messageInput.value = it.query.replace('[CHATBOT]', '').trim();
            historyModal.classList.remove('active');
            messageInput.focus();
          });
          historyList.appendChild(card);
        });
      } catch (err) {
        historyList.innerHTML = `<p style="text-align: center; color: var(--crimson-alert); padding: 20px;">Failed to load logs: ${err.message}</p>`;
      }
    });

    closeModalBtn.addEventListener('click', () => historyModal.classList.remove('active'));
    historyModal.addEventListener('click', (e) => {
      if (e.target === historyModal) historyModal.classList.remove('active');
    });
  }

  function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function showToast(msg) {
    const container = document.getElementById('toastContainer');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.innerHTML = `<i class="fa-solid fa-circle-check" style="color: var(--emerald-live);"></i> <span>${escapeHtml(msg)}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
      toast.style.transition = 'all 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, 3500);
  }

  function escapeHtml(str) {
    if (!str) return '';
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }
});
