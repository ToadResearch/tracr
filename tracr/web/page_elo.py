"""ELO Arena section: HTML and JavaScript for the ELO comparison tab."""

from __future__ import annotations


def elo_section_html() -> str:
    """Return the <section id='elo'> HTML block."""
    return """\
      <!-- ==================== ELO ==================== -->
      <section id="elo" class="section">
        <div class="flex items-end gap-2.5 mb-3 flex-wrap">
          <div class="flex flex-col gap-1 flex-1 min-w-[160px]">
            <label class="text-[10px] font-semibold text-g-muted uppercase tracking-widest">Job</label>
            <div class="dd relative" id="dd-elo-job">
              <button type="button" class="dd-trigger flex items-center justify-between w-full h-[34px] rounded-lg border border-g-border bg-g-surface text-g-text text-[13px] font-sans px-2.5 cursor-pointer hover:border-g-hover focus:outline-none focus:border-blue-500 transition-colors">
                <span class="dd-label truncate">Select...</span>
                <svg class="w-3.5 h-3.5 text-g-muted shrink-0 ml-2" fill="none" viewBox="0 0 20 20"><path stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" d="M6 8l4 4 4-4"/></svg>
              </button>
              <div class="dd-menu hidden absolute z-40 left-0 right-0 mt-1 rounded-lg border border-g-border bg-g-surface ring-1 ring-[var(--c-dd-ring)] dd-panel overflow-hidden">
                <div class="max-h-60 overflow-y-auto py-1"></div>
              </div>
            </div>
          </div>
          <div class="flex flex-col gap-1">
            <label class="text-[10px] font-semibold text-g-muted uppercase tracking-widest">&nbsp;</label>
            <div class="flex gap-0">
              <button id="elo-toggle-mode" class="h-[34px] px-3 rounded-l-lg border border-g-border bg-g-surface text-g-text text-xs font-medium cursor-pointer hover:bg-g-panel hover:border-g-hover transition-all">Raw</button>
              <button id="elo-next" class="h-[34px] px-3 rounded-r-lg border border-blue-500 bg-blue-500 text-white text-xs font-medium cursor-pointer hover:bg-blue-400 transition-all active:scale-95">Next Pair</button>
            </div>
          </div>
          <div id="elo-spinner" class="w-4 h-4 border-2 border-g-border border-t-blue-500 rounded-full hidden self-center mb-1 spin"></div>
        </div>

        <!-- Source image -->
        <div class="border border-g-border rounded-xl overflow-hidden mb-3 bg-g-subtle max-h-[40vh] overflow-y-auto">
          <img id="elo-image" class="block w-full h-auto" alt="Source PDF" />
        </div>

        <!-- Compare panels -->
        <div class="grid grid-cols-2 gap-3 mb-3 max-md:grid-cols-1">
          <div class="bg-g-surface border border-g-border rounded-xl flex flex-col overflow-hidden md-panel">
            <div class="flex items-center justify-between px-3.5 py-2.5 border-b border-g-border shrink-0">
              <span class="text-[11px] font-semibold text-g-muted uppercase tracking-wider" id="elo-left-title">Left</span>
            </div>
            <div class="flex-1 overflow-auto bg-g-subtle px-4 py-3 elo-compare-panels">
              <pre id="elo-left-raw" class="whitespace-pre-wrap break-words m-0 font-mono text-[12.5px] leading-relaxed text-g-dim"></pre>
              <div id="elo-left-rendered" class="md-rendered"></div>
            </div>
          </div>
          <div class="bg-g-surface border border-g-border rounded-xl flex flex-col overflow-hidden md-panel">
            <div class="flex items-center justify-between px-3.5 py-2.5 border-b border-g-border shrink-0">
              <span class="text-[11px] font-semibold text-g-muted uppercase tracking-wider" id="elo-right-title">Right</span>
            </div>
            <div class="flex-1 overflow-auto bg-g-subtle px-4 py-3 elo-compare-panels">
              <pre id="elo-right-raw" class="whitespace-pre-wrap break-words m-0 font-mono text-[12.5px] leading-relaxed text-g-dim"></pre>
              <div id="elo-right-rendered" class="md-rendered"></div>
            </div>
          </div>
        </div>

        <!-- Vote bar -->
        <div class="flex items-center gap-2 px-4 py-3 bg-g-surface border border-g-border rounded-xl flex-wrap">
          <span class="text-[11px] font-semibold text-g-muted uppercase tracking-wider mr-1">Vote</span>
          <button class="h-[30px] px-2.5 rounded-lg border border-green-500/25 bg-green-500/10 text-green-400 text-xs font-medium cursor-pointer hover:bg-green-500/20 hover:border-green-500/40 transition-all active:scale-95" data-vote="left_better">Left Better</button>
          <button class="h-[30px] px-2.5 rounded-lg border border-green-500/25 bg-green-500/10 text-green-400 text-xs font-medium cursor-pointer hover:bg-green-500/20 hover:border-green-500/40 transition-all active:scale-95" data-vote="right_better">Right Better</button>
          <button class="h-[30px] px-2.5 rounded-lg border border-g-border bg-g-panel text-g-text text-xs font-medium cursor-pointer hover:bg-g-raised hover:border-g-hover transition-all active:scale-95" data-vote="both_good">Both Good</button>
          <button class="h-[30px] px-2.5 rounded-lg border border-amber-500/25 bg-amber-500/10 text-amber-400 text-xs font-medium cursor-pointer hover:bg-amber-500/20 hover:border-amber-500/40 transition-all active:scale-95" data-vote="both_bad">Both Bad</button>
          <div class="flex-1"></div>
          <span id="elo-pair-meta" class="text-xs text-g-dim bg-g-raised px-2.5 py-1 rounded-md">--</span>
          <button class="h-[30px] px-2.5 rounded-lg border border-red-500/20 bg-red-500/10 text-red-400 text-xs font-medium cursor-pointer hover:bg-red-500/18 hover:border-red-500/40 transition-all active:scale-95" data-vote="skip">Skip</button>
        </div>

        <!-- Ratings -->
        <div class="mt-3 border border-g-border rounded-xl overflow-hidden bg-g-surface">
          <div class="px-3.5 py-2.5 border-b border-g-border text-[11px] font-semibold text-g-muted uppercase tracking-wider">ELO Ratings</div>
          <table class="w-full border-collapse text-[13px]">
            <thead>
              <tr>
                <th class="px-3.5 py-2 text-left text-[10px] font-semibold text-g-muted uppercase tracking-wider bg-g-subtle border-b border-g-border">Model</th>
                <th class="px-3.5 py-2 text-left text-[10px] font-semibold text-g-muted uppercase tracking-wider bg-g-subtle border-b border-g-border">Rating</th>
                <th class="px-3.5 py-2 text-left text-[10px] font-semibold text-g-muted uppercase tracking-wider bg-g-subtle border-b border-g-border">W</th>
                <th class="px-3.5 py-2 text-left text-[10px] font-semibold text-g-muted uppercase tracking-wider bg-g-subtle border-b border-g-border">L</th>
                <th class="px-3.5 py-2 text-left text-[10px] font-semibold text-g-muted uppercase tracking-wider bg-g-subtle border-b border-g-border">T</th>
                <th class="px-3.5 py-2 text-left text-[10px] font-semibold text-g-muted uppercase tracking-wider bg-g-subtle border-b border-g-border">Comparisons</th>
              </tr>
            </thead>
            <tbody id="elo-ratings-body"></tbody>
          </table>
        </div>
      </section>"""


