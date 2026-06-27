/**
 * app.js — Shanghai Metro Route Planning Frontend
 * D3.js interactive metro map + route planning + station management + network analysis
 */

// ============================================================================
// App State
// ============================================================================
const state = {
    layout: null, stations: [], lines: [], stationMap: {},
    srcStation: null, dstStation: null,
    routeResults: [], highlightedPath: null,
    zoom: null, svg: null, gMap: null, activePanel: 'route-panel',
    tuning: null, currentK: 1, _settleTimer: null,
    sa: {
        completed: false,
        positions: new Map(),      // key: "${name}|${stationX}|${stationY}" → {x,y}
        fallbackReason: null,      // 'timeout' | 'disabled' | null
    },
    // Octilinear schematic layout
    rawCoords: null,              // real lat/lng from station_coords.json
    layoutMode: 'geo',            // 'geo' | 'octilinear'
    octiLayout: null,             // computed schematic coordinates
    activeLayout: null,           // pointer to either state.layout or state.octiLayout
};

// Default label/tier tuning — overridable from localStorage via tuning panel.
// Progressive zoom tier design: zoomed out → only transfer stations visible
// As you zoom in: termini → sparse outer stations → dense city-center stations
const DEFAULT_TUNING = {
    // --- Font sizing ---
    fontBase: 2.8,            // screen-space px at k=1
    fontMin: 1.8,             // visual font floor (px)
    fontMax: 6.5,             // visual font ceiling (px)
    fontDecay: 0.28,          // visual ~ base * k^(-decay); higher = shrinks faster on zoom-in
    majorFontBoost: 1.2,      // transfer-station font multiplier
    // --- Tier thresholds (which labels are eligible at which zoom, progressive reveal)
    // kMajorFadeStart/kMajorFadeEnd: transfer station labels fade out when zoomed very far
    kMajorFadeStart: 0.4,     // major labels start fading out below this zoom
    kMajorFadeEnd: 0.25,      // major labels fully hidden below this zoom
    kMedium: 0.65,            // medium tier (line termini) appears at k >= this
    kNormalSparse: 1.1,       // sparse-area normal stations appear at k >= this
    kNormalDense: 2.0,        // city-center dense stations appear at k >= this
    // --- Density classification ---
    densityRadius: 18,        // px radius (layout coords) for neighbor count
    densityThreshold: 4,      // neighbor count >= this → "dense" tier
    // --- Label position / collision ---
    labelOffsetX: 10,         // px right of station center
    labelOffsetY: -6,         // px below (negative = above) station center
    collisionPadding: 2,      // extra px around label bbox during collision test
    // --- Station / line styling ---
    stationRadiusScale: 1.0,  // multiplier on computed station radius
    lineWidth: 3.5,           // metro line stroke width (px, in layout coords)
    // --- Interaction ---
    settleDelay: 250,         // ms of no-zoom before collision re-runs
    // --- Simulated Annealing ---
    useSA: true,              // master toggle for SA label placement
    saIterations: 2000,       // total SA iterations (two-phase split)
    saMajorAnchor: 8.0,       // anchor weight multiplier for major (transfer) labels
    saNormalAnchor: 1.0,      // anchor weight multiplier for normal labels
    saTimeoutMs: 600,         // hard time limit for SA execution
    // --- Octilinear Schematic Layout ---
    octiIterations: 60,       // layout relaxation passes
    octiMinDist: 14,          // minimum station separation (px)
    octiGeoWeight: 0.15,      // geographic anchor weight (0=free, 1=locked)
    octiAngleSnap: 22.5,      // snap angle threshold for octilinear alignment (deg)
};

// Panel definitions — drives slider rendering. `section` starts a new group.
// `redraw: true` means changing this field requires regenerating label DOM.
const TUNING_DEFS = [
    { section: '字体',            key: 'fontBase',           label: '基础字号 (k=1)', min: 0.1,  max: 60.0,  step: 0.1 },
    {                              key: 'fontMin',            label: '字号下限',       min: 0.05, max: 30.0,  step: 0.1 },
    {                              key: 'fontMax',            label: '字号上限',       min: 0.5,  max: 100.0, step: 0.5 },
    {                              key: 'fontDecay',          label: '随 zoom 衰减',   min: 0.0,  max: 6.0,   step: 0.05 },
    {                              key: 'majorFontBoost',     label: '换乘字号 ×',     min: 0.2,  max: 15.0,  step: 0.05 },
    { section: 'Tier 阈值',       key: 'kMajorFadeEnd',      label: '换乘 全隐 k ≤',  min: 0.05, max: 5.0,   step: 0.05 },
    {                              key: 'kMajorFadeStart',    label: '换乘 开始淡出 k', min: 0.05, max: 5.0,   step: 0.05 },
    {                              key: 'kMedium',            label: '终点 k ≥',       min: 0.05, max: 15.0,  step: 0.05 },
    {                              key: 'kNormalSparse',      label: '郊区 k ≥',       min: 0.05, max: 25.0,  step: 0.05 },
    {                              key: 'kNormalDense',       label: '市中心 k ≥',     min: 0.05, max: 40.0,  step: 0.1 },
    { section: '密度分类',        key: 'densityRadius',      label: '密度半径 (px)',  min: 1,    max: 400,   step: 1, redraw: true },
    {                              key: 'densityThreshold',   label: '密集邻居 ≥',     min: 1,    max: 75,    step: 1, redraw: true },
    { section: '标签位置 / 碰撞', key: 'labelOffsetX',       label: 'X 偏移',         min: -50,  max: 200,   step: 1 },
    {                              key: 'labelOffsetY',       label: 'Y 偏移',         min: -125, max: 125,   step: 1 },
    {                              key: 'collisionPadding',   label: '碰撞 padding',   min: 0,    max: 75,    step: 0.5 },
    { section: '站点 / 线路',     key: 'stationRadiusScale', label: '站点半径 ×',     min: 0.05, max: 17.5,  step: 0.05 },
    {                              key: 'lineWidth',          label: '线路粗细',       min: 0.05, max: 60.0,  step: 0.1 },
    { section: '交互',            key: 'settleDelay',        label: '碰撞延迟 ms',    min: 10,   max: 7500,  step: 25 },
    { section: '模拟退火',        key: 'useSA',              label: '启用 SA',         min: 0,    max: 1,     step: 1 },
    {                              key: 'saIterations',       label: '迭代次数',        min: 10,   max: 10000, step: 10 },
    {                              key: 'saMajorAnchor',      label: '换乘锚权重',      min: 0.2,  max: 100,   step: 0.5 },
    {                              key: 'saNormalAnchor',     label: '普通锚权重',      min: 0.1,  max: 50,    step: 0.1 },
    {                              key: 'saTimeoutMs',        label: '超时 ms',         min: 50,   max: 10000, step: 50 },
    { section: '八边示意图',      key: 'octiIterations',     label: '松弛迭代次数',    min: 0,    max: 300,   step: 5, redraw: true },
    {                              key: 'octiMinDist',        label: '最小站距 px',     min: 2,    max: 100,   step: 1, redraw: true },
    {                              key: 'octiGeoWeight',      label: '地理锚定权重',    min: 0,    max: 1,     step: 0.01, redraw: true },
    {                              key: 'octiAngleSnap',      label: '角度吸附阈值°',   min: 1,    max: 90,    step: 0.5, redraw: true },
];

function loadTuning() {
    try {
        const s = JSON.parse(localStorage.getItem('metroTuning') || '{}');
        return { ...DEFAULT_TUNING, ...s };
    } catch (e) { return { ...DEFAULT_TUNING }; }
}

function saveTuning() {
    try { localStorage.setItem('metroTuning', JSON.stringify(state.tuning)); } catch (e) {}
}

const LINE_COLORS = {
    '1号线':'#E4002B','2号线':'#97D700','3号线':'#FCD600','4号线':'#461D84',
    '5号线':'#944D9B','6号线':'#D6006C','7号线':'#ED6B06','8号线':'#0094D8',
    '9号线':'#7AC8E1','10号线':'#C6AFD4','11号线':'#841C21','12号线':'#007A60',
    '13号线':'#E77CA5','14号线':'#9D8B63','15号线':'#B2A680','16号线':'#77D0C8',
    '17号线':'#BB6414','18号线':'#C4984E','浦江线':'#B5B5B6','市域机场线':'#4A90A4',
};

// ============================================================================
// Geometry utilities for octilinear layout
// ============================================================================

/**
 * Calculate bearing between two WGS84 lat/lng points, in degrees.
 * Returns bearing from point A to point B, 0° = North, increasing clockwise.
 */
function bearing(lat1, lng1, lat2, lng2) {
    const rad = Math.PI / 180;
    const dLng = (lng2 - lng1) * rad;
    const y = Math.sin(dLng) * Math.cos(lat2 * rad);
    const x = Math.cos(lat1 * rad) * Math.sin(lat2 * rad) -
              Math.sin(lat1 * rad) * Math.cos(lat2 * rad) * Math.cos(dLng);
    return (Math.atan2(y, x) * 180 / Math.PI + 360) % 360;
}

/**
 * Snap an angle in degrees to the nearest octilinear direction (0°, 45°, ..., 315°).
 * Returns snapped angle in degrees.
 */
