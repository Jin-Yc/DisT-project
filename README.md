# DisT

DisT 是一个面向产品准备度管理的本地交互原型。它用一个可操作的新产品项目和两个只读的存量项目，演示 PL、Dsci、DA & RV、Ops 如何在同一项目组合内协作。

## 当前状态

- 已完成：O2O 的跨角色协作闭环、多项目组合查看、本地持久化、自动化流程测试与跨平台 UI 优化。
- 原型边界：项目数据、AI 建议、会议纪要和 RI / Ecom 的迭代任务均为模拟内容；不包含真实账号、权限认证、文件上传、通知或线上会议能力。

## 项目与使用方式

| 项目 | 类型 | 使用方式 |
| --- | --- | --- |
| O2O | 新产品 Launch | 可操作的完整协作工作流 |
| RI | 存量产品迭代 | 只读查看 v1.2 方案优化的目标、风险与团队任务 |
| Ecom | 存量产品迭代 | 只读查看 v2.4 开发验证的目标、风险与团队任务 |

在 Overview 中点击项目名称即可进入相应页面。RI 和 Ecom 不重复走立项流程，明确表示为“迭代快照”；O2O 是可供操作和测试的项目。

## 角色与能力

| 角色 | 可用页面 | 当前能力 |
| --- | --- | --- |
| PL | Overview、PL 工作流、RI/Ecom 迭代快照 | 推进 O2O、回复 Issue、确认团队结论、编辑并分发任务、确认交付 |
| Dsci | Overview、我的工作流、RI/Ecom 迭代快照 | 查看 O2O Draft Spec、提交与确认本团队 Issue、提交评审结论与交付结果 |
| DA & RV | Overview、我的工作流、RI/Ecom 迭代快照 | 同 Dsci；关注数据覆盖、口径和招募要求 |
| Ops | Overview、我的工作流、RI/Ecom 迭代快照 | 同 Dsci；关注 Scope、上线、KPI 和交付质量 |

角色通过侧边栏底部的“切换角色”选择。团队角色的 Overview 会同时汇总 RI、Ecom 的模拟迭代任务，以及 O2O 已分发的任务。

## O2O 协作流程

```text
PL 澄清需求
  → 确认 Draft Product Spec
  → Dsci / DA & RV / Ops 收到评审任务
  → 各团队提交 Issue 与评审结论
  → PL 回复 Issue；原提出团队确认关闭
  → PL 确认各团队结论
  → 可行性会议纪要回写
  → PL 编辑排期并分发任务
  → 各团队提交交付结果
  → PL 确认交付完成
```

协作规则：PL 不能单方面关闭其他团队提出的 Issue；PL 可回复问题或记录“接受风险”。团队的评审结论和交付结果都需要 PL 确认后才标记为完成。

## 本地运行

项目使用 Flask 提供页面和 API，并以 SQLite 保存 O2O 的演示状态。

```bash
cd /Users/jinyc/Desktop/DsiT
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python app.py
```

打开 <http://127.0.0.1:8765>。首次运行会创建 `instance/dist.db`；它保存本机的 O2O 流程状态。

## 测试

```bash
python3 -m unittest discover -s tests -v
```

测试覆盖 O2O 的跨团队 Issue、评审确认、排期分发、角色 Overview 任务同步、交付确认，以及 RI / Ecom 迭代快照数据。

## 项目结构

```text
app.py                 Flask 页面路由、SQLite 状态与协作 API
index.html             项目组合 Overview 与角色工作台
workflow.html          PL 的 O2O 端到端工作流
role-workflow.html     Dsci / DA & RV / Ops 的 O2O 工作流
project-view.html      RI / Ecom 的只读迭代项目快照
assets/app.css         原有页面基础样式
assets/ui-polish.css   跨平台系统字体与统一 UI 视觉层
assets/app.js          角色切换、页面交互与 API 调用
tests/test_workflow.py 后端协作流程测试
idea.md                初始产品需求草案
```

## UI 原则

界面采用跨平台系统字体栈（macOS、Windows、Linux 均有合适回退），并提供键盘焦点状态、窄屏布局和“减少动态效果”偏好支持。视觉风格借鉴简洁、克制的产品界面层次，但不依赖任何苹果专属字体或系统能力。
