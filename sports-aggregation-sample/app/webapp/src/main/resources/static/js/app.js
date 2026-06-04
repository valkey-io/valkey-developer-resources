/**
 * Client-side JavaScript for the enhanced live GHL analytics dashboard.
 *
 * Features:
 * - Sidebar game ticker with sparklines
 * - Detail view with time-series charts (uPlot)
 * - History buffers for rolling chart data
 * - Live event feed from Valkey Streams
 * - Advanced stats panel
 */

// ===== STATE =====
let eventSource;
let selectedGameId = null;
let previousScores = {}; // track score changes for pulse animation

// History buffers per game (full game duration, x-axis is game-elapsed seconds 0-3600)
const gameHistory = {}; // gameId -> { elapsed, homeShots, awayShots, homeCorsi, awayCorsi, ... }

// uPlot chart instances
let charts = {
    winProb: null,
    shots: null,
    shotDiff: null,
    corsi: null,
    momentum: null,
    viewers: null,
    zone: null
};

// ===== TEAM COLORS & LOGOS =====
const TEAM_COLORS = {
    ARC: ['#1a237e', '#7c4dff'], VEG: ['#f57f17', '#fff176'], SOL: ['#ff6f00', '#ffd54f'],
    PRX: ['#4a148c', '#ce93d8'], SIR: ['#01579b', '#4fc3f7'], ALT: ['#1b5e20', '#69f0ae'],
    CAS: ['#880e4f', '#f48fb1'], POL: ['#263238', '#b0bec5'], CYG: ['#b71c1c', '#ef5350'],
    AND: ['#311b92', '#b388ff'], LYR: ['#0d47a1', '#82b1ff'], AQL: ['#e65100', '#ffab40'],
    ORI: ['#004d40', '#64ffda'], DRA: ['#1a237e', '#448aff'], CEN: ['#33691e', '#76ff03'],
    GEM: ['#4e342e', '#bcaaa4'], NEB: ['#0d47a1', '#ffd740'], PLR: ['#006064', '#84ffff'],
    HYD: ['#1a237e', '#00e676'], PHX: ['#bf360c', '#ff9100'], CRT: ['#3e2723', '#ff6e40'],
    LEO: ['#e65100', '#fff176'], AQR: ['#006064', '#18ffff'], SCR: ['#4a148c', '#ff1744'],
    VOI: ['#212121', '#9e9e9e'], TAU: ['#5d4037', '#ffab91'], PEG: ['#1565c0', '#e0e0e0'],
    ERI: ['#0097a7', '#e0f7fa'], LUP: ['#37474f', '#80cbc4'], CRV: ['#212121', '#7c4dff'],
    PER: ['#c62828', '#ffd54f'], VEL: ['#1a237e', '#80d8ff'],
};

function teamLogo(abbr, size = 24) {
    const [fill, accent] = TEAM_COLORS[abbr] || ['#455a64', '#90a4ae'];
    const r = size / 2;
    const cx = r, cy = r;
    // Hexagon points
    const pts = Array.from({length: 6}, (_, i) => {
        const a = Math.PI / 180 * (60 * i - 30);
        return `${cx + r * Math.cos(a)},${cy + r * Math.sin(a)}`;
    }).join(' ');
    return `<svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" style="flex-shrink:0">` +
        `<polygon points="${pts}" fill="${fill}" stroke="${accent}" stroke-width="2"/>` +
        `<text x="${cx}" y="${cy}" text-anchor="middle" dominant-baseline="central" ` +
        `fill="${accent}" font-size="${size * 0.32}px" font-weight="bold" font-family="monospace">${abbr}</text></svg>`;
}

// ===== SSE CONNECTION =====
function connect() {
    const status = document.getElementById('connectionStatus');
    eventSource = new EventSource('/api/sse/games');

    eventSource.addEventListener('update', function(e) {
        const data = JSON.parse(e.data);
        const games = (data.games || []).sort((a, b) => {
            const numA = parseInt(a.gameId.replace('game-', ''));
            const numB = parseInt(b.gameId.replace('game-', ''));
            return numA - numB;
        });
        const trending = data.trending || [];
        const winProbs = data.winProbabilities || [];
        const excitement = data.excitement || [];
        const periodStats = data.periodStats || {};
        const periodAverages = data.periodAverages || [];

        // Update history buffers
        updateHistory(games, winProbs);

        // Update UI
        updateTicker(games);
        updateTrending(trending);
        updateProbabilities(winProbs);
        document.getElementById('gameCount').textContent = games.length;

        // Update detail view if a game is selected
        if (selectedGameId) {
            const game = games.find(g => g.gameId === selectedGameId);
            const wp = winProbs.find(p => p.gameId === selectedGameId);
            if (game) {
                updateDetailView(game, wp);
                updateCharts();
                updateAdvancedStats(game);
                const gamePeriods = periodStats[selectedGameId] || [];
                updateAggregateSection(games, winProbs, gamePeriods, periodAverages);
            }
        }

        // Track scores for pulse animation
        games.forEach(g => { previousScores[g.gameId] = (previousScores[g.gameId] || 0); });
    });

    eventSource.onopen = function() {
        status.textContent = '● Connected';
        status.className = 'connection-status connected';
    };

    eventSource.onerror = function() {
        status.textContent = '● Reconnecting...';
        status.className = 'connection-status disconnected';
    };
}

