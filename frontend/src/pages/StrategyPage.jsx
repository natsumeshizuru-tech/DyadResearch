import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import CodeMirror from "@uiw/react-codemirror";
import { python } from "@codemirror/lang-python";
import { oneDark } from "@codemirror/theme-one-dark";
import {
  CaretDown,
  CaretRight,
  ClockCounterClockwise,
  Code,
  FileCode,
  Folder,
  Funnel,
  FloppyDisk,
  ArrowClockwise,
  Desktop,
  Play,
  Plus,
  SlidersHorizontal,
  Trash,
} from "@phosphor-icons/react";
import { DrawdownChart, EquityChart } from "../components/Charts.jsx";
import { ErrorNotice, Field, Loading, Tabs } from "../components/Ui.jsx";
import { api, post, put, remove } from "../lib/api.js";
import { dateLabel, number, percent } from "../lib/format.js";

const DEFAULT_CODE = `# 双均线择时（PIT-safe）
# 仅使用 t-1 可获得的数据，避免未来函数

from dyadresearch import DataAPI, Backtest

def initialize(context):
    context.universe = "000001.SZ"
    context.start_date = "2024-01-02"
    context.end_date = "2026-07-17"
    context.fast = 5
    context.slow = 20
    context.quantity = 1000

def on_bars(context, bars):
    history = context.history(context.universe, context.slow)
    fast_ma = history.close.tail(context.fast).mean()
    slow_ma = history.close.mean()
    position = context.position(context.universe)

    if fast_ma > slow_ma and position == 0:
        context.order_target(context.universe, context.quantity)
    elif fast_ma < slow_ma and position > 0:
        context.order_target(context.universe, 0)

def prepare_data(context):
    """Point-in-time inputs only; every feature is lagged by one bar."""
    fields = ["close", "volume", "turnover_rate", "total_mv"]
    raw = DataAPI.history(
        symbols=context.universe,
        fields=fields,
        start=context.start_date,
        end=context.end_date,
        adjust="pre",
    )
    raw["ret_1d"] = raw.close.pct_change()
    raw["momentum_20d"] = raw.close.pct_change(20).shift(1)
    raw["volatility_20d"] = raw.ret_1d.rolling(20).std().shift(1)
    raw["liquidity_20d"] = raw.turnover_rate.rolling(20).mean().shift(1)
    return raw.dropna()

def build_signal(frame):
    """Combine momentum and low-volatility ranks into one research signal."""
    momentum_rank = frame.momentum_20d.rank(pct=True)
    low_vol_rank = 1.0 - frame.volatility_20d.rank(pct=True)
    liquidity_filter = frame.liquidity_20d > frame.liquidity_20d.quantile(0.2)
    score = 0.6 * momentum_rank + 0.4 * low_vol_rank
    return score.where(liquidity_filter)

def before_trading(context, date):
    frame = prepare_data(context)
    signal = build_signal(frame)
    context.record("signal", signal.iloc[-1])

def after_trading(context, date):
    context.record("cash", context.cash)
    context.record("net_value", context.portfolio_value / context.initial_cash)
`;

const STRATEGY_CODE = {
  moving_average_cross: DEFAULT_CODE,
  buy_and_hold: `STRATEGY = {
    "type": "buy_and_hold",
    "title": "买入并持有",
    "description": "下一可交易 bar 开盘按整手尽可能满仓买入，并持有到回测结束。",
    "parameters": {"allocation_ratio": 1.0},
}
`,
};

const RESULT_TABS = [
  { value: "logs", label: "日志" },
  { value: "trades", label: "历史成交" },
];

const NEW_STRATEGY_CODE = `STRATEGY = {
    "type": "buy_and_hold",
    "title": "我的新策略",
    "description": "在这里修改策略说明和结构化参数。",
    "parameters": {"allocation_ratio": 1.0},
}
`;

const NEW_FACTOR_CODE = `FACTOR = {
    "title": "我的新因子",
    "description": "可运行的量价表达式因子。",
    "expression": "close[-1] / close[0] - 1",
    "input_fields": ["close"],
    "lookback": 20,
    "frequency": "1d",
    "higher_is_better": True,
}
`;