function snapToOctilinear(angleDeg, thresholdDeg) {
    // Octilinear directions: 0, 45, 90, 135, 180, 225, 270, 315
    const octiDirs = [0, 45, 90, 135, 180, 225, 270, 315];
    let best = octiDirs[0];
    let minDiff = Infinity;
    for (const dir of octiDirs) {
        // Handle wrap-around at 0/360
        let diff = Math.abs(angleDeg - dir);
        if (diff > 180) diff = 360 - diff;
        if (diff < minDiff) {
            minDiff = diff;
            best = dir;
        }
    }
    // Only snap if within threshold
    return minDiff <= thresholdDeg ? best : angleDeg;
}

// ============================================================================
// API Helpers
// ============================================================================
async function apiGet(path) {
    const res = await fetch(path);
    if (!res.ok) throw new Error(`API ${res.status}`);
    return res.json();
}
async function apiPost(path, body) {
    const res = await fetch(path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    });
    if (!res.ok) { const err = await res.json().catch(()=> ({})); throw new Error(err.error || `HTTP ${res.status}`); }
    return res.json();
}

// ============================================================================
// Toast
// ============================================================================
function showToast(msg, type='info') {
    const c = document.getElementById('toast-container');
    const t = document.createElement('div');
    t.className = `toast ${type}`; t.textContent = msg;
    c.appendChild(t);
    setTimeout(() => { t.style.opacity='0'; t.style.transition='opacity 0.3s'; setTimeout(() => t.remove(), 300); }, 3000);
}

// ============================================================================
// Loading
// ============================================================================
function setLoading(on) { document.getElementById('loading-overlay').classList.toggle('visible', on); }

// ============================================================================
// Station Search
// ============================================================================
function initStationSearch(inputId, resultsId, selectedId, onSelect) {
    const input = document.getElementById(inputId);
    const resultsDiv = document.getElementById(resultsId);
    let timer;
    input.addEventListener('input', () => {
        clearTimeout(timer);
        const q = input.value.trim();
        if (!q) { resultsDiv.classList.remove('visible'); return; }
        timer = setTimeout(async () => {
            try {
                const r = await apiGet(`/api/stations/search?q=${encodeURIComponent(q)}`);
                resultsDiv.innerHTML = r.map(s => `
                    <div class="search-result-item" data-id="${s.id}">
                        <span class="st-name">${s.name}</span>
                        <span style="font-size:11px;color:${LINE_COLORS[s.line]||'#666'}">${s.line}${!s.is_open?' <span style="color:#e74c3c">[关闭]</span>':''}</span>
                    </div>`).join('');
                resultsDiv.querySelectorAll('.search-result-item').forEach(el => {
                    el.addEventListener('click', () => { const st = r.find(x => x.id===el.dataset.id); if(st){ input.value=''; resultsDiv.classList.remove('visible'); onSelect(st); }});
                });
                resultsDiv.classList.toggle('visible', r.length > 0);
            } catch(e) {}
        }, 150);
    });
    document.addEventListener('click', e => { if(!input.parentElement.contains(e.target)) resultsDiv.classList.remove('visible'); });
    input.addEventListener('keydown', e => {
        const items = resultsDiv.querySelectorAll('.search-result-item');
        if(!items.length) return;
        const active = resultsDiv.querySelector('.search-result-item.active');
        let idx = Array.from(items).indexOf(active);
        if(e.key==='ArrowDown'){ e.preventDefault(); idx=(idx+1)%items.length; items.forEach(i=>i.classList.remove('active')); items[idx].classList.add('active'); }
        else if(e.key==='ArrowUp'){ e.preventDefault(); idx=(idx-1+items.length)%items.length; items.forEach(i=>i.classList.remove('active')); items[idx].classList.add('active'); }
        else if(e.key==='Enter'){ e.preventDefault(); if(active) active.click(); }
        else if(e.key==='Escape'){ resultsDiv.classList.remove('visible'); }
    });
}

function updateSelectedDisplay(elId, st, prefix) {
    const el = document.getElementById(elId);
    if(!st) { el.innerHTML=''; return; }
    el.innerHTML = `<span class="tag ${prefix}"><span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${LINE_COLORS[st.line]||'#666'};margin-right:4px"></span>${st.name} (${st.line})<span class="remove">✕</span></span>`;
    el.querySelector('.remove').addEventListener('click', () => {
        if(prefix==='src') state.srcStation=null; else state.dstStation=null;
        updateSelectedDisplay(elId, null, prefix); updatePlanButton(); updateMapSelection();
    });
}

function updatePlanButton() { document.getElementById('btn-plan').disabled = !(state.srcStation && state.dstStation); }

// ============================================================================
// Route Planning
// ============================================================================
async function planRoute() {
    if(!state.srcStation || !state.dstStation) return;
    const algo = document.querySelector('input[name="algo"]:checked').value;
    const k = parseInt(document.querySelector('input[name="k"]:checked').value);
    setLoading(true);
    try {
        let ep = algo==='shortest-time' ? (k===1?'/api/route/shortest-time':'/api/route/k-shortest-time') : (k===1?'/api/route/min-transfers':'/api/route/k-min-transfers');
        const body = {src_id:state.srcStation.id, dst_id:state.dstStation.id};
        if(k>1) body.k = k;
        const data = await apiPost(ep, body);
        state.routeResults = Array.isArray(data) ? data : [data];
        state.highlightedPath = 0;
        renderRouteResults();
        highlightRouteOnMap(0);
    } catch(e) { showToast(`路径规划失败: ${e.message}`, 'error'); }
    finally { setLoading(false); }
}

function renderRouteResults() {
    const c = document.getElementById('route-results');
    if(!state.routeResults.length){ c.innerHTML=''; return; }
    const first = state.routeResults[0];
    if(!first.valid){ c.innerHTML=`<div class="route-card" style="color:var(--danger)">⚠ ${first.error||'无法找到路径'}</div>`; return; }
    c.innerHTML = state.routeResults.map((r,i) => {
        if(!r.valid) return '';
        const sel = i===state.highlightedPath;
        const rank = state.routeResults.length>1 ? `路径 ${i+1}` : '最优路径';
        return `<div class="route-card ${sel?'selected':''}" data-index="${i}">
            <div class="route-header"><span class="route-rank">🏆 ${rank}</span>${state.routeResults.length>1?`<button class="btn-secondary" style="font-size:10px;padding:2px 8px" data-show="${i}">查看</button>`:''}</div>
            <div class="route-stats"><span>⏱ 总耗时: <strong>${r.total_time} 分钟</strong></span><span>🔄 换乘: <strong>${r.transfer_count} 次</strong></span><span>📍 站点: <strong>${r.station_count}</strong></span></div>
            ${r.transfer_at&&r.transfer_at.length>0?`<div class="route-transfers">${r.transfer_at.map(t=>`<div class="route-transfer-item">🔄 ${t.station_name} <span style="color:${LINE_COLORS[t.from_line]||'#666'}">${t.from_line}</span> → <span style="color:${LINE_COLORS[t.to_line]||'#666'}">${t.to_line}</span></div>`).join('')}</div>`:'<div style="font-size:12px;color:var(--success)">✅ 无需换乘</div>'}
        </div>`;
    }).join('');
    c.querySelectorAll('[data-show]').forEach(btn => btn.addEventListener('click', () => {
        const idx = parseInt(btn.dataset.show); state.highlightedPath = idx; highlightRouteOnMap(idx);
        c.querySelectorAll('.route-card').forEach(cd=>cd.classList.remove('selected'));
        c.querySelector(`[data-index="${idx}"]`)?.classList.add('selected');
    }));
}