// ===== HISTORY MANAGEMENT =====
function gameElapsedSeconds(game) {
    // Convert period + timeRemaining to total elapsed seconds (0-3600 for regulation)
    const period = game.period || 1;
    const parts = (game.timeRemaining || '20:00').split(':');
    const minutes = parseInt(parts[0]) || 0;
    const seconds = parseInt(parts[1]) || 0;
    const remainingInPeriod = minutes * 60 + seconds;
    const periodLength = period > 3 ? 300 : 1200; // OT is 5 min
    const elapsedInPeriod = periodLength - remainingInPeriod;
    const priorPeriods = Math.min(period - 1, 3) * 1200; // cap at 3 full periods
    const otExtra = period > 3 ? elapsedInPeriod : 0;
    return priorPeriods + (period <= 3 ? elapsedInPeriod : 0) + otExtra;
}

function updateHistory(games, winProbs) {
    games.forEach(game => {
        if (!gameHistory[game.gameId]) {
            gameHistory[game.gameId] = {
                elapsed: [],
                homeShots: [], awayShots: [],
                homeCorsi: [], awayCorsi: [],
                homeMomentum: [], awayMomentum: [],
                viewers: [],
                homeZoneTime: [], awayZoneTime: [],
                winProb: [],
                backfilledShots: [],
                homeTeam: game.homeTeam,
                awayTeam: game.awayTeam
            };
        }
        const h = gameHistory[game.gameId];
        const t = gameElapsedSeconds(game);

        // Store team info for backfill dot rendering
        h.homeTeam = game.homeTeam;
        h.awayTeam = game.awayTeam;

        // Avoid duplicate timestamps (same game tick) — update in place if values changed
        if (h.elapsed.length > 0 && h.elapsed[h.elapsed.length - 1] === t) {
            const last = h.elapsed.length - 1;
            h.homeShots[last] = game.homeShots;
            h.awayShots[last] = game.awayShots;
            h.homeCorsi[last] = game.homeCorsi;
            h.awayCorsi[last] = game.awayCorsi;
            h.homeMomentum[last] = game.homeMomentum;
            h.awayMomentum[last] = game.awayMomentum;
            h.viewers[last] = game.viewers;
            h.homeZoneTime[last] = game.homeZoneTime;
            h.awayZoneTime[last] = game.awayZoneTime;
            const wp = winProbs.find(p => p.gameId === game.gameId);
            if (wp) h.winProb[last] = wp.homeProbability;
            return;
        }

        h.elapsed.push(t);
        h.homeShots.push(game.homeShots);
        h.awayShots.push(game.awayShots);
        h.homeCorsi.push(game.homeCorsi);
        h.awayCorsi.push(game.awayCorsi);
        h.homeMomentum.push(game.homeMomentum);
        h.awayMomentum.push(game.awayMomentum);
        h.viewers.push(game.viewers);
        h.homeZoneTime.push(game.homeZoneTime);
        h.awayZoneTime.push(game.awayZoneTime);

        const wp = winProbs.find(p => p.gameId === game.gameId);
        h.winProb.push(wp ? wp.homeProbability : 50);

        // No trim needed — game is finite (max ~3600s / 2s per tick = ~1800 points)
    });
}

// ===== GAME SELECTION =====
function selectGame(gameId) {
    selectedGameId = gameId;

    // Update sidebar selection
    document.querySelectorAll('.ticker-item').forEach(el => {
        el.classList.toggle('selected', el.dataset.gameId === gameId);
    });

    // Show detail sections
    document.getElementById('chartsSection').classList.remove('hidden');
    document.getElementById('bottomSection').classList.remove('hidden');
    document.getElementById('aggregateSection').classList.remove('hidden');

    // Destroy old charts and recreate
    destroyCharts();

    // Fetch current game state immediately so detail view renders without waiting for next SSE tick
    fetch('/api/games')
        .then(r => r.json())
        .then(games => {
            const game = games.find(g => g.gameId === gameId);
            if (game && gameId === selectedGameId) {
                updateDetailView(game, null);
                updateAdvancedStats(game);
            }
        })
        .catch(() => {});

    // Backfill shot history from Valkey stream, then create charts
    backfillShotHistory(gameId).then(() => {
        createCharts();
    });
}

/** Fetch historical events from the stream and pre-populate shot dots in the history buffer */
function backfillShotHistory(gameId) {
    // First get the game state to know which team is home
    return fetch(`/api/games`)
        .then(r => r.json())
        .then(games => {
            const game = games.find(g => g.gameId === gameId);
            if (!game) return;

            // Ensure history buffer exists with correct team info
            if (!gameHistory[gameId]) {
                gameHistory[gameId] = {
                    elapsed: [],
                    homeShots: [], awayShots: [],
                    homeCorsi: [], awayCorsi: [],
                    homeMomentum: [], awayMomentum: [],
                    viewers: [],
                    homeZoneTime: [], awayZoneTime: [],
                    winProb: [],
                    backfilledShots: [],
                    homeTeam: game.homeTeam,
                    awayTeam: game.awayTeam
                };
            }
            const h = gameHistory[gameId];
            h.homeTeam = game.homeTeam;
            h.awayTeam = game.awayTeam;

            // Now fetch events
            return fetch(`/api/events/${gameId}?count=2000`)
                .then(r => r.json())
                .then(events => {
                    if (!events || events.length === 0) return;

                    if (!h.backfilledShots) h.backfilledShots = [];

                    const shotEvents = events.filter(ev => ev.type === 'shot');
                    shotEvents.forEach(ev => {
                        const elapsed = eventToElapsed(ev.period, ev.time);
                        if (elapsed !== null) {
                            h.backfilledShots.push({ elapsed, team: ev.team });
                        }
                    });

                    h.backfilledShots.sort((a, b) => a.elapsed - b.elapsed);
                });
        })
        .catch(err => {
            console.warn('Failed to backfill shot history:', err);
        });
}

