// Hydrate dashboard globals from the generated structured payload.
var WEEKLY_DASHBOARD_DATA = window.WEEKLY_DASHBOARD_DATA || {};
var RAW_TREND = WEEKLY_DASHBOARD_DATA.RAW_TREND || [];
var MEDIA_DATA = WEEKLY_DASHBOARD_DATA.MEDIA_DATA || {};
var CENTER_YEAR = WEEKLY_DASHBOARD_DATA.CENTER_YEAR || {};
var CENTER_MONTHS = WEEKLY_DASHBOARD_DATA.CENTER_MONTHS || [];
var TEAM_DATA = WEEKLY_DASHBOARD_DATA.TEAM_DATA || {};
var BRAND_DATA = WEEKLY_DASHBOARD_DATA.BRAND_DATA || [];
var DEPT_PC_DATA = WEEKLY_DASHBOARD_DATA.DEPT_PC_DATA || [];
var CENTER_PC_DATA = WEEKLY_DASHBOARD_DATA.CENTER_PC_DATA || [];
var DEPT_YEAR_COST_DATA = WEEKLY_DASHBOARD_DATA.DEPT_YEAR_COST_DATA || [];
var ROI_DATA = WEEKLY_DASHBOARD_DATA.ROI_DATA || [];
var DEPT_MONTHLY_ROI = WEEKLY_DASHBOARD_DATA.DEPT_MONTHLY_ROI || {};
var MONTH_CENTER = WEEKLY_DASHBOARD_DATA.MONTH_CENTER || {};
var MONTH_TARGET = WEEKLY_DASHBOARD_DATA.MONTH_TARGET || [];
var MONTH_MEDIA_LIST = WEEKLY_DASHBOARD_DATA.MONTH_MEDIA_LIST || [];
var MONTH_DEPT_PC = WEEKLY_DASHBOARD_DATA.MONTH_DEPT_PC || [];
var MONTH_DEPT_BRAND_PC = WEEKLY_DASHBOARD_DATA.MONTH_DEPT_BRAND_PC || [];
var MONTH_DEPT_ACCT_PC = WEEKLY_DASHBOARD_DATA.MONTH_DEPT_ACCT_PC || [];
var MONTH_ROI = WEEKLY_DASHBOARD_DATA.MONTH_ROI || [];
var MONTH_DEPT_ACCT_DAILY = WEEKLY_DASHBOARD_DATA.MONTH_DEPT_ACCT_DAILY || [];
var WEEK_METRIC_ANALYSIS = WEEKLY_DASHBOARD_DATA.WEEK_METRIC_ANALYSIS || {weeks: [], metrics: []};
var MONTH_MEDIA_TABLE = WEEKLY_DASHBOARD_DATA.MONTH_MEDIA_TABLE || {};
var MONTH_MEDIA_SUB_DEPTS = WEEKLY_DASHBOARD_DATA.MONTH_MEDIA_SUB_DEPTS || [];
var CENTER_YEAR_MEDIA = WEEKLY_DASHBOARD_DATA.CENTER_YEAR_MEDIA || [];
var REPORT_FLOW_OVERVIEW = WEEKLY_DASHBOARD_DATA.REPORT_FLOW_OVERVIEW || {};
var DEPT_GROUP_DATA = WEEKLY_DASHBOARD_DATA.DEPT_GROUP_DATA || {};
var DEPT_STAFF_DATA = WEEKLY_DASHBOARD_DATA.DEPT_STAFF_DATA || {};
var DEPT_STAFF_MONTHLY_DATA = WEEKLY_DASHBOARD_DATA.DEPT_STAFF_MONTHLY_DATA || {};
var WEEKLY_DEPT_AVG = WEEKLY_DASHBOARD_DATA.WEEKLY_DEPT_AVG || {};
var WEEKLY_PROJ_ALERT = WEEKLY_DASHBOARD_DATA.WEEKLY_PROJ_ALERT || [];
var ROI_HIDDEN_DEPTS = {};
var TEMP_YEAR_MEDIA_TARGETS = {
  '腾讯': 992725319,
  '快手': 59156314,
  '小红书': 228123278,
  '头条': 159157036
};

CENTER_YEAR_MEDIA = (CENTER_YEAR_MEDIA || []).map(function(m) {
  var overrideTarget = TEMP_YEAR_MEDIA_TARGETS[m.media];
  if (typeof overrideTarget !== 'number' || !isFinite(overrideTarget)) {
    return m;
  }
  var next = Object.assign({}, m);
  next.target = overrideTarget;
  next.has_target = overrideTarget > 0;
  next.completion_pct = overrideTarget > 0 && typeof next.cost === 'number'
    ? next.cost / overrideTarget * 100
    : null;
  next.target_gap = overrideTarget > 0 && typeof next.cost === 'number'
    ? next.cost - overrideTarget
    : null;
  next.forecast_pct = overrideTarget > 0 && typeof next.forecast === 'number'
    ? next.forecast / overrideTarget * 100
    : null;
  next.forecast_gap = overrideTarget > 0 && typeof next.forecast === 'number'
    ? next.forecast - overrideTarget
    : null;
  return next;
});

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// 部门详情模块 - 每个部门独立展示两张图：左=人均日耗趋势，右=月投产比趋势
// 保留部门/组别维度切换，无人员明细
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
(function(){
  var DETAIL_KEYS = ['K2','K3','K4','K7','K4-\u54c1\u5546','\u54c1\u7b56-\u5c0f\u7ea2\u4e66'];
  var DETAIL_COLORS = {'K2':'#4F6BED','K3':'#D97706','K4':'#0F9D7A','K4-\u54c1\u5546':'#2563EB','K7':'#7C8F2A','\u54c1\u7b56-\u5c0f\u7ea2\u4e66':'#7C6A9A'};
  var DETAIL_COLORS2 = {'K2':'#3157D5','K3':'#B45309','K4':'#0B7F63','K4-\u54c1\u5546':'#1D4ED8','K7':'#5F6F1F','\u54c1\u7b56-\u5c0f\u7ea2\u4e66':'#67557F'};
  var GROUP_PALETTE = ['#4F6BED','#D97706','#0F9D7A','#2563EB','#C65F80','#7C6A9A','#B45309','#0B7F63'];
  var currentDim = 'dept';
  var chartInstances = [];

  // ── Dimension switch buttons ──
  var btnBox = document.getElementById('dept-btns');
  btnBox.innerHTML = '<div class="detail-switch"><span class="detail-switch-label">\u7ef4\u5ea6\uff1a</span>'
    + '<button class="dept-btn active" id="dim-dept-btn" onclick="switchDetailDim(\'dept\')">\u90e8\u95e8</button>'
    + '<button class="dept-btn" id="dim-group-btn" onclick="switchDetailDim(\'group\')">\u7ec4\u522b</button></div>';

  window.switchDetailDim = function(dim) {
    currentDim = dim;
    document.getElementById('dim-dept-btn').classList.toggle('active', dim === 'dept');
    document.getElementById('dim-group-btn').classList.toggle('active', dim === 'group');
    renderAllDepts();
  };

  function fmtW(v) { var w = v / 10000; return w >= 10000 ? (w / 10000).toFixed(1) + '\u4ebf' : w.toFixed(1) + '\u4e07'; }

  // ── Collect months from DEPT_GROUP_DATA for this dept ──
  function getGroupMonths(dept) {
    var groups = DEPT_GROUP_DATA[dept] || {};
    var monthSet = {};
    var gNames = Object.keys(groups);
    for (var gi = 0; gi < gNames.length; gi++) {
      var arr = groups[gNames[gi]];
      for (var mi = 0; mi < arr.length; mi++) {
        monthSet[arr[mi].month] = true;
      }
    }
    return Object.keys(monthSet).sort(function(a, b) { return parseInt(a) - parseInt(b); });
  }

  // ── Build left chart (\u4eba\u5747\u65e5\u8017\u8d8b\u52bf) ──
  function buildPcOption(dept, dim) {
    var clr = DETAIL_COLORS[dept] || '#1A56DB';

    if (dim === 'dept') {
      var td = TEAM_DATA[dept];
      if (!td) return {};
      var months = td.months;
      var pcVals = td.month_pcs;
      return {
        tooltip: { trigger: 'axis', formatter: function(p) { return p[0].name + '<br/>\u4eba\u5747\u65e5\u8017: <b>' + p[0].value.toFixed(2) + '\u4e07</b>'; } },
        grid: { top: 30, right: 50, bottom: 24, left: 50, containLabel: false },
        xAxis: { type: 'category', data: months, axisLine: { lineStyle: { color: '#E5E7EB' } }, axisLabel: { color: '#9CA3AF', fontSize: 10 } },
        yAxis: { type: 'value', axisLine: { show: false }, splitLine: { lineStyle: { color: '#F3F4F6' } }, axisLabel: { color: '#9CA3AF', fontSize: 10, formatter: function(v) { return v.toFixed(1) + '\u4e07'; } } },
        series: [{
          type: 'line', smooth: true, data: pcVals,
          areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: clr + '40' }, { offset: 1, color: clr + '05' }]) },
          lineStyle: { color: clr, width: 2.5 },
          itemStyle: { color: clr },
          symbol: 'circle', symbolSize: 6,
          label: { show: true, position: 'top', fontSize: 10, color: '#374151', fontWeight: 500, formatter: function(p) { return p.value != null ? p.value.toFixed(2) : ''; } },
          markLine: { data: [{ yAxis: 6, symbol: 'none', lineStyle: { color: '#EF4444', type: 'dashed', width: 1 }, label: { show: true, formatter: '6\u4e07', fontSize: 9, color: '#EF4444', position: 'insideEndTop' } }] }
        }]
      };
    } else {
      var months = getGroupMonths(dept);
      var groups = DEPT_GROUP_DATA[dept] || {};
      var gNames = Object.keys(groups);
      var series = [];
      for (var gi = 0; gi < gNames.length; gi++) {
        var gn = gNames[gi];
        var arr = groups[gn];
        var vals = [];
        for (var mi = 0; mi < months.length; mi++) {
          var found = false;
          for (var vi = 0; vi < arr.length; vi++) {
            if (arr[vi].month === months[mi]) { vals.push(arr[vi].daily_pc); found = true; break; }
          }
          if (!found) vals.push(null);
        }
        series.push({
          name: gn, type: 'line', smooth: true, data: vals,
          areaStyle: { color: GROUP_PALETTE[gi % GROUP_PALETTE.length] + '30' },
          lineStyle: { color: GROUP_PALETTE[gi % GROUP_PALETTE.length], width: 2 },
          itemStyle: { color: GROUP_PALETTE[gi % GROUP_PALETTE.length] },
          symbol: 'circle', symbolSize: 5,
          label: { show: true, position: 'top', fontSize: 9, color: '#374151', fontWeight: 500, formatter: function(p) { return p.value != null ? p.value.toFixed(2) : ''; } }
        });
      }
      if (series.length > 0) {
        series[0].markLine = {
          data: [{ yAxis: 6, symbol: 'none', lineStyle: { color: '#EF4444', type: 'dashed', width: 1 }, label: { show: true, formatter: '6\u4e07', fontSize: 9, color: '#EF4444', position: 'insideEndTop' } }]
        };
      }
      return {
        tooltip: { trigger: 'axis', formatter: function(p) {
          var h = '<b>' + p[0].axisValue + '</b><br/>';
          for (var i = 0; i < p.length; i++) { if (p[i].value != null) h += '<span style="color:' + p[i].color + '">\u25cf</span> ' + p[i].seriesName + ': <b>' + p[i].value.toFixed(2) + '\u4e07</b><br/>'; }
          return h;
        } },
        labelLayout: { hideOverlap: true },
        legend: { data: gNames, top: 0, textStyle: { fontSize: 10, color: '#6B7280' } },
        grid: { top: 36, right: 50, bottom: 24, left: 50, containLabel: false },
        xAxis: { type: 'category', data: months, axisLine: { lineStyle: { color: '#E5E7EB' } }, axisLabel: { color: '#9CA3AF', fontSize: 10 } },
        yAxis: { type: 'value', axisLine: { show: false }, splitLine: { lineStyle: { color: '#F3F4F6' } }, axisLabel: { color: '#9CA3AF', fontSize: 10, formatter: function(v) { return v.toFixed(1) + '\u4e07'; } } },
        series: series
      };
    }
  }

  // ── Build right chart (\u6708\u6295\u4ea7\u6bd4\u8d8b\u52bf) ──
  function buildRoiOption(dept) {
    if (ROI_HIDDEN_DEPTS[dept]) {
      return {};
    }
    var clr = DETAIL_COLORS[dept] || '#1A56DB';
    var clr2 = DETAIL_COLORS2[dept] || '#3B82F6';
    var roiArr = (DEPT_MONTHLY_ROI && DEPT_MONTHLY_ROI[dept]) || [];
    if (roiArr.length === 0) {
      return {};
    }
    var months = [];
    var vals = [];
    for (var i = 0; i < roiArr.length; i++) {
      months.push(roiArr[i].month + '\u6708');
      vals.push(roiArr[i].roi);
    }
    return {
      tooltip: { trigger: 'axis', formatter: function(p) { return p[0].name + '<br/>\u6295\u4ea7\u6bd4: <b>' + p[0].value.toFixed(2) + '</b>'; } },
      grid: { top: 30, right: 50, bottom: 24, left: 50, containLabel: false },
      xAxis: { type: 'category', data: months, axisLine: { lineStyle: { color: '#E5E7EB' } }, axisLabel: { color: '#9CA3AF', fontSize: 10 } },
      yAxis: { type: 'value', axisLine: { show: false }, splitLine: { lineStyle: { color: '#F3F4F6' } }, axisLabel: { color: '#9CA3AF', fontSize: 10, formatter: function(v) { return v.toFixed(1); } } },
      series: [{
        type: 'bar', data: vals,
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: clr }, { offset: 1, color: clr2 }]),
          borderRadius: [4, 4, 0, 0]
        },
        barMaxWidth: 32,
        label: { show: true, position: 'top', fontSize: 10, color: '#374151', fontWeight: 600, formatter: function(p) { return p.value.toFixed(2); } }
      }]
    };
  }

  // ── Render all departments ──
  function renderAllDepts() {
    // Dispose old charts
    for (var ci = 0; ci < chartInstances.length; ci++) {
      chartInstances[ci].dispose();
    }
    chartInstances = [];

    var dim = currentDim;
    var dimLabel = dim === 'dept' ? '\u90e8\u95e8' : '\u7ec4\u522b';
    var html = '';

    for (var di = 0; di < DETAIL_KEYS.length; di++) {
      var dept = DETAIL_KEYS[di];
      var clr = DETAIL_COLORS[dept] || '#1A56DB';

      // \u4eba\u5747\u65e5\u8017\u6458\u8981
      var pcSummary = '';
      if (dim === 'dept') {
        var deptPc = 0;
        for (var dpi = 0; dpi < DEPT_PC_DATA.length; dpi++) {
          if (DEPT_PC_DATA[dpi].dept === dept) { deptPc = DEPT_PC_DATA[dpi].pc; break; }
        }
        var passed = deptPc >= 60000;
        pcSummary = '<div class="detail-summary">\u5e74\u5ea6\u4eba\u5747\u65e5\u8017 <strong>' + (deptPc / 10000).toFixed(1) + '\u4e07</strong> <span class="detail-status" style="--status-color:' + (passed ? '#059669' : '#EF4444') + '">' + (passed ? '\u8fbe\u6807 \u2713' : '\u5f85\u63d0\u5347') + '</span></div>';
      } else {
        var staffArr = DEPT_STAFF_DATA[dept] || [];
        var grpPcMap = {};
        var grpCount = {};
        for (var si = 0; si < staffArr.length; si++) {
          var g = staffArr[si].group || '\u672a\u5206\u7ec4';
          grpPcMap[g] = (grpPcMap[g] || 0) + staffArr[si].daily_avg;
          grpCount[g] = (grpCount[g] || 0) + 1;
        }
        var gNames = Object.keys(grpPcMap);
        var tags = [];
        for (var gi = 0; gi < gNames.length; gi++) {
          var avg = grpPcMap[gNames[gi]] / grpCount[gNames[gi]];
          var p = avg >= 60000;
          tags.push('<span class="detail-status-tag" style="--status-color:' + (p ? '#059669' : '#EF4444') + ';--status-bg:' + (p ? '#ECFDF5' : '#FEF2F2') + '">' + gNames[gi] + ' ' + (avg / 10000).toFixed(1) + '\u4e07 ' + (p ? '\u8fbe\u6807' : '\u5f85\u63d0\u5347') + '</span>');
        }
        pcSummary = '<div class="detail-tag-row">' + tags.join('') + '</div>';
      }

      // \u6295\u4ea7\u6bd4\u6458\u8981\uff08\u5e74\u5ea6\u6295\u4ea7\u6bd4\uff09
      var yearRoi = 0;
      if (!ROI_HIDDEN_DEPTS[dept]) {
        for (var ri = 0; ri < ROI_DATA.length; ri++) {
          if (ROI_DATA[ri].dept === dept) { yearRoi = ROI_DATA[ri].roi; break; }
        }
      }
      var roiSummary = '';
      if (yearRoi > 0) {
        roiSummary = '<div class="detail-summary">\u5e74\u5ea6\u6295\u4ea7\u6bd4 <strong>' + yearRoi.toFixed(2) + '</strong></div>';
      } else {
        roiSummary = '<div class="detail-empty">\u6682\u65e0\u6295\u4ea7\u6bd4\u6570\u636e</div>';
      }

      var pcId = 'dept-pc-' + di;
      var roiId = 'dept-roi-' + di;

      html += '<div class="detail-dept-card" style="--dept-color:' + clr + '">'
        + '<div class="detail-card-title"><span class="detail-title-dot"></span>' + dept + '</div>'
        + '<div class="detail-grid">'
        + '<div class="detail-chart-block"><div class="panel-kicker"><span></span>\u4eba\u5747\u65e5\u8017\u8d8b\u52bf\uff08' + dimLabel + '\uff09</div>' + pcSummary + '<div id="' + pcId + '" class="chart-sm"></div></div>'
        + '<div class="detail-chart-block"><div class="panel-kicker"><span></span>\u6708\u6295\u4ea7\u6bd4\u8d8b\u52bf</div>' + roiSummary + '<div id="' + roiId + '" class="chart-sm"></div></div>'
        + '</div></div>';
    }

    document.getElementById('dept-detail-content').innerHTML = html;

    // Init charts
    for (var di = 0; di < DETAIL_KEYS.length; di++) {
      var dept = DETAIL_KEYS[di];
      var pcOpt = buildPcOption(dept, dim);
      var roiOpt = buildRoiOption(dept);

      var pcEl = document.getElementById('dept-pc-' + di);
      var roiEl = document.getElementById('dept-roi-' + di);

      if (pcEl && Object.keys(pcOpt).length > 0) {
        var p = echarts.init(pcEl);
        p.setOption(pcOpt);
        chartInstances.push(p);
      }
      if (roiEl && Object.keys(roiOpt).length > 0) {
        var r = echarts.init(roiEl);
        r.setOption(roiOpt);
        chartInstances.push(r);
      }
    }
  }

  renderAllDepts();
  window.addEventListener('resize', function() {
    for (var ci = 0; ci < chartInstances.length; ci++) {
      chartInstances[ci].resize();
    }
  });
})();