def elo_js() -> str:
    """Return ELO-specific JavaScript: dropdown init, pair loading, voting, ratings."""
    return """\
      /* ============ Init ELO Dropdown ============ */
      const ddEloJob = new Dropdown(byId('dd-elo-job'), (val) => { state.elo.jobId = val; loadNextEloPair(); });
      byId('dd-elo-job')._dd = ddEloJob;

      /* ============ ELO Logic ============ */
      async function loadEloJobs() {
        setSpinner("elo-spinner", true);
        try {
          const data = await fetchJSON("/api/web/elo/jobs");
          state.elo.jobs = data.jobs || [];
          if (!state.elo.jobs.length) {
            ddEloJob.setItems([], 'job_id', 'title');
            return;
          }
          ddEloJob.setItems(state.elo.jobs, 'job_id', 'title');
          const first = ddEloJob.firstValue();
          ddEloJob.selectSilent(first);
          state.elo.jobId = first;
          await loadNextEloPair();
        } finally { setSpinner("elo-spinner", false); }
      }

      function renderEloMarkdown(pair) {
        const lr = byId("elo-left-raw"), lrn = byId("elo-left-rendered");
        const rr = byId("elo-right-raw"), rrn = byId("elo-right-rendered");
        lr.textContent = pair.left.markdown_raw || ""; rr.textContent = pair.right.markdown_raw || "";
        lrn.innerHTML = pair.left.markdown_html || ""; rrn.innerHTML = pair.right.markdown_html || "";
        const m = state.elo.rendered;
        lr.style.display = m ? "none" : "block"; rr.style.display = m ? "none" : "block";
        lrn.style.display = m ? "block" : "none"; rrn.style.display = m ? "block" : "none";
        byId("elo-toggle-mode").textContent = m ? "Rendered" : "Raw";
      }

      function renderRatings(ratings) {
        const body = byId("elo-ratings-body");
        body.innerHTML = "";
        if (!ratings || !ratings.length) {
          body.innerHTML = '<tr><td colspan="6" class="text-center text-g-muted py-4">No ratings yet</td></tr>';
          return;
        }
        for (const r of ratings) {
          const tr = document.createElement("tr");
          tr.className = "hover:bg-g-raised/50 transition-colors";
          tr.innerHTML = `<td class="px-3.5 py-2 text-g-bright font-medium border-b border-g-border">${r.model_label}</td>
            <td class="px-3.5 py-2 text-g-dim tabular-nums border-b border-g-border">${Number(r.rating).toFixed(0)}</td>
            <td class="px-3.5 py-2 text-g-dim tabular-nums border-b border-g-border">${r.wins}</td>
            <td class="px-3.5 py-2 text-g-dim tabular-nums border-b border-g-border">${r.losses}</td>
            <td class="px-3.5 py-2 text-g-dim tabular-nums border-b border-g-border">${r.ties}</td>
            <td class="px-3.5 py-2 text-g-dim tabular-nums border-b border-g-border">${r.comparisons}</td>`;
          body.appendChild(tr);
        }
      }

      async function loadNextEloPair() {
        if (!state.elo.jobId) return;
        setSpinner("elo-spinner", true);
        try {
          const data = await fetchJSON(`/api/web/elo/jobs/${encodeURIComponent(state.elo.jobId)}/next`);
          renderRatings(data.ratings || []);
          if (!data.has_pair) {
            state.elo.pair = null;
            byId("elo-pair-meta").textContent = data.message || "No pair available.";
            byId("elo-left-title").textContent = "Left"; byId("elo-right-title").textContent = "Right";
            byId("elo-image").src = "";
            byId("elo-left-raw").textContent = ""; byId("elo-right-raw").textContent = "";
            byId("elo-left-rendered").innerHTML = ""; byId("elo-right-rendered").innerHTML = "";
            return;
          }
          state.elo.pair = data.pair;
          byId("elo-image").src = data.pair.image_url;
          byId("elo-left-title").textContent = data.pair.left.model_label;
          byId("elo-right-title").textContent = data.pair.right.model_label;
          byId("elo-pair-meta").textContent = `${data.pair.pdf_label} p${data.pair.page_number}`;
          renderEloMarkdown(data.pair);
        } finally { setSpinner("elo-spinner", false); }
      }

      async function submitEloVote(choice) {
        if (!state.elo.jobId || !state.elo.pair) return;
        const p = state.elo.pair;
        await fetchJSON(`/api/web/elo/jobs/${encodeURIComponent(state.elo.jobId)}/vote`, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            choice, pdf_slug: p.pdf_slug, page_number: p.page_number,
            left_model_slug: p.left.model_slug, left_model_label: p.left.model_label, left_run_number: p.left.run_number,
            right_model_slug: p.right.model_slug, right_model_label: p.right.model_label, right_run_number: p.right.run_number,
          }),
        });
        showToast("Vote recorded", "success");
        await loadNextEloPair();
      }"""
