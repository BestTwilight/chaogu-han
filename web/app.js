const state = {
  selectedSymbol: "TECH_A",
  lastPayload: null,
  hoverIndex: null,
  hoverY: null,
  chartLayout: null,
};

const els = {
  sessionMeta: document.querySelector("#sessionMeta"),
  modeSelect: document.querySelector("#modeSelect"),
  symbolSelect: document.querySelector("#symbolSelect"),
  stepOne: document.querySelector("#stepOne"),
  stepFive: document.querySelector("#stepFive"),
  resetSession: document.querySelector("#resetSession"),
  symbolTitle: document.querySelector("#symbolTitle"),
  symbolSub: document.querySelector("#symbolSub"),
  lastPrice: document.querySelector("#lastPrice"),
  lastChange: document.querySelector("#lastChange"),
  regimeTag: document.querySelector("#regimeTag"),
  canvas: document.querySelector("#priceCanvas"),
  hoverInfo: document.querySelector("#hoverInfo"),
  chartTooltip: document.querySelector("#chartTooltip"),
  totalEquity: document.querySelector("#totalEquity"),
  cash: document.querySelector("#cash"),
  marketValue: document.querySelector("#marketValue"),
  drawdown: document.querySelector("#drawdown"),
  equityCanvas: document.querySelector("#equityCanvas"),
  equitySummary: document.querySelector("#equitySummary"),
  orderForm: document.querySelector("#orderForm"),
  orderType: document.querySelector("#orderType"),
  limitRow: document.querySelector("#limitRow"),
  limitPrice: document.querySelector("#limitPrice"),
  orderMessage: document.querySelector("#orderMessage"),
  positions: document.querySelector("#positions"),
  fills: document.querySelector("#fills"),
  returnRate: document.querySelector("#returnRate"),
  tradeCount: document.querySelector("#tradeCount"),
  winRate: document.querySelector("#winRate"),
  profitFactor: document.querySelector("#profitFactor"),
  coachNotes: document.querySelector("#coachNotes"),
};

function money(value) {
  return Number(value || 0).toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function percent(value) {
  return `${(Number(value || 0) * 100).toFixed(2)}%`;
}

function signedMoney(value) {
  const number = Number(value || 0);
  const sign = number > 0 ? "+" : "";
  return `${sign}${money(number)}`;
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "请求失败");
  }
  return payload;
}

async function loadState(symbol = state.selectedSymbol) {
  const payload = await api(`/api/state?symbol=${encodeURIComponent(symbol)}`);
  render(payload);
}

async function loadDatasets() {
  const datasets = await api("/api/datasets");
  const historicalOption = Array.from(els.modeSelect.options).find((option) => option.value === "historical");
  if (historicalOption) {
    historicalOption.disabled = !datasets.historical_available;
    historicalOption.textContent = datasets.historical_available
      ? `历史盲测 (${datasets.historical_count})`
      : "历史盲测 (请放CSV)";
  }
}

function render(payload) {
  state.lastPayload = payload;
  state.selectedSymbol = payload.selected_symbol;
  state.hoverIndex = null;
  state.hoverY = null;
  els.chartTooltip.hidden = true;
  renderSymbolOptions(payload);
  renderHeader(payload);
  renderAccount(payload.account);
  drawEquityCurve(payload.snapshots);
  renderPositions(payload.positions);
  renderFills(payload.fills, payload.selected_symbol);
  drawChart(payload.candles, payload.fills);
  loadReport();
}

function renderSymbolOptions(payload) {
  const existing = Array.from(els.symbolSelect.options).map((option) => option.value).join(",");
  if (existing !== payload.symbols.join(",")) {
    els.symbolSelect.innerHTML = "";
    payload.symbols.forEach((symbol) => {
      const option = document.createElement("option");
      option.value = symbol;
      option.textContent = symbol;
      els.symbolSelect.appendChild(option);
    });
  }
  els.symbolSelect.value = payload.selected_symbol;
}

function renderHeader(payload) {
  const candles = payload.candles;
  const current = candles[candles.length - 1];
  const previous = candles[candles.length - 2] || current;
  const change = current.close / previous.close - 1;
  els.modeSelect.value = payload.mode || "generated";
  els.sessionMeta.textContent = `${current.timestamp.slice(0, 10)} | 第 ${payload.index + 1} / ${payload.total_bars} 根 K 线 | ${payload.message || ""}`;
  els.symbolTitle.textContent = current.symbol;
  els.symbolSub.textContent = `${current.industry} | 成交量 ${current.volume.toLocaleString("zh-CN")}`;
  els.lastPrice.textContent = money(current.close);
  els.lastChange.textContent = percent(change);
  els.lastChange.className = change >= 0 ? "up" : "down";
  els.regimeTag.textContent = current.event_label ? `${current.regime} | ${current.event_label}` : current.regime;
  els.stepOne.disabled = payload.is_finished;
  els.stepFive.disabled = payload.is_finished;
}

