const state = {
  tables: [],
  activeAction: 'trends',
  user: null,
  profile: {
    default_symbol: 'bj920000',
    refresh_interval: 60,
    alert_threshold: 5,
  },
  selectedSymbol: 'bj920000',
  chart: null,
  refreshTimer: null,
  theme: 'dark',
};

const elements = {
  tableHead: document.getElementById('tableHead'),
  tableBody: document.getElementById('tableBody'),
  summaryCards: document.getElementById('summaryCards'),
  resultBox: document.getElementById('resultBox'),
  statusBadge: document.getElementById('statusBadge'),
  tableSelect: document.getElementById('tableSelect'),
  daysInput: document.getElementById('daysInput'),
  dateInput: document.getElementById('dateInput'),
  refreshBtn: document.getElementById('refreshBtn'),
  exportReportBtn: document.getElementById('exportReportBtn'),
  themeToggleBtn: document.getElementById('themeToggleBtn'),
  logoutBtn: document.getElementById('logoutBtn'),
  authStatus: document.getElementById('authStatus'),
  profileForm: document.getElementById('profileForm'),
  profileDefaultSymbol: document.getElementById('profileDefaultSymbol'),
  profileRefreshInterval: document.getElementById('profileRefreshInterval'),
  profileAlertThreshold: document.getElementById('profileAlertThreshold'),
  alertForm: document.getElementById('alertForm'),
  alertSymbol: document.getElementById('alertSymbol'),
  alertPeriod: document.getElementById('alertPeriod'),
  alertEnabled: document.getElementById('alertEnabled'),
  alertList: document.getElementById('alertList'),
  emailConfigForm: document.getElementById('emailConfigForm'),
  mailSenderName: document.getElementById('mailSenderName'),
  mailSenderEmail: document.getElementById('mailSenderEmail'),
  mailSmtpHost: document.getElementById('mailSmtpHost'),
  mailSmtpPort: document.getElementById('mailSmtpPort'),
  mailSmtpUser: document.getElementById('mailSmtpUser'),
  mailSmtpPassword: document.getElementById('mailSmtpPassword'),
  mailRecipientName: document.getElementById('mailRecipientName'),
  mailRecipientEmail: document.getElementById('mailRecipientEmail'),
  mailEnabled: document.getElementById('mailEnabled'),
  stockSearchInput: document.getElementById('stockSearchInput'),
  stockSearchBtn: document.getElementById('stockSearchBtn'),
  stockSearchResults: document.getElementById('stockSearchResults'),
  stockDetail: document.getElementById('stockDetail'),
  stockSignals: document.getElementById('stockSignals'),
  stockChartWrap: document.getElementById('stockChartWrap'),
  backtestResult: document.getElementById('backtestResult'),
  marketTicker: document.getElementById('marketTicker'),
  marketOverview: document.getElementById('marketOverview'),
  marketHeat: document.getElementById('marketHeat'),
  marketPulse: document.getElementById('marketPulse'),
  screenMinChange: document.getElementById('screenMinChange'),
  screenMinScore: document.getElementById('screenMinScore'),
  screenSignalType: document.getElementById('screenSignalType'),
  stockScreenBtn: document.getElementById('stockScreenBtn'),
  stockScreenResults: document.getElementById('stockScreenResults'),
  newsList: document.getElementById('newsList'),
  strategyForm: document.getElementById('strategyForm'),
  strategySymbol: document.getElementById('strategySymbol'),
  strategyName: document.getElementById('strategyName'),
  strategyStatus: document.getElementById('strategyStatus'),
  strategyDescription: document.getElementById('strategyDescription'),
  strategyRule: document.getElementById('strategyRule'),
  entryCondition: document.getElementById('entryCondition'),
  exitCondition: document.getElementById('exitCondition'),
  strategyList: document.getElementById('strategyList'),
  clearStrategyBtn: document.getElementById('clearStrategyBtn'),
  watchlistSymbol: document.getElementById('watchlistSymbol'),
  watchlistNote: document.getElementById('watchlistNote'),
  addWatchlistBtn: document.getElementById('addWatchlistBtn'),
  watchlistList: document.getElementById('watchlistList'),
  portfolioForm: document.getElementById('portfolioForm'),
  portfolioSymbol: document.getElementById('portfolioSymbol'),
  portfolioShares: document.getElementById('portfolioShares'),
  portfolioAvgCost: document.getElementById('portfolioAvgCost'),
  portfolioNote: document.getElementById('portfolioNote'),
  portfolioRisk: document.getElementById('portfolioRisk'),
  portfolioList: document.getElementById('portfolioList'),
  clearPortfolioBtn: document.getElementById('clearPortfolioBtn'),
  planForm: document.getElementById('planForm'),
  planSymbol: document.getElementById('planSymbol'),
  planAmount: document.getElementById('planAmount'),
  planMonths: document.getElementById('planMonths'),
  planTargetReturn: document.getElementById('planTargetReturn'),
  planNote: document.getElementById('planNote'),
  planList: document.getElementById('planList'),
  clearPlanBtn: document.getElementById('clearPlanBtn'),
  strategyCompare: document.getElementById('strategyCompare'),
  backtestTrendChart: document.getElementById('backtestTrendChart'),
  portfolioSummaryChart: document.getElementById('portfolioSummaryChart'),
  aiSummary: document.getElementById('aiSummary'),
  notificationList: document.getElementById('notificationList'),
};

function buildUrl(path, params = {}) {
  const url = new URL(`/api${path}`, window.location.origin);
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      url.searchParams.set(key, value);
    }
  });
  return url;
}

async function api(path, options = {}) {
  const { method = 'GET', params = {}, body } = options;
  const url = buildUrl(path, params);
  const init = {
    method,
    headers: { Accept: 'application/json' },
    credentials: 'include',
  };

  if (body !== undefined && body !== null) {
    init.headers['Content-Type'] = 'application/json';
    init.body = JSON.stringify(body);
  }

  const response = await fetch(url, init);
  const text = await response.text();
  let payload = {};
  try {
    payload = JSON.parse(text);
  } catch (error) {
    payload = { success: false, error: text || '接口返回非 JSON' };
  }

  if (!response.ok || payload.success === false) {
    throw new Error(payload.error || '接口请求失败');
  }

  return payload.data;
}

function exportReport() {
  try {
    const url = buildUrl('/report/export');
    window.location.href = url.toString();
    setStatus('报告已生成并下载');
  } catch (error) {
    setStatus('导出失败', 'error');
    renderTextResults('导出报告失败', error.message);
  }
}

function setStatus(text, type = 'success') {
  elements.statusBadge.textContent = text;
  elements.statusBadge.style.background = type === 'success' ? '#ecfdf5' : '#fef2f2';
  elements.statusBadge.style.color = type === 'success' ? '#16a34a' : '#dc2626';

  const lastUpdatedNode = document.getElementById('lastUpdatedText');
  if (lastUpdatedNode) {
    const now = new Date();
    const timeText = now.toLocaleTimeString('zh-CN', { hour12: false });
    lastUpdatedNode.textContent = `更新 ${timeText}`;
  }
}

function updateClock() {
  const now = new Date();
  const timeText = now.toLocaleTimeString('zh-CN', { hour12: false });
  const dateText = now.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    weekday: 'short',
  });

  const timeNode = document.getElementById('currentTime');
  const dateNode = document.getElementById('currentDate');
  const monthNode = document.getElementById('calendarMonth');
  const dayNode = document.getElementById('calendarDay');

  if (timeNode) timeNode.textContent = timeText;
  if (dateNode) dateNode.textContent = dateText;
  if (monthNode) monthNode.textContent = now.toLocaleDateString('zh-CN', { month: 'short' }).toUpperCase();
  if (dayNode) dayNode.textContent = String(now.getDate()).padStart(2, '0');

  const hourHand = document.getElementById('hourHand');
  const minuteHand = document.getElementById('minuteHand');
  const secondHand = document.getElementById('secondHand');
  if (hourHand && minuteHand && secondHand) {
    const seconds = now.getSeconds();
    const minutes = now.getMinutes() + seconds / 60;
    const hours = (now.getHours() % 12) + minutes / 60;

    const hourAngle = hours * 30;
    const minuteAngle = minutes * 6;
    const secondAngle = seconds * 6;

    hourHand.setAttribute('transform', `rotate(${hourAngle} 50 50)`);
    minuteHand.setAttribute('transform', `rotate(${minuteAngle} 50 50)`);
    secondHand.setAttribute('transform', `rotate(${secondAngle} 50 50)`);
  }
}