export function StrategyPage() {
  const [strategy, setStrategy] = useState("moving_average_cross");
  const [resourceKind, setResourceKind] = useState("strategy");
  const [selectedFactor, setSelectedFactor] = useState("");
  const [editorCode, setEditorCode] = useState(DEFAULT_CODE);
  const [strategies, setStrategies] = useState([]);
  const [factors, setFactors] = useState([]);
  const [result, setResult] = useState(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [bottomTab, setBottomTab] = useState("logs");
  const [strategySearch, setStrategySearch] = useState("");
  const [factorSearch, setFactorSearch] = useState("");
  const [saving, setSaving] = useState(false);
  const [creating, setCreating] = useState("");
  const [draftName, setDraftName] = useState("");
  const [form, setForm] = useState({
    symbol: "000001.SZ",
    benchmark_symbol: "510300.SH",
    period: "1d",
    start: 20240102,
    end: 20260717,
    fast: 5,
    slow: 20,
    quantity: 1000,
    initial_cash: 1000000,
    commission_rate: 0.0001,
    minimum_commission: 5,
    stamp_duty_rate: 0.0005,
    universe_mode: "single",
  });
  const booted = useRef(false);

  useEffect(() => {
    Promise.all([api("/strategies"), api("/factors")])
      .then(([strategyPayload, factorPayload]) => {
        const loadedStrategies = strategyPayload.strategies || [];
        setStrategies(loadedStrategies);
        setFactors(factorPayload.factors || []);
        const initial = loadedStrategies.find((item) => item.name === "moving_average_cross");
        if (initial?.code) setEditorCode(initial.code);
      })
      .catch((loadError) => setError(loadError.message));
  }, []);

  const run = useCallback(async () => {
    setRunning(true);
    setError("");
    try {
      const payload = await post("/backtests/run", {
        strategy,
        policy: "strict_research",
        ...form,
      });
      setResult(payload);
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
  const visibleStrategies = useMemo(() => strategies.filter((item) => `${item.title} ${item.name}`.toLowerCase().includes(strategySearch.toLowerCase())), [strategies, strategySearch]);
  const visibleFactors = useMemo(() => factors.filter((item) => `${item.name} ${item.description}`.toLowerCase().includes(factorSearch.toLowerCase())), [factors, factorSearch]);
  const currentDefinition = resourceKind === "strategy" ? strategies.find((item) => item.name === strategy) : factors.find((item) => item.name === selectedFactor);
  const strategyImplementation = strategies.find((item) => item.name === strategy)?.implementation || strategy;
  const chooseStrategy = (name) => {
    const definition = strategies.find((item) => item.name === name);
    setStrategy(name);
    setResourceKind("strategy");
    setEditorCode(definition?.code || STRATEGY_CODE[name] || DEFAULT_CODE);
    const parameters = definition?.config?.parameters || {};
    setForm((current) => ({
      ...current,
      fast: Number(parameters.fast ?? current.fast),
      slow: Number(parameters.slow ?? current.slow),
      quantity: Number(parameters.quantity ?? current.quantity),
      ...(definition?.implementation === "low_volume_ratio_momentum" ? { symbol: "603580.SH", period: "1m", start: 20260701, universe_mode: "all_market" } : { universe_mode: "single" }),
    }));
    setResult(null);
  };
  const chooseFactor = (name) => {
    const definition = factors.find((item) => item.name === name);
    setSelectedFactor(name);
    setResourceKind("factor");
    setEditorCode(definition?.code || NEW_FACTOR_CODE);
  };
  const changeForm = (key, value) => { updateForm(setForm, key, value); setResult(null); };

  const saveDefinition = async () => {
    if (!currentDefinition) return;
    setSaving(true);
    setError("");
    setMessage("");
    try {
      const payload = await put(`/${resourceKind === "strategy" ? "strategies" : "factors"}/${currentDefinition.name}`, { name: currentDefinition.name, code: editorCode });
      const saved = payload[resourceKind];
      if (resourceKind === "strategy") setStrategies((items) => items.map((item) => item.name === saved.name ? saved : item));
      else setFactors((items) => items.map((item) => item.name === saved.name ? saved : item));
    } catch (saveError) {
      setError(saveError.message);
    } finally {
      setSaving(false);
    }
  };

  const openInVSCode = async () => {
    if (!currentDefinition) return;
    setSaving(true);
    setError("");
    setMessage("");
    try {
      const payload = await post(`/${resourceKind === "strategy" ? "strategies" : "factors"}/${currentDefinition.name}/open-editor`, {});
      setMessage(`已在 VS Code 打开 ${payload.path}`);
    } catch (openError) {
      setError(openError.message);
    } finally {
      setSaving(false);
    }
  };

  const syncFromVSCode = async () => {
    if (!currentDefinition) return;
    setSaving(true);
    setError("");
    try {
      const payload = await post(`/${resourceKind === "strategy" ? "strategies" : "factors"}/${currentDefinition.name}/sync-editor`, {});
      const saved = payload.definition;
      setEditorCode(saved.code);
      if (resourceKind === "strategy") setStrategies((items) => items.map((item) => item.name === saved.name ? saved : item));
      else setFactors((items) => items.map((item) => item.name === saved.name ? saved : item));
      setMessage(`已从 VS Code 同步 ${payload.path}`);
    } catch (syncError) {
      setError(syncError.message);
    } finally {
      setSaving(false);
    }
  };

  const createDefinition = async () => {
    if (!draftName.trim()) return;
    setSaving(true);
    setError("");
    try {
      const payload = await post(`/${creating === "strategy" ? "strategies" : "factors"}`, { name: draftName.trim().toLowerCase(), code: creating === "strategy" ? NEW_STRATEGY_CODE : NEW_FACTOR_CODE });
      const created = payload[creating];
      if (creating === "strategy") {
        setStrategies((items) => [...items, created]);
        setCreating("");
        setDraftName("");
        setStrategy(created.name);
        setResourceKind("strategy");
        setEditorCode(created.code);
        setResult(null);
      } else {
        setFactors((items) => [...items, created]);
        setCreating("");
        setDraftName("");
        setSelectedFactor(created.name);
        setResourceKind("factor");
        setEditorCode(created.code);
      }
    } catch (createError) {
      setError(createError.message);
    } finally {
      setSaving(false);
    }
  };

  const deleteDefinition = async () => {
    if (!currentDefinition || currentDefinition.is_builtin) return;
    setSaving(true);
    setError("");
    try {
      await remove(`/${resourceKind === "strategy" ? "strategies" : "factors"}/${currentDefinition.name}`);
      if (resourceKind === "strategy") {
        const remaining = strategies.filter((item) => item.name !== currentDefinition.name);
        setStrategies(remaining);
        chooseStrategy(remaining[0]?.name || "moving_average_cross");
      } else {
        const remaining = factors.filter((item) => item.name !== currentDefinition.name);
        setFactors(remaining);
        if (remaining[0]) chooseFactor(remaining[0].name);
      }
    } catch (deleteError) {
      setError(deleteError.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="strategy-workspace">
      <header className="workspace-tabs">
        <button type="button" className="workspace-tab active">{currentDefinition?.title || currentDefinition?.name || "研究定义"}.{resourceKind === "strategy" ? "strategy.py" : "factor.py"}</button>
      </header>

      <aside className="strategy-sidebar">
        <div className="sidebar-title"><span>策略研究</span><SlidersHorizontal size={15} /></div>
        <div className="sidebar-section">
          <div className="sidebar-section-heading"><h3>项目</h3><button type="button" title="新建策略" onClick={() => { setCreating("strategy"); setDraftName(""); }}><Plus size={13} /> 新建</button></div>
          <label className="sidebar-search"><Funnel size={14} /><input value={strategySearch} onChange={(event) => setStrategySearch(event.target.value)} placeholder="搜索文件" /></label>
          <div className="tree">
            <TreeRow icon={Folder} label="我的研究" expanded />
            <TreeRow icon={Folder} label="策略" level={1} expanded />
            {visibleStrategies.map((item) => <TreeRow key={item.name} icon={FileCode} label={`${item.title}.py`} level={2} active={strategy === item.name} onClick={() => chooseStrategy(item.name)} />)}
          </div>
        </div>
        <div className="sidebar-section factor-library">
          <div className="sidebar-section-heading"><h3>因子库（可复用）</h3><button type="button" title="新建因子" onClick={() => { setCreating("factor"); setDraftName(""); }}><Plus size={13} /> 新建</button></div>
          <label className="sidebar-search"><Funnel size={14} /><input value={factorSearch} onChange={(event) => setFactorSearch(event.target.value)} placeholder="搜索因子" /></label>
          <FactorGroup title="研究因子" items={visibleFactors} selected={selectedFactor} onSelect={chooseFactor} />
        </div>
      </aside>

      <section className="strategy-editor">
        <div className="editor-toolbar">
          <div className="editor-history"><ClockCounterClockwise size={15} /></div>
          <span className="editor-language">Python 结构化定义 · 保存后立即生效 <CaretDown size={12} /></span>
          <div className="editor-actions"><span>v{currentDefinition?.version || 1}</span><button type="button" onClick={openInVSCode} disabled={saving || !currentDefinition}><Desktop size={13} /> VS Code</button><button type="button" onClick={syncFromVSCode} disabled={saving || !currentDefinition}><ArrowClockwise size={13} /> 同步</button><button type="button" onClick={saveDefinition} disabled={saving || !currentDefinition}><FloppyDisk size={13} /> 保存</button><button type="button" onClick={deleteDefinition} disabled={saving || !currentDefinition || currentDefinition?.is_builtin} title={currentDefinition?.is_builtin ? "内置定义不可删除，但可以修改" : "删除定义"}><Trash size={13} /> 删除</button></div>
        </div>
        <CodeMirror
          value={editorCode}
          onChange={setEditorCode}
          height="100%"
          theme={oneDark}
          extensions={[python()]}
          editable
          basicSetup={{ foldGutter: true, highlightActiveLine: true, bracketMatching: true }}
          className="code-editor"
        />
      </section>

      <aside className="backtest-inspector">
        <div className="inspector-title">回测配置</div>
        <div className="inspector-form">
          <Field label="回测范围">
            <div className="date-pair">
              <input type="date" value={dateLabel(form.start)} onInput={(event) => changeForm("start", event.currentTarget.value.replaceAll("-", ""))} />
              <span>→</span>
              <input type="date" value={dateLabel(form.end)} onInput={(event) => changeForm("end", event.currentTarget.value.replaceAll("-", ""))} />
            </div>
          </Field>
          <Field label="选股范围"><select value={form.universe_mode} onChange={(event) => { const mode = event.target.value; setForm((current) => ({ ...current, universe_mode: mode, ...(mode === "all_market" ? { period: "1m" } : {}) })); setResult(null); }}><option value="single">单标的</option><option value="all_market" disabled={strategies.find((item) => item.name === strategy)?.implementation !== "low_volume_ratio_momentum"}>沪深主板全市场（选股策略）</option></select></Field>
          <Field label="研究标的"><input value={form.universe_mode === "all_market" ? "沪深主板全市场" : form.symbol} disabled={form.universe_mode === "all_market"} onChange={(event) => changeForm("symbol", event.target.value.toUpperCase())} /></Field>
          <div className="field-row">
            <Field label="频率"><select value={form.period} disabled={form.universe_mode === "all_market"} onChange={(event) => { setForm({ ...form, period: event.target.value, start: event.target.value === "1m" ? 20250717 : 20240102 }); setResult(null); }}><option value="1d">日频</option><option value="1m">分钟</option><option value="1q">季度</option><option value="1y">年度</option></select></Field>
            <Field label="策略模型"><select value={strategy} onChange={(event) => chooseStrategy(event.target.value)}>{strategies.map((item) => <option key={item.name} value={item.name}>{item.title}</option>)}</select></Field>
          </div>
          <Field label="指数ETF基准"><input value={form.benchmark_symbol} onChange={(event) => changeForm("benchmark_symbol", event.target.value.toUpperCase())} /></Field>
          <Field label="初始资金"><input type="number" value={form.initial_cash} onChange={(event) => changeForm("initial_cash", event.target.value)} /></Field>
          <div className="inspector-divider"><span>策略参数</span></div>
          {strategyImplementation === "moving_average_cross" && <div className="field-row thirds">
            <Field label="短均线"><input type="number" value={form.fast} onChange={(event) => changeForm("fast", event.target.value)} /></Field>
            <Field label="长均线"><input type="number" value={form.slow} onChange={(event) => changeForm("slow", event.target.value)} /></Field>
            <Field label="每次交易数量"><input type="number" value={form.quantity} onChange={(event) => changeForm("quantity", event.target.value)} /></Field>
          </div>}
          {strategyImplementation === "buy_and_hold" && <div className="config-block"><h3>满仓买入并持有</h3><p>使用 100% 可用资金，扣除佣金后按 100 股整手尽可能满仓；下一可交易 bar 开盘成交。</p></div>}
          {strategyImplementation === "low_volume_ratio_momentum" && <div className="config-block"><h3>五等分仓位</h3><p>单票使用总资产的 20%，最多同时持有 5 只。</p></div>}
          <div className="inspector-divider"><span>交易与成本</span></div>
          <div className="field-row">
            <Field label="佣金率 (%)"><input type="number" min="0" step="0.001" value={form.commission_rate * 100} onChange={(event) => changeForm("commission_rate", Number(event.target.value) / 100)} /></Field>
            <Field label="印花税率 (%)"><input type="number" min="0" step="0.001" value={form.stamp_duty_rate * 100} onChange={(event) => changeForm("stamp_duty_rate", Number(event.target.value) / 100)} /></Field>
          </div>
          <Field label="最低佣金（元）"><input type="number" min="0" step="0.1" value={form.minimum_commission} onChange={(event) => changeForm("minimum_commission", event.target.value)} /></Field>
          <button className="primary-button run-button" type="button" onClick={run} disabled={running}>
            {running ? <Loading label="运行回测" /> : <><Play size={16} weight="fill" /> 运行回测</>}
          </button>
          {message && <p className="success-notice">{message}</p>}
          <ErrorNotice message={error} onClose={() => setError("")} />
        </div>

        <div className="result-summary">
          <div className="result-heading"><span>回测结果</span><small>{dateLabel(form.start)} 至 {dateLabel(form.end)}</small></div>
          <div className="metric-strip">
            <Metric label="总收益" value={percent(metrics.total_return)} />
            <Metric label="年化收益" value={percent(metrics.annualized_return)} />
            <Metric label="Sharpe" value={number(metrics.sharpe)} />
            <Metric label="最大回撤" value={percent(metrics.max_drawdown)} negative />
          </div>
          <div className="equity-region"><EquityChart equity={result?.equity} benchmark={result?.benchmark} /></div>
          <div className="drawdown-region"><span>回撤 (%)</span><DrawdownChart equity={result?.equity} /></div>
        </div>
      </aside>

      <section className="strategy-console">
        <Tabs items={RESULT_TABS.map((item) => ({ ...item, count: item.value === "trades" ? result?.trades?.length : undefined }))} value={bottomTab} onChange={setBottomTab} />
        <ConsoleContent tab={bottomTab} result={result} running={running} symbol={form.symbol} />
      </section>
      {creating && <div className="workspace-overlay"><div className="overlay-dialog definition-dialog"><div className="overlay-header"><div><span className="eyebrow">研究目录</span><h2>新建{creating === "strategy" ? "策略" : "因子"}</h2></div><button type="button" onClick={() => setCreating("")}>×</button></div><div className="definition-dialog-body"><Field label="唯一标识（小写字母、数字、下划线）"><input autoFocus value={draftName} onChange={(event) => setDraftName(event.target.value.replace(/[^a-z0-9_]/g, ""))} placeholder={creating === "strategy" ? "my_strategy" : "my_factor"} /></Field><p>创建后可直接修改结构化 Python 定义；保存成功后运行器会使用新版本。</p><div className="dialog-actions"><button className="secondary-button" type="button" onClick={() => setCreating("")}>取消</button><button className="primary-button" type="button" onClick={createDefinition} disabled={saving || draftName.length < 3}>{saving ? <Loading label="创建" /> : "创建并编辑"}</button></div></div></div></div>}
    </div>
  );
}

function TreeRow({ icon: Icon, label, level = 0, expanded = false, active = false, onClick }) {
  const content = (
    <>
      {Icon === Folder && (expanded ? <CaretDown size={11} /> : <CaretRight size={11} />)}
      {Icon !== Folder && <span className="tree-indent" />}
      <Icon size={14} weight={active ? "fill" : "regular"} />
      <span>{label}</span>
    </>
  );
  return onClick ? <button type="button" className={`tree-row ${active ? "active" : ""}`} style={{ paddingLeft: 8 + level * 16 }} onClick={onClick}>{content}</button> : <div className="tree-row" style={{ paddingLeft: 8 + level * 16 }}>{content}</div>;
}

function FactorGroup({ title, items, selected, onSelect }) {
  return (
    <div className="factor-group">
      <div className="factor-group-title"><CaretDown size={11} /> {title}</div>
      {items.map((item) => <button type="button" className={`factor-item ${selected === item.name ? "active" : ""}`} key={item.name} onClick={() => onSelect(item.name)}><Code size={12} /> {item.name}<span>因子</span></button>)}
    </div>
  );
}

function Metric({ label, value, negative }) {
  return <div className="metric"><span>{label}</span><strong className={negative ? "negative" : ""}>{value}</strong></div>;
}

function ConsoleContent({ tab, result, running, symbol }) {
  if (running) return <div className="console-empty"><Loading label="正在读取只读 SQLite 并运行事件驱动回测" /></div>;
  if (!result) return <div className="console-empty">运行策略后显示可复现实验日志。</div>;
  if (tab === "trades") {
    return (
      <div className="console-table">
        <div className="console-row header"><span>时间</span><span>标的</span><span>方向</span><span>数量</span><span>价格</span></div>
        {(result.trades || []).slice(-8).map((trade) => (
          <div className="console-row" key={trade.trade_id}>
            <span>{new Date(Number(trade.ts)).toISOString().slice(0, 10)}</span><span>{trade.symbol}</span><span>{trade.side}</span><span>{trade.quantity}</span><span>{number(trade.price)}</span>
          </div>
        ))}
      </div>
    );
  }
  const logs = [
    ["INFO", "Backtest", `回测开始：${result.bars_processed} 个时间切片`],
    ["INFO", "Universe", result.universe?.mode === "all_market" ? `沪深主板全市场；日线候选 ${result.universe.candidate_days}；分钟信号 ${result.universe.signal_count}；涨停跳过 ${result.universe.limit_up_skipped}；不可交易跳过 ${result.universe.unavailable_open_skipped}` : `研究标的：${symbol}；指数ETF基准：${result.benchmark_symbol}`],
    ["INFO", "Position", result.positioning ? `满仓建仓 ${number(result.positioning.entry_quantity, 0)} 股；初始资金使用率 ${percent(result.positioning.initial_cash_utilization)}` : result.universe?.mode === "all_market" ? `每只 ${percent(result.universe.allocation_ratio)} 总仓位；最多 ${result.universe.max_positions} 只` : "单标的仓位规则"],
    ["INFO", "Policy", "strict_research；下一 bar 成交；T+1；佣金万一且 5 元起；卖出印花税万五"],
    ["INFO", "Result", `总收益 ${percent(result.metrics?.total_return)}，最大回撤 ${percent(result.metrics?.max_drawdown)}`],
    ["INFO", "Reproduce", `结果哈希 ${result.result_hash?.slice(0, 16)}`],
  ];
  return (
    <div className="log-list">
      {logs.map((log, index) => <div key={index}><span>{new Date().toLocaleTimeString("zh-CN", { hour12: false })}</span><span>{log[0]}</span><span>{log[1]}</span><span>{log[2]}</span></div>)}
    </div>
  );
}

function updateForm(setForm, key, value) {
  setForm((current) => ({ ...current, [key]: ["symbol", "benchmark_symbol", "period", "universe_mode"].includes(key) ? value : Number(value) }));
}