/** Convert event period + time string (e.g. period=2, time="14:32") to game-elapsed seconds */
function eventToElapsed(period, timeStr) {
    if (!timeStr || !period) return null;
    const parts = timeStr.split(':');
    const minutes = parseInt(parts[0]) || 0;
    const seconds = parseInt(parts[1]) || 0;
    const remainingInPeriod = minutes * 60 + seconds;
    const periodLength = period > 3 ? 300 : 1200;
    const elapsedInPeriod = periodLength - remainingInPeriod;
    const priorPeriods = Math.min(period - 1, 3) * 1200;
    return priorPeriods + (period <= 3 ? elapsedInPeriod : 0) + (period > 3 ? elapsedInPeriod : 0);
}

// ===== TICKER UPDATE =====
function updateTicker(games) {
    const ticker = document.getElementById('gameTicker');
    ticker.innerHTML = games.map(game => {
        const isSelected = game.gameId === selectedGameId ? 'selected' : '';
        const sparkSvg = generateSparkline(game.gameId);
        return `
        <div class="ticker-item ${game.status} ${isSelected}" data-game-id="${game.gameId}" onclick="selectGame('${game.gameId}')">
            <div class="ticker-status-dot"></div>
            <div class="ticker-teams">
                <div class="ticker-team">
                    ${teamLogo(game.awayTeam, 20)}
                    <span class="ticker-abbr">${game.awayTeam}</span>
                    <span class="ticker-score">${game.awayScore}</span>
                </div>
                <div class="ticker-team">
                    ${teamLogo(game.homeTeam, 20)}
                    <span class="ticker-abbr">${game.homeTeam}</span>
                    <span class="ticker-score">${game.homeScore}</span>
                </div>
            </div>
            <div class="ticker-period">P${game.period} ${game.timeRemaining}</div>
            ${sparkSvg}
        </div>`;
    }).join('');
}

function generateSparkline(gameId) {
    const h = gameHistory[gameId];
    if (!h || h.winProb.length < 2) return '<div class="ticker-sparkline"></div>';

    const data = h.winProb.slice(-30);
    const width = 100;
    const height = 18;
    const step = width / (data.length - 1);

    const points = data.map((v, i) => `${i * step},${height - (v / 100 * height)}`).join(' ');

    return `<div class="ticker-sparkline">
        <svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none">
            <polyline points="${points}" fill="none" stroke="var(--accent)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
            <line x1="0" y1="${height/2}" x2="${width}" y2="${height/2}" stroke="var(--border-light)" stroke-width="0.5" stroke-dasharray="2,2"/>
        </svg>
    </div>`;
}

// ===== DETAIL VIEW =====
function updateChartLegends(game) {
    const home = game.homeTeam;
    const away = game.awayTeam;

    // Two-team legend (away first = teal, home second = red)
    const twoTeam = `<span class="home-label">${away}</span><span class="legend-sep">·</span><span class="away-label">${home}</span>`;
    // Differential legend (positive = away team advantage)
    const diffLegend = `<span style="color:var(--text-dim)">above 0 =</span> <span class="home-label">${away}</span>`;
    // Win prob (shows away team since teal line = away win %)
    const wpLegend = `<span class="home-label">${away}</span> <span style="color:var(--text-muted)">win %</span>`;

    const el = (id, html) => { const e = document.getElementById(id); if (e) e.innerHTML = html; };
    el('legendWinProb', wpLegend);
    el('legendMomentum', twoTeam);
    el('legendShots', twoTeam);
    el('legendShotDiff', diffLegend);
    el('legendCorsi', twoTeam);
    el('legendZone', twoTeam);
}