function applyTheme(theme = state.theme) {
  const resolvedTheme = theme || 'light';
  state.theme = resolvedTheme;
  document.body.dataset.theme = resolvedTheme;
  localStorage.setItem('stock-theme', resolvedTheme);
  if (elements.themeToggleBtn) {
    elements.themeToggleBtn.textContent = resolvedTheme === 'dark' ? '深色模式' : '浅色模式';
    elements.themeToggleBtn.setAttribute('aria-label', resolvedTheme === 'dark' ? '切换到浅色模式' : '切换到深色模式');
  }
}

function toggleTheme() {
  const nextTheme = state.theme === 'dark' ? 'light' : 'dark';
  applyTheme(nextTheme);
}

function renderSummaryCards(data) {
  const stats = Array.isArray(data?.stats) ? data.stats : [];
  const totalTables = stats.length;
  const totalRows = stats.reduce((sum, item) => sum + (Number(item.total_rows) || 0), 0);
  const firstDate = stats.filter((item) => item.min_date).map((item) => item.min_date).sort()[0] || '—';
  const lastDate = stats.filter((item) => item.max_date).map((item) => item.max_date).sort().pop() || '—';

  const cards = [
    { label: '股票表数量', value: totalTables },
    { label: '总记录数', value: totalRows.toLocaleString() },
    { label: '最早日期', value: firstDate },
    { label: '最新日期', value: lastDate },
  ];

  elements.summaryCards.innerHTML = cards
    .map(
      (card) => `
        <div class="stat-card">
          <div class="stat-label">${card.label}</div>
          <div class="stat-value">${card.value}</div>
        </div>
      `,
    )
    .join('');
}

function renderTableRows(rows, columns) {
  if (!rows.length) {
    elements.tableHead.innerHTML = '';
    elements.tableBody.innerHTML = '<tr><td colspan="10">暂无数据</td></tr>';
    return;
  }

  const visibleColumns = columns.length ? columns : Object.keys(rows[0]);
  elements.tableHead.innerHTML = `
    <tr>
      ${visibleColumns.map((column) => `<th>${column}</th>`).join('')}
    </tr>
  `;

  elements.tableBody.innerHTML = rows
    .map(
      (row) => `
        <tr>
          ${visibleColumns
            .map((column) => `<td>${formatCell(row[column])}</td>`)
            .join('')}
        </tr>
      `,
    )
    .join('');
}