function renderAccount(account) {
  els.totalEquity.textContent = money(account.total_equity);
  els.cash.textContent = money(account.cash);
  els.marketValue.textContent = money(account.market_value);
  els.drawdown.textContent = percent(account.max_drawdown);
}

function drawEquityCurve(snapshots) {
  const canvas = els.equityCanvas;
  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.floor(rect.width * dpr);
  canvas.height = Math.floor(rect.height * dpr);
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  const width = rect.width;
  const height = rect.height;
  ctx.clearRect(0, 0, width, height);
  if (!snapshots || !snapshots.length) return;

  const values = snapshots.map((snapshot) => Number(snapshot.total_equity));
  const start = values[0];
  const latest = values[values.length - 1];
  const minValue = Math.min(...values, start);
  const maxValue = Math.max(...values, start);
  const range = Math.max(1, maxValue - minValue);
  const padding = { top: 14, right: 10, bottom: 22, left: 42 };
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;
  const xFor = (index) => padding.left + (plotWidth * index) / Math.max(1, values.length - 1);
  const yFor = (value) => padding.top + ((maxValue - value) / range) * plotHeight;
  const startY = yFor(start);

  ctx.strokeStyle = "#e5ebf1";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(padding.left, padding.top);
  ctx.lineTo(padding.left, padding.top + plotHeight);
  ctx.lineTo(width - padding.right, padding.top + plotHeight);
  ctx.stroke();

  ctx.setLineDash([4, 4]);
  ctx.strokeStyle = "#aebdca";
  ctx.beginPath();
  ctx.moveTo(padding.left, startY);
  ctx.lineTo(width - padding.right, startY);
  ctx.stroke();
  ctx.setLineDash([]);

  ctx.strokeStyle = latest >= start ? "#d64545" : "#16845f";
  ctx.lineWidth = 2;
  ctx.beginPath();
  values.forEach((value, index) => {
    const x = xFor(index);
    const y = yFor(value);
    if (index === 0) {
      ctx.moveTo(x, y);
    } else {
      ctx.lineTo(x, y);
    }
  });
  ctx.stroke();

  ctx.fillStyle = "#687789";
  ctx.font = "11px Segoe UI, Arial";
  ctx.fillText(money(maxValue), 6, padding.top + 4);
  ctx.fillText(money(minValue), 6, padding.top + plotHeight);
  ctx.fillText("初始", padding.left + 4, Math.max(12, startY - 4));

  const returnRate = latest / start - 1;
  els.equitySummary.textContent = `${money(latest)} | ${percent(returnRate)}`;
  els.equitySummary.className = returnRate >= 0 ? "up" : "down";
}

function renderPositions(positions) {
  const entries = Object.values(positions).filter((position) => position.quantity > 0);
  if (!entries.length) {
    els.positions.className = "list empty";
    els.positions.textContent = "暂无持仓";
    return;
  }
  els.positions.className = "list";
  els.positions.innerHTML = "";
  entries.forEach((position) => {
    const item = document.createElement("div");
    item.className = "position";
    const pnlClass = position.unrealized_pnl >= 0 ? "up" : "down";
    item.innerHTML = `
      <div>
        <strong>${position.symbol}</strong>
        <span>持股 ${position.quantity} | 可卖 ${position.sellable_quantity}</span>
        <span>成本 ${money(position.avg_cost)} | 现价 ${money(position.last_price)}</span>
      </div>
      <div>
        <strong>${money(position.market_value)}</strong>
        <span class="${pnlClass}">${signedMoney(position.unrealized_pnl)}</span>
      </div>
    `;
    els.positions.appendChild(item);
  });
}

function renderFills(fills, symbol) {
  const entries = fills.filter((fill) => fill.symbol === symbol).slice(-8).reverse();
  if (!entries.length) {
    els.fills.className = "list empty";
    els.fills.textContent = "暂无成交";
    return;
  }
  els.fills.className = "list";
  els.fills.innerHTML = "";
  entries.forEach((fill) => {
    const item = document.createElement("div");
    const isBuy = fill.side === "buy";
    item.className = "fill";
    item.innerHTML = `
      <div>
        <strong><span class="fill-side ${isBuy ? "buy" : "sell"}">${isBuy ? "B" : "S"}</span>${isBuy ? "买入" : "卖出"} ${fill.symbol}</strong>
        <span>${fill.timestamp.slice(0, 10)} | ${fill.quantity} 股</span>
      </div>
      <div>
        <strong>${money(fill.price)}</strong>
        <span>费税 ${money(fill.fee + fill.tax)}</span>
      </div>
    `;
    els.fills.appendChild(item);
  });
}

