'use strict';

const $ = (id) => document.getElementById(id);
const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const colors = ['#7a879c','#2b55d9','#087f78','#8653a6','#b87928'];
const finite = (value) => typeof value === 'number' && Number.isFinite(value);
const num = (value) => Number.isInteger(value) && value >= 0 ? value.toLocaleString('en-GB') : 'Unknown';
const date = (value, options = {}) => {
  const parsed = new Date(value);
  return value && Number.isFinite(parsed.getTime()) ? new Intl.DateTimeFormat('en-GB', {day:'numeric',month:'short',year:'numeric',timeZone:'UTC',...options}).format(parsed) : 'Unknown';
};
const shortDate = (value) => date(value, {year:undefined});
const url = (value) => {
  if (typeof value !== 'string') return null;
  try {const resolved = new URL(value, location.href); return ['http:','https:'].includes(resolved.protocol) ? resolved.href : null;} catch {return null;}
};
const link = (value,label) => {const safe = url(value); return safe ? `<a href="${esc(safe)}"${new URL(safe).origin !== location.origin ? ' target="_blank" rel="noopener noreferrer"' : ''}>${esc(label)}</a>` : '';};
let benchmark = null;
let activeStage = 'data';
let selectedWeek = 0;
let visibleModels = new Set();

async function readJSON(path) {
  const response = await fetch(path,{cache:'no-store'});
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}
function validateBenchmark(data) {
  if (data.schema_version !== 'plectis_benchmark_v1' || !data.dataset || !data.split?.train || !data.split?.test || !data.target || !Array.isArray(data.models) || !data.models.length) throw new Error('Unsupported or incomplete benchmark');
  const neutral = data.models.find((model) => model.id === 'neutral');
  if (!neutral || !finite(neutral.brier) || !Array.isArray(neutral.weekly) || !neutral.weekly.length) throw new Error('Missing reference benchmark');
  const dates = neutral.weekly.map((week) => week.date);
  if (new Set(dates).size !== dates.length || dates.some((value) => !/^\d{4}-\d{2}-\d{2}$/.test(value))) throw new Error('Invalid benchmark dates');
  if (!Number.isInteger(data.split.test.rows) || !Number.isInteger(data.split.test.weeks) || data.split.test.weeks !== dates.length) throw new Error('Invalid sample dimensions');
  for (const model of data.models) {
    if (!model.id || !model.name || !finite(model.brier) || model.brier < 0 || model.brier > 1 || !Array.isArray(model.weekly) || model.weekly.length !== dates.length) throw new Error('Invalid model scores');
    if (model.weekly.some((week,index) => week.date !== dates[index] || !finite(week.brier) || week.brier < 0 || week.brier > 1 || !Number.isInteger(week.n) || week.n <= 0 || !finite(week.positive_rate) || week.positive_rate < 0 || week.positive_rate > 1)) throw new Error('Incomplete weekly scores');
  }
  if (new Set(data.models.map((model) => model.id)).size !== data.models.length) throw new Error('Duplicate model identities');
  return data;
}
function modelColor(index) {return colors[index % colors.length];}
function renderBenchmark() {
  const data = benchmark;
  $('period-label').textContent = `${shortDate(data.split.test.start)} – ${date(data.split.test.end)}`;
  const facts = [['Dataset','UCI Dow Jones'],['Constituents',num(data.dataset.stocks)],['Training observations',num(data.split.train.rows)],['Test observations',num(data.split.test.rows)],['Holdout weeks',num(data.split.test.weeks)],['Target','Next-week open → close']];
  $('study-facts').innerHTML = facts.map(([key,value]) => `<div><dt>${esc(key)}</dt><dd>${esc(value)}</dd></div>`).join('');
  const reference = data.models.find((model) => model.id === 'neutral');
  const improves = data.models.filter((model) => model.id !== 'neutral' && model.brier < reference.brier);
  $('conclusion').textContent = improves.length ? `${improves.length} rule${improves.length > 1 ? 's' : ''} scored below the neutral baseline in this sample. This alone does not establish a reliable forecasting edge.` : 'Neither fitted frequency nor fixed momentum improved on the neutral 50% forecast in this sample.';
  $('score-table-body').innerHTML = data.models.map((model,index) => {
    const difference = model.brier - reference.brier;
    const interpretation = model.id === 'neutral' ? 'Reference forecast' : difference < 0 ? 'Lower error in this sample' : difference > 0 ? 'Higher error in this sample' : 'Same error as reference';
    return `<tr${model.id === 'neutral' ? ' class="neutral-row"' : ''}><td><span class="model-name"><i class="model-dot" style="--model-color:${modelColor(index)}"></i>${esc(model.name)}</span></td><td>${model.brier.toFixed(6)}</td><td>${difference === 0 ? 'Reference' : `${difference > 0 ? '+' : '−'}${Math.abs(difference).toFixed(6)}`}</td><td>${interpretation}</td></tr>`;
  }).join('');
  visibleModels = new Set(data.models.map((model) => model.id));
  renderLegend();
  renderChart();
  renderMethods();
  renderStage();
  $('evidence').hidden = false;
  $('load-status').hidden = true;
}
function renderLegend() {
  $('chart-legend').innerHTML = benchmark.models.map((model,index) => `<label class="legend-item${visibleModels.has(model.id) ? '' : ' disabled'}" style="--model-color:${modelColor(index)}"><input type="checkbox" data-model="${esc(model.id)}" ${visibleModels.has(model.id) ? 'checked' : ''}>${esc(model.name)}</label>`).join('');
  $('chart-legend').querySelectorAll('input').forEach((input) => input.addEventListener('change', () => {
    if (input.checked) visibleModels.add(input.dataset.model); else visibleModels.delete(input.dataset.model);
    input.closest('label').classList.toggle('disabled',!input.checked);
    renderChart();
  }));
}
function renderChart() {
  const models = benchmark.models;
  const weeks = models[0].weekly;
  const allValues = models.flatMap((model) => model.weekly.map((week) => week.brier));
  const min = Math.max(0,Math.floor((Math.min(...allValues)-.015)*20)/20);
  const max = Math.min(1,Math.ceil((Math.max(...allValues)+.015)*20)/20);
  const left = 48, right = 814, top = 28, bottom = 264;
  const x = (i) => left + i * (right-left)/(weeks.length-1 || 1);
  const y = (v) => bottom - (v-min)/(max-min)*(bottom-top);
  let html = '<title id="chart-title">Weekly historical Brier scores</title><desc id="chart-description">Lower is better. Score scale '+min.toFixed(2)+' to '+max.toFixed(2)+'. Toggle forecast rules with the checkboxes, then select a week using the pointer or keyboard. The table below reports aggregate scores.</desc>';
  for (let i=0;i<=4;i++) {
    const v = min + (max-min)*i/4;
    html += `<line class="chart-grid" x1="${left}" y1="${y(v)}" x2="${right}" y2="${y(v)}"/><text class="chart-axis-label" x="${left-10}" y="${y(v)+4}" text-anchor="end">${v.toFixed(2)}</text>`;
  }
  html += `<text class="chart-axis-label" x="${left}" y="15">Brier score</text><text class="chart-axis-label" x="${right}" y="312" text-anchor="end">Forecast issue week / 2011</text>`;
  weeks.forEach((week,index) => {if (index % 2 === 0 || index === weeks.length-1) html += `<text class="chart-axis-label" x="${x(index)}" y="287" text-anchor="middle">${esc(shortDate(week.date))}</text>`;});
  html += `<line class="chart-selected" x1="${x(selectedWeek)}" y1="${top}" x2="${x(selectedWeek)}" y2="${bottom}"/>`;
  models.forEach((model,index) => {
    if (!visibleModels.has(model.id)) return;
    const points = model.weekly.map((week,i) => `${x(i)},${y(week.brier)}`).join(' ');
    html += `<polyline class="chart-line" points="${points}" stroke="${modelColor(index)}"${model.id === 'neutral' ? ' stroke-dasharray="5 5"' : ''}/><circle class="chart-dot" cx="${x(selectedWeek)}" cy="${y(model.weekly[selectedWeek].brier)}" r="4.5" fill="${modelColor(index)}"/>`;
  });
  weeks.forEach((week,index) => {
    const half = (right-left)/(weeks.length-1 || 1)/2;
    const a = Math.max(left-12,x(index)-half), b = Math.min(right+12,x(index)+half);
    html += `<rect class="chart-hit" x="${a}" y="${top}" width="${b-a}" height="${bottom-top}" tabindex="0" role="button" aria-label="Inspect forecast week ${esc(date(week.date))}" aria-pressed="${selectedWeek === index}" data-week="${index}"/>`;
  });
  const svg = $('score-chart');
  svg.setAttribute('role','group');
  svg.innerHTML = html;
  svg.querySelectorAll('[data-week]').forEach((hit) => {
    const select = () => {selectedWeek=Number(hit.dataset.week);renderChart();};
    hit.addEventListener('click',select);
    hit.addEventListener('keydown',(event) => {
      if (event.key === 'Enter' || event.key === ' ') {event.preventDefault();select();svg.querySelector(`[data-week="${selectedWeek}"]`).focus();}
      if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') {event.preventDefault();selectedWeek=Math.min(weeks.length-1,Math.max(0,selectedWeek+(event.key === 'ArrowRight' ? 1 : -1)));renderChart();svg.querySelector(`[data-week="${selectedWeek}"]`).focus();}
    });
  });
  const week = weeks[selectedWeek];
  $('week-inspector').innerHTML = `<div><span class="week-date">${esc(shortDate(week.date))} forecast</span><span class="week-note">Outcome ${esc(shortDate(week.event_end))} / ${week.n} observations / ${(week.positive_rate*100).toFixed(1)}% positive</span></div>`+models.filter((model) => visibleModels.has(model.id)).map((model) => `<div class="week-score"><i style="--model-color:${modelColor(models.indexOf(model))}"></i><span>${esc(model.name)}</span><strong>${model.weekly[selectedWeek].brier.toFixed(4)}</strong></div>`).join('')+(visibleModels.size ? '' : '<span>Select a forecast rule above to view its scores.</span>');
}
function renderMethods() {
  const data = benchmark;
  $('method-detail').innerHTML = `<p>${esc(data.target.description)}</p><p>Training uses ${num(data.split.train.rows)} observations from ${esc(date(data.split.train.start))} to ${esc(date(data.split.train.end))}. Test forecasts cover ${num(data.split.test.rows)} observations across ${num(data.split.test.weeks)} issue weeks, from ${esc(date(data.split.test.start))} to ${esc(date(data.split.test.end))}; the final outcome is dated ${esc(date(data.split.test.last_label_date))}.</p><p>${num(data.split.purged_rows)} cross-boundary observations are purged. Another ${num(data.split.unverifiable_horizon_rows)} final-week observations have no verifiable subsequent horizon and are excluded. ${esc(data.methodology?.baseline_fit ?? '')}</p><p>${esc(data.methodology?.feature_availability_assumption ?? '')} This is a retrospective replay, not proof that predictions were recorded in 2011.</p><p>Allowed features: ${esc((data.methodology?.feature_allowlist ?? []).join(', '))}. Future prices and target-derived fields are excluded.</p><ul>${(data.methodology?.limitations ?? []).map((item) => `<li>${esc(item)}</li>`).join('')}</ul>`;
  $('source-detail').innerHTML = `<p>${esc(data.dataset.attribution)}</p><div class="source-links">${link(data.dataset.source_url,'UCI dataset')}${link(data.dataset.license_url,data.dataset.license)}${link(data.downloads?.predictions,'Prediction rows (CSV)')}${link(data.downloads?.source,'Original source archive')}${link(data.downloads?.manifest,'Source manifest')}${link(data.downloads?.attribution,'Attribution')}${link(data.downloads?.methodology,'Full methodology')}</div><p>Source SHA-256: <code>${esc(data.dataset.sha256)}</code></p>${data.protocol_version && data.code_hash ? `<p>Protocol version ${esc(data.protocol_version)}. Benchmark code SHA-256: <code>${esc(data.code_hash)}</code>.</p>` : ''}${data.prediction_artifact ? `<p>Prediction artifact SHA-256: <code>${esc(data.prediction_artifact.sha256)}</code>. ${num(data.prediction_artifact.rows)} forecast rows across all rules.</p>` : ''}<ul class="receipt-list">${(data.checks ?? []).map((check) => `<li><span class="check-state">${esc(check.status)}</span><strong>${esc(check.label)}</strong><br>${esc(check.detail)}</li>`).join('')}</ul>`;
}
function renderStage() {
  const d = benchmark;
  const stages = {
    data:{title:'Source data',caption:'Observe / keep the original',copy:d ? `${d.dataset.name}. ${num(d.dataset.rows)} source rows span ${num(d.dataset.weeks)} observed weeks. The original data and its checksum remain part of the evidence.` : 'Read dated observations from an attributed source. Preserve the original artifact and its acquisition record before making a prediction.',receipt:d ? `${d.dataset.license} / ${num(d.dataset.stocks)} constituents` : 'Benchmark source not loaded',extra:d ? link(d.dataset.source_url,'Inspect source') : ''},
    validation:{title:'Validation',caption:'Check / exclude future information',copy:d ? `Use a fixed time split. Purge ${num(d.split.purged_rows)} cross-boundary horizons and exclude ${num(d.split.unverifiable_horizon_rows)} unverifiable final outcomes. Models receive only allowed current-week features.` : 'Check dates, missing observations, feature availability, and the boundary between a prediction and its future outcome.',receipt:d ? `${(d.checks ?? []).filter((check) => check.status === 'passed').length} recorded checks passed` : 'Validation receipt not loaded',extra:'<a href="#methods">Read the validation receipt</a>'},
    prediction:{title:'Frozen forecast',caption:'Record / before truth is available',copy:'A forecast records a probability, its inputs, the exact rule or model, and a target horizon. This historical replay writes reproducible prediction rows today; it does not claim they were frozen in 2011.',receipt:d ? `${d.models.length} reproducible forecast rules / ${num(d.prediction_artifact?.rows)} rows` : 'Prediction artifact not loaded',extra:d ? link(d.downloads?.predictions,'Inspect prediction rows') : ''},
    truth:{title:'Later truth',caption:'Wait / resolve the same target',copy:d ? `${d.target.description} Outcomes are reconstructed from subsequent observed rows. The last test outcome is dated ${date(d.split.test.last_label_date)}.` : 'Resolve each target only after its horizon. Retain unresolved or failed cases rather than silently replacing them with an outcome.',receipt:d ? `${num(d.split.test.rows)} verifiable test outcomes` : 'Truth receipt not loaded',extra:'<a href="#methods">Inspect the outcome definition</a>'},
    score:{title:'Score & receipt',caption:'Compare / retain the result',copy:'Score every rule on the same held-out observations using the mean squared probability error. Show the neutral baseline, the full sample boundary, and the limitations alongside the result.',receipt:d ? `${num(d.split.test.weeks)} holdout weeks / Brier, lower is better` : 'Scores not loaded',extra:d ? '<a href="data/benchmark.json">Inspect benchmark JSON</a>' : ''}
  };
  const stage = stages[activeStage];
  document.querySelectorAll('[data-stage]').forEach((node) => node.setAttribute('aria-pressed',String(node.dataset.stage === activeStage)));
  $('stage-detail').innerHTML = `<div><h3>${stage.title}</h3><span class="stage-caption">${stage.caption}</span></div><p>${esc(stage.copy)}</p><div class="stage-receipt"><strong>Evidence on record</strong><span>${esc(stage.receipt)}</span>${stage.extra ? `<br>${stage.extra}` : ''}</div>`;
}
function timestamp(value) {
  const parsed = new Date(value);
  if (!value || !Number.isFinite(parsed.getTime())) return 'Unknown';
  return `${date(value)} ${new Intl.DateTimeFormat('en-GB',{hour:'2-digit',minute:'2-digit',timeZone:'UTC',hour12:false}).format(parsed)} UTC`;
}
function age(value) {
  const parsed = new Date(value);
  if (!value || !Number.isFinite(parsed.getTime())) return 'Freshness unknown';
  const minutes = Math.floor((Date.now()-parsed.getTime())/60000);
  if (minutes < -1) return 'Timestamp is in the future';
  if (minutes < 60) return `${Math.max(0,minutes)} min ago`;
  if (minutes < 1440) return `${Math.floor(minutes/60)} h ago`;
  return `${Math.floor(minutes/1440)} d ago`;
}
function renderOperations(d) {
  if ((d.schema ?? d.schema_version) !== 'observatory_operations_v1' || !d.collection || !d.experiments || !d.public_boundary) throw new Error('Unsupported operations receipt');
  const c = d.collection, e = d.experiments;
  const statusLabels = {ready:'Receipt ready',not_ready:'Collection not ready',unknown:'Readiness unknown',unavailable:'Source unavailable',invalid_source:'Source invalid'};
  $('operations-state').textContent = statusLabels[c.readiness] ?? 'Readiness unknown';
  const lanes = Array.isArray(c.lanes) ? c.lanes : [];
  const models = Array.isArray(e.models) ? e.models : [];
  let weekend = false;
  if (c.acquired_at) {try {const weekday = new Intl.DateTimeFormat('en-GB',{weekday:'long',timeZone:c.clock?.timezone || 'UTC'}).format(new Date(c.acquired_at));weekend = ['Saturday','Sunday'].includes(weekday);} catch {}}
  const schedule = c.schedule_kind === 'open' ? 'Opening-window collection' : c.schedule_kind === 'close' ? 'Closing-window collection' : c.schedule_kind === 'scheduled_other' ? 'Other scheduled collection' : c.schedule_kind === 'manual_or_unspecified' ? 'Manual or unspecified collection' : 'Collection schedule unknown';
  const clock = c.clock || {};
  const configuredClock = clock.timezone && clock.open && clock.close ? `Configured window: ${esc(clock.open)} / ${esc(clock.close)}, ${esc(clock.timezone)}. This is schedule configuration, not current market-open status.` : 'Configured collection window unavailable.';
  $('operations-content').innerHTML = `<div class="operations-grid"><div><div class="collection-lines">${lanes.length ? lanes.map((lane) => `<div class="collection-line"><span>${esc(lane.name)}${Number.isInteger(lane.valid_price_rows) || Number.isInteger(lane.missing_price_rows) ? `<small class="lane-coverage">${num(lane.valid_price_rows)} valid prices / ${num(lane.missing_price_rows)} missing</small>` : ''}</span><span class="lane-status">${esc(String(lane.status || 'unknown').replaceAll('_',' '))}</span><span class="row-count">${num(lane.rows)} rows</span></div>`).join('') : '<p class="empty-state">No collection lanes in the receipt.</p>'}</div><p class="operation-meta">Acquired ${esc(timestamp(c.acquired_at))} (${esc(age(c.acquired_at))}).<br>${esc(schedule)}${weekend ? ' / weekend validation; not a market-session receipt' : ''}.<br>${configuredClock}</p></div><div><div class="experiment-counts"><div><strong>${num(e.pending_count)}</strong><span>Pending attempts</span></div><div><strong>${num(e.scored_count)}</strong><span>Scored attempts</span></div><div><strong>${num(e.failed_count)}</strong><span>Failed attempts</span></div></div>${models.length ? models.map((model) => `<div class="model-operation"><div>${esc(model.requested || 'Requested model unknown')}<br><span>Actual: ${esc(model.actual || 'not confirmed')}</span></div><span>${esc(String(model.status || 'unknown').replaceAll('_',' '))}<br>${finite(model.cost) ? `$${model.cost.toFixed(4)} USD` : 'Cost unknown'}</span></div>`).join('') : '<p class="operation-meta">No model attempts reported.</p>'}<p class="operation-meta">${e.source_status ? `Experiment source: ${esc(e.source_status)}.<br>` : ''}${Number.isInteger(e.forecast_count) ? `${num(e.forecast_count)} individual forecast claims. ` : ''}Counts describe model attempts, not independent trials.<br>First truth due: ${esc(timestamp(e.first_truth_due_at))}.</p></div></div><div class="ops-boundary"><p>${esc(d.public_boundary.note || 'Public view contains aggregate research state only.')}</p><p>Receipt exported ${esc(timestamp(d.generated_at))}.</p></div>`;
}

document.querySelectorAll('[data-stage]').forEach((node) => {
  const select = () => {activeStage=node.dataset.stage;renderStage();};
  node.addEventListener('click',select);
  node.addEventListener('keydown',(event) => {if (event.key === 'Enter' || event.key === ' ') {event.preventDefault();select();}});
});
$('chart-reset').addEventListener('click',() => {if (!benchmark) return;visibleModels=new Set(benchmark.models.map((model) => model.id));renderLegend();renderChart();});
renderStage();
readJSON('data/benchmark.json').then(validateBenchmark).then((data) => {benchmark=data;renderBenchmark();}).catch(() => {
  const status=$('load-status');status.classList.add('error');status.setAttribute('role','alert');status.innerHTML='The historical benchmark could not be loaded or validated. Serve this directory over HTTP and check <a href="data/benchmark.json">data/benchmark.json</a>. No result is substituted.';
});
readJSON('data/operations.json').then(renderOperations).catch(() => {
  $('operations-state').textContent='Receipt unavailable';
  $('operations-content').innerHTML='<p class="empty-state">The operations receipt could not be loaded or validated. Collection readiness, model identities, and experiment counts are unknown. <a href="data/operations.json">Inspect operations JSON</a>.</p>';
});