// ═══════════════════════════════════════════════════════════
// 顶部目标进度 KPI 卡
// ═══════════════════════════════════════════════════════════
(function(){
  var yearBox = document.getElementById('year-goal-kpi');
  var monthBox = document.getElementById('month-goal-kpi');
  var year = REPORT_FLOW_OVERVIEW.year || {};
  var month = REPORT_FLOW_OVERVIEW.month || {};
  var TEMP_YEAR_TARGET = 1439161947;
  var TEMP_MONTH_TARGET = 127485001;

  function applyTempTarget(scope, tempTarget) {
    if (!scope || !tempTarget) return scope || {};
    var next = Object.assign({}, scope);
    next.target = tempTarget;
    next.completion_pct = typeof next.cost === 'number' && tempTarget
      ? (next.cost / tempTarget * 100)
      : next.completion_pct;
    next.forecast_pct = typeof next.forecast === 'number' && tempTarget
      ? (next.forecast / tempTarget * 100)
      : next.forecast_pct;
    next.forecast_gap = typeof next.forecast === 'number'
      ? (next.forecast - tempTarget)
      : next.forecast_gap;
    return next;
  }

  year = applyTempTarget(year, TEMP_YEAR_TARGET);
  month = applyTempTarget(month, TEMP_MONTH_TARGET);

  if (yearBox && year.target) {
    yearBox.innerHTML = goalProgressCard({
      theme: 'goal-progress-blue',
      targetLabel: '年目标',
      target: fmtWan(year.target),
      costLabel: '年度消耗',
      cost: fmtWan(year.cost),
      completionPct: year.completion_pct,
      forecastPct: year.forecast_pct,
      forecast: fmtWan(year.forecast),
      forecastGap: year.forecast_gap
    });
  }

  if (monthBox && month.target) {
    monthBox.innerHTML = goalProgressCard({
      theme: 'goal-progress-orange',
      targetLabel: '月目标',
      target: fmtWan(month.target),
      costLabel: '月度消耗',
      cost: fmtWan(month.cost),
      completionPct: month.completion_pct,
      forecastPct: month.forecast_pct,
      forecast: fmtWan(month.forecast),
      forecastGap: month.forecast_gap
    });
  }
})();

// ═══════════════════════════════════════════════════════════
// 去年同期数据（手动维护，每年更新一次）
// ═══════════════════════════════════════════════════════════
var LY_DAILY = 4448088;
var LY_PC    = 52993;

// ═══════════════════════════════════════════════════════════
// 配色 & 常量
// ═══════════════════════════════════════════════════════════
var MCOLORS = {'腾讯':'#0EA5A4','小红书':'#E85D75','头条':'#16A34A','快手':'#F59E0B','阿里UDS':'#64748B','百度':'#2563EB'};
var DCOLORS = {'K部门':'#F97316','K2':'#4F6BED','K3':'#D97706','K4':'#0F9D7A','K5':'#64748B','K7':'#7C8F2A','K4-品商':'#2563EB','品策-小红书':'#7C6A9A'};
var DEPT_KEYS = ['K部门','K2','K3','K4','K5','K7','K4-品商','品策-小红书'];

// 各团队去年年日均（元，手动维护）
var LY_DEPT_DAILY = {'K2':930342,'K3':1126260,'K4':384047,'K4-品商':351106,'K7':623799,'品策-小红书':336012};

// ═══════════════════════════════════════════════════════════
// 工具函数
// ═══════════════════════════════════════════════════════════
function fmtWan(v){ var w=v/10000; return w>=10000?(w/10000).toFixed(1)+'亿':w.toFixed(1)+'万'; }
function fmtPct(v){ return (v>=0?'+':'')+v.toFixed(1)+'%'; }
function pctText(v) {
  return typeof v === 'number' && isFinite(v) ? v.toFixed(1) + '%' : '待定';
}
function goalStatusText(gap) {
  if (typeof gap !== 'number' || !isFinite(gap)) return '目标待定';
  return gap >= 0 ? ('预计超目标 ' + fmtWan(gap)) : ('预计差额 ' + fmtWan(Math.abs(gap)));
}
function goalProgressCard(config) {
  var pct = typeof config.completionPct === 'number' && isFinite(config.completionPct)
    ? Math.max(0, Math.min(config.completionPct, 100))
    : 0;
  return '<div class="goal-progress-card '+config.theme+'">'
      + '<div class="goal-progress-main">'
      + '<div class="goal-metric"><span>'+config.targetLabel+'</span><strong>'+config.target+'</strong></div>'
      + '<div class="goal-metric"><span>'+config.costLabel+'</span><strong>'+config.cost+'</strong></div>'
      + '<div class="goal-metric goal-forecast"><span>预计完成率</span><strong>'+pctText(config.forecastPct)+'</strong></div>'
      + '<div class="goal-progress-line">'
        + '<div class="goal-progress-label"><span>目标完成率</span><b>'+pctText(config.completionPct)+'</b></div>'
        + '<div class="goal-progress-track"><div class="goal-progress-fill" style="--w:'+pct.toFixed(1)+'%"></div></div>'
      + '</div>'
      + '<div class="goal-forecast-detail"><em>预计完成 '+config.forecast+'</em><em>'+goalStatusText(config.forecastGap)+'</em></div>'
    + '</div>'
  + '</div>';
}

function pillHtml(v){
  var cls = v>=0?'up':'dn', arrow = v>=0?'↑':'↓';
  return '<span class="pill '+cls+'">'+arrow+Math.abs(v).toFixed(1)+'%</span>';
}
function getDArr(media) {
  if (media === 'all') return RAW_TREND;
  return MEDIA_DATA[media] || [];
}
function filterByMonth(arr, mo) {
  if (!mo) return arr;
  var prefix = RAW_TREND[0]['日期'].substring(0,4) + '-' + mo;
  return arr.filter(function(d){ return d['日期'].substring(0,7) === prefix; });
}