function formatCell(value) {
  if (value === null || value === undefined || value === '') return '—';
  if (typeof value === 'number') {
    if (Number.isInteger(value)) return String(value);
    return value.toFixed(4);
  }
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

function renderTextResults(title, content) {
  elements.resultBox.classList.remove('empty');
  const safeContent = typeof content === 'string'
    ? content
    : JSON.stringify(content, null, 2);
  const lines = safeContent
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .slice(0, 6);

  elements.resultBox.innerHTML = `
    <div class="result-summary-head">
      <strong>${title}</strong>
      <span>${lines.length} 条</span>
    </div>
    <div class="result-summary-list">
      ${lines.map((line) => `<div class="result-summary-item">${line
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')}</div>`).join('')}
    </div>
  `;
}

function renderLineChart(canvas, labels, values, options = {}) {
  if (!canvas || typeof Chart === 'undefined') return;
  const context = canvas.getContext('2d');
  const config = {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: options.label || '值',
        data: values,
        borderColor: options.color || '#2563eb',
        backgroundColor: options.fillColor || 'rgba(37,99,235,0.12)',
        fill: true,
        tension: 0.25,
        pointRadius: 3,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: !!options.label } },
      scales: { y: { beginAtZero: false } },
    },
  };
  return new Chart(context, config);
}

function renderBuckets(data) {
  if (!data?.items?.length) {
    renderTextResults('分组数据', '没有满足条件的数据');
    return;
  }

  const rows = data.items.map((item) => ({
    table: item.table,
    total: item.total ?? '-',
    dominant: item.dominant_bucket ? `${item.dominant_bucket.range_start}-${item.dominant_bucket.range_end}%` : '-',
    period: `${item.period_start || '-'} ~ ${item.period_end || '-'}`,
  }));

  renderTableRows(rows, ['table', 'total', 'dominant', 'period']);
  const top = data.items.slice(0, 3).map((item) => `${item.table}: ${item.total ?? 0} 条，主分布 ${item.dominant_bucket ? `${item.dominant_bucket.range_start}-${item.dominant_bucket.range_end}%` : '—'}`).join('\n');
  renderTextResults('分组数据', `共 ${data.items.length} 组统计结果\n${top}`);
}

function renderTrendResults(data) {
  const items = data?.items ?? [];
  if (!items.length) {
    renderTextResults('趋势分析', '没有最近趋势数据');
    return;
  }

  const rows = items.map((item) => ({
    table: item.table,
    days: item.days,
    current_drop_pct: item.current_drop_pct ?? '—',
    most_drop_range: item.drop_range_most ? `${item.drop_range_most.range_start}~${item.drop_range_most.range_end}` : '—',
    max_high: item.max_high ?? '—',
    current_close: item.current_close ?? '—',
  }));

  renderTableRows(rows, ['table', 'days', 'current_drop_pct', 'most_drop_range', 'max_high', 'current_close']);
  const top = items.slice(0, 3).map((item) => `${item.table}: 当前跌幅 ${item.current_drop_pct ?? '—'}%，最大高点 ${item.max_high ?? '—'}，收盘 ${item.current_close ?? '—'}`).join('\n');
  renderTextResults('趋势分析', `共 ${items.length} 个股票趋势概览\n${top}`);
}

async function populateTables() {
  const data = await api('/tables');
  state.tables = data.tables || [];
  elements.tableSelect.innerHTML = '<option value="all">全部股票</option>' +
    state.tables.map((table) => `<option value="${table}">${table}</option>`).join('');
  if (state.selectedSymbol) {
    elements.tableSelect.value = state.selectedSymbol;
  }
}

function renderAuth() {
  const isLoggedIn = !!state.user;
  elements.authStatus.textContent = isLoggedIn ? `已登录：${state.user.username}` : '未登录';
  elements.logoutBtn.classList.toggle('hidden', !isLoggedIn);
  if (elements.profileForm && elements.profileForm.parentElement) {
    elements.profileForm.parentElement.classList.toggle('hidden', !isLoggedIn);
  }
}

function applyUserProfile() {
  const defaultSymbol = (state.profile.default_symbol || 'bj920000').toLowerCase();
  state.selectedSymbol = defaultSymbol;
  elements.profileDefaultSymbol.value = defaultSymbol;
  elements.profileRefreshInterval.value = Number(state.profile.refresh_interval || 60);
  elements.profileAlertThreshold.value = Number(state.profile.alert_threshold || 5.0);
  elements.stockSearchInput.value = defaultSymbol;
  if (elements.strategySymbol) {
    elements.strategySymbol.value = defaultSymbol;
  }
}

function startAutoRefresh() {
  if (state.refreshTimer) {
    clearInterval(state.refreshTimer);
  }
  const intervalMs = Number(state.profile.refresh_interval || 60) * 1000;
  if (!state.user || intervalMs <= 0) return;
  state.refreshTimer = setInterval(async () => {
    if (document.visibilityState !== 'visible') return;
    try {
      await loadMarketTicker();
      await loadMarketOverview();
      await loadMarketHeat();
      await loadMarketPulse();
      await loadStockScreener();
      await loadNotifications();
    } catch (error) {
      // ignore for polling
    }
  }, intervalMs);
}

async function loadAuthState() {
  try {
    const data = await api('/auth/me');
    state.user = data.user;
    state.profile = data.preferences || state.profile;
    renderAuth();
    applyUserProfile();
    startAutoRefresh();
  } catch (error) {
    state.user = null;
    state.profile = { default_symbol: 'bj920000', refresh_interval: 60, alert_threshold: 5 };
    renderAuth();
    applyUserProfile();
  }
}

async function loadUserProfile() {
  if (!state.user) {
    state.profile = { default_symbol: 'bj920000', refresh_interval: 60, alert_threshold: 5 };
    applyUserProfile();
    return;
  }
  try {
    const data = await api('/profile');
    state.profile = data || state.profile;
    applyUserProfile();
    startAutoRefresh();
  } catch (error) {
    setStatus('个人设置加载失败', 'error');
  }
}

async function loadEmailConfig() {
  if (!state.user) {
    if (elements.emailConfigForm) {
      elements.emailConfigForm.reset();
    }
    return;
  }
  try {
    const data = await api('/email/config');
    if (elements.mailSenderName) elements.mailSenderName.value = data.sender_name || '';
    if (elements.mailSenderEmail) elements.mailSenderEmail.value = data.sender_email || '';
    if (elements.mailSmtpHost) elements.mailSmtpHost.value = data.smtp_host || '';
    if (elements.mailSmtpPort) elements.mailSmtpPort.value = Number(data.smtp_port || 465);
    if (elements.mailSmtpUser) elements.mailSmtpUser.value = data.smtp_username || '';
    if (elements.mailSmtpPassword) elements.mailSmtpPassword.value = data.smtp_password || '';
    if (elements.mailRecipientName) elements.mailRecipientName.value = data.recipient_name || '';
    if (elements.mailRecipientEmail) elements.mailRecipientEmail.value = data.recipient_email || '';
    if (elements.mailEnabled) elements.mailEnabled.value = data.enabled ? '1' : '0';
  } catch (error) {
    setStatus('邮件配置加载失败', 'error');
  }
}

async function saveEmailConfig(event) {
  event.preventDefault();
  if (!state.user) {
    setStatus('请先登录后再设置邮件配置', 'error');
    return;
  }

  const payload = {
    sender_name: elements.mailSenderName.value.trim(),
    sender_email: elements.mailSenderEmail.value.trim(),
    smtp_host: elements.mailSmtpHost.value.trim(),
    smtp_port: Number(elements.mailSmtpPort.value || 465),
    smtp_username: elements.mailSmtpUser.value.trim(),
    smtp_password: elements.mailSmtpPassword.value,
    use_tls: 1,
    recipient_name: elements.mailRecipientName.value.trim(),
    recipient_email: elements.mailRecipientEmail.value.trim(),
    enabled: Number(elements.mailEnabled.value || 0),
  };

  await api('/email/config', { method: 'POST', body: payload });
  setStatus('邮件配置已保存');
}

async function saveUserProfile(event) {
  event.preventDefault();
  if (!state.user) {
    setStatus('请先登录后再保存设置', 'error');
    return;
  }

  const payload = {
    default_symbol: elements.profileDefaultSymbol.value.trim().toLowerCase() || 'bj920000',
    refresh_interval: Number(elements.profileRefreshInterval.value || 60),
    alert_threshold: Number(elements.profileAlertThreshold.value || 5),
  };

  const data = await api('/profile', {
    method: 'POST',
    body: payload,
  });
  state.profile = data || state.profile;
  applyUserProfile();
  startAutoRefresh();
  setStatus('设置已保存');
}

async function fetchSummary() {
  const data = await api('/summary');
  renderSummaryCards(data);
  setStatus('概览已更新');
}

async function fetchDateStats() {
  const date = elements.dateInput.value || new Date().toISOString().slice(0, 10);
  const data = await api('/date-summary', { params: { date } });
  const rows = (data.matches || []).map(([table, count]) => ({ table, count }));
  renderTableRows(rows, ['table', 'count']);
  const preview = rows.slice(0, 3).map((row) => `${row.table}: ${row.count}`).join(' / ');
  renderTextResults('按日期统计', `日期 ${date}\n${rows.length ? preview : '暂无数据'}`);
  setStatus('日期统计已更新');
}

async function fetchRecentDays() {
  const days = Number(elements.daysInput.value || 30);
  const data = await api('/recent-days', {
    params: { days, end_date: elements.dateInput.value || '' },
  });
  const rows = (data.matches || []).map(([table, count]) => ({ table, count }));
  renderTableRows(rows, ['table', 'count']);
  const preview = rows.slice(0, 3).map((row) => `${row.table}: ${row.count}`).join(' / ');
  renderTextResults('最近日期范围统计', `近 ${days} 天\n${rows.length ? preview : '暂无数据'}`);
  setStatus('日期范围统计已更新');
}

async function fetchTrends() {
  const days = Number(elements.daysInput.value || 30);
  const selectedTable = elements.tableSelect.value === 'all' ? undefined : elements.tableSelect.value;
  const data = await api('/trends', {
    params: {
      days,
      end_date: elements.dateInput.value || '',
      table: selectedTable || '',
      diff_step: 1.0,
      drop_step: 5.0,
    },
  });
  renderTrendResults(data);
  setStatus('趋势分析已更新');
}

async function fetchDropRatio() {
  const days = Number(elements.daysInput.value || 30);
  const selectedTable = elements.tableSelect.value === 'all' ? undefined : elements.tableSelect.value;
  const data = await api('/drop-ratio', {
    params: {
      days,
      end_date: elements.dateInput.value || '',
      table: selectedTable || '',
    },
  });

  const rows = (data.items || []).map((item) => ({
    table: item.table,
    max_high: item.max_high,
    current_close: item.current_close,
    drop_pct: item.drop_pct,
    drop_ratio: item.drop_ratio,
  }));

  renderTableRows(rows, ['table', 'max_high', 'current_close', 'drop_pct', 'drop_ratio']);
  const preview = (data.items || []).slice(0, 3).map((item) => `${item.table}: 跌幅 ${item.drop_pct ?? '—'}%，回撤率 ${item.drop_ratio ?? '—'}`).join('\n');
  renderTextResults('跌幅分析', `近 ${days} 天\n${preview || '暂无数据'}`);
  setStatus('跌幅分析已更新');
}

async function fetchDiffGroup() {
  const days = Number(elements.daysInput.value || 30);
  const selectedTable = elements.tableSelect.value === 'all' ? undefined : elements.tableSelect.value;
  const data = await api('/diff-group', {
    params: {
      days,
      step: 1.0,
      end_date: elements.dateInput.value || '',
      table: selectedTable || '',
    },
  });
  renderBuckets(data);
  setStatus('高低差分布已更新');
}

async function fetchOpenLow() {
  const days = Number(elements.daysInput.value || 30);
  const selectedTable = elements.tableSelect.value === 'all' ? undefined : elements.tableSelect.value;
  const data = await api('/open-low', {
    params: {
      days,
      step: 5.0,
      end_date: elements.dateInput.value || '',
      table: selectedTable || '',
    },
  });
  renderBuckets(data);
  setStatus('开盘跌幅分析已更新');
}

async function handleAction(action) {
  try {
    switch (action) {
      case 'summary':
        await fetchSummary();
        break;
      case 'dateStats':
        await fetchDateStats();
        break;
      case 'trends':
        await fetchTrends();
        break;
      case 'dropRatio':
        await fetchDropRatio();
        break;
      case 'diffGroup':
        await fetchDiffGroup();
        break;
      case 'openLow':
        await fetchOpenLow();
        break;
      default:
        await fetchTrends();
    }
  } catch (error) {
    renderTextResults('接口请求错误', error.message);
    setStatus('失败', 'error');
  }
}

async function searchStocks() {
  const keyword = elements.stockSearchInput.value.trim();
  const data = await api('/stock/search', {
    params: { keyword },
  });
  const items = data.items || [];

  if (!items.length) {
    elements.stockSearchResults.innerHTML = '<div class="stock-item">未找到匹配股票</div>';
    elements.stockDetail.innerHTML = '';
    return;
  }

  elements.stockSearchResults.innerHTML = items
    .map(
      (item) => `
        <div class="stock-item" data-symbol="${item.symbol}">
          <strong>${item.symbol}</strong>
          <div>收盘价：${item.close ?? '—'} &nbsp; 涨跌：${item.change_pct ?? '—'}%</div>
          <small>高：${item.high ?? '—'}  低：${item.low ?? '—'}  成交量：${item.volume ?? '—'}</small>
        </div>
      `,
    )
    .join('');

  elements.stockSearchResults.querySelectorAll('.stock-item').forEach((item) => {
    item.addEventListener('click', () => {
      const symbol = item.dataset.symbol;
      state.selectedSymbol = symbol;
      loadStockDetail(symbol);
      elements.strategySymbol.value = symbol;
      if (elements.alertSymbol) elements.alertSymbol.value = symbol;
    });
  });

  const first = items[0].symbol;
  state.selectedSymbol = first;
  elements.strategySymbol.value = first;
  loadStockDetail(first);
}

function renderChart(symbol, history) {
  const labels = history.map((row) => row.date).slice(-30);
  const values = history.map((row) => Number(row.close)).slice(-30);

  const canvas = document.getElementById('stockChart');
  if (!canvas) return;

  const ctx = canvas.getContext('2d');
  if (state.chart) {
    state.chart.destroy();
  }

  if (!labels.length || !values.length || typeof Chart === 'undefined') {
    elements.stockChartWrap.classList.add('hidden');
    return;
  }

  elements.stockChartWrap.classList.remove('hidden');
  state.chart = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: `${symbol} 收盘价`,
        data: values,
        borderColor: '#1d4ed8',
        backgroundColor: 'rgba(29, 78, 216, 0.1)',
        fill: true,
        tension: 0.25,
        pointRadius: 2,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: true } },
      scales: {
        y: { beginAtZero: false },
      },
    },
  });
}

async function loadBacktest(symbol) {
  const data = await api(`/stock/${encodeURIComponent(symbol)}/backtest`, {
    params: { fast_period: 5, slow_period: 10 },
  });
  const backtest = data.backtest || {};
  elements.backtestResult.innerHTML = `
    <strong>策略回测结果（5日/10日均线）</strong>
    <div>交易次数：${backtest.trades ?? 0}</div>
    <div>净收益：${backtest.net_return ?? 0}%</div>
    <div>最终价值：${backtest.final_value ?? 0}</div>
  `;
}

async function loadSignals(symbol) {
  try {
    const data = await api(`/stock/${encodeURIComponent(symbol)}/signals`);
    const signals = data.signals || {};
    const items = Array.isArray(signals.items) ? signals.items : [];
    const toneClass = (tone) => ({
      up: 'signal-pill up',
      down: 'signal-pill down',
      neutral: 'signal-pill neutral',
    }[tone] || 'signal-pill neutral');

    elements.stockSignals.innerHTML = `
      <div class="signal-header">
        <strong>技术信号</strong>
        <span class="signal-summary ${signals.summary === '偏强' ? 'up' : signals.summary === '偏弱' ? 'down' : 'neutral'}">${signals.summary || '未知'}</span>
      </div>
      <div class="signal-list">
        ${items.map((item) => `
          <span class="${toneClass(item.tone)}">${item.name}: ${item.value}</span>
        `).join('')}
      </div>
    `;
  } catch (error) {
    elements.stockSignals.innerHTML = `<div class="signal-empty">技术信号暂时不可用：${error.message}</div>`;
  }
}

async function loadStockDetail(symbol) {
  const data = await api(`/stock/${encodeURIComponent(symbol)}`);
  const snapshot = data.snapshot || {};
  const history = snapshot.history || [];

  const detailHtml = `
    <div class="stock-detail-grid">
      <div class="metric-box"><span class="metric-label">股票代码</span><span class="metric-value">${symbol}</span></div>
      <div class="metric-box"><span class="metric-label">最新日期</span><span class="metric-value">${snapshot.latest_date || '—'}</span></div>
      <div class="metric-box"><span class="metric-label">收盘价</span><span class="metric-value">${snapshot.close ?? '—'}</span></div>
      <div class="metric-box"><span class="metric-label">涨跌幅</span><span class="metric-value">${snapshot.change_pct ?? '—'}%</span></div>
      <div class="metric-box"><span class="metric-label">最高</span><span class="metric-value">${snapshot.high ?? '—'}</span></div>
      <div class="metric-box"><span class="metric-label">最低</span><span class="metric-value">${snapshot.low ?? '—'}</span></div>
      <div class="metric-box"><span class="metric-label">成交量</span><span class="metric-value">${snapshot.volume ?? '—'}</span></div>
      <div class="metric-box"><span class="metric-label">开盘价</span><span class="metric-value">${snapshot.open ?? '—'}</span></div>
    </div>
    <div style="margin-top:16px;">
      <strong>最近价格走势</strong>
      <table>
        <thead>
          <tr>
            <th>日期</th>
            <th>开盘</th>
            <th>最高</th>
            <th>最低</th>
            <th>收盘</th>
            <th>成交量</th>
          </tr>
        </thead>
        <tbody>
          ${history.slice(-8).map((row) => `
            <tr>
              <td>${row.date}</td>
              <td>${row.open ?? '—'}</td>
              <td>${row.high ?? '—'}</td>
              <td>${row.low ?? '—'}</td>
              <td>${row.close ?? '—'}</td>
              <td>${row.volume ?? '—'}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;
  elements.stockDetail.innerHTML = detailHtml;
  renderChart(symbol, history);
  elements.strategySymbol.value = symbol;
  if (elements.alertSymbol) elements.alertSymbol.value = symbol;
  loadNews(symbol);
  loadStrategies(symbol);
  loadBacktest(symbol);
  loadSignals(symbol);
  loadStrategyComparison(symbol);
  loadBacktestTrend(symbol);
  loadAiSummary();
  loadNotifications();
}

async function loadNews(symbol) {
  const stockSymbol = symbol || state.selectedSymbol || 'bj920000';
  const data = await api('/news', { params: { symbol: stockSymbol } });
  const items = data.items || [];
  if (!items.length) {
    elements.newsList.innerHTML = '<div class="news-item">暂无股票新闻</div>';
    return;
  }

  elements.newsList.innerHTML = items
    .slice(0, 8)
    .map(
      (item) => `
        <div class="news-item">
          <strong>${item.title}</strong>
          <div>${item.content}</div>
          <small>${item.symbol} · ${item.source} · ${item.created_at}</small>
        </div>
      `,
    )
    .join('');
}

async function loadStrategies(symbol = '') {
  if (!state.user) {
    elements.strategyList.innerHTML = '<div class="strategy-item">登录后可查看和设置个股策略</div>';
    return;
  }

  const selectedSymbol = symbol || state.selectedSymbol || '';
  const data = await api('/strategies', {
    params: { symbol: selectedSymbol },
  });
  const items = data.items || [];
  let scoreMap = {};

  try {
    const scoreData = await api('/strategies/score', {
      params: { symbol: selectedSymbol },
    });
    (scoreData.items || []).forEach((entry) => {
      scoreMap[entry.strategy_id] = entry;
    });
  } catch (error) {
    scoreMap = {};
  }

  if (!items.length) {
    elements.strategyList.innerHTML = '<div class="strategy-item">暂无策略，点击上方保存策略</div>';
    return;
  }

  elements.strategyList.innerHTML = items
    .map((item) => {
      const scoreEntry = scoreMap[item.id] || null;
      const scoreMarkup = scoreEntry
        ? `<span class="score-badge ${scoreEntry.grade === '强' ? 'score-strong' : scoreEntry.grade === '中' ? 'score-medium' : 'score-weak'}">${scoreEntry.grade} ${scoreEntry.score}</span>`
        : '<span class="score-badge score-weak">待评估</span>';

      return `
        <div class="strategy-item">
          <div class="strategy-head">
            <strong>${item.name}</strong>
            ${scoreMarkup}
          </div>
          <div>${item.description || '无说明'}</div>
          <div><strong>规则：</strong>${item.rule || '未填写'}</div>
          <div><strong>买入条件：</strong>${item.entry_condition || '未填写'}</div>
          <div><strong>卖出条件：</strong>${item.exit_condition || '未填写'}</div>
          <div class="meta-row">
            <span class="badge">${item.symbol} · ${item.status}</span>
            <button class="ghost-btn" data-delete-strategy="${item.id}">删除</button>
          </div>
        </div>
      `;
    })
    .join('');

  elements.strategyList.querySelectorAll('[data-delete-strategy]').forEach((button) => {
    button.addEventListener('click', async () => {
      const id = Number(button.dataset.deleteStrategy);
      await api(`/strategies/${id}`, { method: 'DELETE' });
      await loadStrategies(state.selectedSymbol);
    });
  });
}

async function registerUser(event) {
  event.preventDefault();
  const username = document.getElementById('registerUser').value.trim();
  const password = document.getElementById('registerPass').value;
  const data = await api('/auth/register', {
    method: 'POST',
    body: { username, password },
  });
  state.user = data.user;
  renderAuth();
  await loadUserProfile();
  await loadEmailConfig();
  await loadStockAlerts();
  await loadStrategies(state.selectedSymbol);
  await loadWatchlist();
  await loadPortfolio();
  await loadStrategyComparison(state.selectedSymbol);
  await loadAiSummary();
  setStatus('注册成功');
}

async function loginUser(event) {
  event.preventDefault();
  const username = document.getElementById('loginUser').value.trim();
  const password = document.getElementById('loginPass').value;
  const data = await api('/auth/login', {
    method: 'POST',
    body: { username, password },
  });
  state.user = data.user;
  renderAuth();
  await loadUserProfile();
  await loadEmailConfig();
  await loadStockAlerts();
  await loadStrategies(state.selectedSymbol);
  await loadWatchlist();
  await loadPortfolio();
  await loadStrategyComparison(state.selectedSymbol);
  await loadAiSummary();
  setStatus('登录成功');
}

async function logoutUser() {
  await api('/auth/logout', { method: 'POST' });
  state.user = null;
  if (state.refreshTimer) {
    clearInterval(state.refreshTimer);
    state.refreshTimer = null;
  }
  renderAuth();
  await loadStrategies();
  await loadStockAlerts();
  await loadEmailConfig();
  await loadWatchlist();
  await loadPortfolio();
  await loadStrategyComparison();
  await loadPortfolioSummary();
  await loadAiSummary();
  await loadNotifications();
  setStatus('已退出登录');
}

async function saveStrategy(event) {
  event.preventDefault();
  if (!state.user) {
    setStatus('请先登录后再保存策略', 'error');
    return;
  }

  const payload = {
    symbol: elements.strategySymbol.value.trim().toUpperCase(),
    name: elements.strategyName.value.trim(),
    description: elements.strategyDescription.value.trim(),
    rule: elements.strategyRule.value.trim(),
    entry_condition: elements.entryCondition.value.trim(),
    exit_condition: elements.exitCondition.value.trim(),
    status: elements.strategyStatus.value,
  };

  await api('/strategies', {
    method: 'POST',
    body: payload,
  });
  setStatus('策略已保存');
  await loadStrategies(payload.symbol);
  await loadStrategyComparison(payload.symbol);
  await loadAiSummary();
  elements.strategyForm.reset();
  elements.strategySymbol.value = state.selectedSymbol || '';
}

function clearStrategyForm() {
  elements.strategyForm.reset();
  elements.strategySymbol.value = state.selectedSymbol || '';
}

async function loadMarketTicker() {
  try {
    const data = await api('/market/overview', { params: { limit: 8 } });
    const items = [...(data.gainers || []), ...(data.losers || [])].slice(0, 4);

    if (!items.length || !elements.marketTicker) {
      if (elements.marketTicker) {
        elements.marketTicker.innerHTML = '<div class="ticker-item neutral"><span class="ticker-name">市场</span><strong>暂无数据</strong><em>—</em></div>';
      }
      return;
    }

    const tickerItems = items.map((item) => {
      const change = Number(item.change_pct || 0);
      const tone = change >= 0 ? 'up' : 'down';
      const label = item.symbol || '股票';

      return `
        <div class="ticker-item ${tone}">
          <span class="ticker-name">${label}</span>
          <strong>${Number(item.close || 0).toFixed(2)}</strong>
          <em>${change >= 0 ? '+' : ''}${change.toFixed(2)}%</em>
        </div>
      `;
    }).join('');

    elements.marketTicker.innerHTML = `${tickerItems}${tickerItems}`;
  } catch (error) {
    if (elements.marketTicker) {
      elements.marketTicker.innerHTML = '<div class="ticker-item neutral"><span class="ticker-name">市场</span><strong>数据异常</strong><em>—</em></div>';
    }
  }
}

async function loadMarketOverview() {
  try {
    const data = await api('/market/overview');
    const gainers = (data.gainers || []).slice(0, 3);
    const losers = (data.losers || []).slice(0, 3);

    const renderBox = (title, list, color = '#16a34a') => `
      <div class="market-box">
        <h3>${title}</h3>
        ${list.length ? list.map((item) => `
          <div class="market-row">
            <span>${item.symbol}</span>
            <span style="color:${color};font-weight:700;">${Number(item.change_pct || 0).toFixed(2)}%</span>
          </div>
        `).join('') : '<div class="market-row"><span>暂无数据</span></div>'}
      </div>
    `;

    elements.marketOverview.innerHTML = renderBox('涨幅榜', gainers, '#16a34a') + renderBox('跌幅榜', losers, '#dc2626');
  } catch (error) {
    elements.marketOverview.innerHTML = `<div class="market-box"><h3>市场概览</h3><div>加载失败：${error.message}</div></div>`;
  }
}

function renderMarketPulse(data) {
  const items = data?.items || [];
  if (!items.length) {
    elements.marketPulse.innerHTML = '<div class="pulse-card neutral"><div class="pulse-header"><span>暂无数据</span></div></div>';
    return;
  }

  elements.marketPulse.innerHTML = items
    .map(
      (item) => `
        <div class="pulse-card ${item.tone || 'neutral'}">
          <div class="pulse-header">
            <span>${item.symbol}</span>
            <span class="pulse-score">${item.score ?? 0}</span>
          </div>
          <div class="pulse-row">${item.summary || '震荡'}</div>
          <div class="pulse-row">${Number(item.change_pct || 0).toFixed(2)}%</div>
          <div class="pulse-row">${item.recommendation || '观察中'}</div>
        </div>
      `,
    )
    .join('');
}

function renderMarketHeat(data) {
  const heat = data || {};
  const gainers = heat.gainers || [];
  const losers = heat.losers || [];
  const hot = heat.hot_items || [];

  const renderHotList = (items) => {
    if (!items.length) {
      return '<div class="market-heat-empty">暂无热点</div>';
    }
    return items
      .map((item) => `
        <div class="market-heat-row">
          <span>${item.symbol || '—'}</span>
          <span>${Number(item.score ?? 0).toFixed(1)}</span>
          <span>${Number(item.change_pct ?? 0).toFixed(2)}%</span>
        </div>
      `)
      .join('');
  };

  elements.marketHeat.innerHTML = `
    <div class="market-heat-header">
      <span>市场热度</span>
      <span class="market-heat-sentiment ${heat.sentiment === '偏强' ? 'up' : heat.sentiment === '偏弱' ? 'down' : 'neutral'}">${heat.sentiment || '震荡'}</span>
    </div>
    <div class="market-heat-grid">
      <div class="market-heat-panel">
        <h4>领涨</h4>
        ${renderHotList(gainers)}
      </div>
      <div class="market-heat-panel">
        <h4>领跌</h4>
        ${renderHotList(losers)}
      </div>
      <div class="market-heat-panel wide">
        <h4>热点轮动</h4>
        ${hot.length ? hot.map((item) => `
          <div class="market-hot-item">
            <div class="market-hot-head"><strong>${item.symbol || '—'}</strong><span>${Number(item.score ?? 0).toFixed(1)}</span></div>
            <div>${item.summary || '暂无描述'}</div>
          </div>
        `).join('') : '<div class="market-heat-empty">暂无热点轮动</div>'}
      </div>
    </div>
  `;
}

async function loadMarketHeat() {
  try {
    const data = await api('/market/heat', { params: { limit: 5 } });
    renderMarketHeat(data);
  } catch (error) {
    elements.marketHeat.innerHTML = `<div class="market-heat-empty">市场热度加载失败：${error.message}</div>`;
  }
}

async function loadMarketPulse() {
  try {
    const data = await api('/market/pulse', { params: { limit: 5 } });
    renderMarketPulse(data);
  } catch (error) {
    elements.marketPulse.innerHTML = `<div class="pulse-card neutral"><div class="pulse-row">情绪雷达加载失败：${error.message}</div></div>`;
  }
}

async function loadStockScreener() {
  try {
    const minChange = Number(elements.screenMinChange.value || 0);
    const minScore = Number(elements.screenMinScore.value || 60);
    const signalType = elements.screenSignalType.value || 'all';
    const data = await api('/stocks/screen', {
      params: {
        min_change: minChange,
        min_score: minScore,
        signal: signalType === 'all' ? '' : signalType,
      },
    });
    const items = data.items || [];
    if (!items.length) {
      elements.stockScreenResults.innerHTML = '<div class="screen-item empty">暂无符合条件的股票</div>';
      return;
    }

    elements.stockScreenResults.innerHTML = items
      .map((item) => `
        <div class="screen-item" data-symbol="${item.symbol}">
          <div class="screen-header">
            <strong>${item.symbol}</strong>
            <span class="score-badge ${item.summary === '偏强' ? 'score-strong' : item.summary === '偏弱' ? 'score-weak' : 'score-medium'}">${item.summary} ${item.score}</span>
          </div>
          <div class="screen-meta">涨跌幅：${Number(item.change_pct || 0).toFixed(2)}% · 收盘价：${Number(item.close || 0).toFixed(2)}</div>
          <div class="screen-meta">趋势：${item.signal_summary || '未知'} · 重点：${item.focus || '均线与量价'}</div>
        </div>
      `)
      .join('');

    elements.stockScreenResults.querySelectorAll('.screen-item').forEach((item) => {
      item.addEventListener('click', () => {
        const symbol = item.dataset.symbol;
        state.selectedSymbol = symbol;
        elements.stockSearchInput.value = symbol;
        loadStockDetail(symbol);
      });
    });
  } catch (error) {
    elements.stockScreenResults.innerHTML = `<div class="screen-item empty">筛选失败：${error.message}</div>`;
  }
}

async function loadStockAlerts() {
  if (!state.user) {
    elements.alertList.innerHTML = '<div class="watchlist-item">登录后可使用股票预警</div>';
    return;
  }

  try {
    const data = await api('/alerts');
    const items = data.items || [];
    if (!items.length) {
      elements.alertList.innerHTML = '<div class="watchlist-item">暂无股票预警</div>';
      return;
    }

    elements.alertList.innerHTML = items
      .map((item) => `
        <div class="watchlist-item">
          <div>
            <strong>${item.symbol}</strong>
            <div>${item.period === '3m' ? '3个月' : item.period === '6m' ? '6个月' : '1年'}最低价提醒</div>
            <small>当前价：${Number(item.current_price || 0).toFixed(2)} / 周期低：${item.period_low !== null ? Number(item.period_low).toFixed(2) : '—'}</small>
          </div>
          <div>
            <button class="ghost-btn" data-alert-id="${item.id}">删除</button>
          </div>
        </div>
      `)
      .join('');

    elements.alertList.querySelectorAll('[data-alert-id]').forEach((button) => {
      button.addEventListener('click', async () => {
        const id = Number(button.dataset.alertId);
        await api(`/alerts/${id}`, { method: 'DELETE' });
        await loadStockAlerts();
      });
    });
  } catch (error) {
    elements.alertList.innerHTML = `<div class="watchlist-item">股票预警加载失败：${error.message}</div>`;
  }
}

async function saveStockAlert(event) {
  event.preventDefault();
  if (!state.user) {
    setStatus('请先登录后再设置股票预警', 'error');
    return;
  }

  const symbol = elements.alertSymbol.value.trim().toUpperCase();
  const period = elements.alertPeriod.value;
  const enabled = Number(elements.alertEnabled.value || 1) === 1;
  if (!symbol) {
    setStatus('股票代码不能为空', 'error');
    return;
  }

  await api('/alerts', {
    method: 'POST',
    body: { symbol, period, enabled },
  });
  elements.alertSymbol.value = symbol;
  setStatus('股票预警已保存');
  await loadStockAlerts();
}

async function loadWatchlist() {
  if (!state.user) {
    elements.watchlistList.innerHTML = '<div class="watchlist-item">登录后可使用自选股功能</div>';
    return;
  }

  try {
    const data = await api('/watchlist');
    const items = data.items || [];
    if (!items.length) {
      elements.watchlistList.innerHTML = '<div class="watchlist-item">暂无自选股</div>';
      return;
    }

    elements.watchlistList.innerHTML = items
      .map(
        (item) => `
          <div class="watchlist-item">
            <div>
              <strong>${item.symbol}</strong>
              <div>${item.note || '无备注'}</div>
            </div>
            <div>
              <button class="ghost-btn" data-watch-symbol="${item.symbol}">查看</button>
              <button class="secondary-btn" data-delete-watch="${item.symbol}">删除</button>
            </div>
          </div>
        `,
      )
      .join('');

    elements.watchlistList.querySelectorAll('[data-watch-symbol]').forEach((button) => {
      button.addEventListener('click', () => {
        const symbol = button.dataset.watchSymbol;
        state.selectedSymbol = symbol;
        elements.stockSearchInput.value = symbol;
        loadStockDetail(symbol);
      });
    });

    elements.watchlistList.querySelectorAll('[data-delete-watch]').forEach((button) => {
      button.addEventListener('click', async () => {
        const symbol = button.dataset.deleteWatch;
        await api(`/watchlist/${encodeURIComponent(symbol)}`, { method: 'DELETE' });
        await loadWatchlist();
      });
    });
  } catch (error) {
    elements.watchlistList.innerHTML = `<div class="watchlist-item">加载自选股失败: ${error.message}</div>`;
  }
}

async function addWatchlist(event) {
  event.preventDefault();
  if (!state.user) {
    setStatus('请先登录后再添加自选股', 'error');
    return;
  }

  const symbol = elements.watchlistSymbol.value.trim().toUpperCase();
  const note = elements.watchlistNote.value.trim();
  if (!symbol) {
    setStatus('自选股代码不能为空', 'error');
    return;
  }

  await api('/watchlist', {
    method: 'POST',
    body: { symbol, note },
  });
  elements.watchlistSymbol.value = '';
  elements.watchlistNote.value = '';
  await loadWatchlist();
  setStatus('已加入自选股');
}

async function loadPortfolioRisk() {
  if (!state.user) {
    elements.portfolioRisk.innerHTML = '<div class="portfolio-risk-item">登录后可查看组合风险</div>';
    return;
  }

  try {
    const data = await api('/portfolio/risk');
    const riskLevel = data.risk_level || '低';
    const riskClass = riskLevel === '高' ? 'danger' : riskLevel === '中' ? 'warning' : 'success';
    elements.portfolioRisk.innerHTML = `
      <div class="portfolio-risk-item ${riskClass}">
        <div class="risk-head">
          <strong>组合风险</strong>
          <span class="risk-badge ${riskClass}">${riskLevel}</span>
        </div>
        <div class="risk-grid">
          <div><span>总市值</span><strong>${Number(data.total_value || 0).toFixed(2)}</strong></div>
          <div><span>总盈亏</span><strong>${Number(data.total_pnl || 0).toFixed(2)}</strong></div>
          <div><span>平均波动</span><strong>${Number(data.avg_change_pct || 0).toFixed(2)}%</strong></div>
          <div><span>重点风险</span><strong>${data.top_risk_symbol || '无'}</strong></div>
        </div>
      </div>
    `;
  } catch (error) {
    elements.portfolioRisk.innerHTML = `<div class="portfolio-risk-item warning">组合风险加载失败：${error.message}</div>`;
  }
}

async function loadPortfolio() {
  if (!state.user) {
    elements.portfolioList.innerHTML = '<div class="portfolio-item">登录后可查看和维护持仓</div>';
    return;
  }

  try {
    const data = await api('/portfolio');
    const items = data.items || [];
    if (!items.length) {
      elements.portfolioList.innerHTML = '<div class="portfolio-item">暂无持仓记录</div>';
      await loadPortfolioRisk();
      return;
    }

    elements.portfolioList.innerHTML = items
      .map((item) => {
        const pnlClass = Number(item.pnl || 0) >= 0 ? 'positive' : 'negative';
        return `
          <div class="portfolio-item">
            <div class="portfolio-head">
              <strong>${item.symbol}</strong>
              <span class="pnl-badge ${pnlClass}">${Number(item.pnl || 0).toFixed(2)}</span>
            </div>
            <div class="portfolio-row"><span>持仓数量</span><span>${Number(item.shares).toFixed(2)}</span></div>
            <div class="portfolio-row"><span>平均成本</span><span>${Number(item.avg_cost).toFixed(2)}</span></div>
            <div class="portfolio-row"><span>当前价</span><span>${Number(item.market_price).toFixed(2)}</span></div>
            <div class="portfolio-row"><span>市值</span><span>${Number(item.market_value).toFixed(2)}</span></div>
            <div class="portfolio-row"><span>备注</span><span>${item.notes || '无'}</span></div>
            <div class="portfolio-row">
              <span>操作</span>
              <button class="ghost-btn" data-delete-portfolio="${item.symbol}">删除</button>
            </div>
          </div>
        `;
      })
      .join('');

    elements.portfolioList.querySelectorAll('[data-delete-portfolio]').forEach((button) => {
      button.addEventListener('click', async () => {
        const symbol = button.dataset.deletePortfolio;
        await api(`/portfolio/${encodeURIComponent(symbol)}`, { method: 'DELETE' });
        await loadPortfolio();
        await loadPortfolioRisk();
      });
    });

    await loadPortfolioRisk();
  } catch (error) {
    elements.portfolioList.innerHTML = `<div class="portfolio-item">读取持仓失败：${error.message}</div>`;
  }
}

async function savePortfolio(event) {
  event.preventDefault();
  if (!state.user) {
    setStatus('请先登录后再保存持仓', 'error');
    return;
  }

  const payload = {
    symbol: elements.portfolioSymbol.value.trim().toUpperCase(),
    shares: Number(elements.portfolioShares.value),
    avg_cost: Number(elements.portfolioAvgCost.value),
    notes: elements.portfolioNote.value.trim(),
  };

  await api('/portfolio', {
    method: 'POST',
    body: payload,
  });
  setStatus('持仓已保存');
  elements.portfolioForm.reset();
  await loadPortfolio();
  await loadPortfolioRisk();
  await loadPortfolioSummary();
  await loadAiSummary();
  await loadNotifications();
}

function clearPortfolioForm() {
  elements.portfolioForm.reset();
}

async function loadInvestmentPlans() {
  if (!state.user) {
    elements.planList.innerHTML = '<div class="plan-item">登录后可查看定投计划</div>';
    return;
  }

  try {
    const data = await api('/plans');
    const items = data.items || [];
    if (!items.length) {
      elements.planList.innerHTML = '<div class="plan-item">暂无定投计划</div>';
      return;
    }

    elements.planList.innerHTML = items
      .map((item) => `
        <div class="plan-item">
          <div class="plan-head">
            <strong>${item.symbol}</strong>
            <span class="plan-badge">${Number(item.target_return || 0).toFixed(1)}%/年</span>
          </div>
          <div class="plan-row"><span>月投入</span><span>${Number(item.monthly_amount || 0).toFixed(2)}</span></div>
          <div class="plan-row"><span>计划月数</span><span>${item.months}</span></div>
          <div class="plan-row"><span>当前价</span><span>${Number(item.current_price || 0).toFixed(2)}</span></div>
          <div class="plan-row"><span>预期累计</span><span>${Number(item.expected_value || 0).toFixed(2)}</span></div>
          <div class="plan-row"><span>目标估值</span><span>${Number(item.projected_value || 0).toFixed(2)}</span></div>
          <div class="plan-row"><span>备注</span><span>${item.note || '无'}</span></div>
          <div class="plan-row">
            <span>操作</span>
            <button class="ghost-btn" data-delete-plan="${item.id}">删除</button>
          </div>
        </div>
      `)
      .join('');

    elements.planList.querySelectorAll('[data-delete-plan]').forEach((button) => {
      button.addEventListener('click', async () => {
        const id = Number(button.dataset.deletePlan);
        await api(`/plans/${id}`, { method: 'DELETE' });
        await loadInvestmentPlans();
      });
    });
  } catch (error) {
    elements.planList.innerHTML = `<div class="plan-item">定投计划加载失败：${error.message}</div>`;
  }
}

async function saveInvestmentPlan(event) {
  event.preventDefault();
  if (!state.user) {
    setStatus('请先登录后再保存定投计划', 'error');
    return;
  }

  const payload = {
    symbol: elements.planSymbol.value.trim().toUpperCase(),
    monthly_amount: Number(elements.planAmount.value),
    target_return: Number(elements.planTargetReturn.value || 0),
    months: Number(elements.planMonths.value || 12),
    note: elements.planNote.value.trim(),
  };

  await api('/plans', {
    method: 'POST',
    body: payload,
  });
  setStatus('定投计划已保存');
  elements.planForm.reset();
  await loadInvestmentPlans();
}

function clearPlanForm() {
  elements.planForm.reset();
}

async function loadStrategyComparison(symbol = '') {
  if (!state.user) {
    elements.strategyCompare.innerHTML = '<div class="compare-item">登录后可查看策略对比</div>';
    return;
  }

  try {
    const data = await api('/strategies/compare', {
      params: { symbol: symbol || state.selectedSymbol || '' },
    });
    const items = data.items || [];
    if (!items.length) {
      elements.strategyCompare.innerHTML = '<div class="compare-item">暂无可比较策略</div>';
      return;
    }

    const rankingHtml = items
      .map((item, index) => `
        <div class="compare-item">
          <div class="compare-head">
            <strong>${index + 1}. ${item.name}</strong>
            <span class="score-badge ${item.grade === '强' ? 'score-strong' : item.grade === '中' ? 'score-medium' : 'score-weak'}">${item.grade} ${item.score}</span>
          </div>
          <div class="compare-meta">${item.symbol} · ${item.status}</div>
          <div class="compare-meta">${item.summary || '未计算'}</div>
          <div class="compare-reasons">${(item.reasons || []).join(' / ') || '暂无说明'}</div>
        </div>
      `)
      .join('');

    elements.strategyCompare.innerHTML = rankingHtml;
  } catch (error) {
    elements.strategyCompare.innerHTML = `<div class="compare-item">策略对比失败：${error.message}</div>`;
  }
}

async function loadAiSummary() {
  if (!state.user) {
    elements.aiSummary.innerHTML = '<div class="ai-card">登录后查看AI交易建议</div>';
    return;
  }

  try {
    const data = await api('/insights/summary');
    const summary = data.summary || {};
    const bullets = (summary.recommendations || []).map((item) => `<li>${item}</li>`).join('');
    elements.aiSummary.innerHTML = `
      <div class="ai-card ${summary.trend === '偏强' ? 'ai-up' : summary.trend === '偏弱' ? 'ai-down' : 'ai-neutral'}">
        <div class="ai-header">
          <strong>整体判断</strong>
          <span class="signal-summary ${summary.trend === '偏强' ? 'up' : summary.trend === '偏弱' ? 'down' : 'neutral'}">${summary.trend || '震荡'}</span>
        </div>
        <div class="ai-grid">
          <div><span class="ai-label">组合市值</span><strong>${Number(summary.portfolio_value || 0).toFixed(2)}</strong></div>
          <div><span class="ai-label">组合盈亏</span><strong>${Number(summary.portfolio_pnl || 0).toFixed(2)}</strong></div>
          <div><span class="ai-label">优先策略</span><strong>${summary.best_strategy || '无'}</strong></div>
          <div><span class="ai-label">重点关注</span><strong>${summary.focus_symbol || '无'}</strong></div>
        </div>
        <ul class="ai-list">${bullets}</ul>
      </div>
    `;
  } catch (error) {
    elements.aiSummary.innerHTML = `<div class="ai-card ai-neutral">AI建议加载失败：${error.message}</div>`;
  }
}

async function loadBacktestTrend(symbol = state.selectedSymbol) {
  if (!symbol) return;
  try {
    const data = await api(`/stock/${encodeURIComponent(symbol)}/backtest/curve`);
    const items = data.items || [];
    const labels = items.map((item) => `${item.fast_period}/${item.slow_period}`);
    const values = items.map((item) => Number(item.net_return || 0));
    renderLineChart(elements.backtestTrendChart, labels, values, {
      label: `${symbol} 回测收益`,
      color: '#8b5cf6',
      fillColor: 'rgba(139,92,246,0.12)',
    });
  } catch (error) {
    elements.backtestTrendChart.parentElement.innerHTML = `<div class="ai-card ai-neutral">回测趋势加载失败：${error.message}</div>`;
  }
}

async function loadPortfolioSummary() {
  if (!state.user) {
    elements.portfolioSummaryChart.parentElement.innerHTML = '<div class="ai-card ai-neutral">登录后查看收益总览</div>';
    return;
  }

  try {
    const data = await api('/portfolio/summary');
    const chartData = data.chart || [];
    const labels = chartData.map((point) => point.label || '');
    const values = chartData.map((point) => Number(point.value || 0));
    renderLineChart(elements.portfolioSummaryChart, labels, values, {
      label: '组合收益',
      color: '#f59e0b',
      fillColor: 'rgba(245,158,11,0.12)',
    });
  } catch (error) {
    elements.portfolioSummaryChart.parentElement.innerHTML = `<div class="ai-card ai-neutral">收益总结加载失败：${error.message}</div>`;
  }
}

async function loadNotifications() {
  if (!state.user) {
    elements.notificationList.innerHTML = '<div class="notification-item info"><strong>提醒中心</strong><div>登录后可查看提醒</div></div>';
    return;
  }

  try {
    const data = await api('/notifications');
    const items = data.items || [];
    const threshold = Number(data.alert_threshold || state.profile.alert_threshold || 5);
    if (!items.length) {
      elements.notificationList.innerHTML = '<div class="notification-item success"><strong>无提醒</strong><div>当前市场状态良好，无需额外处理</div></div>';
      return;
    }

    elements.notificationList.innerHTML = `
      <div class="notification-item info">
        <div class="notification-head">
          <strong>提醒阈值</strong>
          <span class="notification-tag">${threshold.toFixed(1)}%</span>
        </div>
        <div>当前提醒阈值来自个人设置，可在左侧设置中调整。</div>
      </div>
      ${items.map((item) => `
        <div class="notification-item ${item.level || 'info'}">
          <div class="notification-head">
            <strong>${item.title}</strong>
            <span class="notification-tag">${item.level === 'warning' ? '警告' : item.level === 'success' ? '正常' : '信息'}</span>
          </div>
          <div>${item.message}</div>
          <small>${item.created_at || ''}</small>
        </div>
      `).join('')}
    `;
  } catch (error) {
    elements.notificationList.innerHTML = `<div class="notification-item warning"><strong>提醒中心</strong><div>加载失败：${error.message}</div></div>`;
  }
}

async function init() {
  try {
    await loadAuthState();
    await populateTables();
    await fetchSummary();
    await fetchTrends();
    await loadMarketTicker();
    await loadMarketOverview();
    await loadMarketHeat();
    await loadMarketPulse();
    await loadStockScreener();
    const defaultSymbol = state.selectedSymbol || 'bj920000';
    elements.stockSearchInput.value = defaultSymbol;
    elements.alertSymbol.value = defaultSymbol;
    await searchStocks();
    await loadEmailConfig();
    await loadStockAlerts();
    await loadStrategies(defaultSymbol);
    await loadWatchlist();
    await loadPortfolio();
    await loadPortfolioRisk();
    await loadInvestmentPlans();
    await loadStrategyComparison(defaultSymbol);
    await loadBacktestTrend(defaultSymbol);
    await loadPortfolioSummary();
    await loadAiSummary();
    await loadNotifications();
  } catch (error) {
    renderTextResults('初始化失败', error.message);
    setStatus('失败', 'error');
  }
}

document.querySelectorAll('[data-action]').forEach((button) => {
  button.addEventListener('click', () => handleAction(button.dataset.action));
});

const requests = {
  registerForm: elements.registerForm,
  loginForm: elements.loginForm,
  profileForm: elements.profileForm,
  stockSearchBtn: elements.stockSearchBtn,
  refreshBtn: elements.refreshBtn,
  clearStrategyBtn: elements.clearStrategyBtn,
  logoutBtn: elements.logoutBtn,
};

const savedTheme = localStorage.getItem('stock-theme') || 'light';
applyTheme(savedTheme);
updateClock();
setInterval(updateClock, 1000);

if (requests.profileForm) {
  requests.profileForm.addEventListener('submit', saveUserProfile);
}
if (requests.stockSearchBtn) {
  requests.stockSearchBtn.addEventListener('click', searchStocks);
}
elements.stockSearchInput.addEventListener('keydown', (event) => {
  if (event.key === 'Enter') {
    searchStocks();
  }
});
requests.refreshBtn.addEventListener('click', async () => {
  await handleAction(state.activeAction || 'trends');
  await loadStockScreener();
});
elements.exportReportBtn.addEventListener('click', exportReport);
requests.clearStrategyBtn.addEventListener('click', clearStrategyForm);
requests.logoutBtn.addEventListener('click', logoutUser);
elements.themeToggleBtn.addEventListener('click', toggleTheme);

applyTheme();

elements.stockScreenBtn.addEventListener('click', loadStockScreener);
elements.screenMinChange.addEventListener('change', loadStockScreener);
elements.screenMinScore.addEventListener('change', loadStockScreener);
elements.screenSignalType.addEventListener('change', loadStockScreener);

elements.addWatchlistBtn.addEventListener('click', addWatchlist);
elements.watchlistSymbol.addEventListener('keydown', (event) => {
  if (event.key === 'Enter') {
    addWatchlist(event);
  }
});

if (elements.alertForm) {
  elements.alertForm.addEventListener('submit', saveStockAlert);
}
if (elements.emailConfigForm) {
  elements.emailConfigForm.addEventListener('submit', saveEmailConfig);
}

elements.portfolioForm.addEventListener('submit', savePortfolio);
elements.clearPortfolioBtn.addEventListener('click', clearPortfolioForm);
elements.planForm.addEventListener('submit', saveInvestmentPlan);
elements.clearPlanBtn.addEventListener('click', clearPlanForm);

elements.tableSelect.addEventListener('change', () => {
  handleAction(state.activeAction || 'trends');
});

elements.daysInput.addEventListener('change', () => {
  handleAction(state.activeAction || 'trends');
});

elements.dateInput.addEventListener('change', () => {
  handleAction(state.activeAction || 'trends');
});

elements.strategyForm.addEventListener('submit', saveStrategy);

init();
