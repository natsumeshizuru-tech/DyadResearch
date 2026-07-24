# Qlib workflow design reference

DyadResearch 的本地工作流账本参考 Microsoft Qlib 的实验管理与 Recorder 接口，但没有复制 Qlib 源码，也没有引入 MLflow 运行时依赖。

本轮核对的上游文件：

- [`qlib/workflow/recorder.py`](https://github.com/microsoft/qlib/blob/main/qlib/workflow/recorder.py)：`SCHEDULED/RUNNING/FINISHED/FAILED` 生命周期、参数、指标、标签与工件接口。
- [`qlib/workflow/expm.py`](https://github.com/microsoft/qlib/blob/main/qlib/workflow/expm.py)：Experiment 与 Recorder 的分层管理。
- [`workflow_config_lightgbm_Alpha158.yaml`](https://github.com/microsoft/qlib/blob/main/examples/benchmarks/LightGBM/workflow_config_lightgbm_Alpha158.yaml)：数据、模型、分段、记录器和组合分析的声明式工作流边界。

DyadResearch 的实现保持本项目约束：SQLite 本地账本、确定性 JSON、内容寻址 SHA-256 工件、失败留痕、与既有 `ExperimentStore` 外键关联；不共享 Qlib 数据格式、模型实现或 MLflow 服务。
