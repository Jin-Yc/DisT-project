# DisT 工作台、导出与确认后清理优化计划

## 目标与已确认决策

在不改变 DisT 现有项目确认门禁、角色导航和服务端工作流状态的前提下，完成以下四项体验优化：

1. 角色工作台无任务时，在任务列表区域内水平及垂直居中显示空态。
2. 优化确认后项目的导出页面排版，并把浏览器端导出修正为明确的 Markdown 与 PPT 大纲下载。
3. 项目完全确认成功后，只清除该项目对应的新建流程缓存；保留其他尚未提交的表单草稿。
4. 已确认项目的详情页不显示 Leader Check；项目确认前（即使已完成最终评审）仍显示该区块并要求完成确认。
5. 修复 AI 访谈发送消息和十个引导问题的交互，并精简访谈快捷操作。
6. 已进入 Projects 列表的已确认项目详情页不显示顶部流程导航栏。

产品决策：

- “PowerPoint”本期定义为浏览器下载的 PPT 大纲，不生成真实 `.pptx` 文件，不新增后端导出接口或依赖。
- 已确认项目保持现有访问行为：能够打开该详情的各 Leader 都可以导出。
- 空态的视觉边界是 `#team-task-list`，而非整个 `#team-workspace` 卡片。
- 导出正文采用业务可读的 Markdown；复制内容与 Markdown 内容一致，不继续复制 JSON。
- “创建完的项目”严格指 `confirmed=true`、已进入 Overview/侧栏 Projects 列表的项目；不包括仅 `final_complete`、仍等待 Leader Check 或 PL 确认的项目。
- “流程导航栏”指新建页顶部横向 `.creator-tabs`，不移除左侧 `#project-nav` 项目导航。
- “仅保留模拟回答快捷方式”只删除三个预设问题快捷 chips；必须保留文本输入、发送、生成报告、对话记录和右侧十问引导列表。

## 现状与不可违反的约束

- 角色工作台是 `index.html#team-workspace`，空态由 `assets/app.js` 的 `setupOverview()` 写入 `#team-task-list`。
- `POST /api/pl-projects/<id>/confirm` 已在 `app.py` 中验证最终评审、所有 Issue 关闭和四方 Leader Check；成功才写入 `confirmed=true`。不得在前端复制、弱化或绕过这些门禁。
- 已确认项目只读详情由 `assets/new-project.js` 的 `loadReadOnlyProject()` 从 `GET /api/pl-projects/<id>?role=<role>` 恢复。SQLite 中的 `leader_checks` 必须保留以兼容历史和审计；本次只隐藏已确认详情中的 UI。
- 新建项目草稿属于 `localStorage`，不能迁移到 SQLite。确认失败、网络失败或被服务端拒绝时，不能删除任何缓存。
- RI 与 Ecom 迭代均为只读快照；角色导航规则、Issue 提交团队确认关闭规则和“仅已确认项目进入 Overview/侧栏”的规则均不可改变。
- 页面共享版本化资源引用与 `tests/test_ui_layout_contract.py` 的断言必须同步。不要为本期引入第三方包或构建工具。

## 实施任务

### 1. 让工作台空态在任务区居中

**文件：** `assets/ui-polish.css`；仅在需要补充语义容器或辅助文本时才修改 `index.html` / `assets/app.js`。

1. 保持 `setupOverview()` 现有的空态数据分支与 API 错误分支分离：`/api/overview` 请求失败必须继续通过既有反馈显示“无法加载团队工作台”，不能渲染为“暂无待处理任务”。
2. 为 `.team-task-list > .empty` 添加精确 CSS：
   - 跨越 Grid 的所有列（`grid-column: 1 / -1`）；
   - 以合理的 `min-height` 建立可见的任务区垂直边界；
   - 使用 Grid/Flex 在该边界内水平、垂直居中；
   - 不影响有任务时原有三列与响应式单列任务卡布局。
