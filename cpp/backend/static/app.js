/* =============================================================================
 * app.js — 上海地铁路径规划与运营管理系统（最小可行前端）
 *
 * 纯原生 JS，无 D3 / 无地图渲染。所有功能通过后端 REST API 完成，结果以
 * 列表 + 卡片呈现。旧的地理投影 / 八向示意图 / 标签退火算法已归档至
 * backend/static/legacy/。
 *
 * 覆盖三大功能区：
 *   路径规划  — 最短时间 / 最少换乘，单条或 K 条（Yen）
 *   运营管理  — 站点开关、批量 CSV 更新、恢复全部
 *   网络分析  — 受影响区域 BFS、连通分量 DFS
 * ===========================================================================*/

'use strict';

// ---------------------------------------------------------------------------
// 小工具
// ---------------------------------------------------------------------------
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

async function api(path, opts = {}) {
    const res = await fetch(path, opts);
    let data = null;
    try { data = await res.json(); } catch { /* non-JSON */ }
    if (!res.ok) {
        const msg = (data && (data.error || data.message)) || `请求失败 (${res.status})`;
        throw new Error(msg);
    }
    return data;
}

function debounce(fn, ms = 200) {
    let t;
    return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
}

function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, c =>
        ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

function toast(message, type = 'info') {
    const colors = {
        info: 'bg-slate-800',
        success: 'bg-emerald-600',
        error: 'bg-rose-600',
    };
    const node = document.createElement('div');
    node.className = `${colors[type] || colors.info} text-white text-sm px-4 py-2 rounded-lg shadow-lg ` +
                     'opacity-0 translate-y-2 transition duration-200';
    node.textContent = message;
    $('#toasts').appendChild(node);
    requestAnimationFrame(() => node.classList.remove('opacity-0', 'translate-y-2'));
    setTimeout(() => {
        node.classList.add('opacity-0', 'translate-y-2');
        setTimeout(() => node.remove(), 250);
    }, 2800);
}

// ---------------------------------------------------------------------------
// 全局状态
// ---------------------------------------------------------------------------
const state = {
    lineColors: {},     // line name -> hex color
    allStations: [],    // cached station list for the ops panel
    src: null,          // selected route source station {id,name,line}
    dst: null,          // selected route destination station
    anStation: null,    // selected analysis station
};

function lineColor(line) {
    return state.lineColors[line] || '#64748b';
}

// A small colored line badge, e.g. (1号线)
function lineBadge(line) {
    const c = lineColor(line);
    return `<span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-medium"
                  style="color:${c};background:${c}1a">
                <span class="w-1.5 h-1.5 rounded-full" style="background:${c}"></span>${escapeHtml(line)}
            </span>`;
}

// ---------------------------------------------------------------------------
// 站点搜索下拉（可复用：路径起终点 / 分析中心站）
// ---------------------------------------------------------------------------
function attachStationSearch(inputEl, resultsEl, selectedEl, onSelect) {
    const render = (stations) => {
        if (!stations.length) { resultsEl.hidden = true; resultsEl.innerHTML = ''; return; }
        resultsEl.innerHTML = stations.slice(0, 30).map(s => `
            <button type="button" data-id="${s.id}"
                    class="w-full text-left px-3 py-2 hover:bg-slate-50 flex items-center justify-between gap-2 text-sm">
                <span>${escapeHtml(s.name)}</span>
                <span class="flex items-center gap-2">
                    ${lineBadge(s.line)}
                    ${s.is_open === false ? '<span class="text-xs text-rose-500">关闭</span>' : ''}
                </span>
            </button>`).join('');
        resultsEl.hidden = false;
        $$('button', resultsEl).forEach(btn => {
            btn.addEventListener('click', () => {
                const s = stations.find(x => x.id === btn.dataset.id);
                onSelect(s);
                inputEl.value = s.name;
                resultsEl.hidden = true;
                selectedEl.hidden = false;
                selectedEl.innerHTML = `已选 ${escapeHtml(s.name)} ${lineBadge(s.line)}`;
            });
        });
    };

    const search = debounce(async () => {
        const q = inputEl.value.trim();
        if (!q) { resultsEl.hidden = true; return; }
        try {
            const stations = await api('/api/stations/search?q=' + encodeURIComponent(q));
            render(stations);
        } catch (e) { /* ignore transient search errors */ }
    }, 200);

    inputEl.addEventListener('input', () => { selectedEl.hidden = true; search(); });
    inputEl.addEventListener('focus', () => { if (inputEl.value.trim()) search(); });
    document.addEventListener('click', (e) => {
        if (!resultsEl.contains(e.target) && e.target !== inputEl) resultsEl.hidden = true;
    });
}

