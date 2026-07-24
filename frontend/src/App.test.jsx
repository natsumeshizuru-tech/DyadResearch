import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { App } from "./App.jsx";

vi.mock("./pages/StrategyPage.jsx", () => ({
  StrategyPage: () => <div>策略研究工作区</div>,
}));

const responses = {
  "/api/health": {
    ok: true,
    data_through: 20260717,
    database_count: 7,
    data_root: "./data/sqlite",
    readonly: true,
    timezone: "Asia/Shanghai",
  },
  "/api/strategies": { strategies: [], policies: ["strict_research"] },
  "/api/factors": { factors: [] },
};

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(async (input) => {
    const url = typeof input === "string" ? input : input.url;
    const body = responses[url] ?? {};
    return { ok: true, status: 200, json: async () => body };
  }));
});

afterEach(() => vi.unstubAllGlobals());

test("exposes only data, factor, strategy, backtest and report research modules", async () => {
  render(<App />);
  const navigation = screen.getByRole("complementary", { name: "研究模块" });

  expect(navigation.querySelectorAll("button")).toHaveLength(7);
  for (const label of ["数据浏览", "因子研究", "策略研究", "回测实验", "实验报告"]) {
    expect(screen.getByRole("button", { name: label })).toBeInTheDocument();
  }
  expect(screen.queryByText("交易")).not.toBeInTheDocument();
  expect(screen.queryByText("券商账户")).not.toBeInTheDocument();
  await waitFor(() => expect(screen.getByText(/数据截至 2026-07-17/)).toBeInTheDocument());
});
