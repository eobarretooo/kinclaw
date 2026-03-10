async function fetchStatus() {
  try {
    const r = await fetch('/api/status');
    if (!r.ok) return;
    const data = await r.json();

    document.getElementById('status-badge').textContent =
      '● ' + (data.status || 'unknown');
    document.getElementById('stat-phase').textContent =
      (data.phase || 'idle').replace('_', ' ');
    document.getElementById('stat-proposals').textContent =
      data.proposals_today ?? '0';
    document.getElementById('stat-files').textContent =
      data.files ?? '—';
    document.getElementById('stat-lines').textContent =
      data.lines ?? '—';
  } catch (e) {
    console.error('Status fetch failed', e);
  }
}

async function fetchProposals() {
  try {
    const r = await fetch('/api/proposals/');
    if (!r.ok) return;
    const proposals = await r.json();
    const list = document.getElementById('proposals-list');

    if (!proposals.length) {
      list.innerHTML = '<p class="empty-msg">No pending proposals. KinClaw is working on the next cycle.</p>';
      return;
    }

    list.innerHTML = proposals.map(p => `
      <div class="proposal-card">
        <div class="proposal-title">${escapeHtml(p.title)}</div>
        <div class="proposal-meta">
          <span class="tag tag-${p.risk}">${p.risk}</span>
          <span>+${p.impact_pct}% impact</span>
          <span>${p.confidence_pct}% confidence</span>
          <span>${new Date(p.created_at).toLocaleString()}</span>
        </div>
      </div>
    `).join('');
  } catch (e) {
    console.error('Proposals fetch failed', e);
  }
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.appendChild(document.createTextNode(text));
  return div.innerHTML;
}

fetchStatus();
fetchProposals();
setInterval(fetchStatus, 10000);
setInterval(fetchProposals, 30000);
