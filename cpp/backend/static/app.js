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
};

const LINE_COLORS = {
    '1号线':'#E4002B','2号线':'#97D700','3号线':'#FCD600','4号线':'#461D84',
    '5号线':'#944D9B','6号线':'#D6006C','7号线':'#ED6B06','8号线':'#0094D8',
    '9号线':'#7AC8E1','10号线':'#C6AFD4','11号线':'#841C21','12号线':'#007A60',
    '13号线':'#E77CA5','14号线':'#9D8B63','15号线':'#B2A680','16号线':'#77D0C8',
    '17号线':'#BB6414','18号线':'#C4984E','浦江线':'#B5B5B6','市域机场线':'#4A90A4',
};

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
    const [layoutData, stationsData, linesData] = await Promise.all([
        apiGet('/api/layout'), apiGet('/api/stations'), apiGet('/api/lines')
    ]);
    state.layout = layoutData; state.stations = stationsData; state.lines = linesData;
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

    const zoom = d3.zoom().scaleExtent([0.3, 5]).on('zoom', e => gMap.attr('transform', e.transform));
    svg.call(zoom);
    state.zoom = zoom;

    drawLines(gMap, layoutData);
    drawStations(gMap, layoutData, stationsData);
    drawLabels(gMap, layoutData);

    const bbox = gMap.node().getBBox();
    if(bbox.width > 0) {
        const scale = Math.min((W-80)/bbox.width, (H-80)/bbox.height, 1.5);
        const tx = (W - bbox.width*scale)/2 - bbox.x*scale;
        const ty = (H - bbox.height*scale)/2 - bbox.y*scale;
        svg.call(zoom.transform, d3.zoomIdentity.translate(tx, ty).scale(scale));
    }
    document.getElementById('map-legend').innerHTML = `
        <div class="legend-item"><span class="legend-dot" style="background:#fff;border:2px solid #3498db"></span> 普通站</div>
        <div class="legend-item"><span class="legend-dot" style="background:#fff;border:3px solid #e74c3c;width:12px;height:12px"></span> 换乘站</div>
        <div class="legend-item"><span class="legend-dot" style="background:#555"></span> 关闭站</div>
        <div class="legend-item"><span style="display:inline-block;width:20px;height:4px;background:#f1c40f;border-radius:2px"></span> 规划路径</div>`;
}

