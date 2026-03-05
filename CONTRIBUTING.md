# 贡献指南 (Contributing Guide)

感谢你对 AKQuant 的关注！我们需要你的帮助来让这个项目变得更好。无论你是修复 Bug、改进文档，还是增加新功能，我们都非常欢迎！

为了方便“萌新”上手，我们准备了这份详细的 GitHub 合作开发指南。

## 🚀 开发流程 (Workflow)

我们采用 **Git Flow** 的简化模式进行开发。

- **`main` 分支**: 稳定分支，对应 PyPI 发布的版本。
- **`dev` 分支**: 开发分支，所有的日常开发和 PR 都应合并到此分支。

### 1. Fork & Clone (复刻与克隆)

1.  **Fork 项目**: 点击 GitHub 页面右上角的 `Fork` 按钮，将 `akquant` 仓库复刻到你自己的账号下。
2.  **Clone 到本地**:
    ```bash
    # 将 <your-username> 替换为你的 GitHub 用户名
    git clone https://github.com/<your-username>/akquant.git
    cd akquant
    ```
3.  **设置上游仓库 (Upstream)**:
    为了保持你的代码与官方仓库同步，需要添加上游仓库地址：
    ```bash
    git remote add upstream https://github.com/akfamily/akquant.git
    ```

### 2. 环境搭建 (Setup)

本项目混合了 Rust 和 Python，请按以下步骤配置环境：

1.  **安装 Rust**: [官网下载](https://www.rust-lang.org/tools/install)
2.  **创建 Python 虚拟环境 (推荐 Conda)**:
    ```bash
    conda create -n akquant python=3.10
    conda activate akquant
    ```
3.  **安装依赖与编译**:
    ```bash
    # 安装开发依赖
    pip install -e ".[dev,ml,plot]"

    # 编译 Rust 扩展 (开发模式)
    maturin develop
    ```

### 3. 开始开发 (Coding)

1.  **同步最新代码**:
    每次开发前，先确保你的本地 `dev` 分支是最新的：
    ```bash
    git checkout dev
    git pull upstream dev
    ```

2.  **创建功能分支**:
    **不要**直接在 `dev` 或 `main` 上修改。请为每个任务创建一个新分支：
    ```bash
    git checkout -b feature/my-new-feature
    # 或者修复 bug
    git checkout -b fix/bug-fix-name
    ```

3.  **编写代码**:
    *   遵循 PEP 8 编码规范。
    *   确保添加了类型注解 (Type Hints)。
    *   如果是 Python 代码，请运行检查：
        ```bash
        ruff check .
        mypy .
        ```
    *   推荐在提交前统一执行：
        ```bash
        pre-commit run --all-files
        ```
        说明：
        *   仓库中的 mypy hook 已配置为以项目根目录运行并读取 `pyproject.toml`，用于避免 `__init__.py` 与 `__init__.pyi` 的重复模块报错。
        *   如果你修改了 pre-commit 配置或首次运行遇到环境问题，可执行：
            ```bash
            pre-commit clean
            pre-commit install --install-hooks
            ```

### 4. 提交与推送 (Commit & Push)

1.  **提交代码**:
    ```bash
    git add .
    git commit -m "feat: 添加了xxx功能"
    ```
    *(推荐使用 [Conventional Commits](https://www.conventionalcommits.org/) 格式)*

2.  **推送到你的 Fork 仓库**:
    ```bash
    git push origin feature/my-new-feature
    ```

### 6. 测试与验证 (Testing)

为确保代码质量与回测结果的一致性，本项目引入了**黄金测试套件 (Golden Test Suite)**。

1.  **运行常规单元测试**:
    ```bash
    pytest
    ```

2.  **运行黄金测试 (Golden Tests)**:
    黄金测试用于捕捉核心算法变更导致的非预期行为（如 PnL 计算、撮合逻辑差异）。
    ```bash
    pytest tests/golden/test_golden.py
    ```
    *   如果测试失败，请检查差异是否符合预期。
    *   如果是**预期内的算法改进**（例如修复了撮合 bug 导致成交价格变动），你需要更新基线：
        ```bash
        python tests/golden/runner.py --generate-baseline
        ```
        并在 PR 中说明导致基线变更的原因。

3.  **代码风格检查**:
    ```bash
    ruff check .
    mypy .
    ```

---

## ✅ 提交前的检查清单

在提交 PR 之前，请检查：

- [ ] 代码可以通过 `maturin develop` 编译成功。
- [ ] 运行了 `ruff check .` 和 `mypy .` 没有报错。
- [ ] 如果是新功能，是否添加了简单的测试或示例？
- [ ] 文档是否已更新？

## ❓ 遇到问题？

如果你在配置环境或提交代码时遇到困难，欢迎在 [Issues](https://github.com/akfamily/akquant/issues) 中提问，我们会尽快回复！

再次感谢你的贡献！🎉