// ============================================================================
// D3 Map
// ============================================================================
async function initMap() {
    const [layoutData, stationsData, linesData, coordsData] = await Promise.all([
        apiGet('/api/layout'),
        apiGet('/api/stations'),
        apiGet('/api/lines'),
        fetch('/station_coords.json').then(r => r.json()).catch(() => null)
    ]);
    state.layout = layoutData;
    state.stations = stationsData;
    state.lines = linesData;
    state.rawCoords = coordsData;
    state.activeLayout = state.layout;
    state.octiLayout = null;

    // Restore saved layout mode
    if (state.tuning && state.tuning.layoutMode === 'octilinear') {
        state.layoutMode = 'octilinear';
        state.octiLayout = computeOctilinearLayout();
        if (state.octiLayout) state.activeLayout = state.octiLayout;
    }
    stationsData.forEach(s => { state.stationMap[s.id] = s; });
    document.getElementById('stat-stations').textContent = stationsData.length;
    document.getElementById('stat-lines').textContent = linesData.length;
    document.getElementById('stat-closed').textContent = stationsData.filter(s=>!s.is_open).length;

    const container = document.getElementById('map-container');
    const svg = d3.select('#metro-map');
    svg.selectAll('*').remove();
    const W = container.clientWidth, H = container.clientHeight;
    svg.attr('width', W).attr('height', H);
    state.svg = svg;
    const gMap = svg.append('g').attr('class', 'map-layer');
    state.gMap = gMap;

    state.tuning = loadTuning();

    // If octilinear mode is saved and we have raw coords, compute schematic
    // before drawing so lines go through the new station positions
    if (state.tuning.layoutMode === 'octilinear' && !state.octiLayout && state.rawCoords) {
        state.octiLayout = computeOctilinearLayout();
        if (state.octiLayout) state.activeLayout = state.octiLayout;
    }

    // OPTIMIZATION: RAF-based zoom event coalescing to prevent layout thrashing
    let _zoomRAF = 0;
    let _lastTuneTime = 0;
    const TUNE_INTERVAL_MS = 34; // ~30fps

    const zoom = d3.zoom().scaleExtent([0.3, 8]).on('zoom', e => {
        // Abort any running SA immediately when user starts zooming
        abortRunningSA();

        // Store pending transform for RAF coalescing
        state._pendingTransform = e.transform;
        state.currentK = e.transform.k;

        // Don't do anything if we already have a RAF pending
        if (_zoomRAF) return;

        _zoomRAF = requestAnimationFrame(() => {
            gMap.attr('transform', state._pendingTransform);
            _zoomRAF = 0;

            // Time-based throttle instead of frame counter
            const now = performance.now();
            if (now - _lastTuneTime < TUNE_INTERVAL_MS) return;
            _lastTuneTime = now;

            applyTuning(state.currentK);
            scheduleCollisionSettle();
        });
    });
    svg.call(zoom);
    state.zoom = zoom;

    drawLines(gMap, state.activeLayout);
    drawStations(gMap, state.activeLayout, stationsData);
    drawLabels(gMap, state.activeLayout);

    // Line-hover focus/dim behaviour
    initLineFocus(gMap);

    const bbox = gMap.node().getBBox();
    if(bbox.width > 0) {
        const scale = Math.min((W-80)/bbox.width, (H-80)/bbox.height, 1.5);
        const tx = (W - bbox.width*scale)/2 - bbox.x*scale;
        const ty = (H - bbox.height*scale)/2 - bbox.y*scale;
        svg.call(zoom.transform, d3.zoomIdentity.translate(tx, ty).scale(scale));
    }
    // Apply tuning at the post-fit zoom (the throttled zoom handler may have
    // skipped the very first event), then run an initial collision settle.
    applyTuning(state.currentK);
    requestAnimationFrame(() => resolveLabelCollisions(gMap));

    document.getElementById('map-legend').innerHTML = `
        <div class="legend-item"><span class="legend-dot" style="background:#fff;border:2px solid #3498db"></span> 普通站</div>
        <div class="legend-item"><span class="legend-dot" style="background:#fff;border:3px solid #e74c3c;width:12px;height:12px"></span> 换乘站</div>
        <div class="legend-item"><span class="legend-dot" style="background:#555"></span> 关闭站</div>
        <div class="legend-item"><span style="display:inline-block;width:20px;height:4px;background:#f1c40f;border-radius:2px"></span> 规划路径</div>`;
}

// ============================================================================
// Tuning — applies font-size, station radius and tier visibility for current k.
// OPTIMIZED: Consolidated selectAll queries, reduced DOM traversals from 10+ to 4.
// ============================================================================
function applyTuning(k) {
    if (!state.gMap || !state.tuning) return;
    const t = state.tuning;
    const gMap = state.gMap;
    state.currentK = k;

    // --- Precompute all tier opacities once (no DOM involved) ---
    const mediumFadeWidth = 0.15;
    const sparseFadeWidth = 0.2;
    const denseFadeWidth = 0.3;

    const majorOpacity = k < t.kMajorFadeEnd ? 0 :
                         k < t.kMajorFadeStart ? (k - t.kMajorFadeEnd) / (t.kMajorFadeStart - t.kMajorFadeEnd) :
                         1;
    const mediumOpacity = k < t.kMedium - mediumFadeWidth ? 0 :
                          k < t.kMedium + mediumFadeWidth ? (k - (t.kMedium - mediumFadeWidth)) / (mediumFadeWidth * 2) :
                          1;
    const sparseOpacity = k < t.kNormalSparse - sparseFadeWidth ? 0 :
                         k < t.kNormalSparse + sparseFadeWidth ? (k - (t.kNormalSparse - sparseFadeWidth)) / (sparseFadeWidth * 2) :
                         1;
    const denseOpacity = k < t.kNormalDense - denseFadeWidth ? 0 :
                         k < t.kNormalDense + denseFadeWidth ? (k - (t.kNormalDense - denseFadeWidth)) / (denseFadeWidth * 2) :
                         1;

    // --- Font sizing constants ---
    const kEff = Math.max(k, 0.2);
    const baseVisual = Math.min(t.fontMax,
        Math.max(t.fontMin, t.fontBase * Math.pow(kEff, -t.fontDecay)));
    const majorVisual = Math.min(t.fontMax, baseVisual * t.majorFontBoost);

    // --- SINGLE PASS: All label operations in ONE selectAll traversal ---
    // Consolidates: font size + position update + opacity + tier-off class
    gMap.selectAll('.map-label').each(function () {
        // Fast tier detection via data attribute (no classList lookup)
        const tier = this.getAttribute('data-tier') || 'normal-sparse';
        const isHighlighted = this.classList.contains('highlighted');

        // --- Font size ---
        const visualSize = tier === 'major' ? majorVisual : baseVisual;
        this.style.fontSize = Math.round((visualSize / k) * 100) / 100 + 'px';

        // --- Position update ---
        const sx = +this.getAttribute('data-station-x');
        const sy = +this.getAttribute('data-station-y');
        if (Number.isFinite(sx) && Number.isFinite(sy)) {
            const bx = sx + t.labelOffsetX;
            const by = sy + t.labelOffsetY;
            this.setAttribute('data-base-x', bx);
            this.setAttribute('data-base-y', by);
            this.setAttribute('x', bx);
            this.setAttribute('y', by);
        }

        // --- Opacity and tier-off ---
        let opacity;
        if (isHighlighted) {
            opacity = 1; // highlighted always visible
            this.classList.remove('tier-off');
        } else {
            // Compute tier-specific opacity
            switch (tier) {
                case 'major':
                    opacity = majorOpacity;
                    break;
                case 'medium':
                    opacity = mediumOpacity * majorOpacity;
                    break;
                case 'normal-sparse':
                    opacity = sparseOpacity * mediumOpacity * majorOpacity;
                    break;
                case 'normal-dense':
                    opacity = denseOpacity * sparseOpacity * mediumOpacity * majorOpacity;
                    break;
                default:
                    opacity = majorOpacity;
            }
            this.classList.toggle('tier-off', opacity === 0);
        }
        this.style.opacity = opacity;
    });

    // --- Station circle radius (SINGLE selectAll) ---
    const rTargetScale = Math.pow(Math.max(k, 0.5), -0.4);
    gMap.selectAll('.map-station')
        .attr('r', function () {
            const base = +(this.getAttribute('data-base-r')) || 5;
            const clamped = Math.min(base * 1.35, Math.max(base * 0.65, base * rTargetScale));
            const visual = clamped * t.stationRadiusScale;
            return Math.round((visual / k) * 10) / 10;
        })
        // Station opacity handled here too (avoids extra selectAll calls)
        .style('opacity', function() {
            const isRegular = this.classList.contains('regular');
            const isTransfer = this.classList.contains('transfer');
            if (!isRegular && !isTransfer) return null;

            const stationFadeStart = t.kMedium + 0.1;
            const stationFadeEnd = t.kMajorFadeEnd;

            if (isRegular) {
                return k < stationFadeEnd ? 0.15 :
                       k < stationFadeStart ? 0.15 + 0.5 * (k - stationFadeEnd) / (stationFadeStart - stationFadeEnd) :
                       null;
            }
            // transfer
            return k < t.kMajorFadeEnd ? 0.5 :
                   k < t.kMajorFadeStart ? 0.5 + 0.5 * (k - t.kMajorFadeEnd) / (t.kMajorFadeStart - t.kMajorFadeEnd) :
                   null;
        });

    // --- Line stroke width: ONE selectAll with conditional (casing vs regular) ---
    gMap.selectAll('.map-line, .map-line-casing').attr('stroke-width', function () {
        const isCasing = this.classList.contains('map-line-casing');
        return isCasing ? t.lineWidth + 2 : t.lineWidth;
    });

    // --- Overlay markers: only apply if they exist (check once) ---
    const overlay = screenRadius(10);
    const comp = screenRadius(12);
    gMap.selectAll('.map-transfer-marker').attr('r', overlay);
    gMap.selectAll('.map-affected-station').attr('r', overlay);
    gMap.selectAll('.map-component-mark').attr('r', comp);
}

// Debounce collision detection — only run after zoom/pan settles.
function scheduleCollisionSettle() {
    if (state._settleTimer) clearTimeout(state._settleTimer);
    const t = state.tuning || DEFAULT_TUNING;
    state._settleTimer = setTimeout(() => {
        // If SA completed successfully, no need to re-run collision on zoom settle.
        // SA positions are in layout coords, scale uniformly with zoom transform.
        if (t.useSA && state.sa.completed && state.sa.positions.size > 0) {
            return;
        }
        if (state.gMap) resolveLabelCollisions(state.gMap);
        state._settleTimer = null;
    }, t.settleDelay);
}