// ═══════════════════════════════════════════════════════════
// 顶部KPI模块 动态获取数据并渲染
// ═══════════════════════════════════════════════════════════
(function(){
  var minD = new Date(RAW_TREND[0]['日期']);
  var maxD = new Date(RAW_TREND[RAW_TREND.length-1]['日期']);
  var yrMin = minD.getFullYear(), moMax = maxD.getMonth()+1, dayMax = maxD.getDate();
  document.getElementById('header-range').textContent =
    '数据区间：'+yrMin+'-'+(''+(minD.getMonth()+1)).padStart(2,'0')+'-'+(''+minD.getDate()).padStart(2,'0')
    +' ~ '+maxD.getFullYear()+'-'+(''+(maxD.getMonth()+1)).padStart(2,'0')+'-'+(''+maxD.getDate()).padStart(2,'0');

  var yearStart = new Date(yrMin, 0, 1);
  var yrDays = Math.round((maxD - yearStart) / 86400000) + 1;
  
  // ======================================
  // 人工新增,dayPercent:年过去的天数占比,daysInMonth:当月天数
  // ======================================
  var totalDays = (yrMin % 4 === 0 && yrMin % 100 !== 0) || (yrMin % 400 === 0) ? 366 : 365;
  var dayPercent = (yrDays / totalDays * 100).toFixed(1);
  var daysInMonth = new Date(maxD.getFullYear(), maxD.getMonth() + 1, 0).getDate();
  var dayPercentInMonth = (dayMax / daysInMonth * 100).toFixed(1);

  var yrTotal = CENTER_YEAR['消耗'];
  var yrDaily = CENTER_YEAR['日均消耗'];
  var yrPc = CENTER_YEAR['人均日耗'];
  // 月均消耗 = 年度消耗 / (截止上月的完整月数 + 当月已过天数/当月总天数)
  // 当月已过天数 = maxD.getDate()（即最新消耗日期）
  var completedMonths = maxD.getMonth(); // 0-based → 即截止上月的完整月数（1月=0个完整月）
  var monthWeight = completedMonths + dayMax / daysInMonth;
  var yrMonthlyAvg = monthWeight > 0 ? yrTotal / monthWeight : 0;
  document.getElementById('kpi-yr-total').textContent = fmtWan(yrMonthlyAvg);
  // ======================================
  // 人工新增
  // ======================================
  // document.getElementById('yr-days').innerHTML = '年度累计 <b>'+yrDays+'</b> 天';
  // document.getElementById('yr-day-pct').innerHTML = '时间进度  <b>'+dayPercent+'%</b>';

  document.getElementById('kpi-yr-daily').textContent = fmtWan(yrDaily);
  // ======================================
  // 人工临时改动,不展示相比去年环比
  // ======================================
  // 想要恢复环比,改这里 document.getElementById('kpi-yr-daily-comp').innerHTML = '（去年 '+fmtWan(LY_DAILY)+'） '+pillHtml((yrDaily - LY_DAILY)/LY_DAILY*100);
  document.getElementById('kpi-yr-daily-comp').innerHTML = '（去年 '+fmtWan(LY_DAILY)+'） ';
  document.getElementById('kpi-yr-pc').textContent = fmtWan(yrPc);
  // 想要恢复环比,改这里 document.getElementById('kpi-yr-pc-comp').innerHTML = '（去年 '+fmtWan(LY_PC)+'） '+pillHtml((yrPc - LY_PC)/LY_PC*100);
  document.getElementById('kpi-yr-pc-comp').innerHTML = '（去年 '+fmtWan(LY_PC)+'） ';
  // ======================================
  // 人工新增
  // ======================================
  // document.getElementById('tag-yr').textContent = yrMin+'年';
  document.getElementById('yr-days-details').innerHTML = yrMin + '年 <span style="margin:0 6px;color:#9CA3AF">·</span> 已过<b>' + yrDays + '</b>天 <span style="margin:0 6px;color:#9CA3AF">·</span> 进度<b>'+dayPercent+'%</b>';
  
  var latest = CENTER_MONTHS[CENTER_MONTHS.length - 1];
  var prev = CENTER_MONTHS.length >= 2 ? CENTER_MONTHS[CENTER_MONTHS.length - 2] : null;
  // ======================================
  // 人工新增
  // ======================================
  // document.getElementById('mo-days').innerHTML = '当月 <b>'+dayMax+'</b> 天';
  // document.getElementById('mo-day-pct').innerHTML = '时间进度  <b>' + dayPercentInMonth + '%</b>';
  
  
  document.getElementById('kpi-mo-daily').textContent = fmtWan(latest['日均消耗']);
  document.getElementById('kpi-mo-pc').textContent = fmtWan(latest['人均日耗']);
  // ======================================
  // 人工新增
  // ======================================  
  // document.getElementById('tag-mo').textContent = latest['月'];
  document.getElementById('mo-days-details').innerHTML = latest['月'] + '<span style="margin:0 6px;color:#9CA3AF">·</span> 已过<b>' + dayMax + '</b>天 <span style="margin:0 6px;color:#9CA3AF">·</span> 进度<b>'+dayPercentInMonth+'%</b>';

  if (prev) {
    var moPctDaily = (latest['日均消耗'] - prev['日均消耗']) / prev['日均消耗'] * 100;
    var moPctPc = (latest['人均日耗'] - prev['人均日耗']) / prev['人均日耗'] * 100;
    document.getElementById('kpi-mo-daily-comp').innerHTML = '（上月 '+fmtWan(prev['日均消耗'])+'） '+pillHtml(moPctDaily);
    document.getElementById('kpi-mo-pc-comp').innerHTML = '（上月 '+fmtWan(prev['人均日耗'])+'） '+pillHtml(moPctPc);
  } else {
    document.getElementById('kpi-mo-daily-comp').innerHTML = '<span style="color:#9CA3AF">无上月数据</span>';
    document.getElementById('kpi-mo-pc-comp').innerHTML    = '<span style="color:#9CA3AF">无上月数据</span>';
  }
})();

// ═══════════════════════════════════════════════════════════
// 年度媒体消耗占比实心饼图（左图右文）
// ═══════════════════════════════════════════════════════════
(function(){
  var MCL = {'头条':'#16A34A','小红书':'#E85D75','快手':'#F59E0B','百度':'#2563EB','腾讯':'#0EA5A4','阿里UDS':'#64748B'};
  var box = document.getElementById('center-media-ratio');
  if (!box || !CENTER_YEAR_MEDIA || CENTER_YEAR_MEDIA.length === 0) return;

  var validData = CENTER_YEAR_MEDIA.filter(function(m){ return m.pct > 0; });

  var legendRows = validData.map(function(m){
    var clr = MCL[m.media] || '#6B7280';
    var cost = m.cost;
    var shareText = typeof m.pct === 'number' && isFinite(m.pct) ? m.pct.toFixed(1) + '%' : (Number(m.pct || 0).toFixed(1) + '%');
    var hasTarget = !!m.has_target && m.target > 0;
    var finishRate = hasTarget && typeof m.completion_pct === 'number' ? m.completion_pct : 0;
    var barPercent = hasTarget ? Math.min(finishRate, 100).toFixed(1) : '0.0';
    var progressText = hasTarget ? (finishRate.toFixed(1) + '%') : '待定';

    return '<div class="media-ratio-row">'
      + '<span class="media-ratio-dot" style="--media-color:'+clr+'"></span>'
      + '<span class="media-ratio-name">'+m.media+'</span>'
      + '<span class="media-ratio-pct">'+shareText+'</span>'
      + '<div class="media-ratio-meta">'
        + '<div class="media-ratio-meta-row">'
          + '<span class="media-ratio-cost">'+(cost/10000).toFixed(1)+'万</span>'
          + '<span class="media-ratio-progress-text">完成进度：'+progressText+'</span>'
        + '</div>'
        + '<div class="media-ratio-track">'
          + '<div class="media-ratio-fill" style="--w:'+barPercent+'%;--media-color:'+clr+'"></div>'
        + '</div>'
      + '</div>'
    + '</div>';
  }).join('');

  box.innerHTML = '<div class="media-ratio-title"><span></span>年度媒体消耗占比</div>'
    + '<div class="media-ratio-shell">'
    + '<div id="media-pie-chart" class="media-ratio-pie"></div>'
    + '<div class="media-ratio-legend">' + legendRows + '</div>'
    + '</div>';

  var pieData = validData.map(function(m){
    return {
      name: m.media,
      value: m.cost,
      itemStyle: {
        color: MCL[m.media] || '#6B7280',
        borderWidth: 2,
        borderColor: '#ffffff'
      }
    };
  });

  var pieChart = echarts.init(document.getElementById('media-pie-chart'));
  pieChart.setOption({
    tooltip: {
      trigger: 'item',
      backgroundColor: '#fff',
      borderColor: '#E5E7EB',
      borderWidth: 1,
      padding: [8, 12],
      textStyle: { color: '#374151', fontSize: 12 },
      formatter: function(p){
        return '<b style="color:'+p.color+'">● </b><b>' + p.name + '</b>'
          + '<br/><span style="color:#9CA3AF">消耗</span> <b>' + (p.value/10000).toFixed(1) + '万</b>'
          + '&nbsp;&nbsp;<span style="color:#9CA3AF">占比</span> <b>' + p.percent + '%</b>';
      }
    },
    series: [{
      type: 'pie',
      radius: '80%',
      center: ['50%', '50%'],
      avoidLabelOverlap: true,
      label: { show: false },
      emphasis: {
        scale: true,
        scaleSize: 6,
        itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0,0,0,.15)' }
      },
      data: pieData
    }]
  });

  window.addEventListener('resize', function(){ pieChart.resize(); });
})();

// ═══════════════════════════════════════════════════════════
// 汇报视角概览（对照版）：年度指标 → 年度媒体 → 月度指标
// ═══════════════════════════════════════════════════════════
(function(){
  var box = document.getElementById('report-flow-overview');
  var year = REPORT_FLOW_OVERVIEW.year || {};
  var month = REPORT_FLOW_OVERVIEW.month || {};
  if (!box || !year.cost || !month.month) return;

  function progressBar(v, color) {
    var pct = typeof v === 'number' && isFinite(v) ? Math.max(0, Math.min(v, 100)) : 0;
    return '<div class="rf-progress"><div class="rf-progress-fill" style="--w:'+pct.toFixed(1)+'%;--bar-color:'+color+'"></div></div>';
  }
  function mediaForecastHtml(m) {
    if (typeof m.forecast !== 'number' || typeof m.forecast_pct !== 'number' || typeof m.forecast_gap !== 'number') {
      return '';
    }
    var gapText = m.forecast_gap >= 0 ? '预计超目标 ' + fmtWan(m.forecast_gap) : '预计差额 ' + fmtWan(Math.abs(m.forecast_gap));
    return '<div class="rf-media-forecast">'
      + '<span>预计达成 <b>'+fmtWan(m.forecast)+'</b></span>'
      + '<span>预计完成率 <b>'+m.forecast_pct.toFixed(1)+'%</b></span>'
      + '<span>'+gapText+'</span>'
    + '</div>';
  }

  var mediaRows = (CENTER_YEAR_MEDIA || []).filter(function(m){
    return m.pct > 0 && m.has_target && m.target > 0;
  }).map(function(m){
    var clr = MCOLORS[m.media] || '#64748B';
    var finish = typeof m.completion_pct === 'number' ? m.completion_pct : 0;
    return '<div class="rf-media-card" style="--media-color:'+clr+'">'
      + '<div class="rf-media-card-head">'
        + '<div><span class="rf-media-dot"></span><strong>'+m.media+'</strong></div>'
        + '<b>'+finish.toFixed(1)+'%</b>'
      + '</div>'
      + '<div class="rf-media-actual">'
        + '<span>实际 '+fmtWan(m.cost)+'</span>'
        + '<span>目标 '+fmtWan(m.target)+'</span>'
      + '</div>'
      + progressBar(finish, clr)
      + mediaForecastHtml(m)
    + '</div>';
  }).join('');

  box.innerHTML = '<div class="rf-head">'
    + '<div><div class="rf-kicker">汇报视角对照版</div><h3>年度指标 → 年度媒体 → 月度指标</h3></div>'
    + '<span>数据截至 '+(REPORT_FLOW_OVERVIEW.date || '-')+'</span>'
  + '</div>'
    + '<div class="rf-grid">'
      + '<section class="rf-block rf-year">'
        + '<div class="rf-block-title"><span>1. 年度指标</span></div>'
        + goalProgressCard({theme:'goal-progress-blue', targetLabel:'年目标', target:fmtWan(year.target), costLabel:'年度消耗', cost:fmtWan(year.cost), completionPct:year.completion_pct, forecastPct:year.forecast_pct, forecast:fmtWan(year.forecast), forecastGap:year.forecast_gap})
        + '<div class="rf-eff-strip">'
        + '<span>月均 <b>'+fmtWan(year.monthly_avg)+'</b></span>'
        + '<span>日均 <b>'+fmtWan(year.daily_cost)+'</b></span>'
          + '<span>人均 <b>'+fmtWan(year.pc)+'</b></span>'
          + '</div>'
      + '</section>'
    + '<section class="rf-block rf-media">'
      + '<div class="rf-block-title">3. 年度媒体目标进度</div>'
      + '<div class="rf-media-list">'+(mediaRows || '<div class="rf-empty">暂无媒体目标数据</div>')+'</div>'
      + '</section>'
      + '<section class="rf-block rf-month">'
        + '<div class="rf-block-title"><span>2. 月度指标</span></div>'
        + goalProgressCard({theme:'goal-progress-orange', targetLabel:'月目标', target:fmtWan(month.target), costLabel:'月度消耗', cost:fmtWan(month.cost), completionPct:month.completion_pct, forecastPct:month.forecast_pct, forecast:fmtWan(month.forecast), forecastGap:month.forecast_gap})
        + '<div class="rf-eff-strip">'
        + '<span>日均 <b>'+fmtWan(month.daily_cost)+'</b></span>'
        + '<span>人均 <b>'+fmtWan(month.pc)+'</b></span>'
          + '</div>'
      + '</section>'
  + '</div>';
})();

