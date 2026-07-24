import { useCallback, useEffect, useRef, useState } from "react";
import { CheckCircle, Play, SlidersHorizontal } from "@phosphor-icons/react";
import { DrawdownChart, EquityChart } from "../components/Charts.jsx";
import { ErrorNotice, Field, Loading, Tabs } from "../components/Ui.jsx";
import { api, post } from "../lib/api.js";
import { dateLabel, number, percent } from "../lib/format.js";

const RESULT_TABS = [
  { value: "performance", label: "绩效" },
  { value: "drawdown", label: "回撤" },
  { value: "trades", label: "历史成交" },
  { value: "events", label: "事件日志" },
];

export function BacktestPage() {
  const [strategy, setStrategy] = useState("moving_average_cross");
  const [strategies, setStrategies] = useState([]);
  const [result, setResult] = useState(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [tab, setTab] = useState("performance");
  const [form, setForm] = useState({ symbol: "000001.SZ", benchmark_symbol: "510300.SH", period: "1d", start: 20240102, end: 20260717, initial_cash: 1000000, quantity: 1000, fast: 5, slow: 20, commission_rate: 0.0001, minimum_commission: 5, stamp_duty_rate: 0.0005, universe_mode: "single" });
  const booted = useRef(false);

  useEffect(() => {
    api("/strategies").then((payload) => setStrategies(payload.strategies || [])).catch((loadError) => setError(loadError.message));
  }, []);

  const run = useCallback(async () => {
    setRunning(true);
    setError("");
    try {
      setResult(await post("/backtests/run", { strategy, policy: "strict_research", ...form }));
    } catch (runError) {
      setError(runError.message);
    } finally {
      setRunning(false);
    }
  }, [form, strategy]);

  useEffect(() => {
    if (booted.current) return;
    booted.current = true;
    run();
  }, [run]);

  const metrics = result?.metrics || {};
  const selectedDefinition = strategies.find((item) => item.name === strategy);
  const implementation = selectedDefinition?.implementation || strategy;
  const changeForm = (next) => { setForm((current) => ({ ...current, ...next })); setResult(null); };
  const chooseStrategy = (name) => {
    setStrategy(name);
    setResult(null);
    const definition = strategies.find((item) => item.name === name);
    const parameters = definition?.config?.parameters || {};
    setForm((current) => ({
      ...current,
      fast: Number(parameters.fast ?? current.fast),
      slow: Number(parameters.slow ?? current.slow),
      quantity: Number(parameters.quantity ?? current.quantity),
      ...(definition?.implementation === "low_volume_ratio_momentum" ? { symbol: "603580.SH", period: "1m", start: 20260701, universe_mode: "all_market" } : { universe_mode: "single" }),
    }));
  };

  return (
    <div className="backtest-workspace">
      <header className="page-toolbar">
        <div><span className="eyebrow">统一事件驱动内核</span><h1>回测实验</h1></div>
        <div className="toolbar-actions"><span className="verified-badge"><CheckCircle size={16} /> 下一 bar 成交 · T+1</span><button className="primary-button" type="button" onClick={run} disabled={running}>{running ? <Loading label="运行回测" /> : <><Play size={15} weight="fill" /> 运行实验</>}</button></div>
      </header>

      <aside className="backtest-config panel">
        <div className="panel-header"><h2>实验配置</h2><SlidersHorizontal size={15} /></div>
        <div className="config-body">
          <Field label="策略模板"><select value={strategy} onChange={(event) => chooseStrategy(event.target.value)}>{strategies.map((item) => <option key={item.name} value={item.name}>{item.title}</option>)}</select></Field>
          <Field label="选股范围"><select value={form.universe_mode} onChange={(event) => { const mode = event.target.value; changeForm({ universe_mode: mode, ...(mode === "all_market" ? { period: "1m" } : {}) }); }}><option value="single">单标的</option><option value="all_market" disabled={strategies.find((item) => item.name === strategy)?.implementation !== "low_volume_ratio_momentum"}>沪深主板全市场（选股策略）</option></select></Field>
          <Field label="研究标的"><input value={form.universe_mode === "all_market" ? "沪深主板全市场" : form.symbol} disabled={form.universe_mode === "all_market"} onChange={(event) => changeForm({ symbol: event.target.value.toUpperCase() })} /></Field>
          <div className="field-row"><Field label="回测周期"><select value={form.period} disabled={form.universe_mode === "all_market"} onChange={(event) => { const period = event.target.value; changeForm({ period, start: ["1m", "5m", "15m", "1h"].includes(period) ? 20250717 : 20240102 }); }}><option value="1m">1分钟</option><option value="5m">5分钟</option><option value="15m">15分钟</option><option value="1h">1小时</option><option value="1d">日线</option><option value="1q">季度</option><option value="1y">年度</option></select></Field><Field label="指数ETF基准"><input value={form.benchmark_symbol} onChange={(event) => changeForm({ benchmark_symbol: event.target.value.toUpperCase() })} /></Field></div>
          <Field label="日期范围"><div className="date-pair"><input type="date" value={dateLabel(form.start)} onInput={(event) => changeForm({ start: Number(event.currentTarget.value.replaceAll("-", "")) })} /><span>→</span><input type="date" value={dateLabel(form.end)} onInput={(event) => changeForm({ end: Number(event.currentTarget.value.replaceAll("-", "")) })} /></div></Field>
          <Field label="初始资金"><input type="number" value={form.initial_cash} onChange={(event) => changeForm({ initial_cash: Number(event.target.value) })} /></Field>
          {implementation === "moving_average_cross" && <div className="field-row thirds"><Field label="短均线"><input type="number" value={form.fast} onChange={(event) => changeForm({ fast: Number(event.target.value) })} /></Field><Field label="长均线"><input type="number" value={form.slow} onChange={(event) => changeForm({ slow: Number(event.target.value) })} /></Field><Field label="每次交易数量"><input type="number" value={form.quantity} onChange={(event) => changeForm({ quantity: Number(event.target.value) })} /></Field></div>}
          {implementation === "buy_and_hold" && <div className="config-block"><h3>仓位设置</h3><label className="checkbox-row"><input type="checkbox" checked disabled readOnly /> 100% 可用资金，扣除佣金后按 100 股整手尽可能满仓</label><p>首根 K 线仅产生信号，在下一可交易 K 线开盘建仓，避免同 bar 成交。</p></div>}
          {implementation === "low_volume_ratio_momentum" && <div className="config-block"><h3>仓位设置</h3><p>每只股票使用总资产的 20%，最多同时持有 5 只；下一分钟开盘满足可交易条件后建仓。</p></div>}
          <div className="config-block"><h3>执行策略（strict_research 固定）</h3><label className="checkbox-row"><input type="checkbox" checked disabled readOnly /> T+1 可用数量</label><label className="checkbox-row"><input type="checkbox" checked disabled readOnly /> 涨跌停保守成交</label><label className="checkbox-row"><input type="checkbox" checked disabled readOnly /> 原始价成交，除权日调整现金与持仓</label><label className="checkbox-row"><input type="checkbox" checked disabled readOnly /> 指数 ETF 基准采用等比前复权总收益</label></div>
          <div className="config-block"><h3>费用（修改后进入成交计算）</h3><div className="field-row"><Field label="佣金率 (%)"><input type="number" min="0" max="5" step="0.001" value={form.commission_rate * 100} onChange={(event) => changeForm({ commission_rate: Number(event.target.value) / 100 })} /></Field><Field label="印花税率 (%)"><input type="number" min="0" max="5" step="0.001" value={form.stamp_duty_rate * 100} onChange={(event) => changeForm({ stamp_duty_rate: Number(event.target.value) / 100 })} /></Field></div><Field label="最低佣金（元）"><input type="number" min="0" step="0.1" value={form.minimum_commission} onChange={(event) => changeForm({ minimum_commission: Number(event.target.value) })} /></Field></div>
          <ErrorNotice message={error} onClose={() => setError("")} />
        </div>
      </aside>

      <section className="backtest-results panel">
        <div className="result-hero">
          <div><span>总收益</span><strong>{percent(metrics.total_return)}</strong></div>
          <div><span>年化收益</span><strong>{percent(metrics.annualized_return)}</strong></div>
          <div><span>Sharpe</span><strong>{number(metrics.sharpe)}</strong></div>
          <div><span>最大回撤</span><strong className="negative">{percent(metrics.max_drawdown)}</strong></div>
          <div><span>ETF基准收益</span><strong>{percent(metrics.benchmark_total_return)}</strong></div>
          <div><span>超额收益</span><strong>{percent(metrics.excess_return)}</strong></div>
        </div>
        <Tabs items={RESULT_TABS.map((item) => ({ ...item, count: item.value === "trades" ? result?.trades?.length : undefined }))} value={tab} onChange={setTab} />
        <div className="backtest-chart-area">
          {tab === "performance" && <EquityChart equity={result?.equity} benchmark={result?.benchmark} />}
          {tab === "drawdown" && <DrawdownChart equity={result?.equity} />}
          {tab === "trades" && <TradeTable trades={result?.trades || []} />}
          {tab === "events" && <EventTable events={result?.event_log || []} />}
        </div>
        <div className="reproducibility-bar">
          <span><CheckCircle size={15} /> 可复现</span>
          <span>实验 #{result?.experiment_id || "--"}</span>
          <span>结果哈希 {result?.result_hash?.slice(0, 16) || "--"}</span>
          <span>数据指纹 {result?.data_fingerprint?.slice(0, 16) || "--"}</span>
        </div>
      </section>

      <aside className="backtest-runlog panel">
        <div className="panel-header"><h2>运行摘要</h2></div>
        <div className="run-summary">
          <Summary label="运行状态" value={running ? "运行中" : result ? "完成" : "等待"} success={Boolean(result) && !running} />
          <Summary label="时间切片" value={number(result?.bars_processed, 0)} />
          <Summary label="订单数" value={number(result?.orders?.length, 0)} />
          <Summary label="成交数" value={number(result?.trades?.length, 0)} />
          <Summary label="选股范围" value={result?.universe?.mode === "all_market" ? "沪深主板全市场" : (result?.universe?.universe || form.symbol)} />
          {result?.universe?.mode === "all_market" && <Summary label="候选 / 信号" value={`${number(result.universe.candidate_days, 0)} / ${number(result.universe.signal_count, 0)}`} />}
          {result?.universe?.mode === "all_market" && <Summary label="扫描分钟线" value={number(result.universe.scanned_minute_bars, 0)} />}
          {result?.universe?.mode === "all_market" && <Summary label="仓位规则" value={`每只 ${percent(result.universe.allocation_ratio)} / 最多 ${result.universe.max_positions} 只`} />}
          {result?.universe?.mode === "all_market" && <Summary label="涨停 / 不可交易跳过" value={`${number(result.universe.limit_up_skipped, 0)} / ${number(result.universe.unavailable_open_skipped, 0)}`} />}
          {result?.universe?.mode === "all_market" && <Summary label="五仓位限制跳过" value={number(result.universe.position_limit_skipped, 0)} />}
          {result?.positioning && <Summary label="建仓方式" value="可用资金满仓（100 股整手）" />}
          {result?.positioning && <Summary label="首笔建仓" value={`${number(result.positioning.entry_quantity, 0)} 股 / ${number(result.positioning.entry_cost)} 元`} />}
          {result?.positioning && <Summary label="初始资金使用率" value={percent(result.positioning.initial_cash_utilization)} />}
          <Summary label="指数ETF基准" value={result?.benchmark_symbol || form.benchmark_symbol} />
          <Summary label="策略 / 基准复权" value={`${result?.adjustment?.execution_price_mode || "none"} / ${result?.adjustment?.benchmark_price_mode || "front_ratio"}`} />
          <Summary label="公司行动（策略 / 基准）" value={`${number(result?.adjustment?.research_action_count, 0)} / ${number(result?.adjustment?.benchmark_action_count, 0)}`} />
          <Summary label="佣金 / 印花税" value={`${number(Number(result?.policy?.commission_rate ?? form.commission_rate) * 100, 3)}%（最低 ${number(result?.policy?.minimum_commission ?? form.minimum_commission)} 元）/ ${number(Number(result?.policy?.stamp_duty_rate ?? form.stamp_duty_rate) * 100, 3)}%`} />
          <Summary label="引擎策略" value="strict_research" />
          <Summary label="随机种子" value="0" />
        </div>
        <div className="inspector-divider"><span>实验约束</span></div>
        <ul className="constraint-list"><li>禁止同 bar 偷看与成交</li><li>原始价成交；除权日处理现金与持仓</li><li>ETF 基准按 front_ratio 总收益计量</li><li>佣金万一、5 元起；卖出印花税万五</li><li>公司行动写入数据指纹</li></ul>
      </aside>
    </div>
  );
}

function TradeTable({ trades }) {
  return <div className="detail-table"><div className="detail-row header"><span>日期</span><span>证券</span><span>方向</span><span>数量</span><span>价格</span><span>费用</span></div>{trades.map((trade) => <div className="detail-row" key={trade.trade_id}><span>{new Date(Number(trade.ts)).toISOString().slice(0, 10)}</span><span>{trade.symbol}</span><span>{trade.side}</span><span>{trade.quantity}</span><span>{number(trade.price)}</span><span>{number(Number(trade.fees?.commission || 0) + Number(trade.fees?.stamp_duty || 0))}</span></div>)}</div>;
}

function EventTable({ events }) {
  return <div className="event-list">{events.slice(-100).map((event, index) => <pre key={index}>{JSON.stringify(event, null, 2)}</pre>)}</div>;
}

function Summary({ label, value, success }) {
  return <div><span>{label}</span><strong className={success ? "success" : ""}>{value}</strong></div>;
}