function drawLines(gMap, layoutData) {
    const {stations:ly, lines} = layoutData;
    for(const [ln, info] of Object.entries(lines)) {
        const color = info.color || '#666';
        const segments = info.segments || [];
        segments.forEach((seg) => {
            const a = seg[0], b = seg[1];
            const offsetPx = seg[2] || 0;
            const pa = ly[a], pb = ly[b];
            if (!pa || !pb) return;

            // Perpendicular offset for parallel lines sharing a corridor.
            // A non-zero offset shifts the line perpendicular to the segment
            // direction so overlapping lines render side-by-side.
            let ox = 0, oy = 0;
            if (Math.abs(offsetPx) > 0.005) {
                const dx = pb.x - pa.x, dy = pb.y - pa.y;
                const len = Math.sqrt(dx * dx + dy * dy) || 1;
                const px = -dy / len, py = dx / len;
                ox = px * offsetPx;
                oy = py * offsetPx;
            }

            // --- Casing layer: dark stroke behind the coloured line ---
            // Creates a hairline gap between adjacent lines so they don't
            // visually merge in dense corridors.
            gMap.append('line')
                .attr('class', 'map-line-casing')
                .attr('data-line', ln)
                .attr('x1', pa.x + ox).attr('y1', pa.y + oy)
                .attr('x2', pb.x + ox).attr('y2', pb.y + oy)
                .attr('stroke-width', 5.5);

            // --- Coloured line on top ---
            gMap.append('line')
                .attr('class', 'map-line')
                .attr('data-line', ln)
                .attr('x1', pa.x + ox).attr('y1', pa.y + oy)
                .attr('x2', pb.x + ox).attr('y2', pb.y + oy)
                .attr('stroke', color)
                .attr('stroke-width', 3.5)
                .attr('stroke-linecap', 'round');
        });
    }
}

function drawStations(gMap, layoutData, stationsData) {
    const {stations:ly} = layoutData;
    const closedIds = new Set(stationsData.filter(s=>!s.is_open).map(s=>s.id));
    const regular=[], transfer=[];
    for(const [id,pos] of Object.entries(ly)) {
        (pos.is_transfer?transfer:regular).push({id,...pos});
    }
    regular.forEach(d => {
        gMap.append('circle').attr('class',`map-station regular ${closedIds.has(d.id)?'closed':''}`).attr('data-base-r',5).attr('data-line',d.line).attr('cx',d.x).attr('cy',d.y).attr('r',5).attr('fill',closedIds.has(d.id)?'#555':(d.color||'#666')).attr('stroke','rgba(255,255,255,0.3)').attr('stroke-width',1).attr('data-id',d.id).on('click',(e,d)=>onStationClick(d.id)).on('mouseenter',(e,d)=>onStationHover(d.id,e)).on('mouseleave',onStationLeave);
    });
    transfer.forEach(d => {
        gMap.append('circle').attr('class',`map-station transfer ${closedIds.has(d.id)?'closed':''}`).attr('data-base-r',8).attr('data-line',d.line).attr('cx',d.x).attr('cy',d.y).attr('r',8).attr('fill','#fff').attr('stroke',closedIds.has(d.id)?'#555':(d.color||'#666')).attr('stroke-width',3).attr('data-id',d.id).on('click',(e,d)=>onStationClick(d.id)).on('mouseenter',(e,d)=>onStationHover(d.id,e)).on('mouseleave',onStationLeave);
    });
    // X marks on closed
    [...regular, ...transfer].filter(d=>closedIds.has(d.id)).forEach(d => {
        gMap.append('line').attr('class','station-closed-x').attr('x1',d.x-5).attr('y1',d.y-5).attr('x2',d.x+5).attr('y2',d.y+5).attr('stroke','#e74c3c').attr('stroke-width',1.5);
        gMap.append('line').attr('class','station-closed-x').attr('x1',d.x+5).attr('y1',d.y-5).attr('x2',d.x-5).attr('y2',d.y+5).attr('stroke','#e74c3c').attr('stroke-width',1.5);
    });
}

// Density cache - invalidated only when radius/threshold params change
let _densityCache = { key: null, data: null };

function getDensityCacheKey(t) {
    return `${t.densityRadius}|${t.densityThreshold}`;
}

function drawLabels(gMap, layoutData) {
    const {stations:ly} = layoutData;
    const t = state.tuning || DEFAULT_TUNING;

    const transferIds = new Set();
    for(const [id,pos] of Object.entries(ly)) { if(pos.is_transfer) transferIds.add(id); }

    // --- Local density: count neighbours within `densityRadius` in layout space.
    // OPTIMIZATION: Use cached density computation - only recompute when params change
    const cacheKey = getDensityCacheKey(t);
    let densityCount;
    if (_densityCache.key === cacheKey && _densityCache.data) {
        densityCount = _densityCache.data;
    } else {
        const ids = Object.keys(ly);
        const R = t.densityRadius, R2 = R * R;
        densityCount = {};
        for (let i = 0; i < ids.length; i++) {
            const a = ly[ids[i]];
            let cnt = 0;
            for (let j = 0; j < ids.length; j++) {
                if (i === j) continue;
                const b = ly[ids[j]];
                const dx = a.x - b.x, dy = a.y - b.y;
                if (dx*dx + dy*dy < R2) cnt++;
            }
            densityCount[ids[i]] = cnt;
        }
        _densityCache = { key: cacheKey, data: densityCount };
    }

    // De-duplicate: transfer stations with the same name at the same position
    // (multiple nodes per line) produce one label, not N overlapping copies.
    const seen = new Set();

    // Four-tier label visibility:
    //   major          — transfer stations (iconic, always prominent)
    //   medium         — line terminus (orientation cue, medium zoom)
    //   normal-sparse  — outer-area non-transfer (visible at moderate zoom)
    //   normal-dense   — city-center non-transfer (only at deep zoom)
    for(const [id,pos] of Object.entries(ly)) {
        const isTransfer = transferIds.has(id);
        const seq = parseInt(id.slice(2)) || 0;
        const isTerminus = (seq === 1);

        // Transfer stations: key by name + rounded coords so same-point nodes
        // only produce one label regardless of how many lines pass through.
        if (isTransfer) {
            const key = `${pos.name}|${Math.round(pos.x)}|${Math.round(pos.y)}`;
            if (seen.has(key)) continue;
            seen.add(key);
        }

        let tier;
        if (isTransfer) tier = 'major';
        else if (isTerminus) tier = 'medium';
        else if ((densityCount[id] || 0) >= t.densityThreshold) tier = 'normal-dense';
        else tier = 'normal-sparse';

        const baseFont = isTransfer ? 11 : 10;
        const bx = pos.x + t.labelOffsetX;
        const by = pos.y + t.labelOffsetY;
        const label = gMap.append('text')
            .attr('class', `map-label ${tier}`)
            .attr('data-tier', tier)
            .attr('data-base-font-size', baseFont)
            .attr('data-station-x', pos.x)
            .attr('data-station-y', pos.y)
            .attr('data-base-x', bx)
            .attr('data-base-y', by)
            .attr('x', bx).attr('y', by)
            .text(pos.name)
            .style('font-size', baseFont + 'px');
        if (isTransfer) label.style('font-weight', '600');
    }
    // Initial tier visibility is applied by applyTuning() right after drawLabels.
}

// ============================================================================
// Label collision avoidance — greedy priority-based placement.
// Idempotent: clears all .collision-off first, then re-evaluates from scratch.
// Runs only on zoom-settle, so it never fights the zoom handler.
// ============================================================================
// ============================================================================
// Simulated Annealing Label Placement (SA + greedy fallback)
// ============================================================================

function applySALabels(gMap) {
    gMap.selectAll('.map-label').each(function () {
        const el = this;
        const sx = +el.getAttribute('data-station-x');
        const sy = +el.getAttribute('data-station-y');
        const key = `${el.textContent}|${Math.round(sx)}|${Math.round(sy)}`;
        const p = state.sa.positions.get(key);
        if (p) {
            el.setAttribute('x', p.x);
            el.setAttribute('y', p.y);
            el.setAttribute('data-base-x', p.x);
            el.setAttribute('data-base-y', p.y);
        }
    });
}