// ═══════════════════════════════════════════════════════════
// 媒体汇总（动态生成 MEDIA_SMRY）
// ═══════════════════════════════════════════════════════════
var MEDIA_SMRY = {};
(function(){
  var grandTotal = 0;
  for (var m in MEDIA_DATA) {
    var t = 0;
    for (var i=0;i<MEDIA_DATA[m].length;i++) t += MEDIA_DATA[m][i]['消耗'];
    MEDIA_SMRY[m] = {total: t};
    grandTotal += t;
  }
  for (var m in MEDIA_SMRY) MEDIA_SMRY[m].pct = MEDIA_SMRY[m].total / grandTotal * 100;
})();

// 媒体按钮 & 媒体汇总表
(function(){
  var btnBox = document.getElementById('media-btns');
  var MEDIA_ORDER = ['腾讯','小红书','头条','快手','百度','阿里UDS'];
  var btns = [{key:'all',label:'全部媒体',pct:'全部'}];
  for(var mi=0;mi<MEDIA_ORDER.length;mi++){
    var m = MEDIA_ORDER[mi];
    if(MEDIA_SMRY[m]) btns.push({key:m, label:m, pct:MEDIA_SMRY[m].pct.toFixed(1)+'%'});
  }
  // 补充不在固定顺序中的媒体
  for(var m in MEDIA_SMRY){
    if(MEDIA_ORDER.indexOf(m)===-1) btns.push({key:m, label:m, pct:MEDIA_SMRY[m].pct.toFixed(1)+'%'});
  }
  var html = '';
  for(var i=0;i<btns.length;i++){
    var b=btns[i], active=i===0?' active':'';
    html += '<button class="media-btn'+active+'" data-media="'+b.key+'" onclick="switchMedia(this)">'+b.label+'<span class="pct">'+b.pct+'</span></button>';
  }
  btnBox.innerHTML = html;

  var tbody = document.getElementById('media-tbody');
  var rowHtml = '';
  for(var m in MEDIA_SMRY){
    var s = MEDIA_SMRY[m];
    var c = MCOLORS[m] || '#6B7280';
    var pct = s.pct.toFixed(1);
    var barW = Math.max(s.pct, 0.5);
    rowHtml += '<tr><td><span class="media-dot" style="background:'+c+'"></span>'+m+'</td>'
      +'<td class="num bold">'+fmtWan(s.total)+'</td>'
      +'<td class="num">'+pct+'%</td>'
      +'<td class="bar-cell"><div class="bar-inner"><div class="bar-fill" style="width:'+barW+'%;background:'+c+'"></div></div></td></tr>';
  }
  tbody.innerHTML = rowHtml;
})();

// ═══════════════════════════════════════════════════════════
// 趋势图
// ═══════════════════════════════════════════════════════════
var mainChart = echarts.init(document.getElementById('mainChart'));
var curMedia = 'all';
var curMonth = '';

function buildMainOption(media) {
  var allData = getDArr(media);
  var data = filterByMonth(allData, curMonth);
  var c = media === 'all' ? '#1A56DB' : (MCOLORS[media] || '#6B7280');
  var name = media === 'all' ? '总消耗' : media;

  // 找峰值和谷值（手动定位坐标，避免 markPoint type 的 value 问题）
  var maxVal = -Infinity, maxIdx = 0, minVal = Infinity, minIdx = 0;
  for (var i=0; i<data.length; i++) {
    var v = data[i]['消耗'];
    if (v > maxVal) { maxVal = v; maxIdx = i; }
    if (v < minVal) { minVal = v; minIdx = i; }
  }

  var markPoints = [];
  if (data.length > 0) {
    var maxVW = (maxVal/10000).toFixed(1);
    var minVW = (minVal/10000).toFixed(1);
    var maxDate = data[maxIdx]['日期'];
    var minDate = data[minIdx]['日期'];
    // 用UTC解析避免时区偏移导致错位
    var maxTS = Date.UTC(parseInt(maxDate.substr(0,4)), parseInt(maxDate.substr(5,2))-1, parseInt(maxDate.substr(8,2)));
    var minTS = Date.UTC(parseInt(minDate.substr(0,4)), parseInt(minDate.substr(5,2))-1, parseInt(minDate.substr(8,2)));
    if (maxIdx !== minIdx) {
      markPoints.push({coord: [maxTS, maxVal/10000], value: maxVW+'万', name: '峰值', symbol:'pin', symbolSize:60, itemStyle:{color:'#DC2626'}, label:{fontSize:9,color:'#fff',formatter:'{c}'}});
      markPoints.push({coord: [minTS, minVal/10000], value: minVW+'万', name: '谷值', symbol:'pin', symbolSize:60, itemStyle:{color:'#059669'}, label:{fontSize:9,color:'#fff',formatter:'{c}'}});
    } else {
      markPoints.push({coord: [maxTS, maxVal/10000], value: maxVW+'万', name: '峰值', symbol:'pin', symbolSize:60, itemStyle:{color:'#DC2626'}, label:{fontSize:9,color:'#fff',formatter:'{c}'}});
    }
  }

  var seriesData = data.map(function(d){
    var ds = d['日期'];
    var ts = Date.UTC(parseInt(ds.substr(0,4)), parseInt(ds.substr(5,2))-1, parseInt(ds.substr(8,2)));
    return [ts, d['消耗']/10000];
  });

  // 预构建日期→TOP3品牌的映射（运营部门+媒体+品牌聚合）
  var dateTop3Map = {};
  for (var bi=0; bi<BRAND_DATA.length; bi++) {
    var bd = BRAND_DATA[bi];
    // 媒体筛选
    if (curMedia !== 'all' && bd['媒体'] !== curMedia) continue;
    var key = bd['日期'];
    if (!dateTop3Map[key]) dateTop3Map[key] = [];
    dateTop3Map[key].push({dept: bd['运营部门'], media: bd['媒体'], brand: bd['品牌名称'], cost: bd['消耗']});
  }
  // 对每个日期按消耗排序取TOP3
  for (var dk in dateTop3Map) {
    dateTop3Map[dk].sort(function(a,b){return b.cost - a.cost;});
    dateTop3Map[dk] = dateTop3Map[dk].slice(0,3);
  }

  return {
    tooltip: {trigger:'axis', formatter: function(p){
      var fullDate = p[0].axisValue;
      // axisValue在time类型xAxis下可能是Date对象，转为字符串
      if (typeof fullDate !== 'string') {
        var dd = new Date(fullDate);
        fullDate = dd.getFullYear()+'-'+(''+(dd.getMonth()+1)).padStart(2,'0')+'-'+(''+dd.getDate()).padStart(2,'0');
      }
      var parts = fullDate.split('-');
      var ds = "日期: " + parts[1] + '-' + parts[2];
      var html = '<div style="font-size:12px;display:flex;align-items:baseline;gap:8px;margin-bottom:2px">'
        +'<span style="font-weight:700">'+ds+'</span>'
        +'<span><b>'+p[0].value[1].toFixed(1)+'万</b></span>'
        +'</div>';
      var top3 = dateTop3Map[fullDate];
      if (top3 && top3.length > 0) {
        html += '<div style="border-top:1px solid #F3F4F6;margin:6px 0 4px;padding-top:4px;font-size:11px;color:#9CA3AF">当日 TOP3 品牌</div>';
        var medalColors = ['#FFD700','#C0C0C0','#CD7F32'];
        var medalTextColors = ['#92400E','#374151','#fff'];
        for (var ti=0; ti<top3.length; ti++) {
          var t = top3[ti];
          html += '<div style="display:flex;align-items:center;gap:6px;padding:3px 0;font-size:11px">'
            +'<span style="display:inline-block;width:14px;height:14px;border-radius:50%;background:'+medalColors[ti]+';color:'+medalTextColors[ti]+';font-size:9px;font-weight:700;text-align:center;line-height:14px">'+(ti+1)+'</span>'
            +'<span style="color:#374151;font-weight:600">'+t.brand+'</span>'
            +'<span style="color:#9CA3AF;font-size:10px">'+t.dept+' / '+t.media+'</span>'
            +'<span style="margin-left:auto;color:#374151;font-weight:600">'+(t.cost/10000).toFixed(1)+'万</span>'
            +'</div>';
        }
      }
      return html;
    }},
    grid: {top:50, right:19, bottom:24, left:40, containLabel:false},
    xAxis: {type:'time', axisLine:{lineStyle:{color:'#E5E7EB'}}, splitLine:{show:false},
            axisLabel:{color:'#9CA3AF', fontSize:10, rotate: data.length>60?30:0, formatter:'{MM}-{dd}'}},
    yAxis: {type:'value', axisLine:{show:false}, splitLine:{lineStyle:{color:'#F3F4F6'}},
            axisLabel:{color:'#9CA3AF', fontSize:10, formatter:function(v){return Math.round(v)+'万';}}},
    series: [{
      name: name, type: 'line', smooth: true, data: seriesData,
      lineStyle: {color: c, width: 2},
      itemStyle: {color: c},
      areaStyle: {color: new echarts.graphic.LinearGradient(0,0,0,1,[
        {offset:0, color: media==='all' ? 'rgba(26,86,219,0.25)' : c+'40'},
        {offset:1, color: media==='all' ? 'rgba(26,86,219,0)' : c+'00'}
      ])},
      symbol: 'circle', symbolSize: 4, showSymbol: false,
      emphasis: {showSymbol: true, symbolSize: 6},
      markPoint: {data: markPoints, animation: true}
    }],
  };
}

function switchMedia(btn) {
  var btns = document.querySelectorAll('.media-btn');
  for (var i=0;i<btns.length;i++){btns[i].classList.remove('active');}
  btn.classList.add('active');
  curMedia = btn.dataset.media;
  mainChart.setOption(buildMainOption(curMedia), true);
  updateMediaPcts();
  updateTopBrands();
}

function switchMonth(btn) {
  var btns = document.querySelectorAll('.mo-filter-btn');
  for (var i=0;i<btns.length;i++){btns[i].classList.remove('active');}
  btn.classList.add('active');
  curMonth = btn.dataset.month;
  mainChart.setOption(buildMainOption(curMedia), true);
  updateMediaPcts();
  updateTopBrands();
}

function updateMediaPcts() {
  var totals = {};
  var grandTotal = 0;
  for (var m in MEDIA_DATA) {
    var filtered = filterByMonth(MEDIA_DATA[m], curMonth);
    var t = 0;
    for (var i=0;i<filtered.length;i++) t += filtered[i]['消耗'];
    totals[m] = t;
    grandTotal += t;
  }
  var btns = document.querySelectorAll('.media-btn');
  for (var i=0;i<btns.length;i++){
    var pctSpan = btns[i].querySelector('.pct');
    if (!pctSpan) continue;
    var key = btns[i].dataset.media;
    if (key === 'all') {
      pctSpan.textContent = curMonth ? '筛选中' : '全部';
    } else {
      var pct = grandTotal > 0 ? (totals[key] / grandTotal * 100) : 0;
      pctSpan.textContent = pct.toFixed(1) + '%';
    }
  }
}

