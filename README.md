# DisT

DisT 是一个面向产品准备度管理的本地交互原型。当前产品路径以 PL 主导的新项目为核心：项目在跨角色评审、最终结论和全部 Issue 闭环前，不会成为正式项目。

所有产品数据、AI 建议、会议纪要、评审结论及迭代任务均为模拟内容；本原型不包含真实账号认证、通知、线上会议或生产级权限控制。

## 核心工作流

```text
创建方案 → AI 十问访谈 → 生成初版报告 → 发起首次团队评审
  →（处理直接回复或记录会议项）→ 启动会议
  → 分析会议纪要并更新报告 → 最终团队评审
  → 全部 Issue 由提出角色确认关闭 → PL 确认项目
  → 排期会议纪要 → PL 确认并分发工作包
  → 项目进入 Overview、Projects 与各角色甘特图
```

工作流门禁：

- 只有 Dsci、DA & RV、Ops 可以提交 Issue 与团队评审结论；首次评审期间可使用项目问答助手了解当前方案、范围、风险和依赖。问答仅供参考，不会改变项目状态或替代正式评审操作。
- PL 可回复 Issue；只有 Issue 的提出角色可以确认其关闭。
- 首次评审完成后才能启动会议；会议纪要会持久化更新报告并开启最终评审。
- 团队角色提交最终“通过”时，会自动写入已查看、已确认状态；无需再单独执行 Leader Check。最终评审仍可提出 Issue：PL 可直接回复并由提出者确认关闭，或标记为需会议后重新进入会议纪要与最终评审。
- 三方最终结论完成且所有 Issue 关闭后，只有 PL 流程会显示“确认项目”。
- 已确认项目可由 PL 上传或粘贴 `.txt`、`.md`、`.docx`、`.pdf` 排期会议纪要，生成可编辑的关键节点与团队工作包（团队、任务、开始/截止日期、依赖、状态）。只有 PL 确认分发后，团队才会在各自 Overview 工作台与甘特图中看到工作包。
- 未确认项目仅显示在相关角色的工作台；确认后才出现在 Overview、甘特图和 Projects 导航中。

RI 与 Ecom 是只读的存量迭代快照，用于演示项目组合与角色任务展示。

## 角色与页面

| 角色 | 入口 | 主要操作 |
| --- | --- | --- |
| PL | Overview、`new-project.html`、`project-view.html` | 创建方案、处理 Issue、推进评审、确认项目、维护/分发排期、导出方案 |
| Dsci | Overview 工作台、`role-review.html`、`project-view.html` | 方法论相关评审、首次评审项目问答、提交/关闭本人 Issue、提交两轮结论、查看已分发工作包 |
| DA & RV | Overview 工作台、`role-review.html`、`project-view.html` | 数据与调研评审、首次评审项目问答、提交/关闭本人 Issue、提交两轮结论、查看已分发工作包 |
| Ops | Overview 工作台、`role-review.html`、`project-view.html` | Scope、交付与运营评审、首次评审项目问答、提交/关闭本人 Issue、提交两轮结论、查看已分发工作包 |

角色通过侧边栏切换。角色选择仅用于本地界面演示，不构成认证或授权边界。

## 本地运行

```bash
cd /Users/jinyc/Desktop/DsiT
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python app.py
```

打开 <http://127.0.0.1:8765>。首次运行创建 `instance/dist.db`，用于保存本机的新项目评审和确认状态。

已确认项目的导出区只对 PL 显示：可下载 Markdown、复制摘要，以及下载由当前最终方案和已确认排期生成的可编辑 6 页 `.pptx` 简报。

旧 O2O API（`/api/o2o/*`）已退役并返回 `410`；旧工作流页面 URL 会重定向到当前体验。启动时会删除历史 O2O 数据和旧 `workflow_state` 表。

## 测试

```bash
.venv/bin/python -m unittest discover -s tests -v
```

测试覆盖工作流门禁、Issue 所有权、项目确认后的可见性、排期草案不自动分发、角色甘特图分发、6 页 PPT 导出、旧 O2O 数据迁移、只读迭代快照，以及共享页面资源与布局契约。

## 项目结构

```text
app.py                         Flask 页面路由、SQLite 持久化与 JSON API
index.html                     Overview、角色工作台、项目组合
new-project.html               PL 新建项目和工作流推进页
role-review.html               三方角色的首次/最终评审页
project-view.html              项目详情、PL 排期维护与方案导出；RI / Ecom 为只读快照
assets/app.js                  角色、Overview、侧栏及评审页交互
assets/new-project.js          新项目创建、访谈、报告与确认交互
assets/app.css                 基础页面样式
assets/ui-polish.css           共享 UI 视觉层
tests/                         API 工作流与 UI 契约测试
.agents/skills/                项目专用开发、前端和测试工作流指引
AGENTS.md                      项目约束、开发规则与测试约定
```

`workflow.html`、`role-workflow.html` 和 `demo.html` 仅保留为历史 URL 的兼容入口；应用会在服务端将它们重定向至当前页面。

## 维护约定

- SQLite 服务端状态与浏览器 `localStorage` 草稿状态必须分离。
- 动态 HTML 写入前须转义内容，并保留角色限制与流程门禁。
- 修改共享 CSS/JS 时，同步更新 HTML 引用的资源版本与 `tests/test_ui_layout_contract.py`。
- 修改 API、持久化或流程状态时，先读 `.agents/skills/dist-workflow/SKILL.md`；修改前端或测试时读取对应 Skill。