function runGreedyCollision(gMap) {
    const t = state.tuning || DEFAULT_TUNING;
    gMap.selectAll('.map-label.collision-off').classed('collision-off', false);

    // Candidates = all labels that aren't tier-hidden at the current zoom.
    const allLabels = gMap.selectAll('.map-label:not(.tier-off)');
    if (allLabels.empty()) return;

    // --- Step 1: bounding boxes ---
    // OPTIMIZATION: Use cached bbox dimensions to avoid repeated getBBox() calls
    // which force synchronous layout reflow.
    const items = [];
    const pad = t.collisionPadding;
    allLabels.each(function () {
        const el = this;
        const tier = el.getAttribute('data-tier') || 'normal-sparse';

        // Use cached bbox if available - stored as data attributes
        let cachedW = el.getAttribute('data-bbox-w');
        let cachedH = el.getAttribute('data-bbox-h');
        let bbox;
        if (cachedW && cachedH) {
            bbox = { width: +cachedW, height: +cachedH };
        } else {
            bbox = el.getBBox();
            // Cache for future use
            el.setAttribute('data-bbox-w', bbox.width);
            el.setAttribute('data-bbox-h', bbox.height);
        }

        const bx = +(el.getAttribute('data-base-x')) || 0;
        const by = +(el.getAttribute('data-base-y')) || 0;
        let priority;
        if (tier === 'major') priority = 4;
        else if (tier === 'medium') priority = 3;
        else if (tier === 'normal-sparse') priority = 2;
        else priority = 1;
        items.push({
            el, tier, priority,
            baseX: bx, baseY: by,
            w: bbox.width + pad, h: bbox.height + pad,
        });
    });

    // --- Step 2: sort by priority (highest first) ---
    items.sort((a, b) => b.priority - a.priority);

    // --- Step 3: greedy placement ---
    // Simple spatial hash for O(1) collision queries against placed labels.
    const cellSize = 40;
    const grid = new Map();  // key = "cx,cy" → [item, ...]

    function cellKey(x, y) { return `${Math.floor(x / cellSize)},${Math.floor(y / cellSize)}`; }

    function collidesWithPlaced(item, px, py) {
        const x = px, y = py, w = item.w, h = item.h;
        const c0 = Math.floor((x - cellSize) / cellSize);
        const c1 = Math.floor((x + w + cellSize) / cellSize);
        const r0 = Math.floor((y - cellSize) / cellSize);
        const r1 = Math.floor((y + h + cellSize) / cellSize);
        for (let ci = c0; ci <= c1; ci++) {
            for (let ri = r0; ri <= r1; ri++) {
                const bucket = grid.get(`${ci},${ri}`);
                if (!bucket) continue;
                for (const placed of bucket) {
                    if (px < placed.x + placed.w && px + w > placed.x &&
                        py < placed.y + placed.h && py + h > placed.y) {
                        return true;
                    }
                }
            }
        }
        return false;
    }

    function placeItem(item, px, py) {
        item.x = px; item.y = py;
        const key = cellKey(px + item.w / 2, py + item.h / 2);
        if (!grid.has(key)) grid.set(key, []);
        grid.get(key).push(item);
    }

    // Offsets to try: right, up-right, down-right, up, down (screen-direction order)
    const OFFSETS = [
        [8, 0], [10, -6], [10, 6], [0, -10], [0, 10],
        [14, 0], [14, -10], [14, 10],
    ];

    for (const item of items) {
        const bx = item.baseX, by = item.baseY;

        // Try base position first.
        if (!collidesWithPlaced(item, bx, by)) {
            placeItem(item, bx, by);
            d3.select(item.el).attr('x', bx).attr('y', by);
            continue;
        }

        if (item.tier === 'major') {
            // Transfer labels MUST be visible — try offsets aggressively.
            let placed = false;
            for (const [ox, oy] of OFFSETS) {
                const tx = bx + ox, ty = by + oy;
                if (!collidesWithPlaced(item, tx, ty)) {
                    placeItem(item, tx, ty);
                    d3.select(item.el).attr('x', tx).attr('y', ty);
                    placed = true;
                    break;
                }
            }
            if (!placed) {
                // Give up — render at base, accept overlap (better than hiding a transfer).
                placeItem(item, bx, by);
                d3.select(item.el).attr('x', bx).attr('y', by);
            }
        } else if (item.tier === 'medium') {
            // Terminus labels — try a few offsets, hide if none work.
            let placed = false;
            for (const [ox, oy] of OFFSETS.slice(0, 4)) {
                const tx = bx + ox, ty = by + oy;
                if (!collidesWithPlaced(item, tx, ty)) {
                    placeItem(item, tx, ty);
                    d3.select(item.el).attr('x', tx).attr('y', ty);
                    placed = true;
                    break;
                }
            }
            if (!placed) {
                d3.select(item.el).classed('collision-off', true);
            }
        } else {
            // Normal labels (sparse + dense) — hide on first collision.
            d3.select(item.el).classed('collision-off', true);
        }
    }
}

// Global SA abort handle - used when user starts zooming again
let _currentSALabeler = null;

function abortRunningSA() {
    if (_currentSALabeler) {
        _currentSALabeler.abort();
        _currentSALabeler = null;
    }
}

function runLabelerSA(gMap) {
    const t = state.tuning || DEFAULT_TUNING;
    const startTime = performance.now();

    // OPTIMIZATION: Pre-cache bbox dimensions to avoid repeated getBBox() calls
    // Build anchors & labels from ALL labels (works in layout space, valid at any zoom)
    const anchors = [], labels = [];
    gMap.selectAll('.map-label').each(function () {
        const el = this;
        const tier = el.getAttribute('data-tier');
        const sx = +el.getAttribute('data-station-x');
        const sy = +el.getAttribute('data-station-y');

        // OPTIMIZATION: Use cached bbox if available (stored as data attributes)
        let cachedW = el.getAttribute('data-bbox-w');
        let cachedH = el.getAttribute('data-bbox-h');
        let bbox;
        if (cachedW && cachedH) {
            bbox = { width: +cachedW, height: +cachedH };
        } else {
            bbox = el.getBBox();
            // Cache for future use
            el.setAttribute('data-bbox-w', bbox.width);
            el.setAttribute('data-bbox-h', bbox.height);
        }

        const weight = (tier === 'major') ? t.saMajorAnchor :
                       (tier === 'medium') ? 3 : t.saNormalAnchor;
        anchors.push({ x: sx, y: sy, r: weight > 3 ? 8 : 4 });
        labels.push({
            x: +el.getAttribute('data-base-x'),
            y: +el.getAttribute('data-base-y'),
            width: bbox.width + t.collisionPadding,
            height: bbox.height + t.collisionPadding,
            weight: weight,
            anchorWeight: weight,
            tier: tier,
            el: el,
            fixed: false,
        });
    });

    // --- Phase 1: optimize major + medium only (40% of sweeps), then lock ---
    const phase1Labels = labels.filter(l => l.tier === 'major' || l.tier === 'medium');
    const phase1Anchors = anchors.filter((_, i) =>
        labels[i].tier === 'major' || labels[i].tier === 'medium');

    function runPhase2() {
        // Check if we should abort after phase 1 (timeout or aborted)
        if (performance.now() - startTime > t.saTimeoutMs) {
            console.warn('[SA] Timeout during phase 1, falling back to greedy');
            state.sa.fallbackReason = 'timeout';
            state.sa.completed = false;
            _currentSALabeler = null;
            runGreedyCollision(gMap);
            return;
        }

        // Lock phase 1 labels
        phase1Labels.forEach(l => { l.fixed = true; });

        // --- Phase 2: optimize ALL labels with major+medium fixed (60% of sweeps) ---
        const labeler = d3.labeler()
            .label(labels)
            .anchor(anchors)
            .width(1600).height(1200);
        _currentSALabeler = labeler;

        labeler.start(Math.floor(t.saIterations * 0.6), null, function(aborted) {
            _currentSALabeler = null;

            if (aborted) {
                console.log('[SA] Aborted during phase 2');
                return;
            }

            if (performance.now() - startTime > t.saTimeoutMs) {
                console.warn('[SA] Timeout during phase 2, falling back to greedy');
                state.sa.fallbackReason = 'timeout';
                state.sa.completed = false;
                runGreedyCollision(gMap);
                return;
            }

            // --- Store results ---
            state.sa.positions.clear();
            labels.forEach(l => {
                const sx = +l.el.getAttribute('data-station-x');
                const sy = +l.el.getAttribute('data-station-y');
                const key = `${l.el.textContent}|${Math.round(sx)}|${Math.round(sy)}`;
                state.sa.positions.set(key, { x: l.x, y: l.y });
            });
            state.sa.completed = true;
            state.sa.fallbackReason = null;

            console.log(`[SA] Completed in ${Math.round(performance.now() - startTime)}ms, ${state.sa.positions.size} labels placed`);
            applySALabels(gMap);
        });
    }

    // Start phase 1 (async if possible)
    if (phase1Labels.length > 0) {
        const labeler = d3.labeler()
            .label(phase1Labels)
            .anchor(phase1Anchors)
            .width(1600).height(1200);
        _currentSALabeler = labeler;

        labeler.start(Math.floor(t.saIterations * 0.4), null, function(aborted) {
            _currentSALabeler = null;
            if (!aborted) runPhase2();
        });
    } else {
        // No phase 1 needed, start directly with phase 2
        runPhase2();
    }
}

function resolveLabelCollisions(gMap) {
    const t = state.tuning || DEFAULT_TUNING;

    if (!t.useSA) {
        state.sa.fallbackReason = 'disabled';
        runGreedyCollision(gMap);
        return;
    }

    if (state.sa.completed && state.sa.positions.size > 0) {
        applySALabels(gMap);
        return;
    }

    runLabelerSA(gMap);
}

// ============================================================================
// Octilinear Schematic Layout Engine
// Transforms geographic coordinates into a clean schematic-style map where
// lines align to 0°/45°/90°/etc directions. Uses iterative relaxation.
// ============================================================================