// ═══════════════════════════════════════════════════════════
// TOP5 品牌排行（联动媒体 + 月份）
// ═══════════════════════════════════════════════════════════
function updateTopBrands() {
  var filtered = BRAND_DATA.filter(function(d) {
    if (curMedia !== 'all' && d['媒体'] !== curMedia) return false;
    if (curMonth) {
      var prefix = RAW_TREND[0]['日期'].substring(0,4) + '-' + curMonth;
      if (d['日期'].substring(0,7) !== prefix) return false;
    }
    return true;
  });
  // 按品牌+媒体聚合
  var brandMediaMap = {};
  var grandTotal = 0;
  for (var i=0; i<filtered.length; i++) {
    var b = filtered[i]['品牌名称'];
    var m = filtered[i]['媒体'];
    var key = b + '||' + m;
    if (!brandMediaMap[key]) brandMediaMap[key] = {name: b, media: m, cost: 0};
    brandMediaMap[key].cost += filtered[i]['消耗'];
    grandTotal += filtered[i]['消耗'];
  }
  // 排序取TOP5
  var arr = [];
  for (var k in brandMediaMap) arr.push(brandMediaMap[k]);
  arr.sort(function(a,b){ return b.cost - a.cost; });
  var top5 = arr.slice(0, 5);

  var html = '';
  var rankColors = ['#FFD700','#C0C0C0','#CD7F32','#9CA3AF','#9CA3AF'];
  var rankTextColors = ['#92400E','#374151','#fff','#fff','#fff'];
  for (var i=0; i<top5.length; i++) {
    var costW = (top5[i].cost / 10000).toFixed(1);
    var pct = grandTotal > 0 ? (top5[i].cost / grandTotal * 100).toFixed(1) : '0.0';
    html += '<li class="top3-item">'
      +'<div class="top3-rank" style="background:'+rankColors[i]+';color:'+rankTextColors[i]+'">'+(i+1)+'</div>'
      +'<div class="top3-info">'
      +'<span class="top3-dept">'+top5[i].name+'</span>'
      +'<span class="top3-media">'+top5[i].media+'</span>'
      +'</div>'
      +'<div class="top3-right">'
      +'<span class="top3-cost">'+costW+'万</span>'
      +'<span class="top3-pct">('+pct+'%)</span>'
      +'</div>'
      +'</li>';
  }
  if (top5.length === 0) {
    html = '<li style="color:#9CA3AF;text-align:center;padding:20px 0">无数据</li>';
  }
  document.getElementById('top3List').innerHTML = html;
}

// ═══════════════════════════════════════════════════════════
// 月份筛选按钮
// ═══════════════════════════════════════════════════════════
(function(){
  var months = {};
  for (var i=0; i<RAW_TREND.length; i++) {
    var m = RAW_TREND[i]['日期'].substring(5,7);
    months[m] = true;
  }
  var keys = Object.keys(months);
  keys.sort();
  var box = document.getElementById('trend-month-btns');
  var html = '<button class="mo-filter-btn active" data-month="" onclick="switchMonth(this)">全部</button>';
  for (var i=0; i<keys.length; i++) {
    html += '<button class="mo-filter-btn" data-month="'+keys[i]+'" onclick="switchMonth(this)">'+parseInt(keys[i])+'月</button>';
  }
  box.innerHTML = html;
})();

// 初始化
mainChart.setOption(buildMainOption('all'));
updateTopBrands();
window.addEventListener('resize', function(){ mainChart.resize(); });


