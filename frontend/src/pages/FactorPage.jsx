import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import CodeMirror from "@uiw/react-codemirror";
import { python } from "@codemirror/lang-python";
import { oneDark } from "@codemirror/theme-one-dark";
import { ArrowClockwise, Desktop, FloppyDisk, Flask, Funnel, Play, Plus } from "@phosphor-icons/react";
import { DistributionChart, FactorSeriesChart } from "../components/Charts.jsx";
import { ErrorNotice, Field, Loading, Tabs } from "../components/Ui.jsx";
import { api, post, put } from "../lib/api.js";
import { dateLabel, number, percent } from "../lib/format.js";

const FACTOR_CODE = {
  momentum_20: `# 20-bar close-to-close momentum
def momentum(window):
    first = window[0].close
    last = window[-1].close
    if first is None or last is None or first == 0:
        return None
    return last / first - 1`,
  volatility_20: `# 20-bar population volatility of simple returns
def close_volatility(window):
    closes = [bar.close for bar in window]
    returns = [closes[i] / closes[i-1] - 1
               for i in range(1, len(closes))]
    return pstdev(returns)`,
  average_turnover_20: `# 20-bar average traded amount
def average_turnover(window):
    values = [bar.amount for bar in window]
    return sum(values) / len(values)`,
};

const ANALYSIS_TABS = [
  { value: "overview", label: "概览" },
  { value: "series", label: "因子序列" },
  { value: "distribution", label: "分布分析" },
  { value: "robustness", label: "稳健性" },
];

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