function computeOctilinearLayout() {
    // Always compute from the original geographic layout, not the current active layout
    if (!state.layout || !state.layout.stations) return null;

    const t = state.tuning || DEFAULT_TUNING;
    const ly = state.layout;
    const stations = ly.stations;
    const ids = Object.keys(stations);
    const startTime = performance.now();

    // Build station index map: id → array index
    const idx = {};
    ids.forEach((id, i) => idx[id] = i);

    // Build edge list: [fromStationIdx, toStationIdx]
    const edges = [];
    for (const [lineName, lineInfo] of Object.entries(ly.lines)) {
        for (const seg of lineInfo.segments || []) {
            const a = idx[seg[0]], b = idx[seg[1]];
            if (a !== undefined && b !== undefined) {
                edges.push([a, b]);
            }
        }
    }

    // Step 1: Initialize schematic positions from geographic positions
    // pos[i] = {x, y} in layout coordinates
    const pos = ids.map(id => ({
        x: stations[id].x,
        y: stations[id].y,
    }));

    // Step 2: Precompute target octilinear directions for every edge
    // targetDir[i][j] = snapped bearing from station i to station j
    const targetDir = Array(ids.length).fill(0).map(() => ({}));
    for (const [a, b] of edges) {
        const idA = ids[a], idB = ids[b];
        let angle;
        if (state.rawCoords && state.rawCoords[idA] && state.rawCoords[idB]) {
            // Use true geographic bearing if available
            angle = bearing(
                state.rawCoords[idA].lat, state.rawCoords[idA].lng,
                state.rawCoords[idB].lat, state.rawCoords[idB].lng
            );
        } else {
            // Fallback: use projected coordinates bearing
            const dx = stations[idB].x - stations[idA].x;
            const dy = stations[idB].y - stations[idA].y;
            angle = (Math.atan2(dy, dx) * 180 / Math.PI + 360) % 360;
        }
        const snapped = snapToOctilinear(angle, t.octiAngleSnap);
        targetDir[a][b] = snapped * Math.PI / 180;
        // Reverse direction for b→a
        targetDir[b][a] = ((snapped + 180) % 360) * Math.PI / 180;
    }

    // Step 3: Iterative relaxation
    for (let iter = 0; iter < t.octiIterations; iter++) {
        const newPos = pos.map(p => ({ x: p.x * t.octiGeoWeight, y: p.y * t.octiGeoWeight }));
        const neighborCount = Array(ids.length).fill(t.octiGeoWeight);

        // Direction constraint: pull each station along the octilinear direction
        // dictated by each neighbor
        for (const [a, b] of edges) {
            const dist = Math.sqrt(
                Math.pow(pos[b].x - pos[a].x, 2) +
                Math.pow(pos[b].y - pos[a].y, 2)
            ) || 1;

            const dir = targetDir[a][b];
            if (dir !== undefined) {
                // Station a is pulled in dir direction towards station b
                newPos[a].x += (pos[a].x + Math.cos(dir) * dist) * (1 - t.octiGeoWeight);
                newPos[a].y += (pos[a].y + Math.sin(dir) * dist) * (1 - t.octiGeoWeight);
                neighborCount[a] += (1 - t.octiGeoWeight);

                // Station b is pulled in reverse direction
                const revDir = targetDir[b][a];
                newPos[b].x += (pos[b].x + Math.cos(revDir) * dist) * (1 - t.octiGeoWeight);
                newPos[b].y += (pos[b].y + Math.sin(revDir) * dist) * (1 - t.octiGeoWeight);
                neighborCount[b] += (1 - t.octiGeoWeight);
            }
        }

        // Normalize by neighbor count
        for (let i = 0; i < ids.length; i++) {
            if (neighborCount[i] > 0) {
                newPos[i].x /= neighborCount[i];
                newPos[i].y /= neighborCount[i];
            }
        }

        // Repulsion: push apart stations that are too close
        const repulseFactor = 0.15;
        for (let i = 0; i < ids.length; i++) {
            for (let j = i + 1; j < ids.length; j++) {
                const dx = newPos[j].x - newPos[i].x;
                const dy = newPos[j].y - newPos[i].y;
                const dist = Math.sqrt(dx * dx + dy * dy);
                if (dist < t.octiMinDist && dist > 0.001) {
                    const f = (t.octiMinDist - dist) / dist * repulseFactor;
                    const fx = dx * f, fy = dy * f;
                    newPos[i].x -= fx;
                    newPos[i].y -= fy;
                    newPos[j].x += fx;
                    newPos[j].y += fy;
                }
            }
        }

        // Copy back
        for (let i = 0; i < ids.length; i++) {
            pos[i] = newPos[i];
        }
    }

    // Step 4: Build output layout object
    const octiStations = {};
    for (let i = 0; i < ids.length; i++) {
        const id = ids[i];
        octiStations[id] = { ...stations[id], x: Math.round(pos[i].x * 10) / 10, y: Math.round(pos[i].y * 10) / 10 };
    }

    console.log(`[Octilinear] Computed schematic layout in ${Math.round(performance.now() - startTime)}ms`);
    return { ...ly, stations: octiStations };
}

/**
 * Switch between geographic and schematic octilinear layout modes.
 * Invalidates SA positions and redraws everything.
 */
function setLayoutMode(mode) {
    if (!state.layout) return;
    state.layoutMode = mode;
    if (state.tuning) state.tuning.layoutMode = mode;

    if (mode === 'octilinear') {
        if (!state.octiLayout) {
            state.octiLayout = computeOctilinearLayout();
        }
        state.activeLayout = state.octiLayout;
    } else {
        state.activeLayout = state.layout;
    }

    // Invalidate SA positions because coordinates changed
    state.sa.completed = false;
    state.sa.positions.clear();

    // Full redraw
    const g = state.gMap;
    if (g) {
        g.selectAll('.map-line, .map-line-casing, .map-station, .map-label, line').remove();
        drawLines(g, state.activeLayout);
        drawStations(g, state.activeLayout, state.stations);
        drawLabels(g, state.activeLayout);
        applyTuning(state.currentK);
        if (state.tuning?.useSA) runLabelerSA(g);
        else resolveLabelCollisions(g);

        // Re-highlight current route if any
        if (state.routeResults.length > 0 && state.highlightedPath !== null) {
            highlightRouteOnMap(state.highlightedPath);
        }
        updateMapSelection();
    }

    saveTuning();
}

// ============================================================================
// Line focus / dim (hover a line → dim all others)
// ============================================================================
function initLineFocus(gMap) {
    const lines = gMap.selectAll('.map-line');
    const casings = gMap.selectAll('.map-line-casing');
    const allStations = gMap.selectAll('.map-station');

    let focusedLine = null;
    const dimOthers = (ln) => {
        focusedLine = ln;
        lines.classed('dimmed', d => false);           // avoid stale d3 data binding
        casings.classed('dimmed', false);
        lines.each(function () {
            const l = this.getAttribute('data-line');
            if (ln && l && l !== ln) d3.select(this).classed('dimmed', true);
        });
        casings.each(function () {
            const l = this.getAttribute('data-line');
            if (ln && l && l !== ln) d3.select(this).classed('dimmed', true);
        });
        allStations.each(function () {
            const l = this.getAttribute('data-line');
            if (ln && l && l !== ln) d3.select(this).classed('dimmed', true);
        });
    };
    const clearDim = () => {
        focusedLine = null;
        lines.classed('dimmed', false);
        casings.classed('dimmed', false);
        allStations.classed('dimmed', false);
    };

    lines.on('mouseenter', function () {
        const ln = this.getAttribute('data-line');
        if (ln) dimOthers(ln);
    }).on('mouseleave', clearDim);

    casings.on('mouseenter', function () {
        const ln = this.getAttribute('data-line');
        if (ln) dimOthers(ln);
    }).on('mouseleave', clearDim);
}

function onStationClick(stationId) {
    const st = state.stationMap[stationId];
    if(!st) return;
    if(!state.srcStation){ state.srcStation=st; updateSelectedDisplay('src-selected',st,'src'); }
    else if(!state.dstStation){ state.dstStation=st; updateSelectedDisplay('dst-selected',st,'dst'); }
    else { state.srcStation=state.dstStation; state.dstStation=st; updateSelectedDisplay('src-selected',state.srcStation,'src'); updateSelectedDisplay('dst-selected',state.dstStation,'dst'); }
    updatePlanButton(); updateMapSelection();
}

function onStationHover(stationId, event) {
    const st = state.stationMap[stationId];
    if(!st) return;
    const pos = state.activeLayout?.stations[stationId];
    const tt = document.getElementById('map-tooltip');
    tt.innerHTML = `<div class="tt-name">${st.name}</div><div class="tt-line" style="color:${LINE_COLORS[st.line]||'#666'}">${st.line}</div>${pos?.transfer_to?.length?`<div class="tt-transfer">换乘: ${pos.transfer_to.join(', ')}</div>`:''}${!st.is_open?'<div class="tt-closed">已关闭</div>':''}`;
    const rect = document.getElementById('map-container').getBoundingClientRect();
    tt.style.left = (event.clientX-rect.left+15)+'px';
    tt.style.top = (event.clientY-rect.top-10)+'px';
    tt.style.display = 'block';

    // Focus the station's line — dim all other lines.
    const g = state.gMap;
    if (g && st.line) {
        const ln = st.line;
        g.selectAll('.map-line,.map-line-casing').each(function () {
            const l = this.getAttribute('data-line');
            d3.select(this).classed('dimmed', l && l !== ln);
        });
        g.selectAll('.map-station').each(function () {
            const l = this.getAttribute('data-line');
            d3.select(this).classed('dimmed', l && l !== ln);
        });
    }
}