// ═══════════════════════════════════════════════════════════
// 当月指标达成（表格 + 媒体消耗占比条）
// ═══════════════════════════════════════════════════════════
(function(){
  // 媒体颜色映射
  var MC = {'头条':'#16A34A','小红书':'#E85D75','快手':'#F59E0B','百度':'#2563EB','腾讯':'#0EA5A4','阿里UDS':'#64748B'}; 
  var mediaList = MONTH_MEDIA_LIST;
  var TEMP_HIDE_MONTH_GOAL_BOARD = true;

  // 按 DEPT_KEYS 固定顺序排列
  var ORDER = ['K部门','K2','K3','K4','K7','K4-品商','品策-小红书'];
  var deptMap = {};
  for (var i=0; i<MONTH_TARGET.length; i++) {
    deptMap[MONTH_TARGET[i].dept] = MONTH_TARGET[i];
  }
  
  // 迷你条 HTML 生成
  function miniBar(val, maxVal, color) {
    var pct = Math.max(val / maxVal * 100, 2);
    return '<div style="height:4px;border-radius:2px;background:#F3F4F6;margin-top:3px"><div style="height:100%;border-radius:2px;width:'+pct.toFixed(1)+'%;background:'+color+'"></div></div>';
  }

  var box = document.getElementById('month-target');

  // ROI映射 — 取DEPT_MONTHLY_ROI中最新月份的ROI
  var roiMap = {};
  var latestRoiMonth = 0;
  for (var dept in DEPT_MONTHLY_ROI) {
    if (ROI_HIDDEN_DEPTS[dept]) continue;
    var arr = DEPT_MONTHLY_ROI[dept];
    if (arr.length > 0) {
      var last = arr[arr.length - 1];
      roiMap[dept] = last.roi;
      if (last.month > latestRoiMonth) latestRoiMonth = last.month;
    }
  }
  var roiMonthLabel = latestRoiMonth > 0 ? latestRoiMonth + '月预估ROI' : '预估ROI';

  // ── 部门卡片行：当月消耗 + 当月ROI + 目标完成率 ──
  var DC = {'K2':'#4F6BED','K3':'#D97706','K4':'#0F9D7A','K4-品商':'#2563EB','K7':'#7C8F2A','品策-小红书':'#7C6A9A','K部门':'#F97316'};

  function fmtGoalAmount(val) {
    var wan = val / 10000;
    return wan >= 10000 ? (wan / 10000).toFixed(1) + '亿' : wan.toFixed(1) + '万';
  }

  function getMonthTimePct() {
    if (!RAW_TREND.length) return 0;
    var lastDate = new Date(RAW_TREND[RAW_TREND.length - 1]['日期']);
    var daysInMonth = new Date(lastDate.getFullYear(), lastDate.getMonth() + 1, 0).getDate();
    return daysInMonth ? Math.max(0, Math.min(lastDate.getDate() / daysInMonth * 100, 100)) : 0;
  }

  var monthTimePct = getMonthTimePct();
  var monthTimeText = monthTimePct.toFixed(1) + '%';

  // 生成单个部门卡片HTML
  function deptCard(dept, cost, roi, clr, showRoi, roiLabel, target, hasTarget, completionPct, timePct) {
    var costWan = (cost / 10000).toFixed(1);
    var pctValue = hasTarget && typeof completionPct === 'number' ? completionPct : 0;
    var pct = Math.min(pctValue, 100).toFixed(1);
    var timeWidth = Math.max(0, Math.min(timePct || 0, 100)).toFixed(1);
    var pctColor = pct >= 100 ? '#059669' : '#1A56DB';
    var pctBarColor = pct >= 100 ? '#059669' : clr;
    var roiText = (showRoi && roi > 0) ? roi.toFixed(2) : '--';
    var goalLabel = hasTarget ? ('月目标：' + fmtGoalAmount(target)) : '月目标：待定';
    var goalPctText = hasTarget ? (pctValue.toFixed(1) + '%') : '';
    return '<div class="mt-dept-card" style="--dept-color:'+clr+';--bar-color:'+pctBarColor+';--pct-color:'+pctColor+';--w:'+pct+'%;--time-w:'+timeWidth+'%">'
	  + '<div class="mt-dept-head">'
      + '<div class="mt-dept-mark"></div>'
      + '<span class="mt-dept-name">'+dept+'</span>'
      + '</div>'
      + '<div class="mt-dept-cost">'+costWan+'<span>万</span></div>'
      + '<div class="mt-dept-roi">'+roiLabel+' <span>'+roiText+'</span></div>'
      + '<div class="mt-goal-label">'+goalLabel+'</div>'
      + '<div class="mt-goal-row">'
      + '<div class="mt-goal-track">'
      + '<div class="mt-goal-fill"></div>'
      + '</div>'
      + '<span class="mt-goal-pct">'+goalPctText+'</span>'
      + '</div>'
      + '</div>';
  }

  // 所有子部门卡片一行展示
  var subOrder = ['K2','K3','K4','K7','K4-品商','品策-小红书'];
  var cardsHtml = '<div class="mt-card-panel">'
    + '<div class="mt-card-panel-head">'
      + '<div class="panel-kicker"><span></span>当月指标达成</div>'
      + '<div class="mt-goal-legend">'
        + '<span><i class="mt-legend-actual"></i>实际进度</span>'
        + '<span><i class="mt-legend-time" style="--time-w:'+monthTimePct.toFixed(1)+'%"></i>时间进度 '+monthTimeText+'</span>'
      + '</div>'
    + '</div>'
    + '<div class="mt-card-row">';
  for (var si=0; si<subOrder.length; si++) {
    var sd = deptMap[subOrder[si]];
    if (!sd) continue;
    var sRoi = roiMap[subOrder[si]] || 0;
    cardsHtml += deptCard(subOrder[si], sd.cost, sRoi, DC[subOrder[si]], !ROI_HIDDEN_DEPTS[subOrder[si]], roiMonthLabel, sd.target || 0, !!sd.has_target, sd.completion_pct, monthTimePct);
  }
  cardsHtml += '</div>';
  
  // 构建部门→人均品牌数/人均账户数/户均日耗的映射
  var brandPcMap = {}, acctPcMap = {}, acctDailyMap = {};
  for (var bi=0; bi<MONTH_DEPT_BRAND_PC.length; bi++) brandPcMap[MONTH_DEPT_BRAND_PC[bi].dept] = MONTH_DEPT_BRAND_PC[bi].val;
  for (var ai=0; ai<MONTH_DEPT_ACCT_PC.length; ai++) acctPcMap[MONTH_DEPT_ACCT_PC[ai].dept] = MONTH_DEPT_ACCT_PC[ai].val;
  for (var di=0; di<MONTH_DEPT_ACCT_DAILY.length; di++) acctDailyMap[MONTH_DEPT_ACCT_DAILY[di].dept] = MONTH_DEPT_ACCT_DAILY[di].val;

  // 求三个指标的各列最大值（用于迷你条宽度百分比）
  var maxBPC = 0, maxAPC = 0, maxAD = 0;
  for (var bi=0; bi<MONTH_DEPT_BRAND_PC.length; bi++) if (MONTH_DEPT_BRAND_PC[bi].val > maxBPC) maxBPC = MONTH_DEPT_BRAND_PC[bi].val;
  for (var ai=0; ai<MONTH_DEPT_ACCT_PC.length; ai++) if (MONTH_DEPT_ACCT_PC[ai].val > maxAPC) maxAPC = MONTH_DEPT_ACCT_PC[ai].val;
  for (var di=0; di<MONTH_DEPT_ACCT_DAILY.length; di++) if (MONTH_DEPT_ACCT_DAILY[di].val > maxAD) maxAD = MONTH_DEPT_ACCT_DAILY[di].val;
  maxBPC = maxBPC || 1; maxAPC = maxAPC || 1; maxAD = maxAD || 1;



  // 人均日耗映射 + 最大值（用于数据条）
  var pcMap = {};
  var maxPC = 0;
  for (var pi=0; pi<MONTH_DEPT_PC.length; pi++) {
    pcMap[MONTH_DEPT_PC[pi].dept] = MONTH_DEPT_PC[pi].pc;
    if (MONTH_DEPT_PC[pi].pc > maxPC) maxPC = MONTH_DEPT_PC[pi].pc;
  }
  maxPC = maxPC || 1;

  // ── 排序状态 ──
  var sortState = {key: 'pc', dir: 'desc'}; // key: pc/bpc/apc/ad, dir: asc/desc

  function sortIcon(field) {
    if (sortState.key !== field) return '<span class="sort-icon">⇅</span>';
    return sortState.dir === 'desc' ? '<span class="sort-icon-active">↓</span>' : '<span class="sort-icon-active">↑</span>';
  }

  var SORT_LABELS = {pc:'人均日耗', staff:'人效人数', bpc:'人均品牌', apc:'人均账户', ad:'户均日耗'};
  var sortHintEl = null;

  function toggleSort(field) {
    if (sortState.key === field) {
      sortState.dir = sortState.dir === 'desc' ? 'asc' : 'desc';
    } else {
      sortState.key = field;
      sortState.dir = 'desc';
    }
    renderTable();
    // 显示排序提示
    if (!sortHintEl) sortHintEl = box.querySelector('.sort-hint');
    if (sortHintEl) {
      var arrow = sortState.dir === 'desc' ? '↓ 降序' : '↑ 升序';
      sortHintEl.innerHTML = '<span class="sort-hint-text">排序依据：<b>'+(SORT_LABELS[field]||field)+'</b>　<span class="sort-hint-arrow">'+arrow+'</span>　<span class="sort-hint-close" onclick="document.querySelector(\'.sort-hint\').textContent=\'\'">✕ 关闭</span></span>';
    }
  }

  // 把排序按钮暴露到全局
  window._mtToggleSort = toggleSort;

  var sortedDepts;
  function computeSortedOrder() {
    sortedDepts = ['K部门'];
    var otherDepts = ORDER.filter(function(d){ return d !== 'K部门'; });
    var sortKey = sortState.key;
    otherDepts.sort(function(a,b){
      var va, vb;
      if (sortKey === 'pc') { va = pcMap[a]||0; vb = pcMap[b]||0; }
      else if (sortKey === 'bpc') { va = brandPcMap[a]||0; vb = brandPcMap[b]||0; }
      else if (sortKey === 'apc') { va = acctPcMap[a]||0; vb = acctPcMap[b]||0; }
      else if (sortKey === 'ad') { va = acctDailyMap[a]||0; vb = acctDailyMap[b]||0; }
      else if (sortKey === 'staff') { va = (deptMap[a]||{}).staff||0; vb = (deptMap[b]||{}).staff||0; }
      else { va = pcMap[a]||0; vb = pcMap[b]||0; }
      return sortState.dir === 'desc' ? vb - va : va - vb;
    });
    sortedDepts = sortedDepts.concat(otherDepts);
  }

  function renderTable() {
    computeSortedOrder();

    // 表头带排序按钮
    var html = '<table class="mt-table metric-table"><thead>'
      + '<tr>'
      + '<th rowspan="2">部门</th>'
      + '<th colspan="2" class="center-col sortable-head" onclick="_mtToggleSort(\'pc\')">人均日耗 '+sortIcon('pc')+'</th>'
      + '<th rowspan="2" class="center-col sortable-head" onclick="_mtToggleSort(\'bpc\')">人均品牌 '+sortIcon('bpc')+'</th>'
      + '<th rowspan="2" class="center-col sortable-head" onclick="_mtToggleSort(\'apc\')">人均账户 '+sortIcon('apc')+'</th>'
      + '<th rowspan="2" class="center-col sortable-head" onclick="_mtToggleSort(\'ad\')">户均日耗 '+sortIcon('ad')+'</th>'
      + '<th style="display:none">媒体消耗占比</th>'
      + '<th rowspan="2" class="center-col sortable-head" onclick="_mtToggleSort(\'staff\')">人效人数 '+sortIcon('staff')+'</th>'
      + '</tr>'
      + '<tr>'
      + '<th class="center-col subcol-head">条形</th>'
      + '<th class="center-col subcol-head">数值</th>'
      + '</tr>'
      + '</thead><tbody>';

    // 预计算各部门的排序值映射
    var staffMap = {};
    for (var di2=0; di2<sortedDepts.length; di2++) {
      var dd = deptMap[sortedDepts[di2]];
      staffMap[sortedDepts[di2]] = dd ? dd.staff : 0;
    }

    for (var i=0; i<sortedDepts.length; i++) {
      var dept = sortedDepts[i];
      var d = deptMap[dept];
      if (!d) continue;
      var staff = staffMap[dept] || 0;
      var bpc = brandPcMap[dept] || 0;
      var apc = acctPcMap[dept] || 0;
      var ad = acctDailyMap[dept] || 0;

      // 人均品牌数据条（条件格式）
      var bpcPct = Math.max(bpc / maxBPC * 100, 2).toFixed(1);
      var bpcBarHtml = '<div class="metric-bar metric-bar-brand" style="--w:'+bpcPct+'%">'
        + '<span>'+bpc.toFixed(1)+'</span>'
        + '</div>';

      var apcPct = Math.max(apc / maxAPC * 100, 2).toFixed(1);
      var apcBarHtml = '<div class="metric-bar metric-bar-acct" style="--w:'+apcPct+'%">'
        + '<span>'+Math.round(apc)+'</span>'
        + '</div>';

      var adPct = Math.max(ad / maxAD * 100, 2).toFixed(1);
      var adBarHtml = '<div class="metric-bar metric-bar-daily" style="--w:'+adPct+'%">'
        + '<span>'+Math.round(ad)+'</span>'
        + '</div>';

      // K部门行浅底色
      var rowClass = (dept === 'K部门') ? ' class="mt-row-k"' : '';

      // 媒体占比：按占比从高到低排序，过滤掉0%
      var sortedRatios = (d.media_ratios || []).slice().sort(function(a,b){ return b.pct - a.pct; }).filter(function(mr){ return mr.pct > 0; });

      // 媒体占比条
      var barHtml = '';
      if (sortedRatios.length > 0) {
        var labelHtml = '<div class="media-chip-row">';
        for (var j=0; j<sortedRatios.length; j++) {
          var mr = sortedRatios[j];
          var clr = MC[mr.media] || '#6B7280';
          labelHtml += '<span class="media-chip" style="--media-color:'+clr+'">'+mr.media+' '+mr.pct+'%</span>';
        }
        labelHtml += '</div>';
        barHtml = '<div class="mt-bar-row">';
        for (var j=0; j<sortedRatios.length; j++) {
          var mr = sortedRatios[j];
          var clr = MC[mr.media] || '#6B7280';
          barHtml += '<div class="mt-bar-seg" style="width:'+mr.pct+'%;background:'+clr+'" title="'+mr.media+': '+mr.pct+'%"></div>';
        }
        barHtml += '</div>' + labelHtml;
      }

      var pc = pcMap[dept] || 0;
      var pcWan = (pc / 10000).toFixed(1) + '万';
      var pcPassed = pc >= 60000;
      var pcPct = Math.max(pc / maxPC * 100, 2).toFixed(1);
      var pcClr = pcPassed ? '#059669' : '#1A56DB';

      var pcBarHtml = '<div class="mt-pc-bar">'
        + '<div class="mt-pc-track"><div class="mt-pc-fill" style="--w:'+pcPct+'%;--bar-color:'+pcClr+'"></div></div>'
        + '</div>';

      // 超过6万显示✓标记
	  // 人工备注 √标记暂时去除
      // var checkMark = pcPassed ? '<span style="color:#059669;font-size:13px;font-weight:700;margin-left:2px">✓</span>' : '';
      var pcWanWithMark = pcWan;

      html += ''
        + '<tr'+rowClass+'>'
        + '<td class="dept-cell">'+dept+'</td>'
        + '<td class="mt-cell-bar">'+pcBarHtml+'</td>'
        + '<td class="num mt-value-cell">'+pcWanWithMark+'</td>'
        + '<td class="num">'+bpcBarHtml+'</td>'
        + '<td class="num">'+apcBarHtml+'</td>'
        + '<td class="num">'+adBarHtml+'</td>'
        + '<td class="media-cell" style="display:none">'+barHtml+'</td>'
        + '<td class="num">'+staff.toFixed(1)+'</td>'
        + '</tr>';
    }

    html += '</tbody></table>';

    // 更新DOM
    var tbody = box.querySelector('.mt-table-wrap');
    if (!tbody) {
      var wrap = document.createElement('div');
      wrap.className = 'mt-table-wrap';
      box.insertBefore(wrap, box.firstChild);
      while (box.firstChild !== wrap) box.removeChild(box.firstChild);
      wrap.parentNode.insertBefore(wrap, box.firstChild);
    }
    // 找到 mt-table-wrap 或直接替换
    var tableWrap = box.querySelector('.mt-table-wrap');
    if (tableWrap) {
      tableWrap.classList.add('metric-wrap');
      tableWrap.innerHTML = html;
    }
  }

  // ── 通用HTML条形图生成函数（部门名在条上方，数值+合格标签在条内部最右侧） ──
  function buildHtmlBars(dataArr, valKey, title, colorA, colorB, failColorA, failColorB, fmtFn, passFn) {
    var sorted = dataArr.slice().sort(function(a, b) { return b[valKey] - a[valKey]; });
    var maxVal = Math.max.apply(null, sorted.map(function(x) { return x[valKey]; })) || 1;
    var result = '<div class="summary-bars-title"><span></span>' + title + '</div>';
    for (var i = 0; i < sorted.length; i++) {
      var d = sorted[i];
      var v = d[valKey];
      var w = (v / maxVal * 75).toFixed(1);
      var passed = passFn ? passFn(v) : false;
      var barClr = 'linear-gradient(90deg,' + colorA + ',' + colorB + ')';
      var valText = fmtFn(v);
      var badgeHtml = passed ? ' <span class="summary-bars-badge">合格</span>' : '';
      result += '<div class="summary-bars-item">'
        + '<div class="summary-bars-head">'
        + '<span class="summary-bars-name">' + d.dept + '</span>'
        + '</div>'
        + '<div class="summary-bars-track-wrap">'
        + '<div class="summary-bars-track" style="--bar-bg:' + barClr + ';--w:' + w + '%">'
        + '<span class="summary-bars-value">' + valText + badgeHtml + '</span>'
        + '</div>'
        + '</div>'
        + '</div>';
    }
    return result;
  }

  // ── 当月媒体消耗表格 ──────────────────────────────────────────
  var MCL2 = { '头条':'#16A34A','小红书':'#E85D75','快手':'#F59E0B','百度':'#2563EB','腾讯':'#0EA5A4','阿里UDS':'#64748B'};
  var subDepts = (typeof MONTH_MEDIA_SUB_DEPTS !== 'undefined') ? MONTH_MEDIA_SUB_DEPTS : ['K2','K3','K4','K7','K4-品商','品策-小红书'];
  var mediaRows = (typeof MONTH_MEDIA_TABLE !== 'undefined') ? MONTH_MEDIA_TABLE : [];

  var mediaTableHtml = '';
  if (mediaRows.length > 0) {
    // 表头
    mediaTableHtml += '<div class="media-distribution-panel">'
      + '<div class="panel-kicker"><span></span>当月媒体消耗分布</div>'
      + '<table class="mt-table media-distribution-table"><thead><tr>'
      + '<th>媒体</th>'
	  + '<th>运营中心消耗</th>'
      + '<th>运营中心占比</th>';
    for (var di = 0; di < subDepts.length; di++) {
      mediaTableHtml += '<th>' + subDepts[di] + '</th>';
    }
    mediaTableHtml += '</tr></thead><tbody>';

    for (var ri = 0; ri < mediaRows.length; ri++) {
      var mr = mediaRows[ri];
      var mClr = MCL2[mr.media] || '#6B7280';
      mediaTableHtml += '<tr>'
        + '<td><span class="media-label" style="--media-color:' + mClr + '"><span class="media-label-dot"></span><span class="media-label-name">' + mr.media + '</span></span></td>'
		+ '<td><span class="media-cost">' + (mr.center_cost / 10000).toFixed(1) + '万</span></td>'
        
        // 运营中心占比：颜色=媒体小方块颜色 + 全部加粗
        + '<td><span class="media-share" style="--media-color:'+ mClr +'">' + mr.center_pct + '%</span></td>';

      // 分部门占比：纯黑色 + 全部加粗
      for (var di2 = 0; di2 < subDepts.length; di2++) {
        var dPct = (mr.dept_pcts && mr.dept_pcts[subDepts[di2]] !== undefined) ? mr.dept_pcts[subDepts[di2]] : 0;
        mediaTableHtml += '<td><span class="media-dept-share">' + (dPct > 0 ? dPct + '%' : '—') + '</span></td>';
      }
      mediaTableHtml += '</tr>';
    }
    mediaTableHtml += '</tbody></table></div>';
  }

  function buildMonthGoalBoard() {
    var monthRows = [];
    var latestMonth = CENTER_MONTHS.length ? CENTER_MONTHS[CENTER_MONTHS.length - 1]['月'] : '';
    var monthProgressText = '';
    var remainingDays = 0;
    if (RAW_TREND.length > 0) {
      var lastDate = new Date(RAW_TREND[RAW_TREND.length - 1]['日期']);
      var daysInMonth = new Date(lastDate.getFullYear(), lastDate.getMonth() + 1, 0).getDate();
      var elapsedDays = lastDate.getDate();
      remainingDays = Math.max(daysInMonth - elapsedDays, 0);
      monthProgressText = '时间进度 ' + (elapsedDays / daysInMonth * 100).toFixed(1) + '%';
    }

    var monthOrder = ['K部门','K2','K3','K4','K5','K7','K4-品商','品策-小红书'];
    for (var oi = 0; oi < monthOrder.length; oi++) {
      var dept = monthOrder[oi];
      var md = deptMap[dept];
      if (!md || !md.has_target || !md.target) continue;
      var dailyCost = md.daily_cost || 0;
      var forecast = md.cost + dailyCost * remainingDays;
      var forecastPct = md.target > 0 ? forecast / md.target * 100 : null;
      var forecastGap = md.target > 0 ? forecast - md.target : null;
      monthRows.push({
        dept: dept,
        cost: md.cost || 0,
        target: md.target || 0,
        completion: typeof md.completion_pct === 'number' ? md.completion_pct : 0,
        forecast: forecast,
        forecastPct: forecastPct,
        forecastGap: forecastGap
      });
    }

    var html = '<div class="team-goal-board month-goal-board">'
      + '<div class="team-goal-title">月度消耗达成</div>'
      + '<div class="team-goal-head">'
        + '<span>部门</span><span>月度消耗</span><span class="team-goal-progress-head">月目标完成率 <em>'+monthProgressText+'</em></span><span>预计完成</span><span>预计差额</span>'
      + '</div>';
    for (var mi = 0; mi < monthRows.length; mi++) {
      var row = monthRows[mi];
      var color = DC[row.dept] || '#64748B';
      var progressWidth = Math.max(2, Math.min(row.completion, 100));
      var gapClass = row.forecastGap != null && row.forecastGap >= 0 ? 'is-positive' : 'is-negative';
      var gapText = row.forecastGap == null
        ? '待定'
        : (row.forecastGap >= 0 ? '超目标 ' + fmtWan(row.forecastGap) : '缺口 ' + fmtWan(Math.abs(row.forecastGap)));
      html += '<div class="team-goal-row '+(row.dept === 'K部门' ? 'is-kdept' : '')+'" style="--dept-color:'+color+';--w:'+progressWidth.toFixed(1)+'%">'
        + '<div class="team-goal-dept"><span class="team-goal-mark"></span><strong>'+row.dept+'</strong></div>'
        + '<div class="team-goal-cost"><b>'+fmtWan(row.cost)+'</b><span>月目标 '+fmtWan(row.target)+'</span></div>'
        + '<div class="team-goal-progress" title="完成率 '+row.completion.toFixed(1)+'%">'
          + '<div class="team-goal-track"><div class="team-goal-fill"></div></div>'
          + '<b>'+row.completion.toFixed(1)+'%</b>'
        + '</div>'
        + '<div class="team-goal-forecast '+gapClass+'"><b>'+(row.forecastPct == null ? '待定' : row.forecastPct.toFixed(1)+'%')+'</b><span>预计 '+fmtWan(row.forecast)+'</span></div>'
        + '<div class="team-goal-gap '+gapClass+'">'+gapText+'</div>'
      + '</div>';
    }
    return html + '</div>';
  }

  var metricAnalysisOpen = false;
  var activeMetricKey = 'brand_pc';
  var metricAnalysisData = (typeof WEEK_METRIC_ANALYSIS !== 'undefined') ? WEEK_METRIC_ANALYSIS : {weeks: [], metrics: []};

  function getMetricConfig(key) {
    for (var i = 0; i < metricAnalysisData.metrics.length; i++) {
      if (metricAnalysisData.metrics[i].key === key) return metricAnalysisData.metrics[i];
    }
    return metricAnalysisData.metrics.length ? metricAnalysisData.metrics[0] : null;
  }

  function fmtMetric(v, metric) {
    var n = Number(v || 0);
    if (!metric) return n.toFixed(2);
    if (metric.key === 'acct_daily') return Math.round(n).toLocaleString('zh-CN') + '元';
    if (metric.key === 'acct_pc') return n.toFixed(1);
    return n.toFixed(2);
  }

  function fmtDelta(v, metric) {
    var n = Number(v || 0);
    var sign = n > 0 ? '+' : '';
    if (metric && metric.key === 'acct_daily') return sign + Math.round(n).toLocaleString('zh-CN') + '元';
    if (metric && metric.key === 'acct_pc') return sign + n.toFixed(1);
    return sign + n.toFixed(2);
  }

  function deltaClass(v) {
    if (v > 0) return 'pos';
    if (v < 0) return 'neg';
    return 'flat';
  }

  function weekDisplayLabel(week) {
    var ranges = metricAnalysisData.week_ranges || {};
    if (ranges[week] && ranges[week].display) return week + '<br><span>' + ranges[week].display + '</span>';
    return week;
  }

  function weekRangeText(week) {
    var ranges = metricAnalysisData.week_ranges || {};
    if (ranges[week] && ranges[week].display) return week + ' ' + ranges[week].display;
    return week;
  }

  function buildWeekMetricAnalysisHtml() {
    if (!metricAnalysisData.weeks || metricAnalysisData.weeks.length < 2 || !metricAnalysisData.metrics || metricAnalysisData.metrics.length === 0) {
      return '<div class="metric-analysis-shell"><div class="metric-analysis-empty">近两周数据不足，暂不能生成波动分析。</div></div>';
    }
    var metric = getMetricConfig(activeMetricKey);
    var rows = metric ? metric.rows : [];
    var weeks = metricAnalysisData.weeks;
    var html = '<div class="metric-analysis-shell">'
      + '<div class="metric-analysis-toolbar">'
      + '<button class="metric-analysis-main-btn" onclick="_toggleWeekMetricAnalysis()">'
      + (metricAnalysisOpen ? '收起近两周指标分析' : '查看近两周指标分析')
      + '</button>'
      + '<span class="metric-analysis-range">' + weekRangeText(weeks[0]) + ' → ' + weekRangeText(weeks[1]) + '</span>'
      + '</div>';
    html += '<div class="metric-analysis-panel" style="display:' + (metricAnalysisOpen ? 'block' : 'none') + '">';
    html += '<div class="metric-tabs">';
    for (var mi = 0; mi < metricAnalysisData.metrics.length; mi++) {
      var m = metricAnalysisData.metrics[mi];
      html += '<button class="metric-tab' + (m.key === activeMetricKey ? ' active' : '') + '" onclick="_switchWeekMetric(\'' + m.key + '\')">' + m.label + '</button>';
    }
    html += '</div>';
    html += '<table class="metric-analysis-table"><thead><tr>'
      + '<th>团队</th><th class="week-head">' + weeks[0] + '<span>' + weekRangeText(weeks[0]).replace(weeks[0] + ' ', '') + '</span></th><th class="week-head">' + weeks[1] + '<span>' + weekRangeText(weeks[1]).replace(weeks[1] + ' ', '') + '</span></th><th>波动</th><th>原因判断</th><th>原因明细</th>'
      + '</tr></thead><tbody>';
    for (var ri = 0; ri < rows.length; ri++) {
      var r = rows[ri];
      var detailText = (r.details || []).join('；');
      html += '<tr>'
        + '<td class="dept-cell">' + r.dept + '</td>'
        + '<td class="num">' + fmtMetric(r.prev, metric) + '</td>'
        + '<td class="num">' + fmtMetric(r.curr, metric) + '</td>'
        + '<td class="num metric-delta ' + deltaClass(r.delta) + '">' + fmtDelta(r.delta, metric) + '</td>'
        + '<td class="reason-cell"><span class="reason-label">' + r.reason + '</span></td>'
        + '<td class="detail-cell">' + (detailText || '无明显变化') + '</td>'
        + '</tr>';
    }
    html += '</tbody></table></div></div>';
    return html;
  }

  function renderWeekMetricAnalysis() {
    var wrap = box.querySelector('.metric-analysis-shell');
    if (wrap) wrap.outerHTML = buildWeekMetricAnalysisHtml();
  }

  window._toggleWeekMetricAnalysis = function() {
    metricAnalysisOpen = !metricAnalysisOpen;
    renderWeekMetricAnalysis();
  };

  window._switchWeekMetric = function(key) {
    activeMetricKey = key;
    metricAnalysisOpen = true;
    renderWeekMetricAnalysis();
  };

  var chartsHtml = '';
  box.innerHTML = mediaTableHtml + (TEMP_HIDE_MONTH_GOAL_BOARD ? '' : buildMonthGoalBoard()) + cardsHtml + '<div class="sort-hint"></div><div class="mt-table-wrap"></div>' + buildWeekMetricAnalysisHtml() + '</div>' + chartsHtml;
  // 初始渲染表格
  renderTable();
})();