function updateDetailView(game, wp) {
    const detail = document.getElementById('gameDetail');
    const homeName = TEAMS[game.homeTeam] || game.homeTeam;
    const awayName = TEAMS[game.awayTeam] || game.awayTeam;
    const statusClass = game.status === 'final' ? 'final' : game.status === 'intermission' ? 'intermission' : '';

    document.getElementById('detailTitle').textContent = `${awayName} at ${homeName}`;
    updateChartLegends(game);

    detail.innerHTML = `
        <div class="detail-header">
            <div class="detail-team">
                ${teamLogo(game.awayTeam, 48)}
                <span class="detail-team-name">${awayName}</span>
            </div>
            <div class="detail-score">${game.awayScore}</div>
            <div class="detail-center">
                <span class="detail-status-badge ${statusClass}">${game.status}</span>
                <span class="detail-period">Period ${game.period}</span>
                <span class="detail-time">${game.timeRemaining}</span>
                <span style="font-size:0.75rem;color:var(--text-dim);margin-top:4px;">👁 ${formatNumber(game.viewers)}</span>
            </div>
            <div class="detail-score">${game.homeScore}</div>
            <div class="detail-team">
                ${teamLogo(game.homeTeam, 48)}
                <span class="detail-team-name">${homeName}</span>
            </div>
        </div>
        <div class="momentum-bar-container">
            <div class="momentum-bar">
                <div class="home-momentum" style="width:${game.awayMomentum}%"></div>
                <div class="away-momentum" style="width:${game.homeMomentum}%"></div>
            </div>
            <div class="momentum-label">
                <span>${game.awayTeam} momentum ${game.awayMomentum.toFixed(0)}%</span>
                <span>${game.homeTeam} momentum ${game.homeMomentum.toFixed(0)}%</span>
            </div>
        </div>
        <div class="win-prob-inline">
            <div class="prob-bar-container">
                <div class="prob-bar home" style="width:${wp ? wp.awayProbability : 50}%">
                    <span>${wp ? wp.awayProbability : 50}%</span>
                </div>
                <div class="prob-bar away" style="width:${wp ? wp.homeProbability : 50}%">
                    <span>${wp ? wp.homeProbability : 50}%</span>
                </div>
            </div>
            <div class="prob-label">
                <span class="home-pct">${game.awayTeam} win</span>
                <span class="away-pct">${game.homeTeam} win</span>
            </div>
        </div>
    `;
}

