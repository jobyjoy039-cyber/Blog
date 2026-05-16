
# ===========================================================================
# AUTHORITY ARTICLE PIPELINE  (19 agents · 5 phases · 10,000–15,000 words)
# ===========================================================================
# NOTE: AUTHORITY_PHASES and AUTHORITY_STEPS are injected by build_authority.py
# This file contains only the page-builder function, route, and endpoint.


def _build_authority_page():
    """Render the 19-agent, 5-phase authority article pipeline page."""

    ATOTAL = len(AUTHORITY_STEPS)
    GATE_BOUNDARY = {6: 1, 7: 2, 10: 3, 16: 4, 19: 5}
    DELIVERABLES = [
        ("Full Article",   "article_polished",  "authority_article.md"),
        ("SEO Package",    "seo_audit",         "authority_seo.md"),
        ("Appendices",     "appendices",        "authority_appendices.md"),
        ("CMS Package",    "cms_package",       "authority_cms.md"),
        ("Social Package", "social_package",    "authority_social.md"),
        ("Launch Plan",    "launch_plan",       "authority_launch.md"),
    ]

    # ── Sidebar nav ──────────────────────────────────────────────────────────
    nav_items = ""
    prev_phase = 0
    for s in AUTHORITY_STEPS:
        n  = s["step"]
        ph = s["phase"]
        if ph != prev_phase:
            ph_data = AUTHORITY_PHASES[ph - 1]
            nav_items += (
                '<div class="p-phase-header" style="border-left:3px solid ' +
                ph_data["color"] + '">' + ph_data["icon"] +
                ' Phase ' + str(ph) + ': ' + ph_data["label"] + '</div>'
            )
            prev_phase = ph
        nav_items += (
            '<div class="p-nav-item" id="p-nav-' + str(n) +
            '" data-step="' + str(n) + '" onclick="showStep(' + str(n) + ')">' +
            '<span class="p-nav-num" id="p-nav-num-' + str(n) + '">' + str(n) + '</span>' +
            '<div class="p-nav-info"><div class="p-nav-label">' +
            s["icon"] + ' ' + s["label"] + '</div>' +
            '<div class="p-nav-agent">' + s["agent"] + '</div></div>' +
            '<span class="p-nav-check" id="p-nav-check-' + str(n) + '"></span></div>'
        )
    nav_items += (
        '<div class="p-phase-header" style="border-left:3px solid #3fb950">'
        '&#128230; Phase 6: Final Deliverables</div>'
        '<div class="p-nav-item" id="p-nav-20" data-step="20" onclick="showStep(20)">'
        '<span class="p-nav-num" id="p-nav-num-20">&#128230;</span>'
        '<div class="p-nav-info"><div class="p-nav-label">&#128230; Final Deliverables</div>'
        '<div class="p-nav-agent">All outputs assembled</div></div></div>'
    )

    # ── Step panels ──────────────────────────────────────────────────────────
    panels = ""
    for s in AUTHORITY_STEPS:
        n         = s["step"]
        ph        = s["phase"]
        ph_data   = AUTHORITY_PHASES[ph - 1]
        color     = ph_data["color"]
        ph_lbl    = ph_data["label"]
        next_s    = AUTHORITY_STEPS[n] if n < ATOTAL else None
        save_key  = s.get("output_key", "")
        next_label = ("Step " + str(next_s["step"]) + ": " + next_s["label"]) if next_s else "Final Deliverables"

        form_html = ""
        for f in s.get("fields", []):
            fname   = f["name"]
            ftype   = f.get("type", "text")
            sk      = f.get("state_key", "")
            fbk     = f.get("fallback_key", "")
            da      = ('data-state-key="' + sk + '"') if sk else ""
            if fbk:
                da += ' data-fallback-key="' + fbk + '"'
            lbl     = f["label"]
            ph_text = f.get("placeholder", "")
            if ftype == "textarea":
                rows = str(f.get("rows", 4))
                form_html += (
                    '<div class="form-group"><label class="form-label">' + lbl + '</label>'
                    '<textarea name="' + fname + '" class="form-control" rows="' + rows +
                    '" placeholder="' + ph_text + '" ' + da + '></textarea></div>'
                )
            else:
                form_html += (
                    '<div class="form-group"><label class="form-label">' + lbl + '</label>'
                    '<input type="text" name="' + fname + '" class="form-control"'
                    ' placeholder="' + ph_text + '" ' + da + '></div>'
                )

        web_badge = (
            '<span style="font-size:10px;background:#1c2d3a;color:#58a6ff;padding:2px 6px;'
            'border-radius:4px;margin-left:6px">&#127760; web</span>'
        ) if s.get("web_tools") else ""

        back_style = ' style="display:none"' if n == 1 else ""
        prev_n = max(1, n - 1)

        panels += (
            '<div class="p-panel" id="p-panel-' + str(n) + '" style="display:none">'
            '<div class="p-panel-header" style="border-left:4px solid ' + color + '">'
            '<div>'
            '<div class="p-panel-title">' + s["icon"] + ' Step ' + str(n) + ': ' + s["label"] + web_badge + '</div>'
            '<div class="p-panel-meta">' + s["agent"] + ' &middot; Phase ' + str(ph) + ': ' + ph_lbl + '</div>'
            '</div>'
            '<span class="p-status-badge" id="p-status-' + str(n) + '">Ready</span>'
            '</div>'
            '<p style="color:var(--muted);font-size:13px;margin-bottom:16px">' + s["description"] + '</p>'
            '<form id="p-form-' + str(n) + '" onsubmit="return false">'
            + form_html +
            '<div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:16px">'
            '<button type="button" class="btn btn-primary" onclick="runAuthorityStep(' + str(n) + ')">&#9654; Run ' + s["agent"] + '</button>'
            '<button type="button" class="btn btn-ghost btn-sm" onclick="showStep(' + str(prev_n) + ')"' + back_style + '>&#8592; Back</button>'
            '</div>'
            '</form>'
            '<div class="p-output-area" id="p-output-area-' + str(n) + '" style="display:none">'
            '<div class="p-output-toolbar">'
            '<span class="p-output-label">Output &mdash; ' + s["agent"] + '</span>'
            '<div style="display:flex;gap:6px">'
            '<button class="btn btn-ghost btn-sm" onclick="copyOutput()">&#10232; Copy</button>'
            '<button class="btn btn-ghost btn-sm" onclick="downloadOutput(\'authority_step' + str(n) + '_' + s["id"] + '.md\')">&#11015; Save</button>'
            '<button class="btn btn-secondary btn-sm" onclick="useAndNext(' + str(n) + ',\'' + save_key + '\',\'' + next_label.replace("'", "\\'") + '\')" id="p-use-btn-' + str(n) + '">'
            'Use &#8594; ' + next_label + '</button>'
            '</div>'
            '</div>'
            '<div class="p-output" id="p-output-' + str(n) + '"></div>'
            '</div>'
            '</div>'
        )

        # Quality gate after phase-boundary steps
        if n in GATE_BOUNDARY:
            ph_num = GATE_BOUNDARY[n]
            ph_d   = AUTHORITY_PHASES[ph_num - 1]
            fail_opts = "".join(
                '<option value="' + str(v) + '">' + k + '</option>'
                for k, v in ph_d["fail_routes"].items()
            )
            next_ph = str(ph_num + 1) if ph_num < 5 else "6"
            panels += (
                '<div class="p-gate" id="a-gate-' + str(ph_num) + '" style="display:none">'
                '<div class="p-gate-inner">'
                '<div class="p-gate-title">' + ph_d["icon"] + ' Phase ' + str(ph_num) + ' Quality Gate: ' + ph_d["label"] + '</div>'
                '<p class="p-gate-check">' + ph_d["gate"] + '</p>'
                '<div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:16px">'
                '<button class="btn btn-primary" onclick="passAuthorityGate(' + str(ph_num) + ')">&#10003; Pass &mdash; Continue to Phase ' + next_ph + '</button>'
                '<div style="display:flex;align-items:center;gap:6px">'
                '<select class="form-control" id="a-gate-fail-' + str(ph_num) + '" style="width:auto;padding:6px 10px;font-size:13px">'
                + fail_opts +
                '</select>'
                '<button class="btn btn-ghost btn-sm" onclick="failAuthorityGate(' + str(ph_num) + ')">&#8635; Revise</button>'
                '</div>'
                '</div>'
                '</div>'
                '</div>'
            )

    # Final deliverables panel
    dl_rows = ""
    for label, key, fname in DELIVERABLES:
        dl_rows += (
            '<tr>'
            '<td style="padding:8px 0;border-bottom:1px solid var(--border)">'
            '<button class="btn btn-ghost btn-sm" onclick="downloadDeliverable(\'' + key + '\',\'' + fname + '\')">'
            '&#11015; ' + label + '</button></td>'
            '<td style="padding:8px 0;border-bottom:1px solid var(--border);color:var(--muted);font-size:12px">'
            '<span id="a-dl-' + key + '-status">Waiting</span></td>'
            '</tr>'
        )

    panels += (
        '<div class="p-panel" id="p-panel-20" style="display:none">'
        '<div class="p-panel-header" style="border-left:4px solid #3fb950">'
        '<div>'
        '<div class="p-panel-title">&#128230; Final Deliverables</div>'
        '<div class="p-panel-meta">All 19 agents complete &middot; Authority article ready to publish</div>'
        '</div>'
        '</div>'
        '<p style="color:var(--muted);font-size:13px;margin-bottom:20px">'
        'Your 10,000&ndash;15,000 word authority article is complete. Download each deliverable below.'
        '</p>'
        '<table style="width:100%;border-collapse:collapse">' + dl_rows + '</table>'
        '<div style="margin-top:20px;display:flex;gap:8px;flex-wrap:wrap">'
        '<button class="btn btn-primary" onclick="downloadAllAuthority()">&#11015; Download All</button>'
        '<button class="btn btn-ghost btn-sm" onclick="resetAuthority()">&#8635; Start New Article</button>'
        '</div>'
        '</div>'
    )

    # Phase badge HTML
    phase_badges = ""
    for ph_data in AUTHORITY_PHASES:
        c = ph_data["color"]
        phase_badges += (
            '<span style="font-size:11px;padding:3px 8px;border-radius:12px;'
            'background:' + c + '22;color:' + c + ';border:1px solid ' + c + '55">'
            + ph_data["icon"] + ' ' + ph_data["label"] + '</span>'
        )

    # Step metadata for JavaScript (output_key per step)
    import json as _json
    step_meta_js = _json.dumps([
        {"output_key": s.get("output_key", ""), "saves": s.get("saves", [])}
        for s in AUTHORITY_STEPS
    ])
    dl_keys_js   = _json.dumps([key  for _, key, _ in DELIVERABLES])
    dl_fnames_js = _json.dumps([fname for _, _, fname in DELIVERABLES])
    gate_js      = _json.dumps(GATE_BOUNDARY)

    js_authority = (
        "const AUTHORITY_STATE_KEY='cblog_authority';\n"
        "const AUTHORITY_TOTAL=" + str(ATOTAL) + ";\n"
        "const AUTHORITY_GATE_BOUNDARY=" + gate_js + ";\n"
        "const STEP_META=" + step_meta_js + ";\n"
        "const DL_KEYS=" + dl_keys_js + ";\n"
        "const DL_FNAMES=" + dl_fnames_js + ";\n"
        "\n"
        "function aState(){try{return JSON.parse(sessionStorage.getItem(AUTHORITY_STATE_KEY)||'{}');}catch(e){return {};}}\n"
        "function aSave(d){sessionStorage.setItem(AUTHORITY_STATE_KEY,JSON.stringify(d));}\n"
        "\n"
        "function showStep(n){\n"
        "  document.querySelectorAll('.p-panel,.p-gate').forEach(el=>el.style.display='none');\n"
        "  const panel=document.getElementById('p-panel-'+n);\n"
        "  if(panel){panel.style.display='block';populateAuthorityFields(n);}\n"
        "  document.querySelectorAll('.p-nav-item').forEach(el=>el.classList.remove('active'));\n"
        "  const nav=document.getElementById('p-nav-'+n);\n"
        "  if(nav) nav.classList.add('active');\n"
        "  window._currentAuthorityStep=n;\n"
        "}\n"
        "\n"
        "function populateAuthorityFields(n){\n"
        "  const state=aState();\n"
        "  const panel=document.getElementById('p-panel-'+n);\n"
        "  if(!panel) return;\n"
        "  panel.querySelectorAll('[data-state-key]').forEach(el=>{\n"
        "    const key=el.getAttribute('data-state-key');\n"
        "    const fb=el.getAttribute('data-fallback-key');\n"
        "    const val=state[key]||(fb?state[fb]:'')||'';\n"
        "    if(val&&!el.value) el.value=val;\n"
        "  });\n"
        "}\n"
        "\n"
        "function runAuthorityStep(n){\n"
        "  const form=document.getElementById('p-form-'+n);\n"
        "  const fields={};\n"
        "  if(form) form.querySelectorAll('input,textarea,select').forEach(el=>{if(el.name) fields[el.name]=el.value;});\n"
        "  const outputArea=document.getElementById('p-output-area-'+n);\n"
        "  const outputEl=document.getElementById('p-output-'+n);\n"
        "  const statusEl=document.getElementById('p-status-'+n);\n"
        "  if(outputArea) outputArea.style.display='block';\n"
        "  if(outputEl) outputEl.textContent='';\n"
        "  if(statusEl){statusEl.textContent='Running...';statusEl.className='p-status-badge running';}\n"
        "  let full=''; window._lastOutput='';\n"
        "  fetchSSE('/api/authority-run',{step:n,fields},\n"
        "    (chunk)=>{full+=chunk;window._lastOutput=full;if(outputEl) outputEl.textContent=full;},\n"
        "    (err)=>{if(statusEl){statusEl.textContent='Error';statusEl.className='p-status-badge error';}if(outputEl) outputEl.textContent+='\\n\\n[Error: '+err+']';},\n"
        "    ()=>{\n"
        "      if(statusEl){statusEl.textContent='Complete';statusEl.className='p-status-badge complete';}\n"
        "      const checkEl=document.getElementById('p-nav-check-'+n);\n"
        "      if(checkEl) checkEl.textContent='\\u2713';\n"
        "      const navNum=document.getElementById('p-nav-num-'+n);\n"
        "      if(navNum) navNum.style.background='var(--success)';\n"
        "      const state=aState();\n"
        "      if(form) form.querySelectorAll('[name]').forEach(el=>{if(el.name&&el.value) state[el.name]=el.value;});\n"
        "      const meta=STEP_META[n-1];\n"
        "      if(meta&&meta.output_key&&full) state[meta.output_key]=full;\n"
        "      state['_step'+n+'_done']=true;\n"
        "      aSave(state);\n"
        "      showAuthorityGateIfPhaseComplete(n);\n"
        "    }\n"
        "  );\n"
        "}\n"
        "\n"
        "function useAndNext(n,saveKey,nextLabel){\n"
        "  const state=aState();\n"
        "  if(window._lastOutput&&saveKey) state[saveKey]=window._lastOutput;\n"
        "  aSave(state);\n"
        "  if(n<AUTHORITY_TOTAL) showStep(n+1); else showStep(20);\n"
        "}\n"
        "\n"
        "function showAuthorityGateIfPhaseComplete(stepN){\n"
        "  const phaseNum=AUTHORITY_GATE_BOUNDARY[stepN];\n"
        "  if(!phaseNum) return;\n"
        "  const gateEl=document.getElementById('a-gate-'+phaseNum);\n"
        "  if(gateEl){\n"
        "    document.querySelectorAll('.p-panel,.p-gate').forEach(el=>el.style.display='none');\n"
        "    gateEl.style.display='block';\n"
        "    document.getElementById('p-dl-all').disabled=false;\n"
        "  }\n"
        "}\n"
        "\n"
        "function passAuthorityGate(phaseNum){\n"
        "  const entries=Object.entries(AUTHORITY_GATE_BOUNDARY);\n"
        "  const entry=entries.find(([k,v])=>v===phaseNum);\n"
        "  if(!entry) return;\n"
        "  const afterStep=parseInt(entry[0])+1;\n"
        "  if(afterStep>AUTHORITY_TOTAL) showStep(20); else showStep(afterStep);\n"
        "}\n"
        "function failAuthorityGate(phaseNum){\n"
        "  const sel=document.getElementById('a-gate-fail-'+phaseNum);\n"
        "  if(sel) showStep(parseInt(sel.value));\n"
        "}\n"
        "\n"
        "function downloadDeliverable(key,filename){\n"
        "  const state=aState(); const content=state[key]||'No output yet.';\n"
        "  const a=document.createElement('a');\n"
        "  a.href='data:text/markdown;charset=utf-8,'+encodeURIComponent(content);\n"
        "  a.download=filename; a.click();\n"
        "  const el=document.getElementById('a-dl-'+key+'-status');\n"
        "  if(el) el.textContent='Downloaded';\n"
        "}\n"
        "\n"
        "function downloadAllAuthority(){\n"
        "  DL_FNAMES.forEach((f,i)=>{\n"
        "    const state=aState(); const content=state[DL_KEYS[i]]||'No output yet.';\n"
        "    setTimeout(()=>{const a=document.createElement('a');a.href='data:text/markdown;charset=utf-8,'+encodeURIComponent(content);a.download=f;a.click();},i*300);\n"
        "  });\n"
        "}\n"
        "\n"
        "function resetAuthority(){\n"
        "  if(confirm('Reset all authority pipeline state? This cannot be undone.')){\n"
        "    sessionStorage.removeItem(AUTHORITY_STATE_KEY);\n"
        "    showStep(1);\n"
        "    document.querySelectorAll('.p-nav-check').forEach(el=>el.textContent='');\n"
        "    document.querySelectorAll('.p-nav-num').forEach(el=>el.style.background='');\n"
        "  }\n"
        "}\n"
        "\n"
        "async function runAllAuthority(){\n"
        "  const btn=document.getElementById('a-oneshot-btn');\n"
        "  if(btn){btn.disabled=true;btn.textContent='Running...';}\n"
        "  for(let n=1;n<=AUTHORITY_TOTAL;n++){\n"
        "    showStep(n);\n"
        "    await new Promise((resolve)=>{\n"
        "      const form=document.getElementById('p-form-'+n);\n"
        "      const fields={};\n"
        "      if(form) form.querySelectorAll('input,textarea,select').forEach(el=>{if(el.name) fields[el.name]=el.value;});\n"
        "      const outputEl=document.getElementById('p-output-'+n);\n"
        "      const statusEl=document.getElementById('p-status-'+n);\n"
        "      if(statusEl){statusEl.textContent='Running...';statusEl.className='p-status-badge running';}\n"
        "      let full='';\n"
        "      fetchSSE('/api/authority-run',{step:n,fields},\n"
        "        (chunk)=>{full+=chunk;window._lastOutput=full;if(outputEl) outputEl.textContent=full;},\n"
        "        (err)=>{resolve();},\n"
        "        ()=>{\n"
        "          const state=aState();\n"
        "          const meta=STEP_META[n-1];\n"
        "          if(full&&meta&&meta.output_key) state[meta.output_key]=full;\n"
        "          aSave(state);\n"
        "          if(statusEl){statusEl.textContent='Complete';statusEl.className='p-status-badge complete';}\n"
        "          const checkEl=document.getElementById('p-nav-check-'+n);\n"
        "          if(checkEl) checkEl.textContent='\\u2713';\n"
        "          resolve();\n"
        "        }\n"
        "      );\n"
        "    });\n"
        "    await new Promise(r=>setTimeout(r,800));\n"
        "  }\n"
        "  showStep(20);\n"
        "  if(btn){btn.disabled=false;btn.textContent='\\u25b6\\u25b6 Run All (One-Shot)';}\n"
        "}\n"
        "\n"
        "document.addEventListener('DOMContentLoaded',()=>{showStep(1);});\n"
    )

    body = (
        '<div class="p-layout" style="padding-top:0">'
        '<div class="p-header-bar" style="background:linear-gradient(135deg,#0d1117 0%,#1a1f2e 100%);padding:20px 32px;border-bottom:1px solid var(--border)">'
        '<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px">'
        '<div>'
        '<h2 style="margin:0;font-size:22px">&#127942; Authority Article Pipeline</h2>'
        '<p style="margin:4px 0 0;color:var(--muted);font-size:13px">19 agents &middot; 5 phases &middot; targets 10,000&ndash;15,000 words</p>'
        '</div>'
        '<div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">'
        '<div style="font-size:12px;color:var(--muted)">Phase progress:</div>'
        + phase_badges +
        '<button id="a-oneshot-btn" class="btn btn-secondary btn-sm" onclick="runAllAuthority()">&#9654;&#9654; Run All (One-Shot)</button>'
        '</div>'
        '</div>'
        '</div>'
        '<div style="display:flex;height:calc(100vh - 120px)">'
        '<div class="pipeline-sidebar" style="width:240px;min-width:240px">'
        '<div style="padding:12px 16px;border-bottom:1px solid var(--border)">'
        '<a href="/" class="btn btn-ghost btn-sm" style="margin-bottom:8px;display:inline-flex">&#8592; Home</a>'
        '<div style="font-weight:700;font-size:13px">&#127942; 19-Agent Authority Pipeline</div>'
        '<div style="font-size:10px;color:var(--muted);margin-top:2px">5 phases &middot; 10K&ndash;15K word articles</div>'
        '</div>'
        '<div class="p-nav">' + nav_items + '</div>'
        '<div class="pipeline-sidebar-footer">'
        '<button class="btn btn-ghost btn-sm" onclick="resetAuthority()" style="width:100%;justify-content:center">&#8635; Reset</button>'
        '<button class="btn btn-secondary btn-sm" id="p-dl-all" onclick="downloadAllAuthority()" disabled style="width:100%;justify-content:center">&#11015; Download All</button>'
        '</div>'
        '</div>'
        '<div class="pipeline-main">' + panels + '</div>'
        '</div>'
        '</div>'
        '<script>' + js_authority + '</script>'
    )

    pill_cls, pill_label = ("pill-ok", "Claude ✓") if claude_available() else ("pill-err", "Claude ✗")
    return render_template_string(
        "<!DOCTYPE html>\n"
        "<html lang=\"en\">\n"
        "<head>\n"
        "<meta charset=\"UTF-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">\n"
        "<title>Authority Article Pipeline — Claude Blog</title>\n"
        "<style>" + CSS + "</style>\n"
        "</head>\n"
        "<body>\n"
        "<nav>\n"
        "  <div class=\"nav-brand\">✍ Claude<em>Blog</em></div>\n"
        "  <a href=\"/\" class=\"nav-link\">Home</a>\n"
        "  <a href=\"/pipeline\" class=\"nav-link\">⚡ Pipeline</a>\n"
        "  <a href=\"/authority\" class=\"nav-link active\" style=\"color:#d29922;font-weight:600\">\U0001f3c6 Authority</a>\n"
        "  <a href=\"/run/keyword-research\" class=\"nav-link\">Keywords</a>\n"
        "  <a href=\"/run/write\" class=\"nav-link\">Write</a>\n"
        "  <a href=\"/run/humanize\" class=\"nav-link\">Humanize</a>\n"
        "  <a href=\"/saved\" class=\"nav-link\">Saved</a>\n"
        "  <a href=\"/settings\" class=\"nav-link\">Settings</a>\n"
        "  <div class=\"nav-spacer\"></div>\n"
        "  <div class=\"status-pill " + pill_cls + "\"><span class=\"dot\"></span>" + pill_label + "</div>\n"
        "</nav>\n"
        + body +
        "\n<script>" + JS + "</script>\n"
        "</body>\n"
        "</html>"
    )