// ═══════════════════════════════════════════════════════════
// 运营中心各部门人均日耗排名（Tableau 风格条形图）
// ═══════════════════════════════════════════════════════════
(function(){
  // 顶部：各中心年度人均日耗标签
  var tagBox = document.getElementById('centerPcTags');
  var tagHtml = '';
  for (var t=0; t<CENTER_PC_DATA.length; t++) {
    var c = CENTER_PC_DATA[t];
    var isPrimaryCenter = c.center === '运营中心';
    var isPassCenter = c.pc >= 60000;
    tagHtml += '<span class="pc-ref-tag' + (isPrimaryCenter ? ' primary' : '') + (isPassCenter ? ' pass' : '') + '"><b>'+c.center+'</b><span>'+(c.pc/10000).toFixed(1)+'万</span></span>';
  }
  tagBox.innerHTML = tagHtml;

  var pcChart = echarts.init(document.getElementById('deptPcChart'));
  // 按人均日耗从大到小排序
  var hiddenPcDepts = {'K5': true, '品牌策略部-腾讯': true};
  var pcSorted = DEPT_PC_DATA.filter(function(d){ return !hiddenPcDepts[d.dept]; }).sort(function(a,b){ return b.pc - a.pc; });
  var pcNames = pcSorted.map(function(d){ return d.dept; });
  var pcValues = pcSorted.map(function(d){ return d.pc; });
  var maxPC = Math.max.apply(null, pcValues) || 100000;
  var pcMax = Math.ceil(maxPC / 10000) * 10000 + 10000;
  var pcBarData = [];
  for (var i=0; i<pcNames.length; i++) {
    var v = pcValues[i];
    var passed = v >= 60000;
    pcBarData.push({
      value: v,
      itemStyle: {
        color: passed
          ? new echarts.graphic.LinearGradient(0,0,1,0,[{offset:0,color:'#10B981'},{offset:1,color:'#047857'}])
          : new echarts.graphic.LinearGradient(0,0,1,0,[{offset:0,color:'#CBD5E1'},{offset:1,color:'#94A3B8'}]),
        borderRadius: [0,4,4,0]
      },
      label: {
        show: true, position: 'right',
        formatter: function(p){
          var val = (p.value/10000).toFixed(1) + '万';
          if (p.value >= 60000) return '{pass|' + val + '}';
          return '{normal|' + val + '}';
        },
        rich: {
          pass: {color: '#047857', fontSize: 12, fontWeight: 800},
          normal: {color: '#475467', fontSize: 12, fontWeight: 800}
        },
        distance: 6
      }
    });
  }

  pcChart.setOption({
    tooltip: {
      trigger: 'axis', axisPointer: {type: 'shadow'},
      backgroundColor: '#fff', borderColor: '#e5e7eb', borderWidth: 1,
      textStyle: {color: '#374151', fontSize: 12},
      formatter: function(p){
        var d = p[0];
        var color = d.value >= 60000 ? '#10B981' : '#3B82F6';
        return '<b style="color:#111827">'+d.name+'</b><br/>人均日耗: <b style="color:'+color+'">'+(d.value/10000).toFixed(1)+'万</b> <span style="color:#9CA3AF;font-size:11px">('+d.value.toFixed(0)+'元)</span>';
      }
    },
    grid: {top:20, right:86, bottom:12, left:92, containLabel:false},
    xAxis: {type:'value', max: pcMax, show:false},
    yAxis: {
      type:'category', data:pcNames, inverse:true,
      axisLine:{show:false}, axisTick:{show:false},
      axisLabel:{
        fontSize:12, color:'#344054', fontWeight:700,
        backgroundColor:'#F3F6FA', borderRadius:4, padding:[2,6,2,6]
      }
    },
    series: [{
      type:'bar', data:pcBarData, barMaxWidth:18
    }]
  });

  window.addEventListener('resize', function(){ pcChart.resize(); });
})();