// ===== CHARTS (uPlot) =====
function createCharts() {
    const h = gameHistory[selectedGameId];
    if (!h || h.elapsed.length < 2) return;

    const width = getChartWidth();
    const height = 150;

    // Fixed x-axis: 0 to 3600 seconds (3 periods × 20 min)
    // Period dividers at 1200 and 2400
    function fmtGameTime(self, rawValue) {
        const period = Math.floor(rawValue / 1200) + 1;
        const inPeriod = rawValue % 1200;
        const min = Math.floor(inPeriod / 60);
        return `P${Math.min(period, 3)} ${min}:00`;
    }

    // Draw period divider lines via a plugin
    const periodDividersPlugin = {
        hooks: {
            draw: [
                (u) => {
                    const ctx = u.ctx;
                    const { left, top, width, height } = u.bbox;
                    ctx.save();
                    ctx.strokeStyle = '#3a4a5a';
                    ctx.lineWidth = 1;
                    ctx.setLineDash([4, 4]);
                    // Period 1/2 divider at 1200s
                    const x1 = u.valToPos(1200, 'x', true);
                    ctx.beginPath(); ctx.moveTo(x1, top); ctx.lineTo(x1, top + height); ctx.stroke();
                    // Period 2/3 divider at 2400s
                    const x2 = u.valToPos(2400, 'x', true);
                    ctx.beginPath(); ctx.moveTo(x2, top); ctx.lineTo(x2, top + height); ctx.stroke();
                    ctx.restore();

                    // Period labels
                    ctx.save();
                    ctx.fillStyle = '#4a5568';
                    ctx.font = '9px sans-serif';
                    ctx.textAlign = 'center';
                    const p1x = u.valToPos(600, 'x', true);
                    const p2x = u.valToPos(1800, 'x', true);
                    const p3x = u.valToPos(3000, 'x', true);
                    ctx.fillText('1st', p1x, top + 12);
                    ctx.fillText('2nd', p2x, top + 12);
                    ctx.fillText('3rd', p3x, top + 12);
                    ctx.restore();
                }
            ]
        }
    };

    const baseOpts = {
        width,
        height,
        plugins: [periodDividersPlugin],
        cursor: { show: true, x: true, y: false },
        legend: { show: false },
        scales: {
            x: { min: 0, max: 3600, auto: false }
        },
        axes: [
            {
                stroke: '#6b7d8f',
                grid: { show: false },
                ticks: { stroke: '#2a3a4a', width: 1 },
                font: '9px sans-serif',
                size: 24,
                values: (self, ticks) => ticks.map(v => {
                    const p = Math.floor(v / 1200) + 1;
                    const m = Math.floor((v % 1200) / 60);
                    return m === 0 ? `P${Math.min(p,3)}` : `${m}m`;
                }),
                gap: 4
            },
            {
                stroke: '#6b7d8f',
                grid: { stroke: '#1e2d3d', width: 1 },
                size: 40,
                font: '10px sans-serif',
                ticks: { show: false }
            }
        ]
    };

    // Win Probability (away team win % — teal line)
    const awayWinProb = h.winProb.map(v => 100 - v); // winProb stores home %, flip to away %
    charts.winProb = new uPlot({
        ...baseOpts,
        series: [
            {},
            { stroke: '#00d4aa', width: 2, fill: 'rgba(0,212,170,0.1)' }
        ],
        scales: { x: { min: 0, max: 3600, auto: false }, y: { min: 0, max: 100, auto: false } }
    }, [h.elapsed, awayWinProb], document.getElementById('chartWinProb'));

    // Shots (dot strip — colored dots on x-axis showing when shots happen)
    createShotDotsChart();

    // Shot Differential (cumulative awayShots - homeShots) — positive = away advantage
    const shotDiff = h.awayShots.map((v, i) => v - h.homeShots[i]);
    const maxDiff = Math.max(3, Math.abs(Math.min(...shotDiff)), Math.abs(Math.max(...shotDiff)));
    charts.shotDiff = new uPlot({
        ...baseOpts,
        height: 80,
        series: [
            {},
            {
                stroke: '#e8eaed',
                width: 2,
                fill: 'rgba(255,255,255,0.03)'
            }
        ],
        scales: { x: { min: 0, max: 3600, auto: false }, y: { min: -maxDiff - 1, max: maxDiff + 1, auto: false } },
        axes: [
            {
                stroke: '#6b7d8f',
                grid: { show: false },
                ticks: { stroke: '#2a3a4a', width: 1 },
                font: '9px sans-serif',
                size: 24,
                values: (self, ticks) => ticks.map(v => {
                    const p = Math.floor(v / 1200) + 1;
                    const m = Math.floor((v % 1200) / 60);
                    return m === 0 ? `P${Math.min(p,3)}` : `${m}m`;
                }),
                gap: 4
            },
            {
                stroke: '#6b7d8f',
                grid: { stroke: '#1e2d3d', width: 1 },
                size: 32,
                font: '9px sans-serif',
                ticks: { show: true, stroke: '#2a3a4a', width: 1 },
                incrs: [1, 2, 5, 10],
                values: (self, ticks) => ticks.map(v => {
                    const n = Math.round(v);
                    if (n === 0) return '0';
                    return (n > 0 ? '+' : '') + n;
                })
            }
        ]
    }, [h.elapsed, shotDiff], document.getElementById('chartShotDiff'));

    // Corsi — half height, force y-axis to show values
    charts.corsi = new uPlot({
        ...baseOpts,
        height: 70,
        series: [
            {},
            { stroke: '#00d4aa', width: 2 },
            { stroke: '#ff4757', width: 2 }
        ],
        scales: { x: { min: 0, max: 3600, auto: false }, y: { auto: true } },
        axes: [
            baseOpts.axes[0],
            {
                stroke: '#6b7d8f',
                grid: { stroke: '#1e2d3d', width: 1 },
                size: 36,
                font: '9px sans-serif',
                ticks: { show: true, stroke: '#2a3a4a', width: 1 }
            }
        ]
    }, [h.elapsed, h.awayCorsi, h.homeCorsi], document.getElementById('chartCorsi'));

    // Zone Time — half height, fixed 30-70 range so differences are visible
    charts.zone = new uPlot({
        ...baseOpts,
        height: 70,
        series: [
            {},
            { stroke: '#00d4aa', width: 2 },
            { stroke: '#ff4757', width: 2 }
        ],
        scales: { x: { min: 0, max: 3600, auto: false }, y: { min: 30, max: 70, auto: false } },
        axes: [
            baseOpts.axes[0],
            {
                stroke: '#6b7d8f',
                grid: { stroke: '#1e2d3d', width: 1 },
                size: 36,
                font: '9px sans-serif',
                ticks: { show: true, stroke: '#2a3a4a', width: 1 },
                values: (self, ticks) => ticks.map(v => v + '%')
            }
        ]
    }, [h.elapsed, h.awayZoneTime, h.homeZoneTime], document.getElementById('chartZone'));

    // Momentum — full height
    charts.momentum = new uPlot({
        ...baseOpts,
        series: [
            {},
            { stroke: '#00d4aa', width: 2, fill: 'rgba(0,212,170,0.08)' },
            { stroke: '#ff4757', width: 2, fill: 'rgba(255,71,87,0.08)' }
        ],
        scales: { x: { min: 0, max: 3600, auto: false }, y: { min: 0, max: 100, auto: false } }
    }, [h.elapsed, h.awayMomentum, h.homeMomentum], document.getElementById('chartMomentum'));

    // Viewers — full height
    charts.viewers = new uPlot({
        ...baseOpts,
        series: [
            {},
            { stroke: '#3b82f6', width: 2, fill: 'rgba(59,130,246,0.1)' }
        ],
        scales: { x: { min: 0, max: 3600, auto: false } }
    }, [h.elapsed, h.viewers], document.getElementById('chartViewers'));
}