async function loadReport() {
  const report = await api("/api/report");
  els.returnRate.textContent = percent(report.total_return);
  els.returnRate.className = report.total_return >= 0 ? "up" : "down";
  els.tradeCount.textContent = report.trade_count;
  els.winRate.textContent = percent(report.win_rate);
  els.profitFactor.textContent = report.profit_factor === "Infinity" || report.profit_factor === Infinity ? "∞" : Number(report.profit_factor).toFixed(2);
  els.coachNotes.innerHTML = "";
  report.coach_notes.forEach((note) => {
    const li = document.createElement("li");
    li.textContent = note;
    els.coachNotes.appendChild(li);
  });
}

function drawChart(candles, fills = []) {
  const canvas = els.canvas;
  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.floor(rect.width * dpr);
  canvas.height = Math.floor(rect.height * dpr);
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  const width = rect.width;
  const height = rect.height;
  ctx.clearRect(0, 0, width, height);

  const padding = { top: 18, right: 70, bottom: 34, left: 52 };
  const volumeHeight = 118;
  const priceHeight = height - padding.top - padding.bottom - volumeHeight - 18;
  const visible = candles.slice(-90);
  if (!visible.length) return;

  const highs = visible.map((candle) => candle.high);
  const lows = visible.map((candle) => candle.low);
  const maxPrice = Math.max(...highs);
  const minPrice = Math.min(...lows);
  const priceRange = Math.max(0.01, maxPrice - minPrice);
  const maxVolume = Math.max(...visible.map((candle) => candle.volume));
  const plotWidth = width - padding.left - padding.right;
  const candleGap = plotWidth / visible.length;
  const candleWidth = Math.max(3, Math.min(12, candleGap * 0.58));
  const firstVisibleIndex = candles.length - visible.length;

  ctx.strokeStyle = "#e5ebf1";
  ctx.lineWidth = 1;
  ctx.font = "12px Segoe UI, Arial";
  ctx.fillStyle = "#687789";
  for (let i = 0; i <= 4; i += 1) {
    const y = padding.top + (priceHeight / 4) * i;
    const price = maxPrice - (priceRange / 4) * i;
    ctx.beginPath();
    ctx.moveTo(padding.left, y);
    ctx.lineTo(width - padding.right, y);
    ctx.stroke();
    ctx.fillText(price.toFixed(2), width - padding.right + 8, y + 4);
  }

  const priceY = (price) => padding.top + ((maxPrice - price) / priceRange) * priceHeight;
  const priceFromY = (y) => maxPrice - ((y - padding.top) / priceHeight) * priceRange;
  const volumeTop = padding.top + priceHeight + 18;
  const candlePoints = [];
  visible.forEach((candle, index) => {
    const x = padding.left + candleGap * index + candleGap / 2;
    candlePoints.push({ x, index: firstVisibleIndex + index, candle });
    const up = candle.close >= candle.open;
    const color = up ? "#d64545" : "#16845f";
    const openY = priceY(candle.open);
    const closeY = priceY(candle.close);
    const highY = priceY(candle.high);
    const lowY = priceY(candle.low);
    ctx.strokeStyle = color;
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.moveTo(x, highY);
    ctx.lineTo(x, lowY);
    ctx.stroke();
    const bodyTop = Math.min(openY, closeY);
    const bodyHeight = Math.max(2, Math.abs(closeY - openY));
    ctx.fillRect(x - candleWidth / 2, bodyTop, candleWidth, bodyHeight);

    const volumeBarHeight = (candle.volume / maxVolume) * volumeHeight;
    ctx.globalAlpha = 0.28;
    ctx.fillRect(x - candleWidth / 2, volumeTop + volumeHeight - volumeBarHeight, candleWidth, volumeBarHeight);
    ctx.globalAlpha = 1;
  });

  drawTradeMarkers(ctx, visible, fills, {
    padding,
    candleGap,
    candleWidth,
    priceY,
    firstVisibleIndex,
  });

  if (state.hoverIndex !== null) {
    drawCrosshair(ctx, visible, {
      padding,
      width,
      height,
      priceHeight,
      volumeHeight,
      candleGap,
      candlePoints,
      priceFromY,
    });
  }

  ctx.fillStyle = "#687789";
  ctx.fillText(visible[0].timestamp.slice(5, 10), padding.left, height - 12);
  ctx.fillText(visible[visible.length - 1].timestamp.slice(5, 10), width - padding.right - 36, height - 12);
  state.chartLayout = {
    rect,
    padding,
    width,
    height,
    priceHeight,
    volumeHeight,
    candleGap,
    candlePoints,
    firstVisibleIndex,
    visible,
    priceFromY,
  };
}