// ---------------------------------------------------------------------------
// 路径规划
// ---------------------------------------------------------------------------
function renderPathCard(path, index, total) {
    if (!path.valid) {
        return `<div class="bg-white rounded-xl shadow-sm border border-rose-200 p-5 text-sm text-rose-600">
                    ${escapeHtml(path.error || '未找到可达路径。')}
                </div>`;
    }

    // Build a vertical timeline; insert a 换乘 marker whenever the riding line changes.
    const rows = [];
    const stations = path.stations || [];
    for (let i = 0; i < stations.length; i++) {
        const s = stations[i];
        const prev = stations[i - 1];
        if (prev && prev.line !== s.line) {
            rows.push(`<div class="flex items-center gap-2 py-1 pl-1 text-xs text-amber-600">
                           <span class="w-3 text-center">↕</span><span>换乘</span>
                       </div>`);
        }
        const c = lineColor(s.line);
        rows.push(`<div class="flex items-center gap-2 py-0.5">
                       <span class="w-3 flex justify-center">
                           <span class="w-2.5 h-2.5 rounded-full ring-2 ring-white" style="background:${c}"></span>
                       </span>
                       <span class="text-sm text-slate-800">${escapeHtml(s.name)}</span>
                       ${lineBadge(s.line)}
                   </div>`);
    }

    const header = total > 1
        ? `<span class="text-sm font-semibold text-slate-900">方案 ${index + 1}</span>`
        : `<span class="text-sm font-semibold text-slate-900">推荐路径</span>`;

    const transferSummary = (path.transfer_at && path.transfer_at.length)
        ? `<div class="mt-3 pt-3 border-t border-slate-100 text-xs text-slate-500 space-y-1">
               ${path.transfer_at.map(t =>
                   `<div>· ${escapeHtml(t.station_name)}：${escapeHtml(t.from_line)} → ${escapeHtml(t.to_line)}</div>`
               ).join('')}
           </div>`
        : '';

    return `<div class="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
                <div class="flex items-center justify-between mb-3">
                    ${header}
                    <div class="flex items-center gap-3 text-sm">
                        <span class="text-slate-500">总耗时 <strong class="text-slate-900">${path.total_time}</strong> 分</span>
                        <span class="text-slate-500">换乘 <strong class="text-slate-900">${path.transfer_count}</strong> 次</span>
                        <span class="text-slate-500">途经 <strong class="text-slate-900">${path.station_count}</strong> 站</span>
                    </div>
                </div>
                <div class="border-l-2 border-slate-100 pl-2">${rows.join('')}</div>
                ${transferSummary}
            </div>`;
}

