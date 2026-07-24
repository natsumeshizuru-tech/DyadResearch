import { useCallback, useEffect, useRef, useState } from "react";
import { Database, DownloadSimple, MagnifyingGlass, Play, ShieldCheck } from "@phosphor-icons/react";
import { MarketChart } from "../components/Charts.jsx";
import { ErrorNotice, Field, Loading, Tabs } from "../components/Ui.jsx";
import { api, post } from "../lib/api.js";
import { compact, dateLabel, number } from "../lib/format.js";

const DATA_TABS = [
  { value: "chart", label: "行情图表" },
  { value: "table", label: "原始数据" },
  { value: "financial", label: "财务数据" },
  { value: "reference", label: "参考数据" },
  { value: "quality", label: "数据质量" },
  { value: "xtdata", label: "XtData 下载" },
];
const PERIOD_LABELS = { "1m": "1分钟", "5m": "5分钟", "15m": "15分钟", "1h": "1小时", "1d": "日线", "1q": "季度", "1y": "年度" };
const PERIOD_STARTS = { "1m": 20250711, "5m": 20250711, "15m": 20250711, "1h": 20250711, "1d": 20100104, "1q": 20100104, "1y": 20100104 };

export function DataPage() {
  const [instruments, setInstruments] = useState([]);
  const [bars, setBars] = useState([]);
  const [meta, setMeta] = useState(null);
  const [coverage, setCoverage] = useState(null);
  const [latestDailyEnd, setLatestDailyEnd] = useState(20260717);
  const [financial, setFinancial] = useState(null);
  const [financialTable, setFinancialTable] = useState("Income");
  const [financialLoading, setFinancialLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [tab, setTab] = useState("chart");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [form, setForm] = useState({ symbol: "000001.SZ", period: "1d", start: PERIOD_STARTS["1d"], end: 20260717 });
  const booted = useRef(false);
  const querySequence = useRef(0);

  useEffect(() => {
    const timer = setTimeout(() => {
      api(`/instruments?search=${encodeURIComponent(search)}&limit=40`)
        .then((payload) => setInstruments(payload.instruments))
        .catch((loadError) => setError(loadError.message));
    }, 150);
    return () => clearTimeout(timer);
  }, [search]);

  const refreshCoverage = useCallback(() => {
    const coverageRequest = api("/data/coverage").then((payload) => {
      setCoverage(payload);
      return payload;
    });
    const healthRequest = api("/health").then((payload) => {
      if (payload.data_through) setLatestDailyEnd(payload.data_through);
    });
    return Promise.all([coverageRequest, healthRequest])
      .then(([coveragePayload]) => coveragePayload)
      .catch((loadError) => setError(loadError.message));
  }, []);

  useEffect(() => { void refreshCoverage(); }, [refreshCoverage]);

  useEffect(() => {
    if (tab !== "financial") return;
    let cancelled = false;
    setFinancialLoading(true);
    const params = new URLSearchParams({
      symbol: form.symbol,
      table_name: financialTable,
      start: String(form.start),
      end: String(form.end),
      limit: "200",
    });
    api(`/financials?${params}`)
      .then((payload) => { if (!cancelled) setFinancial(payload); })
      .catch((loadError) => { if (!cancelled) setError(loadError.message); })
      .finally(() => { if (!cancelled) setFinancialLoading(false); });
    return () => { cancelled = true; };
  }, [tab, form.symbol, form.start, form.end, financialTable]);

  const query = useCallback(async (next = form) => {
    const requestId = ++querySequence.current;
    setLoading(true);
    setError("");
    setBars([]);
    setMeta(null);
    try {
      const params = new URLSearchParams({ ...next, limit: "10000" });
      const payload = await api(`/bars?${params}`);
      if (requestId === querySequence.current) {
        setBars(payload.bars);
        setMeta(payload);
      }
    } catch (queryError) {
      if (requestId === querySequence.current) setError(queryError.message);
    } finally {
      if (requestId === querySequence.current) setLoading(false);
    }
  }, [form]);

  useEffect(() => {
    if (booted.current) return;
    booted.current = true;
    query();
  }, [query]);

  useEffect(() => {
    if (form.end >= latestDailyEnd) return;
    const next = { ...form, end: latestDailyEnd };
    setForm(next);
    query(next);
  }, [latestDailyEnd, form, query]);

  const chooseInstrument = (symbol) => {
    const next = { ...form, symbol };
    setForm(next);
    query(next);
  };

  const choosePeriod = (period) => {
    const next = { ...form, period, start: PERIOD_STARTS[period] };
    setForm(next);
    query(next);
  };

  return (
    <div className="data-workspace">
      <header className="page-toolbar">
        <div><span className="eyebrow">行情与数据</span><h1>数据浏览</h1></div>
        <div className="toolbar-actions"><span className="verified-badge"><ShieldCheck size={16} /> 查询只读 · 导入受控</span><button className="primary-button" type="button" onClick={() => query()} disabled={loading}>{loading ? <Loading label="查询" /> : <><Play size={15} weight="fill" /> 查询数据</>}</button></div>
      </header>

      <aside className="instrument-panel panel">
        <div className="panel-header"><h2>证券目录</h2><span>{instruments.length}</span></div>
        <label className="catalog-search with-icon"><MagnifyingGlass size={14} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="代码 / 名称" /></label>
        <div className="instrument-list">
          {instruments.map((instrument) => (
            <button key={instrument.symbol} type="button" className={form.symbol === instrument.symbol ? "active" : ""} onClick={() => chooseInstrument(instrument.symbol)}>
              <span className="market-tag">{instrument.market}</span>
              <span><strong>{instrument.symbol}</strong><small>{instrument.name || "--"}</small></span>
              <em>{instrument.is_active ? "上市" : "退市"}</em>
            </button>
          ))}
        </div>
      </aside>

      <section className="data-main panel">
        <div className="data-querybar">
          <Field label="证券代码"><input value={form.symbol} onChange={(event) => setForm({ ...form, symbol: event.target.value.toUpperCase() })} /></Field>
          <Field label="周期"><select value={form.period} onChange={(event) => choosePeriod(event.target.value)}><option value="1m">1分钟</option><option value="5m">5分钟</option><option value="15m">15分钟</option><option value="1h">1小时</option><option value="1d">日线</option><option value="1q">季度</option><option value="1y">年度</option></select></Field>
          <Field label="开始日期"><input type="date" value={dateLabel(form.start)} onInput={(event) => setForm({ ...form, start: Number(event.currentTarget.value.replaceAll("-", "")) })} /></Field>
          <Field label="结束日期"><input type="date" value={dateLabel(form.end)} onInput={(event) => setForm({ ...form, end: Number(event.currentTarget.value.replaceAll("-", "")) })} /></Field>
          <div className="query-meta"><Database size={14} /><span>{meta?.rows || 0} 行</span><span>{meta?.paths?.length || 0} 分片</span></div>
        </div>
        <Tabs items={DATA_TABS} value={tab} onChange={setTab} />
        <ErrorNotice message={error} onClose={() => setError("")} />

        {tab === "chart" && (
          <div className="market-chart-stack">
            <div className="chart-title"><span>{form.symbol} · {PERIOD_LABELS[form.period]}</span><small>{dateLabel(form.start)} → {dateLabel(form.end)}</small></div>
            <MarketChart bars={bars} />
          </div>
        )}
        {tab === "table" && <BarsTable bars={bars} />}
        {tab === "financial" && <FinancialPanel payload={financial} tableName={financialTable} onTableChange={setFinancialTable} loading={financialLoading} />}
        {tab === "reference" && <ReferencePanel />}
        {tab === "quality" && <QualityPanel meta={meta} coverage={coverage} />}
        {tab === "xtdata" && <XtDataPanel onImported={refreshCoverage} />}
      </section>

      <aside className="data-inspector panel">
        <div className="panel-header"><h2>查询概览</h2></div>
        <div className="inspection-metrics">
          <DataMetric label="返回行数" value={number(meta?.returned, 0)} />
          <DataMetric label="原始行数" value={number(meta?.rows, 0)} />
          <DataMetric label="首日" value={dateLabel(bars[0]?.trade_date)} />
          <DataMetric label="末日" value={dateLabel(bars.at(-1)?.trade_date)} />
          <DataMetric label="最新收盘" value={number(bars.at(-1)?.close, 3)} />
          <DataMetric label="最新成交额" value={compact(bars.at(-1)?.amount)} />
        </div>
        <div className="inspector-divider"><span>数据指纹</span></div>
        <code className="fingerprint">{meta?.fingerprint || "等待查询"}</code>
        <div className="inspector-divider"><span>命中分片</span></div>
        <div className="path-list">{meta?.paths?.map((path) => <div key={path}>{path.split(/[\\/]/).at(-1)}</div>)}</div>
      </aside>
    </div>
  );
}

function XtDataPanel({ onImported }) {
  const [catalog, setCatalog] = useState(null);
  const [dataset, setDataset] = useState("history");
  const [symbols, setSymbols] = useState("000001.SZ");
  const [period, setPeriod] = useState("1d");
  const [startDate, setStartDate] = useState("20240101");
  const [endDate, setEndDate] = useState("");
  const [tables, setTables] = useState("Balance,Income,CashFlow,Capital");
  const [shouldImport, setShouldImport] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  useEffect(() => {
    api("/xtdata/catalog").then(setCatalog).catch((reason) => setError(reason.message));
  }, []);

  const selected = catalog?.datasets?.find((item) => item.value === dataset);
  const run = async () => {
    setBusy(true);
    setError("");
    setResult(null);
    try {
      const payload = await post("/xtdata/download", {
        dataset,
        symbols: symbols.split(/[\s,;]+/).filter(Boolean),
        period,
        start_date: startDate,
        end_date: endDate,
        tables: tables.split(/[\s,;]+/).filter(Boolean),
        import_to_shared_store: shouldImport && Boolean(selected?.supports_shared_import),
      });
      setResult(payload);
      if (payload.imported_to_shared_store) onImported?.();
    } catch (reason) {
      setError(reason.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="xtdata-panel">
      <div className="xtdata-heading"><div><strong>MiniQMT · XtData 数据中心</strong><span>与 DyadTetrade 使用同一份 SQLite 数据契约</span></div><span className={catalog?.capabilities?.connected ? "online-pill" : "offline-pill"}>{catalog?.capabilities?.connected ? "已连接" : "未连接"}</span></div>
      <div className="xtdata-fields">
        <Field label="数据类别"><select value={dataset} onChange={(event) => setDataset(event.target.value)}>{catalog?.datasets?.map((item) => <option key={item.value} value={item.value} disabled={!item.available}>{item.label}{item.available ? "" : "（不可用）"}</option>)}</select></Field>
        {selected?.requires_symbols && <Field label="合约代码"><input value={symbols} onChange={(event) => setSymbols(event.target.value.toUpperCase())} /></Field>}
        {selected?.requires_period && <Field label="周期"><select value={period} onChange={(event) => setPeriod(event.target.value)}>{catalog?.periods?.map((item) => <option key={item.value} value={item.value}>{item.group} · {item.label}{item.reported_by_client ? "" : " *"}</option>)}</select></Field>}
        {(dataset === "history" || dataset === "financial") && <><Field label="开始日期"><input value={startDate} onChange={(event) => setStartDate(event.target.value.replace(/\D/g, "").slice(0, 8))} /></Field><Field label="结束日期"><input value={endDate} onChange={(event) => setEndDate(event.target.value.replace(/\D/g, "").slice(0, 8))} placeholder="留空为今天" /></Field></>}
        {dataset === "financial" && <Field label="财务表"><input value={tables} onChange={(event) => setTables(event.target.value)} /></Field>}
        <label className="xtdata-import-check"><input type="checkbox" checked={shouldImport} disabled={!selected?.supports_shared_import} onChange={(event) => setShouldImport(event.target.checked)} /> 导入共享 SQLite</label>
        <button className="primary-button" type="button" onClick={run} disabled={busy || !selected?.available}><DownloadSimple size={16} /> {busy ? "下载导入中…" : "执行下载 / 导入"}</button>
      </div>
      <ErrorNotice message={error} onClose={() => setError("")} />
      <div className="xtdata-output"><section><h3>可下载类别</h3><p>客户端报告 {catalog?.capabilities?.available_periods?.length || 0} 个周期，{catalog?.capabilities?.sector_count || 0} 个板块。</p><ul>{catalog?.notes?.map((note) => <li key={note}>{note}</li>)}</ul></section><section><h3>执行结果</h3><pre>{result ? JSON.stringify(result, null, 2) : "等待执行；特色数据是否成功取决于当前迅投账号权限。"}</pre></section></div>
    </div>
  );
}

function BarsTable({ bars }) {
  const [order, setOrder] = useState("desc");
  const [page, setPage] = useState(1);
  const pageSize = 300;
  const ordered = order === "desc" ? [...bars].reverse() : bars;
  const totalPages = Math.max(1, Math.ceil(ordered.length / pageSize));
  const currentPage = Math.min(page, totalPages);
  const visible = ordered.slice((currentPage - 1) * pageSize, currentPage * pageSize);

  const changeOrder = (nextOrder) => {
    setOrder(nextOrder);
    setPage(1);
  };

  return (
    <div className="bars-table">
      <div className="bars-table-toolbar">
        <span>共 {number(bars.length, 0)} 行</span>
        <button type="button" className={order === "asc" ? "active" : ""} onClick={() => changeOrder("asc")}>最早记录</button>
        <button type="button" className={order === "desc" ? "active" : ""} onClick={() => changeOrder("desc")}>最新记录</button>
        <button type="button" disabled={currentPage <= 1} onClick={() => setPage(currentPage - 1)}>上一页</button>
        <span>{currentPage} / {totalPages}</span>
        <button type="button" disabled={currentPage >= totalPages} onClick={() => setPage(currentPage + 1)}>下一页</button>
      </div>
      <div className="bars-row header"><span>日期</span><span>开盘</span><span>最高</span><span>最低</span><span>收盘</span><span>成交量</span><span>成交额</span><span>来源</span></div>
      {visible.map((bar) => <div className="bars-row" key={`${bar.symbol}-${bar.ts}`}><span>{dateLabel(bar.trade_date)}</span><span>{number(bar.open, 3)}</span><span>{number(bar.high, 3)}</span><span>{number(bar.low, 3)}</span><span>{number(bar.close, 3)}</span><span>{compact(bar.volume)}</span><span>{compact(bar.amount)}</span><span>{bar.source}</span></div>)}
    </div>
  );
}

function FinancialPanel({ payload, tableName, onTableChange, loading }) {
  const tables = payload?.available_tables?.length ? payload.available_tables : ["Balance", "Capital", "CashFlow", "HolderNum", "Income", "PershareIndex", "Top10FlowHolder", "Top10Holder"];
  return (
    <div className="extended-data-panel">
      <div className="extended-toolbar">
        <div><strong>{payload?.symbol || "--"}</strong><span>迅投财务原始记录 · 公告日与报告期均保留</span></div>
        <label>数据表<select value={tableName} onChange={(event) => onTableChange(event.target.value)}>{tables.map((name) => <option key={name} value={name}>{name}</option>)}</select></label>
      </div>
      {loading ? <div className="list-loading"><Loading label="读取财务数据" /></div> : (
        <div className="financial-records">
          <div className="financial-row header"><span>报告期</span><span>公告日</span><span>表名</span><span>序号</span><span>原始字段</span></div>
          {payload?.records?.map((record) => (
            <div className="financial-row" key={`${record.table_name}-${record.report_date}-${record.announcement_date}-${record.row_ordinal}`}>
              <span>{dateLabel(record.report_date)}</span><span>{dateLabel(record.announcement_date)}</span><span>{record.table_name}</span><span>{record.row_ordinal}</span><RawFields value={record.fields} />
            </div>
          ))}
          {!payload?.records?.length && <div className="empty-inline">该证券和日期范围内没有 {tableName} 记录。</div>}
        </div>
      )}
    </div>
  );
}

function RawFields({ value }) {
  const entries = value && typeof value === "object" && !Array.isArray(value) ? Object.entries(value) : [["value", value]];
  return <div className="raw-fields">{entries.slice(0, 8).map(([key, item]) => <span key={key}><em>{key}</em>{item == null ? "--" : String(item)}</span>)}</div>;
}

function ReferencePanel() {
  const [kind, setKind] = useState("sectors");
  const [payload, setPayload] = useState(null);
  const [selected, setSelected] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const endpoint = kind === "sectors" ? "/reference/sectors" : "/reference/index-weights";
  const keyName = kind === "sectors" ? "sector_name" : "index_code";

  const load = useCallback(async (selection = "") => {
    setLoading(true);
    setError("");
    try {
      const query = selection ? `?${keyName}=${encodeURIComponent(selection)}&limit=500` : "?limit=500";
      const result = await api(`${endpoint}${query}`);
      if (!selection && result.catalogs?.length) {
        const first = result.catalogs[0][keyName];
        setSelected(first);
        const detail = await api(`${endpoint}?${keyName}=${encodeURIComponent(first)}&limit=500`);
        setPayload({ ...detail, catalogs: result.catalogs });
      } else {
        setPayload((current) => ({ ...result, catalogs: result.catalogs?.length ? result.catalogs : current?.catalogs || [] }));
      }
    } catch (loadError) {
      setError(loadError.message);
    } finally {
      setLoading(false);
    }
  }, [endpoint, keyName]);

  useEffect(() => { setSelected(""); setPayload(null); load(); }, [kind, load]);

  const choose = (value) => { setSelected(value); load(value); };
  return (
    <div className="extended-data-panel">
      <div className="extended-toolbar">
        <div className="reference-switch"><button type="button" className={kind === "sectors" ? "active" : ""} onClick={() => setKind("sectors")}>板块快照</button><button type="button" className={kind === "indexes" ? "active" : ""} onClick={() => setKind("indexes")}>指数权重</button></div>
        <label>数据集<select value={selected} onChange={(event) => choose(event.target.value)}>{payload?.catalogs?.map((item) => <option key={item[keyName]} value={item[keyName]}>{item[keyName]}</option>)}</select></label>
        <span className="snapshot-badge">快照 {dateLabel(payload?.snapshot_date)}</span>
      </div>
      <ErrorNotice message={error} onClose={() => setError("")} />
      {loading ? <div className="list-loading"><Loading label="读取参考数据" /></div> : (
        <div className="reference-records">
          <div className="reference-row header"><span>证券代码</span><span>{kind === "indexes" ? "权重" : "成员"}</span><span>来源</span></div>
          {payload?.members?.map((member) => <div className="reference-row" key={member.symbol}><strong>{member.symbol}</strong><span>{kind === "indexes" ? number(member.weight, 6) : selected}</span><span>{member.source}</span></div>)}
          {!payload?.members?.length && <div className="empty-inline">当前快照没有可显示的成员记录。</div>}
        </div>
      )}
    </div>
  );
}

function QualityPanel({ meta, coverage }) {
  const stocks = coverage?.instruments?.find((item) => item.instrument_type === "stock");
  const etfs = coverage?.instruments?.find((item) => item.instrument_type === "etf");
  const financialRows = coverage?.financials?.reduce((sum, item) => sum + Number(item.rows || 0), 0);
  const references = coverage?.references;
  return (
    <div className="quality-panel">
      <div className="quality-card"><ShieldCheck size={22} /><div><strong>只读连接已启用</strong><span>所有 SQLite 连接强制 PRAGMA query_only=1。</span></div></div>
      <div className="quality-card"><Database size={22} /><div><strong>查询指纹可复现</strong><span>{meta?.fingerprint?.slice(0, 24) || "运行查询后生成"}</span></div></div>
      <div className="quality-card"><Database size={22} /><div><strong>证券目录</strong><span>股票 {number(stocks?.count, 0)} · ETF {number(etfs?.count, 0)}</span></div></div>
      <div className="quality-card"><Database size={22} /><div><strong>财务数据</strong><span>{number(financialRows, 0)} 行 · {coverage?.financials?.length || 0} 个年度分片</span></div></div>
      <div className="quality-card"><ShieldCheck size={22} /><div><strong>板块参考数据</strong><span>{number(references?.sectors?.snapshot_rows, 0)} 条 · 最新 {dateLabel(references?.sectors?.last_snapshot)}</span></div></div>
      <div className="quality-card"><ShieldCheck size={22} /><div><strong>指数权重数据</strong><span>{number(references?.index_weights?.snapshot_rows, 0)} 条 · 最新 {dateLabel(references?.index_weights?.last_snapshot)}</span></div></div>
    </div>
  );
}

function DataMetric({ label, value }) {
  return <div><span>{label}</span><strong>{value || "--"}</strong></div>;
}