export function FactorPage() {
  const [factors, setFactors] = useState([]);
  const [selected, setSelected] = useState("momentum_20");
  const [code, setCode] = useState(FACTOR_CODE.momentum_20);
  const [result, setResult] = useState(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState("overview");
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");
  const [form, setForm] = useState({ symbol: "000001.SZ", start: 20240102, end: 20260717 });
  const [preprocessing, setPreprocessing] = useState({ winsorize: true, standardize: true, direction: "high" });
  const [creating, setCreating] = useState(false);
  const [draftName, setDraftName] = useState("");
  const booted = useRef(false);

  useEffect(() => {
    api("/factors").then((payload) => {
      setFactors(payload.factors);
      const initial = payload.factors?.find((factor) => factor.name === "momentum_20");
      if (initial?.code) setCode(initial.code);
    }).catch((loadError) => setError(loadError.message));
  }, []);

  const run = useCallback(async (factorName = selected) => {
    setRunning(true);
    setError("");
    try {
      setResult(await post("/factors/run", { name: factorName, period: "1d", ...form, ...preprocessing }));
    } catch (runError) {
      setError(runError.message);
    } finally {
      setRunning(false);
    }
  }, [form, preprocessing, selected]);

  useEffect(() => {
    if (booted.current) return;
    booted.current = true;
    run("momentum_20");
  }, [run]);

  const current = factors.find((factor) => factor.name === selected);
  const values = useMemo(() => result?.observations?.map((item) => Number(item.value)) || [], [result]);
  const latest = values.at(-1);
  const filteredFactors = useMemo(() => factors.filter((factor) => {
    const matchesSearch = `${factor.name} ${factor.description}`.toLowerCase().includes(search.toLowerCase());
    const isFundamental = factor.input_fields?.some((field) => !["open", "high", "low", "close", "volume", "amount"].includes(field));
    return matchesSearch && (filter === "all" || (filter === "fundamental" ? isFundamental : !isFundamental));
  }), [factors, filter, search]);
  const robustness = useMemo(() => robustnessStats(values), [values]);

  const chooseFactor = (name) => {
    const chosen = factors.find((factor) => factor.name === name);
    setSelected(name);
    setCode(chosen?.code || FACTOR_CODE[name] || "# 自定义因子\n");
    setPreprocessing((current) => ({ ...current, direction: chosen?.higher_is_better === false ? "low" : "high" }));
    setResult(null);
  };

  const saveFactor = async () => {
    if (!current) return;
    setRunning(true);
    setError("");
    try {
      const payload = await put(`/factors/${current.name}`, { name: current.name, code });
      setFactors((items) => items.map((item) => item.name === current.name ? payload.factor : item));
    } catch (saveError) {
      setError(saveError.message);
    } finally {
      setRunning(false);
    }
  };

  const createFactor = async () => {
    if (draftName.length < 3) return;
    setRunning(true);
    setError("");
    try {
      const payload = await post("/factors", { name: draftName, code: NEW_FACTOR_CODE });
      setFactors((items) => [...items, payload.factor]);
      setSelected(payload.factor.name);
      setCode(payload.factor.code);
      setCreating(false);
      setDraftName("");
      setResult(null);
    } catch (createError) {
      setError(createError.message);
    } finally {
      setRunning(false);
    }
  };

  const openInVSCode = async () => {
    if (!current) return;
    setRunning(true);
    setError("");
    try {
      await post(`/factors/${current.name}/open-editor`, {});
    } catch (openError) {
      setError(openError.message);
    } finally {
      setRunning(false);
    }
  };

  const syncFromVSCode = async () => {
    if (!current) return;
    setRunning(true);
    setError("");
    try {
      const payload = await post(`/factors/${current.name}/sync-editor`, {});
      setCode(payload.definition.code);
      setFactors((items) => items.map((item) => item.name === current.name ? payload.definition : item));
    } catch (syncError) {
      setError(syncError.message);
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="factor-workspace">
      <header className="page-toolbar">
        <div><span className="eyebrow">因子研究</span><h1>{current?.description || "20日动量因子"}</h1></div>
        <div className="toolbar-actions">
          <button className="secondary-button" type="button" onClick={() => setCreating(true)} disabled={running}><Plus size={15} /> 新建因子</button>
          <button className="secondary-button" type="button" onClick={openInVSCode} disabled={running || !current}><Desktop size={15} /> VS Code</button>
          <button className="secondary-button" type="button" onClick={syncFromVSCode} disabled={running || !current}><ArrowClockwise size={15} /> 同步</button>
          <button className="secondary-button" type="button" onClick={saveFactor} disabled={running || !current}><FloppyDisk size={15} /> 保存因子定义</button>
          <button className="primary-button" type="button" onClick={() => run()} disabled={running}>
            {running ? <Loading label="运行分析" /> : <><Play size={15} weight="fill" /> 运行因子分析</>}
          </button>
        </div>
      </header>

      <aside className="factor-catalog panel">
        <div className="panel-header"><h2>因子库</h2><Funnel size={15} /></div>
        <label className="catalog-search"><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="搜索因子名称 / 字段" /></label>
        <div className="filter-chips"><button className={filter === "all" ? "active" : ""} type="button" onClick={() => setFilter("all")}>全部类型</button><button className={filter === "price" ? "active" : ""} type="button" onClick={() => setFilter("price")}>量价</button><button className={filter === "fundamental" ? "active" : ""} type="button" onClick={() => setFilter("fundamental")}>基本面</button></div>
        <div className="factor-list">
          {filteredFactors.map((factor) => (
            <button key={factor.name} type="button" className={selected === factor.name ? "active" : ""} onClick={() => chooseFactor(factor.name)}>
              <span className="factor-icon"><Flask size={15} /></span>
              <span><strong>{factor.name}</strong><small>{factor.description}</small></span>
              <em>{factor.lookback}D</em>
            </button>
          ))}
        </div>
        <div className="catalog-foot">显示 {filteredFactors.length} / {factors.length} 个已注册因子 · Python SDK</div>
      </aside>

      <section className="factor-code panel">
        <div className="panel-header"><h2>可执行因子定义</h2><span className="language-badge">Python · 保存生效</span></div>
        <CodeMirror value={code} onChange={setCode} height="100%" theme={oneDark} extensions={[python()]} editable className="code-editor" />
      </section>

      <aside className="factor-config panel">
        <div className="panel-header"><h2>因子配置</h2></div>
        <div className="config-body">
          <Field label="研究标的"><input value={form.symbol} onChange={(event) => setForm({ ...form, symbol: event.target.value.toUpperCase() })} /></Field>
          <Field label="日期范围"><div className="date-pair"><input type="date" value={dateLabel(form.start)} onChange={(event) => setForm({ ...form, start: Number(event.target.value.replaceAll("-", "")) })} /><span>→</span><input type="date" value={dateLabel(form.end)} onChange={(event) => setForm({ ...form, end: Number(event.target.value.replaceAll("-", "")) })} /></div></Field>
          <div className="field-row"><Field label="频率"><select value="1d" disabled><option value="1d">日频</option></select></Field><Field label="回看窗口"><input value={`${current?.lookback || 20} bars`} readOnly /></Field></div>
          <div className="config-block"><h3>数据预处理</h3><label className="checkbox-row"><input type="checkbox" checked={preprocessing.winsorize} onChange={(event) => setPreprocessing({ ...preprocessing, winsorize: event.target.checked })} /> 去极值 Winsorize（1%）</label><label className="checkbox-row"><input type="checkbox" checked={preprocessing.standardize} onChange={(event) => setPreprocessing({ ...preprocessing, standardize: event.target.checked })} /> 标准化 Z-Score</label></div>
          <div className="config-block"><h3>中性化（需要多标的横截面）</h3><label className="checkbox-row" title="当前单标的研究不支持行业中性化"><input type="checkbox" disabled /> 行业中性</label><label className="checkbox-row" title="当前单标的研究不支持市值中性化"><input type="checkbox" disabled /> 市值中性</label></div>
          <div className="config-block"><h3>方向</h3><select value={preprocessing.direction} onChange={(event) => setPreprocessing({ ...preprocessing, direction: event.target.value })}><option value="high">值越大越优</option><option value="low">值越小越优（反向）</option></select></div>
          <ErrorNotice message={error} onClose={() => setError("")} />
        </div>
      </aside>

      <section className="factor-analysis panel">
        <Tabs items={ANALYSIS_TABS} value={activeTab} onChange={setActiveTab} />
        <div className="factor-metrics">
          <Metric label="覆盖率" value={percent(result?.coverage_ratio)} />
          <Metric label="观测数" value={number(result?.summary?.count, 0)} />
          <Metric label="最新因子值" value={number(latest, 4)} />
          <Metric label="均值" value={number(result?.summary?.mean, 4)} />
          <Metric label="最小值" value={number(result?.summary?.minimum, 4)} />
          <Metric label="最大值" value={number(result?.summary?.maximum, 4)} />
        </div>
        {activeTab === "overview" && <div className="factor-charts"><div><h3>因子时间序列</h3><FactorSeriesChart observations={result?.observations} /></div><div><h3>因子分布（10组）</h3><DistributionChart observations={result?.observations} /></div></div>}
        {activeTab === "series" && <div className="factor-charts single"><div><h3>因子时间序列</h3><FactorSeriesChart observations={result?.observations} /></div></div>}
        {activeTab === "distribution" && <div className="factor-charts single"><div><h3>因子分布（10组）</h3><DistributionChart observations={result?.observations} /></div></div>}
        {activeTab === "robustness" && <div className="robustness-grid"><Metric label="前半段均值" value={number(robustness.firstMean, 4)} /><Metric label="后半段均值" value={number(robustness.secondMean, 4)} /><Metric label="均值漂移" value={number(robustness.meanShift, 4)} /><Metric label="全样本标准差" value={number(robustness.deviation, 4)} /></div>}
        <div className="analysis-status">
          {running ? <Loading label="正在计算因子观测" /> : result ? <><span className="success-dot" /> 计算完成 · 实验 #{result.experiment_id} · 哈希 {result.result_hash?.slice(0, 12)}</> : "等待运行"}
        </div>
      </section>
      {creating && <div className="workspace-overlay"><div className="overlay-dialog definition-dialog"><div className="overlay-header"><div><span className="eyebrow">因子库</span><h2>新建因子</h2></div><button type="button" onClick={() => setCreating(false)}>×</button></div><div className="definition-dialog-body"><Field label="唯一标识（小写字母、数字、下划线）"><input autoFocus value={draftName} onChange={(event) => setDraftName(event.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ""))} placeholder="my_factor" /></Field><p>创建后可在内置编辑器或 VS Code 中修改，并从外部工作区同步回来。</p><div className="dialog-actions"><button className="secondary-button" type="button" onClick={() => setCreating(false)}>取消</button><button className="primary-button" type="button" onClick={createFactor} disabled={running || draftName.length < 3}>{running ? <Loading label="创建" /> : "创建并编辑"}</button></div></div></div></div>}
    </div>
  );
}

function Metric({ label, value }) {
  return <div><span>{label}</span><strong>{value}</strong></div>;
}

function robustnessStats(values) {
  if (!values.length) return {};
  const midpoint = Math.max(1, Math.floor(values.length / 2));
  const first = values.slice(0, midpoint);
  const second = values.slice(midpoint);
  const mean = (items) => items.length ? items.reduce((sum, value) => sum + value, 0) / items.length : 0;
  const fullMean = mean(values);
  const firstMean = mean(first);
  const secondMean = mean(second);
  return {
    firstMean,
    secondMean,
    meanShift: secondMean - firstMean,
    deviation: Math.sqrt(mean(values.map((value) => (value - fullMean) ** 2))),
  };
}