function onStationLeave() {
    document.getElementById('map-tooltip').style.display='none';
    // Clear line focus on mouse leave.
    const g = state.gMap;
    if (g) {
        g.selectAll('.map-line,.map-line-casing,.map-station').classed('dimmed', false);
    }
}

function updateMapSelection() {
    if(!state.gMap) return;
    state.gMap.selectAll('.map-station').attr('stroke', d => {
        const closed = new Set(state.stations.filter(s=>!s.is_open).map(s=>s.id));
        return closed.has(d.id)?'#444':'rgba(255,255,255,0.3)';
    }).attr('stroke-width', d => d.is_transfer?3:1);
    if(state.srcStation) state.gMap.selectAll(`.map-station[data-id="${state.srcStation.id}"]`).attr('stroke','#27ae60').attr('stroke-width',4).raise();
    if(state.dstStation) state.gMap.selectAll(`.map-station[data-id="${state.dstStation.id}"]`).attr('stroke','#e74c3c').attr('stroke-width',4).raise();
}

// ============================================================================
// Route Highlighting
// ============================================================================
// Compute SVG `r` attr value such that, after multiplication by the current
// zoom k, the rendered circle is `targetVisualPx` pixels wide. Used for
// overlay circles inside gMap (which inherits the zoom transform).
function screenRadius(targetVisualPx) {
    const k = state.currentK || 1;
    return Math.round((targetVisualPx / k) * 10) / 10;
}

function highlightRouteOnMap(idx) {
    if(!state.gMap || !state.routeResults.length) return;
    clearRouteHighlight();
    const path = state.routeResults[idx];
    if(!path||!path.valid||!path.station_ids) return;
    const ly = state.activeLayout?.stations||{};
    const g = state.gMap;
    for(let i=0;i<path.station_ids.length-1;i++){
        const a=ly[path.station_ids[i]], b=ly[path.station_ids[i+1]];
        if(a&&b){
            g.append('line').attr('class','map-route-glow').attr('x1',a.x).attr('y1',a.y).attr('x2',b.x).attr('y2',b.y);
            g.append('line').attr('class','map-route-edge').attr('x1',a.x).attr('y1',a.y).attr('x2',b.x).attr('y2',b.y);
        }
    }
    if(path.transfer_at) {
        path.transfer_at.forEach(t => {
            for(const [id,pos] of Object.entries(ly)) {
                if(pos.name===t.station_name && pos.is_transfer) {
                    g.append('circle').attr('class','map-transfer-marker')
                        .attr('cx',pos.x).attr('cy',pos.y)
                        .attr('r', screenRadius(10));
                    break;
                }
            }
        });
    }
    // Label highlight — match by station name. Labels are appended without
    // a d3 data binding, so we cannot rely on `d` in the each callback.
    // Path station_ids → set of names via stationMap; then test label text.
    const pathNames = new Set();
    path.station_ids.forEach(sid => {
        const st = state.stationMap[sid];
        if (st && st.name) pathNames.add(st.name);
    });
    state.gMap.selectAll('.map-label').each(function () {
        if (pathNames.has(this.textContent)) {
            d3.select(this).classed('highlighted', true);
        }
    });
}

function clearRouteHighlight() {
    if(!state.gMap) return;
    state.gMap.selectAll('.map-route-edge,.map-route-glow,.map-transfer-marker,.map-affected-station,.map-component-mark').remove();
    state.gMap.selectAll('.map-label.highlighted').classed('highlighted', false);
}

// ============================================================================
// Station Management
// ============================================================================
async function loadStationList() {
    const lf = document.getElementById('status-line-filter').value;
    const sf = document.getElementById('status-filter').value;
    const q = document.getElementById('status-search').value.trim().toLowerCase();
    try {
        const stations = await apiGet('/api/stations');
        state.stations = stations; stations.forEach(s=>{state.stationMap[s.id]=s;});
        let f = stations;
        if(lf) f = f.filter(s=>s.line===lf);
        if(sf==='open') f = f.filter(s=>s.is_open);
        if(sf==='closed') f = f.filter(s=>!s.is_open);
        if(q) f = f.filter(s=>s.name.toLowerCase().includes(q));
        const c = document.getElementById('station-list');
        c.innerHTML = f.map(s=>`<div class="station-list-item ${s.is_open?'':'closed'}"><div class="st-info"><span class="line-dot" style="background:${LINE_COLORS[s.line]||'#666'}"></span><span>${s.name}</span><span style="font-size:11px;color:var(--text-dim)">${s.line}</span></div><button class="toggle-btn ${s.is_open?'close-btn':'open-btn'}" data-id="${s.id}" data-action="${s.is_open?'close':'open'}">${s.is_open?'关闭':'开启'}</button></div>`).join('');
        c.querySelectorAll('.toggle-btn').forEach(btn => btn.addEventListener('click', async ()=>{
            const id=btn.dataset.id, act=btn.dataset.action;
            try {
                await apiPost(`/api/stations/${id}/${act}`,{});
                showToast(act==='close'?'站点已关闭':'站点已开启', act==='close'?'info':'success');
                await refreshAll();
            }catch(e){showToast(`操作失败: ${e.message}`,'error');}
        }));
    }catch(e){showToast(`加载失败: ${e.message}`,'error');}
}

async function initStatusPanel() {
    const lines = await apiGet('/api/lines');
    const sel = document.getElementById('status-line-filter');
    sel.innerHTML = '<option value="">全部线路</option>'+lines.map(l=>`<option value="${l.name}">${l.name} (${l.station_count})</option>`).join('');
    document.getElementById('status-line-filter').addEventListener('change', loadStationList);
    document.getElementById('status-filter').addEventListener('change', loadStationList);
    document.getElementById('status-search').addEventListener('input', debounce(loadStationList, 200));
    document.getElementById('btn-restore-all').addEventListener('click', async ()=>{
        if(!confirm('确定要恢复所有站点到初始状态吗？')) return;
        try { await apiPost('/api/stations/restore',{}); showToast('已恢复初始状态','success'); await refreshAll(); }
        catch(e){showToast(`恢复失败: ${e.message}`,'error');}
    });
    document.getElementById('batch-csv-input').addEventListener('change', async (e)=>{
        const file=e.target.files[0]; if(!file) return;
        const fd=new FormData(); fd.append('file',file);
        setLoading(true);
        try {
            const res=await fetch('/api/stations/batch-update',{method:'POST',body:fd});
            const data=await res.json();
            if(data.error) throw new Error(data.error);
            showToast(`批量更新: ${data.updated} 更新, ${data.not_found} 未找到, ${data.invalid} 无效`, 'info');
            await refreshAll();
        }catch(err){showToast(`批量更新失败: ${err.message}`,'error');}
        finally{setLoading(false); e.target.value='';}
    });
    await loadStationList();
}

// ============================================================================
// Network Analysis
// ============================================================================
function initAnalysisPanel() {
    let analysisStation = null;
    initStationSearch('analysis-station-input','analysis-station-results','analysis-station-selected', st => {
        analysisStation = st; updateSelectedDisplay('analysis-station-selected', st, 'src');
    });
    document.getElementById('bfs-depth').addEventListener('input', function(){ document.getElementById('bfs-depth-label').textContent=this.value; });
    document.getElementById('btn-affected-area').addEventListener('click', async ()=>{
        if(!analysisStation){ showToast('请先选择一个站点','error'); return; }
        setLoading(true);
        try {
            const data = await apiPost('/api/analysis/affected-area', {station_id:analysisStation.id, max_depth:parseInt(document.getElementById('bfs-depth').value)});
            document.getElementById('affected-result').innerHTML = `<div class="result-count">找到 ${data.affected_count} 个受影响站点 (深度=${data.max_depth})</div><div>${data.affected_stations.map(s=>`<div class="search-result-item" style="cursor:default"><span>${s.name}</span><span style="font-size:11px;color:${LINE_COLORS[s.line]||'#666'}">${s.line}</span></div>`).join('')}</div>`;
            highlightAffected(data.affected_stations.map(s=>s.id));
        }catch(e){showToast(`分析失败: ${e.message}`,'error');}
        finally{setLoading(false);}
    });
    document.getElementById('btn-components').addEventListener('click', async ()=>{
        setLoading(true);
        try {
            const data = await apiGet('/api/analysis/components');
            const c = document.getElementById('components-result');
            if(data.component_count===1){ c.innerHTML = `<div class="result-count" style="color:var(--success)">✅ 网络连通正常 (${data.total_stations} 个站点全连通)</div>`; }
            else { c.innerHTML = `<div class="result-count">⚠ 网络分裂为 ${data.component_count} 个连通分量</div>${data.components.map(cp=>`<div class="search-result-item" style="cursor:default"><span>分量 ${cp.index+1}</span><span><strong>${cp.size}</strong> 个站点</span></div>`).join('')}`; }
            if(data.component_count>1) highlightComponents(data.components);
        }catch(e){showToast(`分析失败: ${e.message}`,'error');}
        finally{setLoading(false);}
    });
}