function createShotDotsChart() {
    const h = gameHistory[selectedGameId];
    if (!h || h.elapsed.length < 2) return;

    const width = getChartWidth();
    const homeShotDeltas = h.homeShots.map((v, i) => i === 0 ? 0 : v - h.homeShots[i-1]);
    const awayShotDeltas = h.awayShots.map((v, i) => i === 0 ? 0 : v - h.awayShots[i-1]);
    const homeTotal = h.homeShots[h.homeShots.length - 1] || 0;
    const awayTotal = h.awayShots[h.awayShots.length - 1] || 0;
    const backfilled = h.backfilledShots || [];

    // Away team is teal (top), home team is red (bottom)
    const homeTeam = h.homeTeam || '';

    const shotDotsPlugin = {
        hooks: {
            draw: [
                (u) => {
                    const ctx = u.ctx;
                    const { left, top, width: bw, height: bh } = u.bbox;
                    const midY = top + bh / 2;
                    const rightCutoff = left + bw - 35;

                    // Draw backfilled shots first (slightly transparent to distinguish)
                    if (backfilled.length > 0) {
                        backfilled.forEach(shot => {
                            const x = u.valToPos(shot.elapsed, 'x', true);
                            if (x < left || x > rightCutoff) return;
                            const isAway = shot.team !== homeTeam;
                            ctx.fillStyle = isAway ? 'rgba(0,212,170,0.5)' : 'rgba(255,71,87,0.5)';
                            ctx.beginPath();
                            ctx.arc(x, isAway ? midY - 7 : midY + 7, 3, 0, Math.PI * 2);
                            ctx.fill();
                        });
                    }

                    // Draw live shots — away (teal, above), home (red, below)
                    ctx.fillStyle = '#00d4aa';
                    for (let i = 0; i < awayShotDeltas.length; i++) {
                        if (awayShotDeltas[i] > 0) {
                            const x = u.valToPos(h.elapsed[i], 'x', true);
                            if (x > rightCutoff) continue;
                            ctx.beginPath();
                            ctx.arc(x, midY - 7, 3, 0, Math.PI * 2);
                            ctx.fill();
                        }
                    }

                    ctx.fillStyle = '#ff4757';
                    for (let i = 0; i < homeShotDeltas.length; i++) {
                        if (homeShotDeltas[i] > 0) {
                            const x = u.valToPos(h.elapsed[i], 'x', true);
                            if (x > rightCutoff) continue;
                            ctx.beginPath();
                            ctx.arc(x, midY + 7, 3, 0, Math.PI * 2);
                            ctx.fill();
                        }
                    }

                    // Running totals on the right edge (away teal top, home red bottom)
                    ctx.font = 'bold 11px sans-serif';
                    ctx.textAlign = 'right';
                    ctx.fillStyle = '#00d4aa';
                    ctx.fillText(awayTotal.toString(), left + bw - 2, midY - 4);
                    ctx.fillStyle = '#ff4757';
                    ctx.fillText(homeTotal.toString(), left + bw - 2, midY + 13);

                    // Center divider
                    ctx.strokeStyle = '#2a3a4a';
                    ctx.lineWidth = 0.5;
                    ctx.beginPath();
                    ctx.moveTo(left, midY);
                    ctx.lineTo(left + bw - 30, midY);
                    ctx.stroke();

                    // Period dividers
                    ctx.strokeStyle = '#3a4a5a';
                    ctx.lineWidth = 1;
                    ctx.setLineDash([4, 4]);
                    const x1 = u.valToPos(1200, 'x', true);
                    ctx.beginPath(); ctx.moveTo(x1, top); ctx.lineTo(x1, top + bh); ctx.stroke();
                    const x2 = u.valToPos(2400, 'x', true);
                    ctx.beginPath(); ctx.moveTo(x2, top); ctx.lineTo(x2, top + bh); ctx.stroke();
                    ctx.setLineDash([]);
                }
            ]
        }
    };

    charts.shots = new uPlot({
        width,
        height: 36,
        plugins: [shotDotsPlugin],
        cursor: { show: false },
        legend: { show: false },
        series: [{}],
        scales: { x: { min: 0, max: 3600, auto: false }, y: { min: 0, max: 1, auto: false } },
        axes: [{ show: false }, { show: false }]
    }, [h.elapsed], document.getElementById('chartShots'));
}

function updateCharts() {
    const h = gameHistory[selectedGameId];
    if (!h || h.elapsed.length < 2) return;

    if (charts.winProb) {
        const awayWinProb = h.winProb.map(v => 100 - v);
        charts.winProb.setData([h.elapsed, awayWinProb]);
    }

    // Shots dot strip — recreate since plugin draws from computed data
    if (charts.shots) {
        charts.shots.destroy();
        charts.shots = null;
        document.getElementById('chartShots').innerHTML = '';
    }
    createShotDotsChart();

    if (charts.shotDiff) {
        const shotDiff = h.awayShots.map((v, i) => v - h.homeShots[i]);
        charts.shotDiff.setData([h.elapsed, shotDiff]);
    }
    if (charts.corsi) charts.corsi.setData([h.elapsed, h.awayCorsi, h.homeCorsi]);
    if (charts.momentum) charts.momentum.setData([h.elapsed, h.awayMomentum, h.homeMomentum]);
    if (charts.viewers) charts.viewers.setData([h.elapsed, h.viewers]);
    if (charts.zone) charts.zone.setData([h.elapsed, h.awayZoneTime, h.homeZoneTime]);
}

function destroyCharts() {
    Object.keys(charts).forEach(k => {
        if (charts[k]) {
            charts[k].destroy();
            charts[k] = null;
        }
    });
    // Clear chart containers
    ['chartWinProb', 'chartShots', 'chartShotDiff', 'chartCorsi', 'chartMomentum', 'chartViewers', 'chartZone'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.innerHTML = '';
    });
}

function getChartWidth() {
    const container = document.querySelector('.chart-card .chart-container');
    return container ? container.clientWidth - 10 : 400;
}

// ===== AGGREGATE ANALYTICS =====
function updateAggregateSection(games, winProbs, gamePeriods, periodAverages) {
    const section = document.getElementById('aggregateSection');
    if (!selectedGameId) return;
    section.classList.remove('hidden');

    // Per-period breakdown from server-stored data + league averages from FT.AGGREGATE
    updatePeriodStats(gamePeriods, periodAverages);

    // Excitement ranking across all games
    updateExcitementRanking(games, winProbs);
}

