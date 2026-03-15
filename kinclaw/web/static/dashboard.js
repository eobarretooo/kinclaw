const STATUS_POLL_INTERVAL = 15000;
let statusPollTimer = null;

function byId(id) {
  return document.getElementById(id);
}

function setText(id, value) {
  const node = byId(id);
  if (node) {
    node.textContent = value;
  }
}

function formatPhase(phase) {
  if (!phase) {
    return 'idle';
  }
  return String(phase).replace(/_/g, ' ');
}

function formatDate(value) {
  if (!value) {
    return 'Not reported';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

function renderNotes(data) {
  const notes = [
    `Mode: ${data.status || 'unknown'}`,
    `Phase: ${formatPhase(data.phase)}`,
    `Latest scan covered ${data.files ?? 0} files and ${data.lines ?? 0} lines.`,
  ];

  if (data.last_cycle_started_at) {
    notes.push(`Last cycle started ${formatDate(data.last_cycle_started_at)}.`);
  } else {
    notes.push('Last cycle start has not been reported yet.');
  }

  if ((data.proposal_summary?.active_total || 0) === 0) {
    notes.push('No active proposals are waiting in the queue.');
  } else {
    notes.push(`${data.proposal_summary.active_total} active proposal(s) currently visible in the queue.`);
  }

  const list = byId('runtime-notes');
  list.innerHTML = notes.map((item) => `<li>${escapeHtml(item)}</li>`).join('');
}

function renderStatus(data, source) {
  setText('status-badge', `Agent ${data.status || 'unknown'}`);
  setText('connection-badge', source === 'stream' ? 'live stream connected' : 'polling fallback active');
  setText('stat-phase', formatPhase(data.phase));
  setText('stat-cycle', formatDate(data.last_cycle_started_at));
  setText('stat-updated', new Date().toLocaleTimeString());
  setText('stat-proposals', String(data.proposals_today ?? 0));
  setText('stat-files', String(data.files ?? 0));
  setText('stat-lines', String(data.lines ?? 0));
  setText('stat-active-proposals', String(data.proposal_summary?.active_total ?? 0));
  setText('summary-pending', String(data.proposal_summary?.pending ?? 0));
  setText('summary-sent', String(data.proposal_summary?.sent ?? 0));
  setText('summary-total', String(data.proposal_summary?.active_total ?? 0));
  renderNotes(data);
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.appendChild(document.createTextNode(text));
  return div.innerHTML;
}

function renderProposals(proposals) {
  const list = byId('proposals-list');

  if (!proposals.length) {
    list.innerHTML = '<p class="empty-msg">No active proposals yet. The dashboard stays explicit until the next real proposal arrives.</p>';
    return;
  }

  list.innerHTML = proposals.map((proposal) => `
    <article class="proposal-card">
      <div class="proposal-header">
        <div class="proposal-title">${escapeHtml(proposal.title)}</div>
        <span class="tag">${escapeHtml(proposal.status)}</span>
      </div>
      <div class="proposal-meta">
        <div class="proposal-signals">
          <span class="tag tag-${escapeHtml(proposal.risk)}">${escapeHtml(proposal.risk)} risk</span>
          <span>${escapeHtml(String(proposal.impact_pct))}% impact</span>
          <span>${escapeHtml(String(proposal.confidence_pct))}% confidence</span>
        </div>
        <span>${escapeHtml(formatDate(proposal.created_at))}</span>
      </div>
    </article>
  `).join('');
}

async function fetchStatus(source) {
  const response = await fetch('/api/status');
  if (!response.ok) {
    throw new Error('status request failed');
  }
  const data = await response.json();
  renderStatus(data, source);
  renderProposals(data.recent_proposals || []);
}

async function refreshFromPoll() {
  try {
    await fetchStatus('poll');
  } catch (error) {
    console.error('Status refresh failed', error);
    setText('connection-badge', 'runtime temporarily unavailable');
  }
}

function startStream() {
  if (!window.EventSource) {
    return false;
  }

  const stream = new EventSource('/api/status/stream');

  stream.addEventListener('status', (event) => {
    const data = JSON.parse(event.data);
    renderStatus(data, 'stream');
    renderProposals(data.recent_proposals || []);
  });

  stream.onerror = () => {
    setText('connection-badge', 'stream interrupted, falling back to polling');
    stream.close();
    refreshFromPoll();
    if (statusPollTimer === null) {
      statusPollTimer = window.setInterval(refreshFromPoll, STATUS_POLL_INTERVAL);
    }
  };

  return true;
}

refreshFromPoll();

if (!startStream()) {
  statusPollTimer = window.setInterval(refreshFromPoll, STATUS_POLL_INTERVAL);
}