function highlightAffected(ids) {
    if(!state.gMap) return;
    state.gMap.selectAll('.map-affected-station').remove();
    const ly = state.activeLayout?.stations||{};
    ids.forEach(id => { const p=ly[id]; if(p) state.gMap.append('circle').attr('class','map-affected-station').attr('cx',p.x).attr('cy',p.y).attr('r', screenRadius(10)); });
}

function highlightComponents(components) {
    if(!state.gMap) return;
    state.gMap.selectAll('.map-component-mark').remove();
    const ly = state.activeLayout?.stations||{};
    const colors = d3.schemeCategory10;
    components.forEach((comp,ci)=>{
        comp.stations.forEach(st=>{
            const p=ly[st.id]; if(!p) return;
            state.gMap.append('circle').attr('class','map-component-mark').attr('cx',p.x).attr('cy',p.y).attr('r', screenRadius(12)).attr('fill','none').attr('stroke',colors[ci%10]).attr('stroke-width',3).attr('stroke-dasharray','4,2').attr('opacity',0.6).attr('vector-effect','non-scaling-stroke');
        });
    });
}

// ============================================================================
// Panel Switching
// ============================================================================
function switchPanel(name) {
    state.activePanel = name;
    document.querySelectorAll('.nav-tab').forEach(t=>t.classList.toggle('active', t.dataset.panel===name));
    document.querySelectorAll('.panel').forEach(p=>p.classList.toggle('active', p.id===name));
    if(name!=='route-panel'){ clearRouteHighlight(); }
    if(name==='status-panel') loadStationList();
}

// ============================================================================
// Refresh
// ============================================================================
async function refreshAll() {
    try {
        const stations = await apiGet('/api/stations');
        state.stations = stations; stations.forEach(s=>{state.stationMap[s.id]=s;});
        document.getElementById('stat-stations').textContent = stations.length;
        document.getElementById('stat-closed').textContent = stations.filter(s=>!s.is_open).length;
        if(state.activePanel==='status-panel') await loadStationList();
        if(state.gMap){
            // Only remove elements that change with station status - NEVER remove metro lines!
            // .map-line and .map-line-casing are permanent topological subway line edges
            state.gMap.selectAll(
                '.map-station,.map-label,' +
                '.map-route-edge,.map-route-glow,.map-transfer-marker,' +
                '.map-affected-station,.map-component-mark,' +
                '.station-closed-x'
            ).remove();
            drawStations(state.gMap, state.activeLayout, state.stations);
            drawLabels(state.gMap, state.activeLayout);
            applyTuning(state.currentK);
            scheduleCollisionSettle();
            updateMapSelection();
        }
        updateSelectedDisplay('src-selected', state.srcStation, 'src');
        updateSelectedDisplay('dst-selected', state.dstStation, 'dst');
    }catch(e){showToast(`刷新失败: ${e.message}`,'error');}
}

function debounce(fn, ms) { let t; return (...a)=>{ clearTimeout(t); t=setTimeout(()=>fn(...a),ms); }; }

// ============================================================================
// Tuning Panel — live sliders for label sizing and tier thresholds.
// Data-driven from TUNING_DEFS; persists changes to localStorage.
// ============================================================================
function formatTuningValue(def, v) {
    const stepStr = String(def.step);
    const decimals = stepStr.includes('.') ? stepStr.split('.')[1].length : 0;
    return decimals === 0 ? String(Math.round(v)) : Number(v).toFixed(decimals);
}

function initTuningPanel() {
    if (!state.tuning) state.tuning = loadTuning();
    const container = document.getElementById('tuning-content');
    if (!container) return;
    container.innerHTML = '';

    // Layout mode dropdown handler
    const modeSelect = document.getElementById('layout-mode-select');
    if (modeSelect && !modeSelect._wired) {
        modeSelect._wired = true;
        modeSelect.value = state.layoutMode;
        modeSelect.addEventListener('change', (e) => {
            setLayoutMode(e.target.value);
        });
    }

    for (const def of TUNING_DEFS) {
        if (def.section) {
            const h = document.createElement('div');
            h.className = 'tune-section';
            h.textContent = def.section;
            container.appendChild(h);
        }
        const row = document.createElement('div');
        row.className = 'tune-row';
        row.id = `tune-row-${def.key}`;
        row.innerHTML = `
            <label>${def.label}</label>
            <input type="range" min="${def.min}" max="${def.max}" step="${def.step}" value="${state.tuning[def.key]}">
            <span class="tune-val">${formatTuningValue(def, state.tuning[def.key])}</span>`;
        container.appendChild(row);

        const input = row.querySelector('input');
        const valEl = row.querySelector('.tune-val');
        input.addEventListener('input', () => {
            const v = parseFloat(input.value);
            state.tuning[def.key] = v;
            valEl.textContent = formatTuningValue(def, v);
            saveTuning();

            // Invalidate SA positions: on any redraw trigger, or on anchor weight changes
            const saInvalidated =
                (def.key === 'useSA') ||
                (def.key === 'saMajorAnchor') ||
                (def.key === 'saNormalAnchor') ||
                (def.key === 'collisionPadding');

            if (def.redraw && state.gMap && state.layout) {
                // octi parameters: recompute schematic layout + full redraw
                if (def.key.startsWith('octi') && state.layoutMode === 'octilinear') {
                    state.octiLayout = computeOctilinearLayout();
                    if (state.octiLayout) {
                        state.activeLayout = state.octiLayout;
                        state.gMap.selectAll('.map-line, .map-line-casing, .map-station, .map-label, line').remove();
                        drawLines(state.gMap, state.activeLayout);
                        drawStations(state.gMap, state.activeLayout, state.stations);
                        drawLabels(state.gMap, state.activeLayout);
                    }
                } else {
                    // Just redraw labels (densityRadius/densityThreshold)
                    state.gMap.selectAll('.map-label').remove();
                    drawLabels(state.gMap, state.activeLayout);
                }
                state.sa.completed = false;
                state.sa.positions.clear();
            } else if (saInvalidated && state.gMap) {
                state.sa.completed = false;
                state.sa.positions.clear();
            }

            applyTuning(state.currentK);
            scheduleCollisionSettle();
        });
    }

    const resetBtn = document.getElementById('tune-reset');
    if (resetBtn && !resetBtn._wired) {
        resetBtn._wired = true;
        resetBtn.addEventListener('click', () => {
            state.tuning = { ...DEFAULT_TUNING };
            saveTuning();
            // Sync all slider DOM with the reset values.
            for (const def of TUNING_DEFS) {
                const row = document.getElementById(`tune-row-${def.key}`);
                if (!row) continue;
                const input = row.querySelector('input');
                const valEl = row.querySelector('.tune-val');
                if (input) input.value = state.tuning[def.key];
                if (valEl) valEl.textContent = formatTuningValue(def, state.tuning[def.key]);
            }
            // Reset layout mode to geographic
            state.layoutMode = 'geo';
            state.activeLayout = state.layout;
            state.octiLayout = null;
            if (state.gMap && state.layout) {
                state.gMap.selectAll('.map-line, .map-line-casing, .map-station, .map-label, line').remove();
                drawLines(state.gMap, state.activeLayout);
                drawStations(state.gMap, state.activeLayout, state.stations);
                drawLabels(state.gMap, state.activeLayout);
            }
            state.sa.completed = false;
            state.sa.positions.clear();
            applyTuning(state.currentK);
            scheduleCollisionSettle();
        });
    }
}

// ============================================================================
// Init
// ============================================================================
async function init() {
    try {
        await initMap();
        initStationSearch('src-input','src-results','src-selected', st => { state.srcStation=st; updateSelectedDisplay('src-selected',st,'src'); updatePlanButton(); updateMapSelection(); });
        initStationSearch('dst-input','dst-results','dst-selected', st => { state.dstStation=st; updateSelectedDisplay('dst-selected',st,'dst'); updatePlanButton(); updateMapSelection(); });
        document.getElementById('btn-plan').addEventListener('click', planRoute);
        updatePlanButton();
        ['src-input','dst-input'].forEach(id=>document.getElementById(id).addEventListener('keydown',e=>{ if(e.key==='Enter'&&state.srcStation&&state.dstStation) planRoute(); }));
        document.querySelectorAll('.nav-tab').forEach(t=>t.addEventListener('click', ()=>switchPanel(t.dataset.panel)));
        initStatusPanel();
        initAnalysisPanel();
        initTuningPanel();
        document.addEventListener('keydown', e => {
            if(e.key==='Escape'){
                state.srcStation=null; state.dstStation=null; state.routeResults=[];
                updateSelectedDisplay('src-selected',null,'src'); updateSelectedDisplay('dst-selected',null,'dst');
                updatePlanButton(); updateMapSelection(); clearRouteHighlight();
                document.getElementById('route-results').innerHTML='';
            }
        });
        window.addEventListener('resize', debounce(()=>{
            if(state.svg) { const c=document.getElementById('map-container'); state.svg.attr('width',c.clientWidth).attr('height',c.clientHeight); }
        },300));
        console.log('[OK] Metro frontend initialized');
    }catch(e){ console.error('Init error:',e); showToast(`初始化失败: ${e.message}`,'error'); }
}
document.addEventListener('DOMContentLoaded', init);