3. 保持现有空态文案，除非实现中需要最小化的、可访问的结构调整。不要把团队角色仍有的 RI/Ecom 只读任务误判为空任务。

**验收：**

- PL 的 `pending_projects` 为空时，空态横跨所有列并在任务列表区域居中。
- 窄屏下空态不会溢出，任务存在时卡片布局没有变化。
- API 错误仍展示明确错误而不是空态。

### 2. 重构导出页布局与浏览器端导出

**文件：** `new-project.html`、`assets/new-project.js`、`assets/ui-polish.css`。

1. 在 `#view-export` 内建立专用、稳定的导出 DOM 合同（例如导出主卡、格式说明区、操作区、行动项/摘要侧栏和反馈区域），不要依赖泛用 `.creator-grid .actions` 控制布局。
2. 使用响应式布局：
   - 桌面端：左栏放导出说明/按钮，右栏放行动项与摘要预览；
   - 窄屏：说明、按钮、行动项顺序堆叠，导出按钮全宽且间距一致；
   - 保留现有 `stepUnlocked('export')`：只有 `plan.confirmed` 才能进入导出。
3. 从现有 `plan` 与 `context` 抽取单一的纯内容构建函数（如 `buildExportMarkdown(plan, context)`），同时供 Markdown 下载、PPT 大纲下载和复制使用：
   - 输出项目名称、类型/版本、背景、目标客户、痛点、价值主张、包含与不包含范围、数据/指标/交付/协作角色、风险/依赖/假设/待确认、结论和行动项；
   - 全部列表项使用正确的 `- ` Markdown 格式；
   - 对空字段提供统一的业务可读占位，不能输出 `undefined`、异常或格式破损；
   - 用户可控内容写入页面时继续用既有 `escape()` 转义。
4. 将现有不准确的“PowerPoint”导出改成明确的“下载 PPT 大纲”，使按钮文字、反馈、MIME 和扩展名一致：
   - Markdown 下载使用 `.md` 和 `text/markdown;charset=utf-8`；
   - PPT 大纲也使用清晰标注的文本格式（推荐 `.md`），不再下载扩展名为 `.txt` 却声称是 PowerPoint 的文件；
   - 使用清理过路径分隔符、控制字符和 Windows 保留字符的文件名，同时保留中文项目名。
5. 强化交互可靠性：
   - 导出/复制进行期间禁用相应按钮，完成后恢复；
   - `navigator.clipboard` 不可用或权限失败时给出明确失败反馈，成功时给出成功反馈；
   - 失败不得丢失方案、切换视图或造成成功假象。
6. 不新增后端路由。本期导出仍是浏览器端行为，且已确认详情保持各 Leader 可导出。

**验收：**

- 已确认项目在桌面和窄屏导出页均有清晰、稳定的层次与响应式排版。
- Markdown、PPT 大纲和复制三种输出包含同一完整且格式正确的方案摘要。
- 下载文件类型/扩展名/按钮文案相符；复制失败可见，重复点击不会产生并发操作。
- 未确认项目依旧不能通过正常 UI 使用导出。

### 3. 仅在项目确认成功后清理该项目的流程缓存

**文件：** `assets/new-project.js`。

1. 跟踪 `confirmProjectV2()` 的成功分支：只在 `/api/pl-projects/<id>/confirm` 返回成功且 `confirmed === true` 后开始清理。
2. 删除当前已确认项目的流程存储项（`dist-new-project-flow`）并从 `dist-new-project-history` 中剔除当前 `activeId` 对应记录，然后以既有存储格式保存剩余历史。
3. 不无条件删除全局 `dist-new-project-draft`：它可能属于另一份尚未提交的表单草稿，当前结构没有可靠的项目 ID 关联。
4. 确认成功后继续转入已确认、只读详情的既有流程；刷新或重新打开时不可恢复该已确认项目为“创建中”状态。
5. 对解析损坏的历史缓存采用项目既有的显式、安全处理模式；不要用静默吞错伪装成清理成功。