async function planRoute() {
    if (!state.src || !state.dst) { toast('请先选择起点和终点站', 'error'); return; }
    const algo = $('input[name="algo"]:checked').value;       // shortest-time | min-transfers
    const k = parseInt($('input[name="k"]:checked').value, 10); // 1 | 3
    const out = $('#route-results');
    const btn = $('#btn-plan');

    btn.disabled = true;
    out.innerHTML = `<div class="text-sm text-slate-400 py-6 text-center">计算中…</div>`;

    const endpoint = k > 1
        ? (algo === 'min-transfers' ? '/api/route/k-min-transfers' : '/api/route/k-shortest-time')
        : (algo === 'min-transfers' ? '/api/route/min-transfers'   : '/api/route/shortest-time');

    const body = { src_id: state.src.id, dst_id: state.dst.id };
    if (k > 1) body.k = k;

    try {
        const data = await api(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        const paths = Array.isArray(data) ? data : [data];
        if (!paths.length || (paths.length === 1 && !paths[0].valid)) {
            out.innerHTML = renderPathCard(paths[0] || { valid: false }, 0, 1);
            return;
        }
        out.innerHTML = paths.map((p, i) => renderPathCard(p, i, paths.length)).join('');
    } catch (e) {
        out.innerHTML = `<div class="bg-white rounded-xl border border-rose-200 p-5 text-sm text-rose-600">${escapeHtml(e.message)}</div>`;
    } finally {
        btn.disabled = false;
    }
}

// ---------------------------------------------------------------------------
// 运营管理
// ---------------------------------------------------------------------------
function renderOpsList() {
    const lineFilter = $('#ops-line').value;
    const statusFilter = $('#ops-status').value;
    const kw = $('#ops-search').value.trim();

    let rows = state.allStations;
    if (lineFilter) rows = rows.filter(s => s.line === lineFilter);
    if (statusFilter === 'open') rows = rows.filter(s => s.is_open);
    if (statusFilter === 'closed') rows = rows.filter(s => !s.is_open);
    if (kw) rows = rows.filter(s => s.name.includes(kw));

    $('#ops-count').textContent = `共 ${rows.length} 个站点`;

    const list = $('#ops-list');
    if (!rows.length) {
        list.innerHTML = `<div class="px-3 py-6 text-center text-sm text-slate-400">无匹配站点</div>`;
        return;
    }
    list.innerHTML = rows.slice(0, 400).map(s => `
        <div class="flex items-center gap-3 px-3 py-2 hover:bg-slate-50">
            <span class="text-sm text-slate-800 flex-1">${escapeHtml(s.name)}</span>
            ${lineBadge(s.line)}
            <span class="text-xs ${s.is_open ? 'text-emerald-600' : 'text-rose-500'} w-10 text-center">
                ${s.is_open ? '开启' : '关闭'}
            </span>
            <button data-id="${s.id}" data-open="${s.is_open}"
                    class="ops-toggle px-2.5 py-1 rounded-md text-xs font-medium border transition
                           ${s.is_open ? 'border-rose-200 text-rose-600 hover:bg-rose-50'
                                       : 'border-emerald-200 text-emerald-600 hover:bg-emerald-50'}">
                ${s.is_open ? '关闭' : '开启'}
            </button>
        </div>`).join('') +
        (rows.length > 400 ? `<div class="px-3 py-2 text-center text-xs text-slate-400">仅显示前 400 条，请用筛选缩小范围</div>` : '');

    $$('.ops-toggle', list).forEach(btn => {
        btn.addEventListener('click', () => toggleStation(btn.dataset.id, btn.dataset.open === 'true'));
    });
}

async function toggleStation(id, isOpen) {
    const action = isOpen ? 'close' : 'open';
    try {
        await api(`/api/stations/${encodeURIComponent(id)}/${action}`, { method: 'POST' });
        const s = state.allStations.find(x => x.id === id);
        if (s) { s.is_open = !isOpen; s.status = s.is_open ? '开启' : '关闭'; }
        renderOpsList();
        refreshStats();
        toast(`${s ? s.name : id} 已${isOpen ? '关闭' : '开启'}`, 'success');
    } catch (e) {
        toast(e.message, 'error');
    }
}

async function restoreAll() {
    try {
        const r = await api('/api/stations/restore', { method: 'POST' });
        await loadStations();
        renderOpsList();
        refreshStats();
        toast(`已恢复全部站点（当前关闭 ${r.closed_count} 个）`, 'success');
    } catch (e) {
        toast(e.message, 'error');
    }
}

async function batchUpload(file) {
    const fd = new FormData();
    fd.append('file', file);
    try {
        const r = await api('/api/stations/batch-update', { method: 'POST', body: fd });
        await loadStations();
        renderOpsList();
        refreshStats();
        toast(`批量更新：成功 ${r.updated}，未匹配 ${r.not_found}，非法 ${r.invalid}`, 'success');
    } catch (e) {
        toast(e.message, 'error');
    }
}

// ---------------------------------------------------------------------------
// 网络分析
// ---------------------------------------------------------------------------
async function analyzeAffected() {
    if (!state.anStation) { toast('请先选择中心站点', 'error'); return; }
    const depth = parseInt($('#an-depth').value, 10);
    const out = $('#affected-result');
    out.innerHTML = `<div class="text-sm text-slate-400 py-4">分析中…</div>`;
    try {
        const r = await api('/api/analysis/affected-area', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ station_id: state.anStation.id, max_depth: depth }),
        });
        const chips = r.affected_stations.map(s =>
            `<span class="inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-slate-100 text-sm">
                 ${escapeHtml(s.name)} ${lineBadge(s.line)}
             </span>`).join('');
        out.innerHTML = `
            <div class="mt-2 text-sm text-slate-600 mb-2">
                以 <strong>${escapeHtml(state.anStation.name)}</strong> 为中心，${depth} 阶范围内受影响
                <strong class="text-blue-600">${r.affected_count}</strong> 个开放站点：
            </div>
            <div class="flex flex-wrap gap-2">${chips || '<span class="text-sm text-slate-400">无受影响站点</span>'}</div>`;
    } catch (e) {
        out.innerHTML = `<div class="text-sm text-rose-600 mt-2">${escapeHtml(e.message)}</div>`;
    }
}

