# GUI v1 服务接口清单

GUI v1 应调用稳定 Python 函数，而不是在界面层拼接长命令行。当前核心脚本已经具备可复用入口，后续 GUI 可以先薄包装这些函数，再按需要抽到 `src/cad_budget/gui_services.py`。

## 当前可用入口

### 运行真实验收

函数：

```python
run_real_acceptance(
    *,
    dxf_path: Path,
    template_path: Path,
    output_dir: Path,
    unit_prices_path: Path,
    priced_output_dir: Path,
    unit: CadUnit = CadUnit.MILLIMETER,
    rules_path: Path | None = None,
) -> RealAcceptanceSummary
```

当前来源：`scripts/run_real_acceptance.py`

GUI 输入：

- DXF 路径。
- 商品房模板路径。
- 全局单价表路径。
- 回归输出目录。
- 正式报价输出目录。
- 可选规则文件。

GUI 输出：

- 自动化统计。
- 复核状态统计。
- 行动优先级统计。
- 单价匹配行数。
- 输出目录路径。

错误展示：

- 捕获 `AcceptanceError`。
- 主提示格式建议为：`验收失败：{message}`。
- 可按 message 前缀映射失败阶段：
  - `real pipeline failed`
  - `key result assertions failed`
  - `priced output check failed`

### 生成报价回归和正式报价包

函数：

```python
run_quote_review_pipeline(
    *,
    dxf_path: Path,
    template_path: Path,
    output_dir: Path,
    unit: CadUnit,
    rules_path: Path | None,
    unit_prices_path: Path | None,
    fail_on: str | None,
    priced_output_dir: Path | None,
    check_priced_output: bool,
) -> QuoteReviewPipelineSummary
```

当前来源：`scripts/run_real_template_quote_review.py`

GUI 用途：

- 支持“只生成当前项目输出”和“生成正式报价包”两类按钮。
- 读取 `failed_actions` 展示被门禁拦截的复核行动。

### 校验正式报价包

函数：

```python
check_priced_quote_outputs(
    output_dir: Path,
    *,
    unit_prices_path: Path | None,
    expected_automation_counts: dict[str, int] | None,
    expected_status_counts: dict[str, int] | None,
) -> dict[str, Any]
```

当前来源：`scripts/check_priced_quote_outputs.py`

GUI 输出：

- 文件数量。
- 自动化统计。
- 复核状态统计。
- 单价匹配行数。

错误展示：

- 捕获 `PricedQuoteOutputError`。
- 主提示格式建议为：`正式报价包校验失败：{message}`。

### 关键业务断言

函数：

```python
assert_real_template_key_results(output_dir: Path) -> None
```

当前来源：`scripts/assert_real_template_key_results.py`

GUI 用途：

- 只在“真实验收”按钮里使用。
- 普通用户生成新项目报价时不应默认运行真实模板断言，因为断言锁的是当前真实样例。

## 建议新增 GUI 服务模块

进入 GUI 实现时，建议新增：

```text
src/cad_budget/gui_services.py
```

建议职责：

- 定义 GUI 专用请求对象，例如 `AcceptanceRequest`、`QuoteGenerationRequest`。
- 调用现有脚本函数。
- 捕获异常并转换为 GUI 友好的 `GuiServiceError`。
- 统一返回可序列化摘要，便于 GUI 和测试使用。

第一版不要把业务规则迁入 GUI 服务层。GUI 服务层只做参数组织、调用、摘要转换和错误归类。

## 进度与取消

当前核心函数是同步执行。GUI 实现时应放到后台线程运行，避免窗口卡死。

建议事件：

- `input_validated`
- `cad_import_started`
- `quantity_started`
- `quote_started`
- `review_started`
- `priced_check_started`
- `completed`
- `failed`

第一版可以先用日志文本模拟进度，不必做精细百分比。

## 文件打开

GUI 不需要解析所有输出文件；只需要提供打开目录和打开文件按钮。

重点输出：

- `quote-priced.xlsx`
- `quote-priced-review.md`
- `quote-priced-review-checklist.xlsx`
- `summary.json`

Windows 下可用 `os.startfile(path)` 打开目录或文件。该调用应只在 GUI 层使用，不放进核心业务服务。