**验收：**

- 成功确认后，本项目 flow key 不存在，history 中不存在该项目；其他草稿与历史项目不受影响。
- 确认请求返回错误、网络失败或缺少门禁时，所有本地缓存保持原样。
- 此项不改变服务端已确认项目可见性或确认门禁。

### 4. 在已确认项目详情隐藏 Leader Check

**文件：** `new-project.html`、`assets/new-project.js`。

1. 给 Leader Check 区块添加稳定容器选择器（例如 `#creator-leader-check`），以便无歧义控制和测试。
2. 在 `loadReadOnlyProject()` 按服务端 `data.confirmed` 设置视图状态；在 `renderDetail()` 中也以该状态决定容器是否显示，防止后续重渲染将其恢复。
3. `confirmed === true` 时隐藏整个 Leader Check 区块及其确认按钮；不删除服务器响应中的 `leader_checks`，也不修改持久化字段。
4. `final_complete && !confirmed` 时必须继续显示该区块、现有四方状态及确认按钮，确保项目仍必须通过全部 Leader Check 才能调用确认。

**验收：**

- 已确认项目的详情不展示 Leader Check。
- 未确认但已完成最终评审的项目仍展示 Leader Check，缺少任一确认时后端仍返回现有拒绝结果。
- 详情只读权限、Issue 和项目确认 API 行为无回归。

### 5. 修复 AI 访谈消息与十问引导交互，并删除非必要快捷问题

**文件：** `new-project.html`、`assets/new-project.js`。

1. 修复 `#send-message` 的绑定：事件处理函数不得直接传给接收“模拟回答文本”参数的 `sendMessage(simulatedText = '')`。浏览器会传入 `PointerEvent`，当前实现会把它展示为 `[object PointerEvent]`，并在后续对 `.trim()` 的调用中中断进度和缓存更新。改为零参数包装调用（如 `() => sendMessage()`）。
2. 令 `sendMessage` 只使用字符串模拟文本；普通点击始终读取并清理 `#message-input`。对本地旧缓存中非字符串回答做类型保护，避免已有异常缓存导致 `updateProgress()` 崩溃。
3. 保持且验证十问完整交互：发送当前题答案后更新用户消息、下一题、`#interview-count`、`#progress-list`、结构化摘要和 `dist-new-project-flow`。点击右侧十问必须能回到对应题目、回填答案并支持 Enter/Space 键盘操作。
4. 当第十题调用 `/api/positioning-assistant` 时检查 `response.ok`。失败要在 `#creator-feedback` 显示显式错误，保留输入以便重试，且不能追加空 AI 消息；成功后才写入用户消息和 AI 回复。
5. 从 `.quick-prompts` 删除三个预设问题快捷按钮（“客户是谁？”、“主要痛点是什么？”、“首版功能”），仅保留 `#simulate-answer`。同时删除不再存在的 `[data-prompt]` 监听器。
6. 动态对话内容继续使用既有 `escape()` 或 `textContent`，不得把用户输入、localStorage 或 API 返回内容直接插入 `innerHTML`。

**验收：**

- 输入首题后点击发送，原文显示在对话中，不出现 `[object PointerEvent]`，计数更新为 `1 / 10`。
- 十道问题可逐项发送、点击返回并修改，进度、摘要和缓存持续正确更新；网络/API 失败有明确可见错误。
- 访谈输入区只剩“模拟回答”这一快捷按钮，完成十问和生成报告的必要输入/控制仍可用。

### 6. 在已确认（进入 Projects 列表）项目详情隐藏顶部流程导航

**文件：** `new-project.html`、`assets/new-project.js`、`assets/ui-polish.css`。

