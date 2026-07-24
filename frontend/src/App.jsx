import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import {
  ChartLineUp,
  CaretDown,
  Code,
  Database,
  FileText,
  Flask,
  Gear,
  MagnifyingGlass,
  Pulse,
  Question,
  SquaresFour,
  TerminalWindow,
} from "@phosphor-icons/react";
import { api } from "./lib/api.js";

const BacktestPage = lazy(() => import("./pages/BacktestPage.jsx").then((module) => ({ default: module.BacktestPage })));
const DataPage = lazy(() => import("./pages/DataPage.jsx").then((module) => ({ default: module.DataPage })));
const FactorPage = lazy(() => import("./pages/FactorPage.jsx").then((module) => ({ default: module.FactorPage })));
const ReportsPage = lazy(() => import("./pages/ReportsPage.jsx").then((module) => ({ default: module.ReportsPage })));
const StrategyPage = lazy(() => import("./pages/StrategyPage.jsx").then((module) => ({ default: module.StrategyPage })));

const NAV_ITEMS = [
  { id: "data", label: "数据浏览", icon: Database },
  { id: "factor", label: "因子研究", icon: Flask },
  { id: "strategy", label: "策略研究", icon: Code },
  { id: "backtest", label: "回测实验", icon: ChartLineUp },
  { id: "reports", label: "实验报告", icon: FileText },
];

export function App() {
  const [active, setActive] = useState("strategy");
  const [health, setHealth] = useState(null);
  const [healthError, setHealthError] = useState("");
  const [overlay, setOverlay] = useState("");
  const [commandSearch, setCommandSearch] = useState("");

  useEffect(() => {
    api("/health")
      .then(setHealth)
      .catch((error) => setHealthError(error.message));
  }, []);

  useEffect(() => {
    const onKeyDown = (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOverlay("commands");
      }
      if (event.key === "Escape") setOverlay("");
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  const page = useMemo(() => {
    if (active === "data") return <DataPage />;
    if (active === "factor") return <FactorPage />;
    if (active === "backtest") return <BacktestPage />;
    if (active === "reports") return <ReportsPage />;
    return <StrategyPage />;
  }, [active]);

  const statusText = health
    ? `数据截至 ${formatDate(health.data_through)} · ${health.database_count} 个库正常`
    : healthError
      ? "研究 API 未连接"
      : "正在检查本地数据…";

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark"><Pulse size={18} weight="bold" /></span>
          <span>DyadResearch</span>
        </div>
        <button className="environment-button" type="button" onClick={() => setOverlay("environment")}>
          本地研究环境 <CaretDown size={12} />
        </button>
        <div className={`data-status ${health?.ok ? "healthy" : ""}`}>
          <span className="status-dot" />
          {statusText}
        </div>
        <div className="topbar-spacer" />
        <label className="command-search">
          <MagnifyingGlass size={15} />
          <input aria-label="全局搜索" value={commandSearch} onChange={(event) => setCommandSearch(event.target.value)} onFocus={() => setOverlay("commands")} placeholder="搜索研究模块与命令" />
          <kbd>Ctrl K</kbd>
        </label>
        <button className="quiet-button" type="button" onClick={() => setOverlay("commands")}><TerminalWindow size={16} /> 命令面板</button>
      </header>

      <aside className="nav-rail" aria-label="研究模块">
        <div className="nav-primary">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.id}
                type="button"
                className={`nav-item ${active === item.id ? "active" : ""}`}
                onClick={() => setActive(item.id)}
                aria-current={active === item.id ? "page" : undefined}
              >
                <Icon size={21} weight={active === item.id ? "fill" : "regular"} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </div>
        <div className="nav-secondary">
          <button type="button" className="nav-item" onClick={() => setOverlay("settings")}><Gear size={21} /><span>设置</span></button>
          <button type="button" className="nav-item" onClick={() => setOverlay("help")}><Question size={21} /><span>帮助</span></button>
        </div>
      </aside>

      <main className="workspace"><Suspense fallback={<div className="empty-state">正在加载研究工作区…</div>}>{page}</Suspense></main>

      <footer className="global-statusbar">
        <span><span className="status-dot healthy-dot" /> 就绪</span>
        <span>SQLite 只读</span>
        <span>Asia/Shanghai</span>
        <span className="statusbar-spacer" />
        <span><SquaresFour size={13} /> 数据根目录已迁移</span>
        <span>{health?.data_root || "./data/sqlite"}</span>
      </footer>

      {overlay && <WorkspaceOverlay kind={overlay} health={health} search={commandSearch} onSearch={setCommandSearch} onClose={() => setOverlay("")} onNavigate={(id) => { setActive(id); setOverlay(""); setCommandSearch(""); }} />}
    </div>
  );
}