async function analyzeComponents() {
    const out = $('#components-result');
    out.innerHTML = `<div class="text-sm text-slate-400 py-4">计算中…</div>`;
    try {
        const r = await api('/api/analysis/components');
        const sorted = [...r.components].sort((a, b) => b.size - a.size);
        const items = sorted.map((c, i) => {
            const label = i === 0 ? '主连通块' : `连通块 ${i + 1}`;
            const preview = c.stations.slice(0, 6).map(s => escapeHtml(s.name)).join('、');
            const more = c.size > 6 ? ` 等 ${c.size} 站` : '';
            return `<div class="flex items-start gap-3 px-3 py-2 border border-slate-100 rounded-lg">
                        <span class="text-xs font-medium px-2 py-0.5 rounded bg-blue-50 text-blue-600 whitespace-nowrap">${label}</span>
                        <span class="text-sm text-slate-600">${c.size} 个站点 — ${preview}${more}</span>
                    </div>`;
        }).join('');
        const banner = r.component_count === 1
            ? `<div class="text-sm text-emerald-600 mb-2">网络连通良好，共 1 个连通块（${r.total_stations} 站全部互通）。</div>`
            : `<div class="text-sm text-amber-600 mb-2">网络已分裂为 <strong>${r.component_count}</strong> 个连通块。</div>`;
        out.innerHTML = `<div class="mt-2 space-y-2">${banner}${items}</div>`;
    } catch (e) {
        out.innerHTML = `<div class="text-sm text-rose-600 mt-2">${escapeHtml(e.message)}</div>`;
    }
}

// ---------------------------------------------------------------------------
// 初始化数据
// ---------------------------------------------------------------------------
async function loadLines() {
    const lines = await api('/api/lines');
    lines.forEach(l => { state.lineColors[l.name] = l.color; });
    // Populate the ops line filter, sorted by station count desc then name.
    const sel = $('#ops-line');
    lines.sort((a, b) => a.name.localeCompare(b.name, 'zh'));
    lines.forEach(l => {
        const opt = document.createElement('option');
        opt.value = l.name; opt.textContent = `${l.name} (${l.station_count})`;
        sel.appendChild(opt);
    });
    $('#stat-lines').textContent = lines.length;
}

async function loadStations() {
    state.allStations = await api('/api/stations');
}

async function refreshStats() {
    try {
        const s = await api('/api/graph/summary');
        $('#stat-stations').textContent = s.station_count;
        $('#stat-closed').textContent = s.closed_count;
    } catch { /* non-fatal */ }
}

// ---------------------------------------------------------------------------
// Tab 切换
// ---------------------------------------------------------------------------
function setupTabs() {
    const activate = (name) => {
        $$('.tab-btn').forEach(b => {
            const on = b.dataset.tab === name;
            b.classList.toggle('bg-blue-600', on);
            b.classList.toggle('text-white', on);
            b.classList.toggle('text-slate-600', !on);
            b.classList.toggle('hover:bg-slate-100', !on);
        });
        $$('section[data-panel]').forEach(s => { s.hidden = s.dataset.panel !== name; });
    };
    $$('.tab-btn').forEach(b => b.addEventListener('click', () => activate(b.dataset.tab)));
    activate('route');
}

// ---------------------------------------------------------------------------
// 启动
// ---------------------------------------------------------------------------
async function init() {
    setupTabs();

    attachStationSearch($('#src-input'), $('#src-results'), $('#src-selected'), s => { state.src = s; });
    attachStationSearch($('#dst-input'), $('#dst-results'), $('#dst-selected'), s => { state.dst = s; });
    attachStationSearch($('#an-input'), $('#an-results'), $('#an-selected'), s => { state.anStation = s; });

    $('#btn-plan').addEventListener('click', planRoute);
    $('#btn-restore').addEventListener('click', restoreAll);
    $('#btn-affected').addEventListener('click', analyzeAffected);
    $('#btn-components').addEventListener('click', analyzeComponents);

    $('#batch-input').addEventListener('change', (e) => {
        const f = e.target.files[0];
        if (f) batchUpload(f);
        e.target.value = '';
    });

    ['#ops-line', '#ops-status'].forEach(sel => $(sel).addEventListener('change', renderOpsList));
    $('#ops-search').addEventListener('input', debounce(renderOpsList, 150));
    $('#an-depth').addEventListener('input', (e) => { $('#an-depth-label').textContent = e.target.value; });

    try {
        await Promise.all([loadLines(), loadStations(), refreshStats()]);
        renderOpsList();
    } catch (e) {
        toast('初始化失败：' + e.message, 'error');
    }
}

document.addEventListener('DOMContentLoaded', init);