function updatePeriodStats(gamePeriods, periodAverages) {
    const container = document.getElementById('periodStats');

    if (!gamePeriods || gamePeriods.length === 0) {
        container.innerHTML = '<p class="empty-state">Waiting for period data...</p>';
        return;
    }

    // Build averages lookup by period
    const avgByPeriod = {};
    (periodAverages || []).forEach(a => {
        avgByPeriod[a.period] = a;
    });

    const periodLabels = ['1st Period', '2nd Period', '3rd Period'];

    container.innerHTML = gamePeriods.map((p, idx) => {
        const label = periodLabels[idx] || `Period ${p.period}`;
        const avg = avgByPeriod[p.period] || {};

        const avgHomeShots = avg.avgHomeShots ? parseFloat(avg.avgHomeShots).toFixed(0) : '—';
        const avgAwayShots = avg.avgAwayShots ? parseFloat(avg.avgAwayShots).toFixed(0) : '—';
        const avgMomentum = avg.avgMomentum ? parseFloat(avg.avgMomentum).toFixed(0) + '%' : '—';
        const avgZone = avg.avgZoneTime ? parseFloat(avg.avgZoneTime).toFixed(0) + '%' : '—';

        return `<div class="period-card">
            <h5>${label}</h5>
            <div class="period-score">${p.awayGoals || 0} - ${p.homeGoals || 0}</div>
            <div class="period-stat">
                <span class="label">SOG</span>
                <span>${p.awayShots} - ${p.homeShots}</span>
                <span class="avg-compare" title="League avg">avg ${avgAwayShots}-${avgHomeShots}</span>
            </div>
            <div class="period-stat">
                <span class="label">Corsi</span>
                <span>${p.awayCorsi} - ${p.homeCorsi}</span>
                <span class="avg-compare" title="League avg">avg ${avg.avgAwayCorsi ? parseFloat(avg.avgAwayCorsi).toFixed(0) + '-' + parseFloat(avg.avgHomeCorsi).toFixed(0) : '—'}</span>
            </div>
            <div class="period-stat">
                <span class="label">Hits</span>
                <span>${p.awayHits} - ${p.homeHits}</span>
                <span class="avg-compare"></span>
            </div>
            <div class="period-stat">
                <span class="label">Momentum</span>
                <span>${parseFloat(p.avgHomeMomentum || 50).toFixed(0)}%</span>
                <span class="avg-compare" title="League avg">avg ${avgMomentum}</span>
            </div>
            <div class="period-stat">
                <span class="label">Zone</span>
                <span>${parseFloat(p.avgHomeZoneTime || 50).toFixed(0)}%</span>
                <span class="avg-compare" title="League avg">avg ${avgZone}</span>
            </div>
        </div>`;
    }).join('');
}

function updateExcitementRanking(games, winProbs) {
    const container = document.getElementById('excitementRanking');
    if (!games || games.length === 0) {
        container.innerHTML = '<p class="empty-state">No games</p>';
        return;
    }

    // Compute excitement score: combines closeness, shot volume, momentum swing, viewers
    // In production this is an FT.AGGREGATE with APPLY computing the formula server-side
    const ranked = games
        .filter(g => g.status === 'live' || g.status === 'intermission')
        .map(g => {
            const closeness = Math.max(0, 10 - Math.abs(g.homeScore - g.awayScore) * 3);
            const shotVolume = (g.homeShots + g.awayShots) / 10;
            const momentumSwing = Math.abs(g.homeMomentum - 50) / 10;
            const viewerFactor = g.viewers / 10000;
            const score = (closeness * 3 + shotVolume * 2 + momentumSwing * 2 + viewerFactor).toFixed(1);
            return { ...g, excitementScore: parseFloat(score) };
        })
        .sort((a, b) => b.excitementScore - a.excitementScore);

    if (ranked.length === 0) {
        container.innerHTML = '<p class="empty-state">No live games</p>';
        return;
    }

    container.innerHTML = ranked.map(g => `
        <div class="excitement-item">
            <span class="excitement-score">${g.excitementScore}</span>
            <div>
                <div class="excitement-matchup">
                    ${teamLogo(g.homeTeam, 18)} ${g.homeTeam} ${g.homeScore} - ${g.awayScore} ${g.awayTeam} ${teamLogo(g.awayTeam, 18)}
                </div>
                <div class="excitement-factors">Closeness: ${(10 - Math.abs(g.homeScore - g.awayScore) * 3).toFixed(0)} · Shots: ${g.homeShots + g.awayShots} · Viewers: ${formatNumber(g.viewers)}</div>
            </div>
        </div>
    `).join('');
}