function WorkspaceOverlay({ kind, health, search, onSearch, onClose, onNavigate }) {
  const normalized = search.trim().toLowerCase();
  const commands = NAV_ITEMS.filter((item) => `${item.label} ${item.id}`.toLowerCase().includes(normalized));
  return (
    <div className="workspace-overlay" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section className="overlay-dialog" role="dialog" aria-modal="true" aria-label={overlayTitle(kind)}>
        <div className="overlay-header"><div><span className="eyebrow">DyadResearch</span><h2>{overlayTitle(kind)}</h2></div><button type="button" onClick={onClose} aria-label="关闭">×</button></div>
        {kind === "commands" && <div className="command-panel"><label className="overlay-search"><MagnifyingGlass size={15} /><input autoFocus value={search} onChange={(event) => onSearch(event.target.value)} placeholder="输入数据、因子、策略、回测或报告" /></label><div className="command-list">{commands.map((item) => { const Icon = item.icon; return <button type="button" key={item.id} onClick={() => onNavigate(item.id)}><Icon size={18} /><span><strong>打开{item.label}</strong><small>切换到 {item.label} 工作区</small></span><kbd>Enter</kbd></button>; })}{!commands.length && <div className="empty-command">没有匹配的本地命令</div>}</div></div>}
        {kind === "environment" && <OverlayFacts values={[["运行模式", "本地只读研究"], ["API 状态", health?.ok ? "正常" : "不可用"], ["SQLite 数据库", `${health?.database_count || 0} 个`], ["数据截至", formatDate(health?.data_through)], ["时区", health?.timezone || "Asia/Shanghai"], ["数据目录", health?.data_root || "--"]]} />}
        {kind === "settings" && <><div className="overlay-note">这里展示影响研究结果的有效设置；源行情库保持只读，配置修改请编辑 <code>config/research.yaml</code> 后重启。</div><OverlayFacts values={[["源数据", health?.data_root || "--"], ["数据库模式", health?.readonly ? "SQLite mode=ro" : "检查配置"], ["默认基准", "510300.SH"], ["成交策略", "下一 bar · T+1 · 含费用"], ["派生周期", "1m→5m/15m/30m/1h；1d→周/月/季/半年/年"]]} /></>}
        {kind === "help" && <div className="help-panel"><h3>开始使用</h3><p>双击项目根目录的 <code>Start-DyadResearch.cmd</code> 即可启动并打开平台。</p><h3>研究边界</h3><p>平台不会连接账户或实盘交易；源 SQLite 只读，实验只写入 <code>research.db</code> 与 <code>reports</code>。</p><h3>分钟数据说明</h3><p>已安装 QMT 的沪深 1 分钟历史从 2025-07-11 起，之前缺口不会用日线插值伪造。</p></div>}
      </section>
    </div>
  );
}

function OverlayFacts({ values }) {
  return <div className="overlay-facts">{values.map(([label, value]) => <div key={label}><span>{label}</span><strong>{value || "--"}</strong></div>)}</div>;
}

function overlayTitle(kind) {
  return { commands: "命令面板", environment: "本地研究环境", settings: "研究设置", help: "帮助与边界" }[kind] || "DyadResearch";
}

function formatDate(value) {
  const text = String(value || "");
  return text.length === 8 ? `${text.slice(0, 4)}-${text.slice(4, 6)}-${text.slice(6)}` : text;
}