1. 为顶部 `.creator-tabs` 添加稳定选择器（例如 `#creator-workflow-nav`）；不要移除左侧 `#project-nav`。
2. 在集中更新视图状态的逻辑中，只按 `Boolean(plan?.confirmed)` 设置该导航的 `hidden` 属性：
   - 已确认项目从 `?project_id=` 恢复时隐藏；
   - 在当前创建流程中确认成功并进入已确认详情时隐藏；
   - `final_complete && !confirmed` 时保持显示，供用户查看流程与完成所有 Leader Check/PL 确认操作；
   - 新建、未完成恢复和重置流程时恢复显示。
3. 在 CSS 显式添加 `.creator-tabs[hidden] { display: none; }`。现有 `.creator-tabs { display: flex; }` 否则会覆盖浏览器 `[hidden]` 默认样式。
4. 仅隐藏完成态的导航 UI；不得更改 `switchView()` 或 `stepUnlocked()` 的阶段门禁，且不影响团队 Leader 进入只读详情、完成其 Leader Check 或 PL 的最终确认门禁。

**验收：**

- 已确认项目通过 `new-project.html?project_id=<id>` 打开时，顶部流程导航不可见。
- 完成最终评审但尚未确认的项目、以及新建或未完成项目中流程导航照常可见，既有阶段限制和角色导航无回归。

## 测试与验证顺序

1. 更新 `tests/test_ui_layout_contract.py`：
   - 断言空态的全宽/居中 CSS 合同；
   - 断言导出专用 DOM、按钮 ID 与 JS handler/文本格式合同；
   - 断言已确认状态对应 Leader Check 隐藏控制，且未确认最终评审状态仍保留容器；
   - 断言 AI 访谈保留 `#simulate-answer`、删除三个 `data-prompt` 快捷问题，且发送按钮使用零参数包装调用而非直接传入事件；
   - 断言仅确认状态控制 `#creator-workflow-nav` 隐藏，`final_complete && !confirmed` 状态仍显示，且 `.creator-tabs[hidden]` 明确为 `display: none`；
   - 如实际升级任一 asset query version，同步更新所有 HTML 引用与本测试的版本断言。
2. 更新 `tests/test_workflow.py`（仅保护已有关联行为，不为纯前端逻辑新增无关 API）：
   - 确认前缺任一 Leader Check 仍被拒绝；
   - 完整确认仍返回 `confirmed=true`、既有 stage/readiness 和完整 `leader_checks`；
   - 已确认项目仍仅在正式 Overview 项目列表中可见。
3. 先运行：

   ```powershell
   .\.venv\Scripts\python.exe -m unittest tests.test_ui_layout_contract.UiLayoutContractTest -v
   .\.venv\Scripts\python.exe -m unittest tests.test_workflow.WorkflowApiTest -v
   ```

4. 两个目标类通过后运行：

   ```powershell
   .\.venv\Scripts\python.exe -m unittest discover -s tests -v
   ```

5. Windows 全量测试若仅在临时 SQLite 清理阶段出现既有 `WinError 32`，与断言/功能失败分开报告；本次没有改连接生命周期，不应将其归为回归。
6. 在现有仓库没有浏览器 DOM 测试依赖的前提下，补充手工 smoke test：
   - 新建方案后输入并发送首题，确认原文显示且计数为 `1 / 10`；
   - 依次完成十题，并点击右侧问题返回修改，确认回填、进度和键盘操作；
   - 确认访谈区只剩模拟回答快捷按钮；
   - 确认最终评审完成但尚未确认时顶部流程栏仍显示；已确认项目从 URL 恢复时顶部流程栏隐藏，但左侧项目导航保留。

## 非目标

- 不生成真实 PPTX，不引入 PPTX 依赖、公司模板、导出审计记录或服务器文件存储。
- 不修改 SQLite 数据模型、确认 API 的门禁或响应形状。
- 不清空与当前确认项目无可靠关联的 `dist-new-project-draft`。
- 不改变任何角色权限、项目可见性、RI/Ecom 只读规则或 Issue 关闭责任。