function drawLines(gMap, layoutData) {
    const {stations:ly, lines} = layoutData;
    for(const [ln, info] of Object.entries(lines)) {
        const pts = info.station_ids.map(id=>ly[id]).filter(p=>p);
        if(pts.length<2) continue;
        const segs=[]; let cur=[pts[0]];
        for(let i=1;i<pts.length;i++){
            const d=Math.sqrt((pts[i].x-pts[i-1].x)**2+(pts[i].y-pts[i-1].y)**2);
            if(d>120){segs.push(cur);cur=[pts[i]];}else cur.push(pts[i]);
        }
        if(cur.length>=2) segs.push(cur);
        const color = info.color||'#666';
        segs.forEach(seg => {
            gMap.append('path').attr('class','map-line').attr('d', d3.line().x(d=>d.x).y(d=>d.y)(seg)).attr('stroke',color).attr('stroke-width',3.5);
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
        gMap.append('circle').attr('class',`map-station ${closedIds.has(d.id)?'closed':''}`).attr('cx',d.x).attr('cy',d.y).attr('r',5).attr('fill',closedIds.has(d.id)?'#555':(d.color||'#666')).attr('stroke','rgba(255,255,255,0.3)').attr('stroke-width',1).attr('data-id',d.id).on('click',(e,d)=>onStationClick(d.id)).on('mouseenter',(e,d)=>onStationHover(d.id,e)).on('mouseleave',onStationLeave);
    });
    transfer.forEach(d => {
        gMap.append('circle').attr('class',`map-station ${closedIds.has(d.id)?'closed':''}`).attr('cx',d.x).attr('cy',d.y).attr('r',8).attr('fill','#fff').attr('stroke',closedIds.has(d.id)?'#555':(d.color||'#666')).attr('stroke-width',3).attr('data-id',d.id).on('click',(e,d)=>onStationClick(d.id)).on('mouseenter',(e,d)=>onStationHover(d.id,e)).on('mouseleave',onStationLeave);
    });
    // X marks on closed
    [...regular, ...transfer].filter(d=>closedIds.has(d.id)).forEach(d => {
        gMap.append('line').attr('x1',d.x-5).attr('y1',d.y-5).attr('x2',d.x+5).attr('y2',d.y+5).attr('stroke','#e74c3c').attr('stroke-width',1.5);
        gMap.append('line').attr('x1',d.x+5).attr('y1',d.y-5).attr('x2',d.x-5).attr('y2',d.y+5).attr('stroke','#e74c3c').attr('stroke-width',1.5);
    });
}

function drawLabels(gMap, layoutData) {
    const {stations:ly} = layoutData;
    const transferIds = new Set();
    for(const [id,pos] of Object.entries(ly)) { if(pos.is_transfer) transferIds.add(id); }
    const labels = [];
    for(const [id,pos] of Object.entries(ly)) {
        const seq = parseInt(id.slice(2))||0;
        if(transferIds.has(id) || seq%3===0 || seq===1) labels.push({id,...pos});
    }
    labels.forEach(d => {
        gMap.append('text').attr('class','map-label').attr('x',d.x+10).attr('y',d.y-14).text(d.name).attr('font-size','10px');
    });
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
    const pos = state.layout?.stations[stationId];
    const tt = document.getElementById('map-tooltip');
    tt.innerHTML = `<div class="tt-name">${st.name}</div><div class="tt-line" style="color:${LINE_COLORS[st.line]||'#666'}">${st.line}</div>${pos?.transfer_to?.length?`<div class="tt-transfer">换乘: ${pos.transfer_to.join(', ')}</div>`:''}${!st.is_open?'<div class="tt-closed">已关闭</div>':''}`;
    const rect = document.getElementById('map-container').getBoundingClientRect();
    tt.style.left = (event.clientX-rect.left+15)+'px';
    tt.style.top = (event.clientY-rect.top-10)+'px';
    tt.style.display = 'block';
}

function onStationLeave() { document.getElementById('map-tooltip').style.display='none'; }

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
function highlightRouteOnMap(idx) {
    if(!state.gMap || !state.routeResults.length) return;
    clearRouteHighlight();
    const path = state.routeResults[idx];
    if(!path||!path.valid||!path.station_ids) return;
    const ly = state.layout?.stations||{};
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
                    g.append('circle').attr('class','map-transfer-marker').attr('cx',pos.x).attr('cy',pos.y).attr('r',10);
                    break;
                }
            }
        });
    }
    state.gMap.selectAll('.map-label').each(function(d) {
        if(path.station_ids.includes(d.id)) d3.select(this).attr('class','map-label highlighted');
    });
}

function clearRouteHighlight() {
    if(!state.gMap) return;
    state.gMap.selectAll('.map-route-edge,.map-route-glow,.map-transfer-marker,.map-affected-station,.map-component-mark').remove();
    state.gMap.selectAll('.map-label.highlighted').attr('class','map-label');
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
    const ly = state.layout?.stations||{};
    ids.forEach(id => { const p=ly[id]; if(p) state.gMap.append('circle').attr('class','map-affected-station').attr('cx',p.x).attr('cy',p.y).attr('r',10); });
}

function highlightComponents(components) {
    if(!state.gMap) return;
    state.gMap.selectAll('.map-component-mark').remove();
    const ly = state.layout?.stations||{};
    const colors = d3.schemeCategory10;
    components.forEach((comp,ci)=>{
        comp.stations.forEach(st=>{
            const p=ly[st.id]; if(!p) return;
            state.gMap.append('circle').attr('class','map-component-mark').attr('cx',p.x).attr('cy',p.y).attr('r',12).attr('fill','none').attr('stroke',colors[ci%10]).attr('stroke-width',3).attr('stroke-dasharray','4,2').attr('opacity',0.6);
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
        if(state.gMap){ state.gMap.selectAll('.map-station,.map-label,line').remove(); drawStations(state.gMap, state.layout, state.stations); drawLabels(state.gMap, state.layout); updateMapSelection(); }
        updateSelectedDisplay('src-selected', state.srcStation, 'src');
        updateSelectedDisplay('dst-selected', state.dstStation, 'dst');
    }catch(e){showToast(`刷新失败: ${e.message}`,'error');}
}

function debounce(fn, ms) { let t; return (...a)=>{ clearTimeout(t); t=setTimeout(()=>fn(...a),ms); }; }

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
