# orchestrator-tools

本目录是 Claude Code 配置仓内的 Python 子项目，承载 orchestrator MVP 工具集。

## Quickstart

```bash
cd tools
uv pip install -e '.[dev]'
pytest
ruff check .
```

## 边界说明

本子项目从仓根拆出，依据 plan §5.1 和 §7.3：

- **独立 lifecycle**（§5.1）：Python 工具集有自己的版本号、测试套件和发布节奏，
  与 Claude Code Markdown 配置文件解耦，互不干扰。
- **零运行时依赖**（§7.3）：MVP 阶段仅依赖标准库（`tomllib`、`pathlib`、`json`
  等），无需在 host 环境安装第三方包，降低集成摩擦。
- **未来可独立发包**：`name = "orchestrator-tools"` 已注册 PyPI 友好命名，
  需要时可直接 `pip install orchestrator-tools`。

## 目录结构（含 TBD 占位）

```
tools/
├── pyproject.toml          # 本文件同级 — 项目元数据与工具配置
├── README.md               # 本文件
├── orchestrator.py         # TBD (step-3) — 核心 orchestrator 逻辑
├── schemas/                # TBD (step-4) — HANDOFF / prd.json JSON Schema
│   └── handoff.schema.json
└── tests/                  # TBD (step-3) — pytest 测试套件
    └── test_orchestrator.py
```

> 本步骤只创建 `pyproject.toml` 和 `README.md`；
> 其余文件/目录由后续 step 按计划添加。