// ═══════════════════════════════════════════════════════════
// 部门年度目标进度榜
// ═══════════════════════════════════════════════════════════
(function(){
  var box = document.getElementById('team-cards');
  var rows = [];
  var yearProgressText = '';
  var yearProgressPct = 0;
  if (RAW_TREND.length > 0) {
    var _lastDate = new Date(RAW_TREND[RAW_TREND.length - 1]['日期']);
    var _yearStart = new Date(_lastDate.getFullYear(), 0, 1);
    var _elapsedDays = Math.round((_lastDate - _yearStart) / 86400000) + 1;
    var _totalYearDays = ((_lastDate.getFullYear() % 4 === 0 && _lastDate.getFullYear() % 100 !== 0) || (_lastDate.getFullYear() % 400 === 0)) ? 366 : 365;
    yearProgressPct = _elapsedDays / _totalYearDays * 100;
    yearProgressText = '时间进度 ' + yearProgressPct.toFixed(1) + '%';
  }
  for (var i=0; i<DEPT_KEYS.length; i++) {
    var dept = DEPT_KEYS[i];
    var td = TEAM_DATA[dept];
    if (!td) continue;
    var hasTarget = !!td.has_target && td.target > 0;
    if (!hasTarget) continue;
    var rawProgress = hasTarget && typeof td.completion_pct === 'number' ? td.completion_pct : 0;
    rows.push({dept: dept, data: td, completion: rawProgress});
  }
  var html = '<div class="team-goal-board">'
    + '<div class="team-goal-title">年度消耗达成</div>'
    + '<div class="team-goal-head">'
      + '<span>部门</span><span>年度消耗</span><span class="team-goal-progress-head">年目标完成率 <span class="team-goal-legend"><i class="team-legend-actual"></i>实际进度 <i class="team-legend-time" style="--time-w:'+yearProgressPct.toFixed(1)+'%"></i>'+yearProgressText+'</span></span><span>预计完成</span><span>预计差额</span>'
    + '</div>';
  for (var ri=0; ri<rows.length; ri++) {
    var row = rows[ri];
    var dept = row.dept;
    var td = row.data;
    var color = DCOLORS[dept] || '#64748B';
    var completion = row.completion;
    var progressWidth = Math.max(2, Math.min(completion, 100));
    var forecastPct = typeof td.forecast_pct === 'number' && isFinite(td.forecast_pct) ? td.forecast_pct : null;
    var forecastGap = typeof td.forecast_gap === 'number' && isFinite(td.forecast_gap) ? td.forecast_gap : null;
    var gapClass = forecastGap != null && forecastGap >= 0 ? 'is-positive' : 'is-negative';
    var gapText = forecastGap == null
      ? '待定'
      : (forecastGap >= 0 ? '超目标 ' + fmtWan(forecastGap) : '缺口 ' + fmtWan(Math.abs(forecastGap)));
    html += '<div class="team-goal-row '+(dept === 'K部门' ? 'is-kdept' : '')+'" style="--dept-color:'+color+';--w:'+progressWidth.toFixed(1)+'%;--time-w:'+yearProgressPct.toFixed(1)+'%">'
      + '<div class="team-goal-dept"><span class="team-goal-mark"></span><strong>'+dept+'</strong></div>'
      + '<div class="team-goal-cost"><b>'+fmtWan(td.total)+'</b><span>年目标 '+fmtWan(td.target)+'</span></div>'
      + '<div class="team-goal-progress" title="完成率 '+completion.toFixed(1)+'%">'
        + '<div class="team-goal-track"><div class="team-goal-fill"></div></div>'
        + '<b>'+completion.toFixed(1)+'%</b>'
      + '</div>'
      + '<div class="team-goal-forecast '+gapClass+'"><b>'+(forecastPct == null ? '待定' : forecastPct.toFixed(1)+'%')+'</b><span>预计 '+(td.forecast ? fmtWan(td.forecast) : '待定')+'</span></div>'
      + '<div class="team-goal-gap '+gapClass+'">'+gapText+'</div>'
    + '</div>';
  }
  html += '</div>';
  box.innerHTML = html;

  // ── 年度ROI（投产比）条形图 ──
  var roiChart = echarts.init(document.getElementById('roiChart'));
  // 按ROI从大到小排序
  var roiSorted = ROI_DATA.filter(function(d){ return !ROI_HIDDEN_DEPTS[d.dept]; }).sort(function(a,b){ return b.roi - a.roi; });
  var roiNames = roiSorted.map(function(d){ return d.dept; }).reverse();
  var roiValues = roiSorted.map(function(d){ return d.roi; }).reverse();
  var maxRoi = Math.max.apply(null, roiValues) || 2;
  var roiMax = Math.ceil(maxRoi * 10) / 10 + 0.5;

  roiChart.setOption({
    tooltip: {
      trigger: 'axis', axisPointer: {type: 'shadow'},
      backgroundColor: '#fff', borderColor: '#e5e7eb', borderWidth: 1,
      textStyle: {color: '#374151', fontSize: 12},
      formatter: function(p){
        var d = p[0];
        return '<b style="color:#111827">'+d.name+'</b><br/>投产比: <b style="color:#059669">'+d.value.toFixed(2)+'</b>';
      }
    },
    grid: {top:48, right:80, bottom:12, left:80, containLabel:false},
    xAxis: {type:'value', max: roiMax, show:false},
    yAxis: {
      type:'category', data:roiNames,
      axisLine:{show:false}, axisTick:{show:false},
      axisLabel:{
        fontSize:12, color:'#374151', fontWeight:700,
        backgroundColor:'#F3F4F6', borderRadius:4, padding:[2,6,2,6]
      }
    },
    series: [{
      type:'bar', data:roiValues, barMaxWidth:18,
      itemStyle: {
        color: new echarts.graphic.LinearGradient(0,0,1,0,[
          {offset:0, color:'#FBBF24'},
          {offset:1, color:'#D97706'}
        ]),
        borderRadius: [0,4,4,0]
      },
      label: {
        show: true, position: 'insideRight',
        formatter: function(p){ return p.value.toFixed(2); },
        color: '#fff', fontSize: 12, fontWeight: 700
      }
    }]
  });

  window.addEventListener('resize', function(){ roiChart.resize(); });
})();

// ═══════════════════════════════════════════════════════════
// 周度消耗波动
// ═══════════════════════════════════════════════════════════
(function(){
  var MC = {'头条':'#16A34A','小红书':'#E85D75','快手':'#F59E0B','百度':'#2563EB','腾讯':'#0EA5A4','阿里UDS':'#64748B'};
  var DC = {'K2':'#4F6BED','K3':'#D97706','K4':'#0F9D7A','K4-品商':'#2563EB','K7':'#7C8F2A','品策-小红书':'#7C6A9A'};

  // 显示周范围
  if (WEEKLY_DEPT_AVG.length > 0) {
    var ws = WEEKLY_DEPT_AVG[0].weeks;
    document.getElementById('weekly-range').textContent = ws[0].range + ' ~ ' + ws[3].range;
  }

  // ── 左侧：项目环比异动列表 ──
  var alertBox = document.getElementById('weekly-proj-alert');
  if (WEEKLY_PROJ_ALERT.length === 0) {
    alertBox.innerHTML = '<div style="text-align:center;color:#9CA3AF;padding:40px 0;font-size:12px">暂无显著异动项目</div>';
  } else {
    // 按部门分组
    var byDept = {};
    for (var i=0; i<WEEKLY_PROJ_ALERT.length; i++) {
      var a = WEEKLY_PROJ_ALERT[i];
      if (!byDept[a.dept]) byDept[a.dept] = [];
      byDept[a.dept].push(a);
    }
    var html = '';
    for (var dept in byDept) {
      var clr = DC[dept] || '#6B7280';
      html += '<div style="margin-bottom:14px">';
      html += '<div style="display:flex;align-items:center;gap:6px;margin-bottom:8px">';
      html += '<div style="width:4px;height:14px;border-radius:2px;background:'+clr+'"></div>';
      html += '<span style="font-size:12px;font-weight:700;color:#374151">'+dept+'</span>';
      html += '<span style="font-size:10px;color:#9CA3AF">'+byDept[dept].length+'项</span>';
      html += '</div>';
      for (var j=0; j<byDept[dept].length; j++) {
        var p = byDept[dept][j];
        // 提取媒体名
        var mediaName = p.label.split(' \u00b7 ')[0] || '';
        var mediaClr = MC[mediaName] || '#6B7280';
        var w4w = (p.w4_daily/10000).toFixed(1)+'万';
        var w3w = (p.w3_daily/10000).toFixed(1)+'万';
        var pctText, pctColor;
        if (p.pct === null) {
          if (p.w3_daily === 0 && p.w4_daily > 0) {
            pctText = '新增'; pctColor = '#7C3AED';
          } else {
            pctText = '停投'; pctColor = '#DC2626';
          }
        } else {
          pctColor = p.pct >= 0 ? '#DC2626' : '#059669';
          pctText = (p.pct>=0?'+':'') + p.pct.toFixed(1) + '%';
        }
        var pillBg = p.pct !== null ? (p.pct >= 0 ? '#D1FAE5' : '#FEE2E2') : (p.w3_daily===0 ? '#EDE9FE' : '#FEE2E2');
        var pillFg = p.pct !== null ? (p.pct >= 0 ? '#059669' : '#DC2626') : (p.w3_daily===0 ? '#7C3AED' : '#DC2626');
        html += '<div style="display:flex;align-items:center;gap:8px;padding:5px 0;border-bottom:1px dashed #F3F4F6;font-size:11px">';
        html += '<span style="display:inline-block;width:6px;height:6px;border-radius:50%;background:'+mediaClr+';flex-shrink:0"></span>';
        html += '<span style="flex:1;color:#374151;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="'+p.label+'">'+p.label+'</span>';
        html += '<span style="color:#9CA3AF;white-space:nowrap;font-size:10px">'+w3w+' → '+w4w+'</span>';
        html += '<span style="background:'+pillBg+';color:'+pillFg+';font-size:10px;font-weight:700;padding:1px 7px;border-radius:6px;white-space:nowrap">'+pctText+'</span>';
        html += '</div>';
      }
      html += '</div>';
    }
    alertBox.innerHTML = html;
  }

  // ── 右侧：部门近四周日均消耗表格 ──
  var tblBox = document.getElementById('weekly-dept-table');
  var thtml = '<table class="mt-table report-table"><thead><tr>';
  thtml += '<th>部门</th>';
  // 从WEEKLY_DEPT_AVG取周标签
  if (WEEKLY_DEPT_AVG.length > 0) {
    var ws = WEEKLY_DEPT_AVG[0].weeks;
    for (var wi=0; wi<ws.length; wi++) {
      thtml += '<th class="num-col">'+ws[wi].label+'<span class="subhead">'+ws[wi].range+'</span></th>';
    }
  }
  thtml += '<th class="num-col">总消耗波动</th><th class="center-col">环比</th>';
  thtml += '</tr></thead><tbody>';

  for (var di=0; di<WEEKLY_DEPT_AVG.length; di++) {
    var d = WEEKLY_DEPT_AVG[di];
    var clr = DC[d.dept] || '#6B7280';
    var isKSum = d._is_kdept_sum;
    var deptFw = isKSum ? '900' : '700';
    thtml += '<tr' + (isKSum ? ' class="sum-row"' : '') + '>';
    thtml += '<td class="dept-cell" style="font-weight:'+deptFw+';--dept-color:'+clr+'"><span class="dept-mark"></span>'+d.dept+'</td>';
    for (var wi2=0; wi2<d.weeks.length; wi2++) {
      var wv = d.weeks[wi2].total_cost;
      thtml += '<td class="num">'+(wv/10000).toFixed(1)+'万</td>';
    }
    // 日均波动
    var diff = d.w4_vs_w3_diff;
    var diffW = (diff/10000).toFixed(1)+'万';
    var diffPrefix = diff >= 0 ? '+' : '';
    var diffClass = diff > 0 ? 'delta-up' : (diff < 0 ? 'delta-down' : 'delta-flat');
    thtml += '<td class="num '+diffClass+'">'+diffPrefix+diffW+'</td>';
    // 环比
    if (d.w4_vs_w3_pct !== null) {
      var pctVal = d.w4_vs_w3_pct;
      var pPrefix = pctVal >= 0 ? '+' : '';
      thtml += '<td class="center-col"><span class="pct-pill ' + (pctVal >= 0 ? 'up' : 'down') + '">'+pPrefix+pctVal.toFixed(1)+'%</span></td>';
    } else {
      thtml += '<td class="center-col delta-flat">--</td>';
    }
    thtml += '</tr>';
  }
  thtml += '</tbody></table>';
  tblBox.innerHTML = '<div class="mt-table-wrap report-wrap">' + thtml + '</div>';
})();

// ═══════════════════════════════════════════════════════════
// 通用备注输入框（URL hash 持久化）
// 使用方式：输入框 id 以 "note-" 开头，如 note-roi
// 保存时自动将所有 note-* 输入框的值写入 URL hash
// 打开页面时自动从 URL hash 回填
// ═══════════════════════════════════════════════════════════
(function(){
  var PREFIX = 'note-';
  // 从URL hash回填
  function loadNotes(){
    var hash = location.hash.slice(1);
    if(!hash) return;
    try {
      var data = JSON.parse(decodeURIComponent(hash));
      for(var key in data){
        var el = document.getElementById(PREFIX + key);
        if(el && data[key]) el.value = data[key];
      }
    } catch(e){}
  }
  // 将所有note-*输入框的值写入URL hash
  function saveNotes(){
    var inputs = document.querySelectorAll('input[id^="'+PREFIX+'"]');
    var data = {};
    inputs.forEach(function(inp){
      var k = inp.id.slice(PREFIX.length);
      if(inp.value.trim()) data[k] = inp.value.trim();
    });
    var newHash = Object.keys(data).length > 0 ? '#'+encodeURIComponent(JSON.stringify(data)) : '';
    history.replaceState(null, '', location.pathname + location.search + newHash);
  }
  // 监听所有note-*输入框的变化
  document.querySelectorAll('input[id^="'+PREFIX+'"]').forEach(function(inp){
    inp.addEventListener('input', saveNotes);
  });
  // 页面加载时回填
  loadNotes();
  // 监听hash变化（如从书签打开）
  window.addEventListener('hashchange', loadNotes);
})();
