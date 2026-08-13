# DisT

DisT 是一个面向产品准备度管理的本地交互原型。平台以 PL 主导的新建项目流程为核心，并在同一 Overview 中区分已确认的新项目与只读的存量迭代项目。

## 当前能力

- PL 可创建方案、完成十问 AI 访谈、生成并更新方案报告、发起跨角色团队评审，并在 Leader Check 后确认项目。
- Dsci、DA & RV、Ops 仅在收到评审指示后，通过自己的 Overview 工作台进入对应评审页。
- 团队角色可提交 Issue；PL 回复后，提出角色确认关闭；每位角色完成结论后，PL 才能结束团队评审。
- 项目只有在 PL 点击“确认项目”后，才会出现在 Overview 的项目列表、甘特图和侧栏 Projects 中。
- RI 与 Ecom 保留为只读的存量项目迭代快照。

原型数据、AI 建议、会议纪要、评审内容与迭代任务均为模拟内容；不包含真实账号、权限认证、通知或线上会议能力。

## 新建项目流程

```text
创建方案
  → AI 十问访谈
  → 生成方案报告
  → 会议纪要分析并更新成熟度
  → 发起团队评审
  → Dsci / DA & RV / Ops 提交 Issue 与评审结论
  → PL 回复 Issue；提出角色确认关闭
  → PL 确认团队评审完成
  → Leader Check
  → 确认方案
  → 确认项目
  → 项目进入 Overview 与 Projects
```

团队评审的约束是：所有 Issue 必须关闭，且 Dsci、DA & RV、Ops 均提交评审结论后，PL 才能结束团队评审。

## 角色与页面

| 角色 | 入口 | 能力 |
| --- | --- | --- |
| PL | Overview、新建项目、存量项目页 | 创建并推进新项目；处理团队 Issue；完成 Leader Check 与项目确认 |
| Dsci | Overview 工作台、团队评审页、存量项目页 | 从任务卡进入评审；提交/确认 Issue；提交方法论评审结论 |
| DA & RV | Overview 工作台、团队评审页、存量项目页 | 从任务卡进入评审；提交/确认 Issue；提交数据与调研结论 |
| Ops | Overview 工作台、团队评审页、存量项目页 | 从任务卡进入评审；提交/确认 Issue；提交落地与运营结论 |

角色可通过侧边栏底部的“切换角色”选择。非 PL 不显示新建项目入口，也不能进入 PL 的创建流程。

## 项目展示规则

| 项目状态 | Overview / 侧栏 Projects | 团队工作台 |
| --- | --- | --- |
| PL 创建、AI 访谈、方案报告、团队评审、Leader Check | 不展示为正式项目 | 仅在 PL 发起团队评审后显示相应工作指示 |
| PL 确认项目 | 展示项目列表、甘特图与 Projects 导航 | 保留项目协作上下文 |
| RI / Ecom 存量迭代 | 始终展示为只读项目快照 | 展示对应模拟迭代任务 |

## 本地运行

```bash
cd /Users/jinyc/Desktop/DsiT
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python app.py
```

打开 <http://127.0.0.1:8765>。首次运行会创建 `instance/dist.db`，保存本机的新项目评审与确认状态。

## 测试

```bash
.venv/bin/python -m unittest discover -s tests -v
```

测试覆盖新项目的团队评审、Issue 闭环、项目确认后的 Overview 展示、角色工作台跳转、存量项目快照，以及 UI 资源版本契约。

## 项目结构

```text
app.py                 Flask 页面路由、SQLite 状态与新项目协作 API
index.html             Overview、角色工作台与项目列表
new-project.html       PL 新建项目：创建、访谈、报告、评审与确认
role-review.html       团队角色的 Issue 与评审结论页面
project-view.html      RI / Ecom 的只读迭代项目快照
assets/app.css         基础布局与交互样式
assets/ui-polish.css   统一的卡片、表单、状态与响应式视觉层
assets/app.js          角色切换、工作台任务跳转与评审页交互
assets/new-project.js  PL 新建项目流程交互
tests/                 API 与 UI 契约测试
```

## UI 原则

所有主页面共用同一套基础样式与 UI 资源版本：统一的侧栏、顶部导航、卡片、标签、表单圆角、按钮层级、状态颜色与响应式规则。历史 O2O 页面已重定向至当前体验，避免保留两套视觉语言。
