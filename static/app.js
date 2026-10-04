const $ = (id) => document.getElementById(id);

function fmt(v, d = 1) {
    const n = Number(v);
    return v == null || !Number.isFinite(n) ? '—' : n.toFixed(d);
}

function tm(s) {
    if (!s) return '—';
    const d = new Date(s);
    return isNaN(d) ? '—' : d.toLocaleTimeString();
}

function showTab(id, btn) {
    document.querySelectorAll('.tabcontent').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.tab').forEach(el => el.classList.remove('active'));

    const section = $(id);
    if (!section) return;

    section.classList.add('active');
    if (btn) btn.classList.add('active');

    if (id === 'reports') loadSummary();
}

async function getJSON(url) {
    const response = await fetch(url + (url.includes('?') ? '&' : '?') + 't=' + Date.now(), {
        cache: 'no-store'
    });
    if (!response.ok) throw new Error(`${url}: HTTP ${response.status}`);
    return response.json();
}

async function poll() {
    // Sensor data is deliberately fetched separately from ML/alerts.
    // A problem in one optional section must never hide the live readings.
    try {
        const [airResult, waterResult] = await Promise.allSettled([
            getJSON('/api/air'),
            getJSON('/api/water')
        ]);

        let gotSensorData = false;

        if (airResult.status === 'fulfilled') {
            const a = airResult.value.data || {};
            $('at').textContent = fmt(a.temperature);
            $('ah').textContent = fmt(a.humidity);
            $('ap').textContent = fmt(a.pressure);
            $('m1').textContent = fmt(a.mq135_1, 0);
            $('m2').textContent = fmt(a.mq135_2, 0);
            $('aq').textContent = fmt(a.air_quality, 0);
            $('as').textContent = a.air_quality == null
                ? 'Waiting'
                : a.air_quality > 300 ? 'SEVERE'
                : a.air_quality > 200 ? 'POOR'
                : a.air_quality > 100 ? 'MODERATE'
                : 'GOOD';
            $('airStatus').textContent = a.timestamp ? 'ONLINE' : 'WAITING';
            $('airTime').textContent = tm(a.timestamp);
            if (a.timestamp) {
                $('time').textContent = tm(a.timestamp);
                gotSensorData = true;
            }
        }

        if (waterResult.status === 'fulfilled') {
            const w = waterResult.value.data || {};
            $('ph').textContent = fmt(w.ph, 2);
            $('tds').textContent = fmt(w.tds, 0);
            $('turb').textContent = fmt(w.turbidity, 2);
            $('wt').textContent = fmt(w.water_temperature);
            $('waterStatus').textContent = w.timestamp ? 'ONLINE' : 'WAITING';
            $('waterTime').textContent = tm(w.timestamp);
            if (w.timestamp && !gotSensorData) $('time').textContent = tm(w.timestamp);
            if (w.timestamp) gotSensorData = true;
        }

        if (gotSensorData) {
            $('dot').classList.add('online');
            $('conn').textContent = 'Live sensor data connected';
        } else {
            $('dot').classList.remove('online');
            $('conn').textContent = 'Waiting for sensor data';
        }
    } catch (e) {
        $('dot').classList.remove('online');
        $('conn').textContent = 'Backend disconnected';
    }

    // Optional ML/trend section.
    try {
        const t = await getJSON('/api/trends');
        if (t.status === 'active') {
            $('overall').textContent = 'Water trend: ' + String(t.overall || 'mixed').toUpperCase();
            $('trendNote').textContent = (t.note || 'Trend calculated from collected readings.') + ' Samples: ' + (t.samples ?? 0);

            [
                ['ph', 'tph', 'tphv'],
                ['tds', 'ttds', 'ttdsv'],
                ['turbidity', 'tturb', 'tturbv'],
                ['water_temperature', 'twt', 'twtv']
            ].forEach(([key, directionId, changeId]) => {
                const p = t.parameters?.[key] || {};
                $(directionId).textContent = p.direction || '—';
                $(changeId).textContent = p.change == null
                    ? ''
                    : 'Change: ' + Number(p.change).toFixed(2) +
                      (p.percent_change == null ? '' : ' (' + Number(p.percent_change).toFixed(1) + '%)');
            });
        } else {
            $('overall').textContent = 'Waiting for trend model';
            $('trendNote').textContent = t.message || 'Collecting data...';
        }
    } catch (e) {
        $('overall').textContent = 'Waiting for trend model';
        $('trendNote').textContent = 'Collecting water readings...';
    }

    // Optional alert section.
    try {
        const a = await getJSON('/alerts/recent');
        const alerts = a.alerts || [];
        $('alerts').innerHTML = alerts.length
            ? alerts.map(x => `
                <div class="alert">
                    <b class="${x.severity}">${x.severity}</b>
                    ${x.message}<br>
                    <span class="muted">${x.node} · ${x.sensor}: ${x.value} · ${tm(x.timestamp)}</span>
                </div>`).join('')
            : '<span class="muted">No alerts yet.</span>';
    } catch (e) {
        $('alerts').innerHTML = '<span class="muted">Alerts unavailable.</span>';
    }
}

async function loadSummary() {
    try {
        const j = await getJSON('/reports/summary');
        const s = j.summary || {};
        $('records').textContent = s.records ?? 0;
        $('airrecords').textContent = s.air_records ?? 0;
        $('waterrecords').textContent = s.water_records ?? 0;
        $('alertrecords').textContent = s.alerts ?? 0;
    } catch (e) {
        console.error('Report summary unavailable', e);
    }
}

function downloadReport(type) {
    window.location.href = '/reports/' + type;
}

// Bind navigation in JavaScript rather than inline onclick handlers.
// This makes the tabs work reliably even if the page is cached or the script is deferred.
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.tab').forEach(btn => {
        btn.addEventListener('click', () => showTab(btn.dataset.tab, btn));
    });

    document.querySelectorAll('[data-download]').forEach(btn => {
        btn.addEventListener('click', () => downloadReport(btn.dataset.download));
    });

    poll();
    setInterval(poll, 2000);
});