@app.route("/authority")
def authority():
    return _build_authority_page()


@app.route("/api/authority-run", methods=["POST"])
def api_authority_run():
    if not claude_available():
        return jsonify({"error": "claude CLI not found"}), 503

    data      = request.get_json()
    step_n    = int(data.get("step", 0))
    fields    = data.get("fields", {})

    if step_n < 1 or step_n > len(AUTHORITY_STEPS):
        return jsonify({"error": f"Invalid step: {step_n}"}), 400

    s             = AUTHORITY_STEPS[step_n - 1]
    system_prompt = s["system_prompt"]

    try:
        user_msg = s["prompt"].format(**{k: v or "" for k, v in fields.items()})
    except KeyError as e:
        return jsonify({"error": f"Missing field: {e}"}), 400

    web_tools     = s.get("web_tools", False)
    allowed_tools = "WebSearch,WebFetch" if web_tools else ""

    def generate():
        model = get_model()
        cmd = [
            "claude", "-p", user_msg,
            "--system-prompt", system_prompt,
            "--output-format", "stream-json",
            "--include-partial-messages", "--verbose",
            "--no-session-persistence",
        ]
        if allowed_tools:
            cmd += ["--allowedTools", allowed_tools]
        else:
            cmd += ["--tools", ""]
        if model:
            cmd += ["--model", model]

        clean_env = {k: v for k, v in os.environ.items()
                     if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY_ID", "ANTHROPIC_BASE_URL")}

        proc = subprocess.Popen(
            cmd, env=clean_env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1, cwd=str(ROOT),
        )

        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
                if ev.get("type") == "stream_event":
                    inner = ev.get("event", {})
                    if inner.get("type") == "content_block_delta":
                        delta = inner.get("delta", {})
                        if delta.get("type") == "text_delta":
                            text = delta.get("text", "")
                            if text:
                                yield f"data: {json.dumps({'text': text})}\n\n"
                elif ev.get("type") == "result" and ev.get("is_error"):
                    yield f"data: {json.dumps({'error': ev.get('result', 'Unknown error')})}\n\n"
            except json.JSONDecodeError:
                pass

        proc.wait()
        if proc.returncode not in (0, None):
            err = proc.stderr.read() if proc.stderr else ""
            if err:
                yield f"data: {json.dumps({'error': err[:300]})}\n\n"
        yield "data: [DONE]\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
