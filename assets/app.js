/* 全国台风实时监测大屏 —— 渲染逻辑 */
(function () {
  'use strict';

  // ---------- 常量 ----------
  var LEVELS = [
    { key: 'TD',      name: '热带低压',   color: '#63b3ed' },
    { key: 'TS',      name: '热带风暴',   color: '#38b2ac' },
    { key: 'STS',     name: '强热带风暴', color: '#48bb78' },
    { key: 'TY',      name: '台风',       color: '#f6ad55' },
    { key: 'STY',     name: '强台风',     color: '#ed8936' },
    { key: 'SuperTY', name: '超强台风',   color: '#e53e3e' }
  ];
  var LEVEL_MAP = {};
  LEVELS.forEach(function (l) { LEVEL_MAP[l.key] = l; });
  function colorOf(k) { return (LEVEL_MAP[k] || LEVELS[0]).color; }
  function nameOf(k) { return (LEVEL_MAP[k] || LEVELS[0]).name; }

  var SPECIAL = {
    '新疆维吾尔自治区': '新疆', '宁夏回族自治区': '宁夏', '广西壮族自治区': '广西',
    '内蒙古自治区': '内蒙古', '西藏自治区': '西藏', '香港特别行政区': '香港',
    '澳门特别行政区': '澳门', '台湾省': '台湾', '北京市': '北京',
    '天津市': '天津', '上海市': '上海', '重庆市': '重庆'
  };
  function shortName(n) {
    if (SPECIAL[n]) return SPECIAL[n];
    return String(n).replace(/省$/, '').replace(/市$/, '');
  }

  // 台风符号（双螺旋）
  var EYE_PATH = 'path://M0,-11 C6.5,-11 11,-6.5 11,0 C11,4.5 8,8.2 4,9.6 ' +
    'C0.8,10.7 -1.8,9.2 -1.8,6.6 C-1.8,4.6 -0.3,3.4 1.3,3.9 C2.4,4.2 2.9,5.3 2.2,6.1 ' +
    'M0,11 C-6.5,11 -11,6.5 -11,0 C-11,-4.5 -8,-8.2 -4,-9.6 ' +
    'C-0.8,-10.7 1.8,-9.2 1.8,-6.6 C1.8,-4.6 0.3,-3.4 -1.3,-3.9 C-2.4,-4.2 -2.9,-5.3 -2.2,-6.1';

  var DIRS = {
    N: '偏北', NNE: '北东北', NE: '东北', ENE: '东东北', E: '偏东', ESE: '东东南',
    SE: '东南', SSE: '南东南', S: '偏南', SSW: '南西南', SW: '西南',
    WSW: '西西南', W: '偏西', WNW: '西西北', NW: '西北', NNW: '北西北'
  };

  var $ = function (id) { return document.getElementById(id); };

  // ---------- 全局状态 ----------
  var DATA = null;          // 台风数据
  var currentId = null;     // 当前选中台风
  var mapChart = null;
  var trendChart = null;
  var showCircle = true;
  var showForecast = true;
  var playTimer = null;
  var playIndex = -1;       // -1 表示不回放
  var autoTimer = null;

  // ---------- 工具 ----------
  function pad(n) { return n < 10 ? '0' + n : '' + n; }

  function fmtWind(w) { return (w == null ? '--' : w); }
  function fmtPres(p) { return (p == null ? '--' : p); }

  function renderList() {
    var el = $('tyList');
    el.innerHTML = '';
    DATA.typhoons.forEach(function (t) {
      var d = document.createElement('div');
      d.className = 'ty-item' + (t.id === currentId ? ' on' : '');
      var c = colorOf(t.latest.strength);
      var imp = t.impact || {};
      var loc = imp.current || imp.near
        ? (imp.current ? '位于' + imp.current : '临近' + imp.near)
        : '远离我国';

      d.style.borderLeftColor = c;
      d.innerHTML =
        '<div class="r1">' +
          '<span class="num">' + t.num + '</span>' +
          '<span class="nm">' + t.cnName + '</span>' +
          '<span class="en">' + (t.enName || '') + '</span>' +
        '</div>' +
        '<div class="r2">' +
          '<span class="tag" style="background:' + c + '">' + t.latest.strengthName + '</span>' +
          (t.active ? '<i class="dot-live"></i><span style="color:#ff8fa3">活跃</span>'
                    : '<span class="tag ghost">已停编</span>') +
          '<span style="margin-left:auto">' + loc + '</span>' +
        '</div>';
      d.onclick = function () { select(t.id); };
      el.appendChild(d);
    });
  }

  function renderHead(t) {
    var c = colorOf(t.latest.strength);
    var imp = t.impact || {};
    $('tyHead').innerHTML =
      '<div class="l1">' +
        '<span class="code" style="background:' + c + '">' + t.num + '</span>' +
        '<span class="name">' + t.cnName + '</span>' +
        '<span class="enname">' + (t.enName || '') + '</span>' +
      '</div>' +
      '<div class="l2">' +
        '<span>状态 <b style="color:' + (t.active ? '#ff4d6d' : '#7e9ac2') + '">' +
          (t.active ? '活跃中' : '已停编') + '</b></span>' +
        '<span>观测 <b>' + t.pointCount + '</b> 次</span>' +
        '<span>起止 <b>' + t.startTime.slice(5, 16) + ' ~ ' + t.endTime.slice(5, 16) + '</b></span>' +
      '</div>' +
      (t.desc ? '<div class="l2"><span>命名含义 <b>' + t.desc + '</b></span></div>' : '');
  }

  function renderParams(t) {
    var L = t.latest;
    var dir = DIRS[L.moveDir] || (L.moveDir === '0' || L.moveDir === 0 ? '少动' : (L.moveDir || '--'));
    var items = [
      { k: '当前强度', v: L.strengthName, cls: 'hl' },
      { k: '最大风速', v: fmtWind(L.wind), u: 'm/s', cls: 'hl' },
      { k: '中心气压', v: fmtPres(L.pressure), u: 'hPa', cls: 'cy' },
      { k: '移动方向', v: dir, cls: 'wa' },
      { k: '移动速度', v: (L.moveSpeed == null ? '--' : L.moveSpeed), u: 'km/h', cls: 'wa' },
      { k: '中心位置', v: L.lng.toFixed(1) + '°E', u: L.lat.toFixed(1) + '°N', cls: 'pu' }
    ];
    $('tyParams').innerHTML = items.map(function (i) {
      return '<div class="param ' + i.cls + '">' +
        '<div class="k">' + i.k + '</div>' +
        '<div class="v">' + i.v +
        (i.u ? '<small>' + i.u + '</small>' : '') + '</div></div>';
    }).join('');
  }

  function renderImpact(t) {
    var imp = t.impact || {};
    var html = '';
    if (imp.current) {
      html += '<span class="chip">台风中心位于 ' + imp.current + '</span>';
    } else if (imp.near) {
      html += '<span class="chip warn">中心临近 ' + imp.near + '</span>';
    }
    (imp.forecast || []).forEach(function (p) {
      html += '<span class="chip">预报影响 ' + p + '</span>';
    });
    (imp.history || []).forEach(function (p) {
      if ((imp.forecast || []).indexOf(p) < 0 && p !== imp.current) {
        html += '<span class="chip warn">已过境 ' + p + '</span>';
      }
    });
    if (t.landfall && t.landfall.length) {
      var lf = t.landfall[0];
      html += '<span class="chip">' + (lf.place || '登陆') + ' ' +
              (lf.timeText || lf.time).slice(5) + '</span>';
    }
    if (!html) html = '<span class="chip calm">路径未进入我国陆地</span>';
    $('tyImpact').innerHTML = html;
  }

  function renderForecast(t) {
    var fc = (t.forecast && t.forecast[0]);
    $('fcAgency').textContent = fc ? fc.agencyName : '暂无';
    if (!fc) { $('fcTable').innerHTML = '<tr><td class="empty">暂无预报数据</td></tr>'; return; }
    var rows = '<tr><th>时效</th><th>时间</th><th>强度</th><th>风速</th><th>气压</th></tr>';
    fc.points.forEach(function (p) {
      var c = colorOf(p.strength);
      rows += '<tr>' +
        '<td>' + p.hour + 'h</td>' +
        '<td>' + (p.time || '--').slice(5, 16) + '</td>' +
        '<td class="st" style="color:' + c + '">' + (p.strengthName || '--') + '</td>' +
        '<td>' + fmtWind(p.wind) + '</td>' +
        '<td>' + fmtPres(p.pressure) + '</td>' +
      '</tr>';
    });
    $('fcTable').innerHTML = rows;
  }

  function renderTrend(t) {
    if (!trendChart) trendChart = echarts.init($('trend'));
    var pts = t.points;
    var times = pts.map(function (p) { return p.time.slice(5, 16); });
    var winds = pts.map(function (p) { return p.wind; });
    var press = pts.map(function (p) { return p.pressure; });

    trendChart.setOption({
      grid: { left: 38, right: 40, top: 26, bottom: 22 },
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(6,20,40,0.94)',
        borderColor: 'rgba(0,190,255,0.4)',
        textStyle: { color: '#dce9ff', fontSize: 11 },
        axisPointer: { type: 'line', lineStyle: { color: 'rgba(0,229,255,0.35)' } }
      },
      xAxis: {
        type: 'category', data: times,
        axisLine: { lineStyle: { color: 'rgba(0,190,255,0.28)' } },
        axisLabel: { color: '#7e9ac2', fontSize: 9, interval: Math.max(1, Math.floor(times.length / 5)) },
        axisTick: { show: false }
      },
      yAxis: [
        {
          type: 'value', name: 'm/s', nameTextStyle: { color: '#7e9ac2', fontSize: 9 },
          axisLine: { show: false }, axisTick: { show: false },
          axisLabel: { color: '#7e9ac2', fontSize: 9 },
          splitLine: { lineStyle: { color: 'rgba(0,190,255,0.09)' } }
        },
        {
          type: 'value', name: 'hPa', nameTextStyle: { color: '#7e9ac2', fontSize: 9 },
          min: function (v) { return Math.floor((v.min - 15) / 10) * 10; },
          max: function (v) { return Math.ceil((v.max + 10) / 10) * 10; },
          axisLine: { show: false }, axisTick: { show: false },
          axisLabel: { color: '#7e9ac2', fontSize: 9 },
          splitLine: { show: false }
        }
      ],
      series: [
        {
          name: '风速', type: 'line', data: winds, smooth: true,
          symbol: 'none',
          lineStyle: { width: 2, color: '#ffb020' },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(255,176,32,0.42)' },
              { offset: 1, color: 'rgba(255,176,32,0)' }
            ])
          }
        },
        {
          name: '气压', type: 'line', yAxisIndex: 1, data: press, smooth: true,
          symbol: 'none',
          lineStyle: { width: 1.8, color: '#00e5ff', type: 'dashed' }
        }
      ]
    }, true);
  }

  function renderLegend() {
    $('legend').innerHTML = LEVELS.map(function (l) {
      return '<li><i style="background:' + l.color + '"></i>' + l.name + '</li>';
    }).join('') +
      '<li><i style="background:#fff;height:0;border-top:2px dashed #fff"></i>预报路径</li>' +
      '<li><span class="dotm" style="background:rgba(255,77,109,0.5);border:1px solid #ff4d6d"></span>风圈半径</li>';
  }

  // ---------- 地图 ----------
  function buildSeries(t) {
    var s = [];
    var pts = t.points;
    var end = playIndex >= 0 ? Math.min(playIndex + 1, pts.length) : pts.length;
    var view = pts.slice(0, end);

    // 1. 历史路径（逐段着色）
    var segs = [];
    for (var i = 1; i < view.length; i++) {
      var a = view[i - 1], b = view[i];
      segs.push({
        coords: [[a.lng, a.lat], [b.lng, b.lat]],
        lineStyle: { color: colorOf(b.strength) },
        _info: b
      });
    }
    var tailStart = Math.max(0, segs.length - 26);
    s.push({
      name: '历史路径', type: 'lines', coordinateSystem: 'geo',
      zlevel: 2, silent: true,
      lineStyle: { width: 2, opacity: 0.85, curveness: 0 },
      data: segs.slice(0, tailStart)
    });
    s.push({
      name: '近期路径', type: 'lines', coordinateSystem: 'geo',
      zlevel: 3, silent: true,
      lineStyle: { width: 3, opacity: 1, curveness: 0 },
      effect: {
        show: true, period: 5, trailLength: 0.42,
        symbol: 'arrow', symbolSize: 7, color: '#fff'
      },
      data: segs.slice(tailStart)
    });

    // 2. 观测点
    s.push({
      name: '观测点', type: 'scatter', coordinateSystem: 'geo',
      zlevel: 5, symbolSize: 5,
      itemStyle: { opacity: 0.8, borderColor: 'rgba(255,255,255,0.5)', borderWidth: 0.6 },
      data: view.map(function (p) {
        return { name: p.time, value: [p.lng, p.lat], itemStyle: { color: colorOf(p.strength) }, _p: p };
      }),
      tooltip: {
        formatter: function (o) {
          var p = o.data._p;
          return '<b>' + t.num + ' ' + t.cnName + '</b><br/>' +
            '时间：' + p.time + '<br/>' +
            '强度：<span style="color:' + colorOf(p.strength) + '">' + p.strengthName + '</span><br/>' +
            '风速：' + fmtWind(p.wind) + ' m/s　气压：' + fmtPres(p.pressure) + ' hPa<br/>' +
            '位置：' + p.lng.toFixed(1) + '°E, ' + p.lat.toFixed(1) + '°N';
        }
      }
    });

    // 3. 预报路径
    if (showForecast && !t.forecastHidden && t.forecast && t.forecast.length && playIndex < 0) {
      var fc = t.forecast[0];
      var line = [[view[view.length - 1].lng, view[view.length - 1].lat]];
      fc.points.forEach(function (p) { line.push([p.lng, p.lat]); });
      s.push({
        name: '预报路径', type: 'lines', coordinateSystem: 'geo',
        zlevel: 4, silent: true,
        lineStyle: {
          width: 2.2, color: '#ffffff', type: [7, 5], opacity: 0.9, curveness: 0.12
        },
        data: [{ coords: line }]
      });
      s.push({
        name: '预报点', type: 'scatter', coordinateSystem: 'geo',
        zlevel: 6, symbolSize: 9,
        symbol: 'circle',
        itemStyle: { color: 'rgba(255,255,255,0.16)', borderColor: '#fff', borderWidth: 1.6 },
        label: {
          show: true, formatter: function (o) { return o.data._h + 'h'; },
          color: '#fff', fontSize: 9, position: 'top',
          textBorderColor: 'rgba(0,0,0,0.75)', textBorderWidth: 2.5
        },
        data: fc.points.map(function (p) {
          return { value: [p.lng, p.lat], _h: p.hour, _p: p, itemStyle: { borderColor: colorOf(p.strength) } };
        }),
        tooltip: {
          formatter: function (o) {
            var p = o.data._p;
            return '<b>预报 ' + p.hour + ' 小时</b><br/>' +
              '时间：' + (p.time || '--') + '<br/>' +
              '强度：<span style="color:' + colorOf(p.strength) + '">' + (p.strengthName || '--') + '</span><br/>' +
              '风速：' + fmtWind(p.wind) + ' m/s　气压：' + fmtPres(p.pressure) + ' hPa';
          }
        }
      });
    }

    // 4. 风圈
    if (showCircle) {
      var last = view[view.length - 1];
      if (last && last.circles && last.circles.length) {
        var cdata = [];
        last.circles.forEach(function (c, ci) {
          cdata.push({
            value: [last.lng, last.lat],
            _r: c.radius, _name: c.name, _lv: c.level, _idx: ci
          });
        });
        s.push({
          name: '风圈', type: 'custom', coordinateSystem: 'geo',
          zlevel: 1, silent: true,
          renderItem: function (params, api) {
            var d = cdata[params.dataIndex];
            if (!d) return;
            var lng = api.value(0), lat = api.value(1);
            var p0 = api.coord([lng, lat]);
            var pLat = api.coord([lng, lat + 1]);
            var pxPerKm = Math.abs(pLat[1] - p0[1]) / 111.32;
            if (!isFinite(pxPerKm) || pxPerKm <= 0) return;

            var R = d._r;                       // [NE, SE, SW, NW] 单位 km
            var order = [0, 3, 2, 1];           // NE -> NW -> SW -> SE（逆时针）
            // 按风圈级别区分颜色（与影响省份红色区分）
            var palette = {
              '30KTS': { fill: 'rgba(160,220,255,0.18)', border: 'rgba(120,200,255,0.55)' },
              '50KTS': { fill: 'rgba(255,210,80,0.20)', border: 'rgba(255,190,60,0.60)' },
              '64KTS': { fill: 'rgba(255,120,80,0.22)', border: 'rgba(255,110,80,0.65)' },
              '85KTS': { fill: 'rgba(220,80,180,0.24)', border: 'rgba(220,80,180,0.70)' }
            };
            var p = palette[d._lv] || palette['30KTS'];
            var children = [];
            for (var q = 0; q < 4; q++) {
              var rkm = R[order[q]];
              if (!rkm || rkm <= 0) continue;
              children.push({
                type: 'sector',
                shape: {
                  cx: p0[0], cy: p0[1],
                  r: rkm * pxPerKm, r0: 0,
                  startAngle: q * Math.PI / 2,
                  endAngle: (q + 1) * Math.PI / 2
                },
                style: {
                  fill: p.fill,
                  stroke: p.border,
                  lineWidth: 1.1
                }
              });
            }
            if (!children.length) return;
            return { type: 'group', children: children };
          },
          data: cdata
        });
      }
    }

    // 5. 台风眼
    var last2 = view[view.length - 1];
    if (last2) {
      var sc = colorOf(last2.strength);
      s.push({
        name: '当前中心', type: 'scatter', coordinateSystem: 'geo',
        zlevel: 10,
        symbol: EYE_PATH,
        symbolSize: 40,
        symbolOffset: [0, 0],
        itemStyle: { color: sc, shadowBlur: 16, shadowColor: sc },
        label: {
          show: true,
          position: 'right',
          distance: 10,
          formatter: t.num + ' ' + t.cnName,
          color: '#fff', fontSize: 13, fontWeight: 'bold',
          backgroundColor: 'rgba(6,18,36,0.8)',
          borderColor: sc, borderWidth: 1, borderRadius: 3,
          padding: [4, 8],
          textBorderColor: 'rgba(0,0,0,0.6)', textBorderWidth: 2
        },
        data: [{
          value: [last2.lng, last2.lat],
          itemStyle: { color: sc }
        }],
        tooltip: {
          formatter: function () {
            return '<b>' + t.num + ' ' + t.cnName + '</b><br/>' +
              '最新定位：' + last2.time + '<br/>' +
              '强度：<span style="color:' + sc + '">' + last2.strengthName + '</span><br/>' +
              '风速：' + fmtWind(last2.wind) + ' m/s　气压：' + fmtPres(last2.pressure) + ' hPa';
          }
        }
      });
      s.push({
        name: '中心涟漪', type: 'effectScatter', coordinateSystem: 'geo',
        zlevel: 9,
        symbolSize: 12,
        rippleEffect: { brushType: 'stroke', scale: 4.2, period: 3.2 },
        itemStyle: { color: sc },
        silent: true,
        data: [{ value: [last2.lng, last2.lat] }]
      });
    }

    return s;
  }

  function buildRegions(t) {
    var imp = t.impact || {};
    var hi = {};
    (imp.history || []).forEach(function (p) { hi[p] = 'hist'; });
    (imp.forecast || []).forEach(function (p) { hi[p] = 'fc'; });
    if (imp.current) hi[imp.current] = 'cur';

    return Object.keys(hi).map(function (name) {
      var kind = hi[name];
      var color = kind === 'cur' ? 'rgba(255,77,109,0.42)'
                : kind === 'fc' ? 'rgba(255,176,32,0.34)'
                : 'rgba(255,120,140,0.18)';
      var border = kind === 'cur' ? '#ff4d6d'
                 : kind === 'fc' ? '#ffb020'
                 : 'rgba(255,140,160,0.5)';
      return {
        name: name,
        itemStyle: {
          areaColor: color,
          borderColor: border,
          borderWidth: kind === 'cur' ? 1.8 : 1.2,
          shadowColor: kind === 'cur' ? 'rgba(255,77,109,0.6)' : 'transparent',
          shadowBlur: kind === 'cur' ? 16 : 0
        },
        label: { show: true, color: kind === 'cur' ? '#fff' : '#ffd0d8', fontWeight: 'bold' }
      };
    });
  }

  function drawMap() {
    var t = DATA.typhoons.filter(function (x) { return x.id === currentId; })[0];
    if (!t) return;
    if (!mapChart) mapChart = echarts.init($('map'));

    mapChart.setOption({
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'item',
        backgroundColor: 'rgba(6,20,40,0.94)',
        borderColor: 'rgba(0,190,255,0.4)',
        textStyle: { color: '#dce9ff', fontSize: 12 },
        extraCssText: 'box-shadow:0 0 18px rgba(0,190,255,0.25);border-radius:4px;'
      },
      geo: {
        map: 'china',
        roam: true,
        zoom: 1.0,
        aspectScale: 0.82,
        layoutCenter: ['50%', '50%'],
        layoutSize: '112%',
        scaleLimit: { min: 0.7, max: 14 },
        selectedMode: false,
        itemStyle: {
          areaColor: {
            type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(14,48,88,0.92)' },
              { offset: 1, color: 'rgba(8,26,52,0.92)' }
            ]
          },
          borderColor: 'rgba(0,200,255,0.42)',
          borderWidth: 0.9,
          shadowColor: 'rgba(0,120,220,0.5)',
          shadowBlur: 12,
          shadowOffsetY: 4
        },
        emphasis: {
          itemStyle: { areaColor: 'rgba(0,140,220,0.5)', borderColor: '#00e5ff', borderWidth: 1.4 },
          label: { show: true, color: '#fff', fontSize: 11 }
        },
        label: {
          show: true, color: 'rgba(150,190,230,0.72)', fontSize: 9.5
        },
        regions: buildRegions(t)
      },
      series: buildSeries(t)
    }, true);
  }

  // ---------- 交互 ----------
  function select(id) {
    stopPlay();
    currentId = id;
    renderList();
    var t = DATA.typhoons.filter(function (x) { return x.id === id; })[0];
    if (!t) return;
    renderHead(t); renderParams(t); renderImpact(t); renderForecast(t);
    renderTrend(t); drawMap();
  }

  function stopPlay() {
    if (playTimer) { clearInterval(playTimer); playTimer = null; }
    playIndex = -1;
    $('btnPlay').classList.remove('on');
    $('btnPlay').textContent = '路径回放';
  }

  function startPlay() {
    var t = DATA.typhoons.filter(function (x) { return x.id === currentId; })[0];
    if (!t) return;
    playIndex = 0;
    $('btnPlay').classList.add('on');
    $('btnPlay').textContent = '停止回放';
    var step = Math.max(1, Math.floor(t.points.length / 90));
    playTimer = setInterval(function () {
      playIndex += step;
      if (playIndex >= t.points.length - 1) { playIndex = t.points.length - 1; stopPlay(); }
      drawMap();
    }, 90);
  }

  function bindTools() {
    $('btnReset').onclick = function () {
      if (mapChart) mapChart.dispatchAction({ type: 'restore' });
      drawMap();
    };
    $('btnPlay').onclick = function () { playTimer ? stopPlay() : startPlay(); };
    $('btnCircle').onclick = function () {
      showCircle = !showCircle;
      this.classList.toggle('on', showCircle);
      drawMap();
    };
    $('btnForecast').onclick = function () {
      showForecast = !showForecast;
      this.classList.toggle('on', showForecast);
      drawMap();
    };
  }

  function fitScreen() {
    var s = Math.min(window.innerWidth / 1920, window.innerHeight / 1080);
    var el = $('screen');
    el.style.transform = 'translate(-50%, -50%) scale(' + s + ')';
  }

  function tickClock() {
    var d = new Date();
    $('clock').textContent = pad(d.getHours()) + ':' + pad(d.getMinutes()) + ':' + pad(d.getSeconds());
  }

  function renderOverview() {
    var active = DATA.activeCount;
    var maxWind = 0, provs = {};
    DATA.typhoons.forEach(function (t) {
      maxWind = Math.max(maxWind, t.maxWind || 0);
      (t.impact ? (t.impact.history || []).concat(t.impact.forecast || []) : [])
        .forEach(function (p) { provs[p] = 1; });
    });
    $('mActive').textContent = active;
    $('mTotal').textContent = DATA.yearCount || DATA.typhoons.length;
    $('mMaxWind').textContent = maxWind;
    $('mProv').textContent = Object.keys(provs).length;
    $('yearTag').textContent = DATA.year + ' 年度';
    $('updateTime').textContent = DATA.updateTime;
    $('liveText').textContent = active > 0 ? '监测中 · ' + active + ' 个活跃' : '暂无活跃台风';
  }

  // ---------- 启动 ----------
  function boot(mapJson, tyData) {
    // 省份名转简称后注册
    (mapJson.features || []).forEach(function (f) {
      var p = f.properties || {};
      p.fullName = p.name;
      p.name = shortName(p.name || '');
    });
    echarts.registerMap('china', mapJson);

    DATA = tyData;
    // 年度编号总数（来自列表长度，脚本写入 yearCount）
    renderOverview();
    renderLegend();

    var first = DATA.typhoons[0];
    select(first ? first.id : null);

    bindTools();
    fitScreen();
    window.addEventListener('resize', function () {
      fitScreen();
      if (mapChart) mapChart.resize();
      if (trendChart) trendChart.resize();
    });
    tickClock();
    setInterval(tickClock, 1000);

    // 多活跃台风时自动轮播
    if (DATA.activeCount > 1) {
      autoTimer = setInterval(function () {
        if (playTimer) return;
        var acts = DATA.typhoons.filter(function (t) { return t.active; });
        if (acts.length < 2) return;
        var i = 0;
        acts.forEach(function (t, k) { if (t.id === currentId) i = k; });
        select(acts[(i + 1) % acts.length].id);
      }, 15000);
    }

    $('loading').style.display = 'none';
  }

  function fail(msg) {
    var el = $('loading');
    el.classList.add('err');
    el.innerHTML = '<p>' + msg + '</p>';
  }

  function getJSON(url) {
    return fetch(url, { cache: 'no-store' }).then(function (r) {
      if (!r.ok) throw new Error(url + ' → HTTP ' + r.status);
      return r.json();
    });
  }

  window.addEventListener('DOMContentLoaded', function () {
    if (location.protocol === 'file:') {
      fail('浏览器禁止以 <code>file://</code> 方式读取本地数据。<br/>' +
           '请在项目目录下运行启动脚本后访问 <code>http://localhost:8080</code>：<br/>' +
           '<code>start.bat</code>（Windows）或 <code>bash start.sh</code>');
      return;
    }
    Promise.all([
      getJSON('data/china_province.json'),
      getJSON('data/typhoon.json')
    ]).then(function (res) {
      boot(res[0], res[1]);
    }).catch(function (e) {
      console.error(e);
      fail('数据载入失败：' + e.message + '<br/>' +
           '如为首次使用，请先运行 <code>python scripts/fetch_typhoon.py</code> 抓取数据。');
    });
  });
})();
