import { useEffect, useMemo, useState } from "react";
import { ArrowSquareOut, ArrowsClockwise, CheckCircle, DownloadSimple, FileText, Funnel, Hash, Package } from "@phosphor-icons/react";
import { ErrorNotice, Loading } from "../components/Ui.jsx";
import { api, post } from "../lib/api.js";
import { number, percent } from "../lib/format.js";

export function ReportsPage() {
  const [experiments, setExperiments] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [kind, setKind] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [report, setReport] = useState(null);
  const [building, setBuilding] = useState(false);
  const [release, setRelease] = useState(null);
  const [exporting, setExporting] = useState(false);

  const load = () => {
    setLoading(true);
    api(`/experiments${kind ? `?kind=${kind}` : ""}`)
      .then((payload) => {
        setExperiments(payload.experiments);
        setSelectedId((current) => current || payload.experiments[0]?.id || null);
      })
      .catch((loadError) => setError(loadError.message))
      .finally(() => setLoading(false));
  };

  useEffect(load, [kind]);
  const selected = useMemo(() => experiments.find((item) => item.id === selectedId) || experiments[0], [experiments, selectedId]);

  const build = async () => {
    if (!selected) return;
    setError("");
    setBuilding(true);
    try {
      setReport(await post(`/reports/build/${selected.id}`, {}));
    } catch (buildError) {
      setError(buildError.message);
    } finally {
      setBuilding(false);
    }
  };

  const chooseExperiment = (id) => { setSelectedId(id); setReport(null); setRelease(null); };
  const exportRelease = async () => {
    if (!selected || selected.kind !== "backtest") return;
    setError(""); setExporting(true);
    try {
      setRelease(await post("/releases/export", { experiment_id: selected.id }));
    } catch (exportError) {
      setError(exportError.message);
    } finally { setExporting(false); }
  };

  return (
    <div className="reports-workspace">
      <header className="page-toolbar">
        <div><span className="eyebrow">结果仓库</span><h1>实验与报告</h1></div>
        <div className="toolbar-actions"><button className="secondary-button" type="button" onClick={load}><ArrowsClockwise size={15} /> 刷新</button><button className="secondary-button" type="button" disabled={selected?.kind !== "backtest" || exporting} onClick={exportRelease}>{exporting ? <Loading label="导出发布包" /> : <><Package size={15} /> 导出策略发布包</>}</button><button className="primary-button" type="button" disabled={!selected || building} onClick={build}>{building ? <Loading label="生成报告" /> : <><FileText size={15} /> 生成报告</>}</button></div>
      </header>

      <aside className="report-list panel">
        <div className="panel-header"><h2>实验记录</h2><Funnel size={15} /></div>
        <div className="report-filters"><button type="button" className={!kind ? "active" : ""} onClick={() => setKind("")}>全部</button><button type="button" className={kind === "backtest" ? "active" : ""} onClick={() => setKind("backtest")}>回测</button><button type="button" className={kind === "factor" ? "active" : ""} onClick={() => setKind("factor")}>因子</button></div>
        {loading ? <div className="list-loading"><Loading /></div> : (
          <div className="experiment-list">
            {experiments.map((experiment) => <button key={experiment.id} type="button" className={selected?.id === experiment.id ? "active" : ""} onClick={() => chooseExperiment(experiment.id)}><span className={`experiment-kind ${experiment.kind}`}>{experiment.kind === "backtest" ? "回" : "因"}</span><span><strong>{experiment.name}</strong><small>#{experiment.id} · {experiment.created_at.replace("T", " ").slice(0, 19)}</small></span><CheckCircle size={15} /></button>)}
          </div>
        )}
      </aside>

      <section className="report-detail panel">
        <ErrorNotice message={error} onClose={() => setError("")} />
        {selected ? <ExperimentDetail experiment={selected} report={report} release={release} /> : <div className="empty-state"><FileText size={30} /><strong>暂无实验</strong><span>先在因子研究或回测实验中运行一次。</span></div>}
      </section>
    </div>
  );
}

function ExperimentDetail({ experiment, report, release }) {
  const metrics = experiment.metrics || {};
  const metricItems = experiment.kind === "factor" ? [
    ["覆盖率", percent(metrics.coverage_ratio)], ["样本数", number(metrics.count, 0)], ["均值", number(metrics.mean, 6)], ["最小值", number(metrics.minimum, 6)], ["最大值", number(metrics.maximum, 6)],
  ] : [
    ["总收益", percent(metrics.total_return)], ["年化收益", percent(metrics.annualized_return)], ["Sharpe", number(metrics.sharpe)], ["最大回撤", percent(metrics.max_drawdown)], ["成交数", number(metrics.trade_count, 0)],
  ];
  return (
    <>
      <div className="report-title"><div><span className={`experiment-kind ${experiment.kind}`}>{experiment.kind === "backtest" ? "回测" : "因子"}</span><h2>{experiment.name}</h2></div><span className="repro-badge"><CheckCircle size={15} /> 可复现</span></div>
      <div className="report-metrics">
        {metricItems.map(([label, value]) => <ReportMetric key={label} label={label} value={value} />)}
      </div>
      <div className="report-grid">
        <section><h3>实验配置</h3><KeyValueTable values={experiment.config} /></section>
        <section><h3>可复现信息</h3><div className="hash-card"><Hash size={18} /><div><span>结果哈希</span><code>{experiment.result_hash}</code></div></div><div className="hash-card"><Hash size={18} /><div><span>数据指纹</span><code>{experiment.data_fingerprint}</code></div></div></section>
      </div>
      <div className="report-footer"><span>实验编号 #{experiment.id}</span><span>创建时间 {experiment.created_at}</span><span>{report?.html ? "HTML / JSON / CSV 已生成" : "报告将写入 reports/generated"}</span></div>
      {report?.urls && <div className="report-artifacts"><a href={report.urls.html} target="_blank" rel="noreferrer"><ArrowSquareOut size={14} /> 打开 HTML</a><a href={report.urls.json} download><DownloadSimple size={14} /> 下载 JSON</a><a href={report.urls.csv} download><DownloadSimple size={14} /> 下载 CSV</a></div>}
      {release && <div className="hash-card"><Package size={18} /><div><span>StrategyReleaseBundle（draft）</span><code>{release.path}</code><small>SHA-256 {release.bundle_hash}</small></div></div>}
    </>
  );
}

function ReportMetric({ label, value }) {
  return <div><span>{label}</span><strong>{value}</strong></div>;
}

function KeyValueTable({ values }) {
  return <div className="key-value-table">{Object.entries(values || {}).map(([key, value]) => <div key={key}><span>{key}</span><code>{Array.isArray(value) ? value.join(", ") : String(value)}</code></div>)}</div>;
}