// ===== ADVANCED STATS =====
function updateAdvancedStats(game) {
    const stats = document.getElementById('advancedStats');
    const totalFaceoffs = game.homeFaceoffWins + game.awayFaceoffWins || 1;
    const homeFO = ((game.homeFaceoffWins / totalFaceoffs) * 100).toFixed(0);
    const awayFO = ((game.awayFaceoffWins / totalFaceoffs) * 100).toFixed(0);

    // Display order: away (left/teal) vs home (right/red)
    const rows = [
        { label: 'SOG', left: game.awayShots, right: game.homeShots },
        { label: 'Corsi', left: game.awayCorsi, right: game.homeCorsi },
        { label: 'Hits', left: game.awayHits, right: game.homeHits },
        { label: 'Blocks', left: game.awayBlockedShots, right: game.homeBlockedShots },
        { label: 'PP', left: game.awayPowerPlays, right: game.homePowerPlays },
        { label: 'PIM', left: game.awayPenaltyMinutes, right: game.homePenaltyMinutes },
        { label: 'FO%', left: awayFO + '%', right: homeFO + '%' },
        { label: 'SV%', left: game.awaySavePercentage.toFixed(1) + '%', right: game.homeSavePercentage.toFixed(1) + '%' },
        { label: 'Zone', left: game.awayZoneTime.toFixed(0) + '%', right: game.homeZoneTime.toFixed(0) + '%' },
    ];

    stats.innerHTML = rows.map(r => {
        const leftNum = parseFloat(r.left) || 0;
        const rightNum = parseFloat(r.right) || 0;
        const total = leftNum + rightNum || 1;
        const leftPct = (leftNum / total * 100).toFixed(0);
        const rightPct = (rightNum / total * 100).toFixed(0);
        return `
        <div class="stat-row">
            <span class="home-val">${r.left}</span>
            <div class="stat-bar-container home"><div class="stat-bar-home" style="width:${leftPct}%"></div></div>
            <span class="stat-label">${r.label}</span>
            <div class="stat-bar-container"><div class="stat-bar-away" style="width:${rightPct}%"></div></div>
            <span class="away-val">${r.right}</span>
        </div>`;
    }).join('');
}

// ===== TRENDING =====
function updateTrending(trending) {
    const list = document.getElementById('trendingList');
    if (trending.length === 0) {
        list.innerHTML = '<p class="empty-state">No live games</p>';
        return;
    }
    list.innerHTML = trending.slice(0, 5).map((match, i) => `
        <div class="trending-item">
            <span class="rank">#${i + 1}</span>
            <span class="trending-matchup">
                ${teamLogo(match.homeTeam, 16)} ${match.homeTeam}
                <span style="color:var(--text-muted);margin:0 2px;">v</span>
                ${match.awayTeam} ${teamLogo(match.awayTeam, 16)}
            </span>
            <span class="trending-score">${match.homeScore}-${match.awayScore}</span>
            <span class="trending-viewers">👁 ${formatNumber(match.viewers)}</span>
        </div>
    `).join('');
}

// ===== WIN PROBABILITIES (ALL GAMES) =====
function updateProbabilities(probs) {
    const container = document.getElementById('probabilities');
    if (probs.length === 0) {
        container.innerHTML = '<p class="empty-state">Waiting for game data...</p>';
        return;
    }
    container.innerHTML = probs.map(wp => `
        <div class="prob-card">
            <div class="prob-matchup">
                ${teamLogo(wp.awayTeam, 20)} ${TEAMS[wp.awayTeam] || wp.awayTeam}
                <span class="prob-vs">at</span>
                ${TEAMS[wp.homeTeam] || wp.homeTeam} ${teamLogo(wp.homeTeam, 20)}
            </div>
            <div class="prob-bar-container">
                <div class="prob-bar home" style="width:${wp.awayProbability}%">
                    <span>${wp.awayProbability}%</span>
                </div>
                <div class="prob-bar away" style="width:${wp.homeProbability}%">
                    <span>${wp.homeProbability}%</span>
                </div>
            </div>
        </div>
    `).join('');
}

// ===== BENCHMARK =====
function runBenchmark() {
    const btn = document.getElementById('runBenchmark');
    const results = document.getElementById('benchmarkResults');
    btn.disabled = true;
    btn.textContent = 'Running...';
    results.innerHTML = '<p>Running benchmark...</p>';

    fetch('/api/benchmark?iterations=100')
        .then(r => r.json())
        .then(data => {
            results.innerHTML = `
                <table>
                    <thead>
                        <tr>
                            <th>Query</th><th>Iterations</th><th>Avg (ms)</th>
                            <th>P50 (ms)</th><th>P95 (ms)</th><th>P99 (ms)</th><th>Ops/sec</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${data.map(r => `
                            <tr>
                                <td>${r.queryName}</td><td>${r.iterations}</td>
                                <td>${r.avgLatencyMs.toFixed(2)}</td><td>${r.p50LatencyMs}</td>
                                <td>${r.p95LatencyMs}</td><td>${r.p99LatencyMs}</td>
                                <td>${r.throughputOpsPerSec.toFixed(1)}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            `;
            btn.disabled = false;
            btn.textContent = '⚡ Run Benchmark (100 iterations)';
        })
        .catch(err => {
            results.innerHTML = `<p class="error">Error: ${err.message}</p>`;
            btn.disabled = false;
            btn.textContent = '⚡ Benchmark';
        });
}

// ===== UTILITIES =====
function formatNumber(n) {
    return Number(n).toLocaleString();
}

function teamName(abbr) {
    return TEAMS[abbr] || abbr;
}

// Handle window resize for charts
let resizeTimeout;
window.addEventListener('resize', () => {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(() => {
        if (selectedGameId && charts.winProb) {
            const width = getChartWidth();
            Object.values(charts).forEach(c => { if (c) c.setSize({ width, height: 150 }); });
        }
    }, 200);
});

// ===== INIT =====
connect();