function drawTradeMarkers(ctx, visible, fills, layout) {
  const visibleByDate = new Map();
  visible.forEach((candle, index) => {
    visibleByDate.set(candle.timestamp.slice(0, 10), { candle, index });
  });
  fills
    .filter((fill) => fill.symbol === state.selectedSymbol)
    .forEach((fill) => {
      const match = visibleByDate.get(fill.timestamp.slice(0, 10));
      if (!match) return;
      const x = layout.padding.left + layout.candleGap * match.index + layout.candleGap / 2;
      const y = layout.priceY(fill.price);
      const isBuy = fill.side === "buy";
      const color = isBuy ? "#d64545" : "#16845f";
      const markerY = isBuy ? y + 18 : y - 18;
      ctx.save();
      ctx.fillStyle = color;
      ctx.strokeStyle = "#ffffff";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(x, markerY, 10, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
      ctx.fillStyle = "#ffffff";
      ctx.font = "700 12px Segoe UI, Arial";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(isBuy ? "B" : "S", x, markerY + 0.5);
      ctx.fillStyle = color;
      ctx.font = "12px Segoe UI, Arial";
      ctx.textBaseline = isBuy ? "top" : "bottom";
      ctx.fillText(money(fill.price), x, isBuy ? markerY + 13 : markerY - 13);
      ctx.restore();
    });
}

function drawCrosshair(ctx, visible, layout) {
  const localIndex = state.hoverIndex - layout.firstVisibleIndex;
  if (localIndex < 0 || localIndex >= visible.length) return;
  const point = layout.candlePoints[localIndex];
  const candle = point.candle;
  const x = point.x;
  const y = Math.max(layout.padding.top, Math.min(state.hoverY ?? layout.padding.top, layout.padding.top + layout.priceHeight));
  const cursorPrice = layout.priceFromY(y);

  ctx.save();
  ctx.setLineDash([4, 4]);
  ctx.strokeStyle = "#8da2b6";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(x, layout.padding.top);
  ctx.lineTo(x, layout.padding.top + layout.priceHeight + 18 + layout.volumeHeight);
  ctx.moveTo(layout.padding.left, y);
  ctx.lineTo(layout.width - layout.padding.right, y);
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.fillStyle = "#17212b";
  ctx.fillRect(layout.width - layout.padding.right + 4, y - 10, 58, 20);
  ctx.fillStyle = "#ffffff";
  ctx.font = "12px Segoe UI, Arial";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(money(cursorPrice), layout.width - layout.padding.right + 33, y);
  ctx.restore();
}

function handleCanvasMove(event) {
  if (!state.lastPayload || !state.chartLayout) return;
  const layout = state.chartLayout;
  const rect = els.canvas.getBoundingClientRect();
  const x = event.clientX - rect.left;
  const y = event.clientY - rect.top;
  const points = layout.candlePoints;
  if (!points.length) return;
  const nearest = points.reduce((best, point) => (Math.abs(point.x - x) < Math.abs(best.x - x) ? point : best), points[0]);
  state.hoverIndex = nearest.index;
  state.hoverY = y;
  updateHoverInfo(nearest.candle);
  updateTooltip(event, nearest.candle, layout.priceFromY(Math.max(layout.padding.top, Math.min(y, layout.padding.top + layout.priceHeight))));
  drawChart(state.lastPayload.candles, state.lastPayload.fills);
}

function handleCanvasLeave() {
  state.hoverIndex = null;
  state.hoverY = null;
  els.chartTooltip.hidden = true;
  if (state.lastPayload) {
    renderHeader(state.lastPayload);
    els.hoverInfo.textContent = "移动鼠标查看 K 线详情";
    drawChart(state.lastPayload.candles, state.lastPayload.fills);
  }
}

function updateHoverInfo(candle) {
  const payload = state.lastPayload;
  const candles = payload.candles;
  const index = candles.findIndex((item) => item.timestamp === candle.timestamp);
  const previous = candles[index - 1] || candle;
  const change = candle.close / previous.close - 1;
  const className = change >= 0 ? "up" : "down";
  els.hoverInfo.innerHTML = `
    <strong>${candle.timestamp.slice(0, 10)}</strong>
    开 ${money(candle.open)}
    高 ${money(candle.high)}
    低 ${money(candle.low)}
    收 <span class="${className}">${money(candle.close)}</span>
    涨跌 <span class="${className}">${percent(change)}</span>
    量 ${candle.volume.toLocaleString("zh-CN")}
  `;
}

function updateTooltip(event, candle, cursorPrice) {
  const fills = state.lastPayload.fills.filter(
    (fill) => fill.symbol === state.selectedSymbol && fill.timestamp.slice(0, 10) === candle.timestamp.slice(0, 10)
  );
  const tradeRows = fills
    .map((fill) => {
      const label = fill.side === "buy" ? "买入" : "卖出";
      return `<div><span>${label}</span><strong>${fill.quantity} 股 @ ${money(fill.price)}</strong></div>`;
    })
    .join("");
  els.chartTooltip.innerHTML = `
    <div><span>日期</span><strong>${candle.timestamp.slice(0, 10)}</strong></div>
    <div><span>开</span><strong>${money(candle.open)}</strong></div>
    <div><span>高</span><strong>${money(candle.high)}</strong></div>
    <div><span>低</span><strong>${money(candle.low)}</strong></div>
    <div><span>收</span><strong>${money(candle.close)}</strong></div>
    <div><span>指针价</span><strong>${money(cursorPrice)}</strong></div>
    <div><span>成交量</span><strong>${candle.volume.toLocaleString("zh-CN")}</strong></div>
    ${tradeRows}
  `;
  const wrapRect = els.canvas.parentElement.getBoundingClientRect();
  const left = Math.min(event.clientX - wrapRect.left + 16, wrapRect.width - 220);
  const top = Math.max(8, event.clientY - wrapRect.top - 16);
  els.chartTooltip.style.left = `${left}px`;
  els.chartTooltip.style.top = `${top}px`;
  els.chartTooltip.hidden = false;
}

async function step(bars) {
  const payload = await api("/api/step", {
    method: "POST",
    body: JSON.stringify({ bars, symbol: state.selectedSymbol }),
  });
  render(payload);
}

async function reset() {
  const seed = Math.floor(Math.random() * 100000);
  const mode = els.modeSelect.value;
  const days = mode === "historical" ? 180 : 260;
  try {
    const payload = await api("/api/reset", {
      method: "POST",
      body: JSON.stringify({ mode, seed, days, cash: 100000, symbol: state.selectedSymbol }),
    });
    els.orderMessage.textContent = `已重置场景 seed=${seed}`;
    els.orderMessage.className = "message";
    render(payload);
    loadDatasets();
  } catch (error) {
    els.orderMessage.textContent = error.message;
    els.orderMessage.className = "message error";
  }
}

els.symbolSelect.addEventListener("change", (event) => loadState(event.target.value));
els.modeSelect.addEventListener("change", () => {
  els.orderMessage.textContent = "切换模式后点击重置开始新训练";
  els.orderMessage.className = "message";
});
els.stepOne.addEventListener("click", () => step(1));
els.stepFive.addEventListener("click", () => step(5));
els.resetSession.addEventListener("click", reset);
els.canvas.addEventListener("mousemove", handleCanvasMove);
els.canvas.addEventListener("mouseleave", handleCanvasLeave);
els.orderType.addEventListener("change", () => {
  els.limitRow.style.display = els.orderType.value === "limit" ? "grid" : "none";
});

els.orderForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(els.orderForm);
  const body = {
    symbol: state.selectedSymbol,
    side: form.get("side"),
    quantity: Number(form.get("quantity")),
    order_type: form.get("order_type"),
    limit_price: form.get("limit_price"),
  };
  try {
    const result = await api("/api/orders", {
      method: "POST",
      body: JSON.stringify(body),
    });
    const order = result.order;
    if (result.fill) {
      els.orderMessage.textContent = `${order.side === "buy" ? "买入" : "卖出"} ${result.fill.quantity} 股，成交价 ${money(result.fill.price)}`;
      els.orderMessage.className = "message";
    } else {
      els.orderMessage.textContent = order.message || "未成交";
      els.orderMessage.className = "message error";
    }
    render(result.state);
  } catch (error) {
    els.orderMessage.textContent = error.message;
    els.orderMessage.className = "message error";
  }
});

window.addEventListener("resize", () => {
  if (state.lastPayload) {
    drawChart(state.lastPayload.candles, state.lastPayload.fills);
    drawEquityCurve(state.lastPayload.snapshots);
  }
});

els.limitRow.style.display = "none";
loadDatasets();
loadState();
