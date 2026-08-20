const roles = ['PL', 'Dsci', 'DA & RV', 'Ops'];
const teamRoles = ['Dsci', 'DA & RV', 'Ops'];
const roleKey = 'dist-role';

function currentRole() { return localStorage.getItem(roleKey) || 'PL'; }

function applyRole(role) {
  const selected = roles.includes(role) ? role : 'PL';
  document.body.classList.toggle('role-pl', selected === 'PL');
  // Keep role-specific navigation deterministic even when a browser applies
  // different default styles to hidden links or native controls.
  document.querySelectorAll('.pl-only').forEach(node => node.toggleAttribute('hidden', selected !== 'PL'));
  document.querySelectorAll('.team-only').forEach(node => node.toggleAttribute('hidden', selected === 'PL'));
  document.querySelectorAll('#role-select').forEach(select => select.value = selected);
  document.querySelectorAll('#role-name').forEach(node => node.textContent = selected);
  document.querySelectorAll('#role-avatar').forEach(node => node.textContent = selected === 'DA & RV' ? 'DA' : selected.slice(0, 2).toUpperCase());
  document.querySelectorAll('#topbar-role').forEach(node => node.textContent = selected);
  localStorage.setItem(roleKey, selected);
  const isPlWorkflow = location.pathname.endsWith('/workflow.html');
  const isTeamWorkflow = location.pathname.endsWith('/role-workflow.html');
  if (isPlWorkflow && selected !== 'PL') location.href = 'index.html';
  if (isTeamWorkflow && selected === 'PL') location.href = 'workflow.html';
  if (location.pathname.endsWith('/new-project.html') && selected !== 'PL' && !new URLSearchParams(location.search).get('project_id')) location.href = 'index.html';
  if (location.pathname.endsWith('/role-review.html') && selected === 'PL') location.href = 'index.html';
}

function setupRoles() {
  applyRole(currentRole());
  document.querySelectorAll('#role-select').forEach(select => select.addEventListener('change', event => {
    const role = event.target.value;
    applyRole(role);
    location.href = 'index.html';
  }));
}

async function api(path, options = {}) {
  const response = await fetch(path, {headers: {'Content-Type': 'application/json', ...(options.headers || {})}, ...options});
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || '操作未完成，请稍后重试。');
  return body;
}

function setFeedback(selector, message, error = false) {
  const node = document.querySelector(selector);
  if (!node) return;
  node.textContent = message;
  node.className = `workflow-feedback show${error ? ' error' : ''}`;
}

function statusText(status) {
  return ({pending: '待处理', awaiting_pl_confirmation: '待 PL 确认', completed: '已完成', open: '待 PL 处理', awaiting_submitter: '待提出团队确认', closed: '已关闭', accepted_risk: '已接受风险', '待确认': '待确认', '进行中': '进行中', '待开始': '待开始'})[status] || status;
}
function escapeHtml(value) {
  const node = document.createElement('span'); node.textContent = value == null ? '' : String(value); return node.innerHTML;
}

function renderOverviewGantt(items) {
  const gantt = document.querySelector('#overview-gantt');
  if (!gantt || !items?.length) return;
  const dates = items.flatMap(item => [item.start_date, item.due_date]).filter(Boolean).sort();
  const start = new Date(`${dates[0]}T00:00:00`), end = new Date(`${dates.at(-1)}T00:00:00`);
  const range = Math.max(1, end - start);
  const ticks = Array.from({length: 8}, (_, index) => new Date(start.getTime() + (range * index / 7)));
  const format = value => `${value.getMonth() + 1}/${String(value.getDate()).padStart(2, '0')}`;
  const rows = items.map(item => {
    const left = Math.max(0, ((new Date(`${item.start_date}T00:00:00`) - start) / range) * 100);
    const width = Math.max(5, ((new Date(`${item.due_date}T00:00:00`) - new Date(`${item.start_date}T00:00:00`)) / range) * 100);
    return `<div class="gantt-row"><div class="gantt-name"><b>${escapeHtml(item.project)}</b><small>${escapeHtml(item.role)} · ${escapeHtml(item.start_date)} 至 ${escapeHtml(item.due_date)}</small></div><div class="gantt-track"><span class="gantt-bar delivery" style="left:${left.toFixed(1)}%;width:${width.toFixed(1)}%"><em style="width:0"></em>${escapeHtml(item.title)}</span></div></div>`;
  }).join('');
  gantt.innerHTML = `<div class="gantt-header"><span>项目 / 工作项</span>${ticks.map(tick => `<span>${format(tick)}</span>`).join('')}</div>${rows}`;
  gantt.setAttribute('aria-label', `${format(start)} 至 ${format(end)} 的已分发项目排期`);
}

async function setupOverview() {
  const table = document.querySelector('#projects tbody'); if (!table) return;
  try {
    const role = currentRole(); const data = await api(`/api/overview?role=${encodeURIComponent(role)}`);
    table.innerHTML = data.projects.map(project => {
      const link = `project-view.html?project=${encodeURIComponent(project.id)}`;
      return `<tr><td><a href="${link}">${escapeHtml(project.name)}</a></td><td>${escapeHtml(project.type)}</td><td><span class="tag ${project.pl_project ? 'amber' : 'blue'}">${escapeHtml(project.stage)}</span></td><td><span class="tag ${project.readiness.includes('待处理') || project.readiness.includes('风险') ? 'red' : 'amber'}">${escapeHtml(project.readiness)}</span></td><td>${escapeHtml(project.next)}</td></tr>`;
    }).join('');
    renderOverviewGantt(data.gantt);
    const workspace = document.querySelector('#team-workspace');
    if (workspace) {
      if (role === 'PL') {
        const pendingProjects = data.pending_projects || [];
        document.querySelector('#team-workspace-title').textContent = 'PL 工作台';
        document.querySelector('#team-workspace-desc').textContent = pendingProjects.length ? '以下未确认项目保存在服务器中；选择项目后可继续当前阶段。' : '暂无需要继续处理的未确认项目。';
        document.querySelector('#team-task-list').innerHTML = pendingProjects.length ? pendingProjects.map(project => `<a class="team-task task-link" href="new-project.html?project_id=${encodeURIComponent(project.project_id)}"><span class="tag amber">${escapeHtml(project.kind)} · ${escapeHtml(project.project)}</span><b>${escapeHtml(project.title)}</b><span>${escapeHtml(project.action)} · ${escapeHtml(project.status)}</span></a>`).join('') : '<div class="empty">暂无待处理任务。</div>';
      } else {
        document.querySelector('#team-workspace-title').textContent = `${role} 的工作台`;
        document.querySelector('#team-workspace-desc').textContent = data.tasks.length ? '以下任务区分既有项目与 PL 新项目；请按工作指示完成评审或执行。' : `PL 尚未向 ${role} 分配新项目任务。`;
        document.querySelector('#team-task-list').innerHTML = data.tasks.length ? data.tasks.map(task => task.review_task ? `<a class="team-task task-link" href="${task.phase === 'final_complete' ? `new-project.html?project_id=${encodeURIComponent(task.project_id)}` : `role-review.html?project=${encodeURIComponent(task.project_id)}`}"><span class="tag amber">${escapeHtml(task.kind)} · ${escapeHtml(task.project)}</span><b>${escapeHtml(task.title)}</b><span>${escapeHtml(task.action || task.status)} · 点击完成当前角色操作</span></a>` : `<a class="team-task task-link" href="project-view.html?project=${encodeURIComponent(task.project_id)}"><span class="tag blue">${escapeHtml(task.kind)} · ${escapeHtml(task.project)}</span><b>${escapeHtml(task.title)}</b><span>${escapeHtml(statusText(task.status))} · 截止 ${escapeHtml(task.due_date || '待排期')}</span></a>`).join('') : '<div class="empty">暂无待处理任务。</div>';
      }
    }
  } catch (error) {
    setFeedback('#team-task-list', `无法加载团队工作台：${error.message}`, true);
  }
}

let projectViewData = null;

function exportValue(value) { return typeof value === 'string' && value.trim() ? value.trim() : '待确认'; }
function exportList(items) { return Array.isArray(items) && items.length ? items.map(item => `- ${exportValue(item)}`).join('\n') : '- 待确认'; }
function buildProjectExportMarkdown(item, projectContext) { const current = item || {}, positioning = current.positioning || {}, scope = current.scope || {}, business = current.business || {}, risks = current.risks || {}, verdict = current.verdict || {}; return `# ${exportValue(projectContext.productName)}\n\n- 类型/版本：${exportValue(projectContext.projectType)}${projectContext.iterationVersion ? ` · ${exportValue(projectContext.iterationVersion)}` : ''}\n\n## 产品定位\n\n- 背景：${exportValue(positioning.background)}\n- 目标客户：${exportValue(positioning.target)}\n- 客户痛点：${exportValue(positioning.pain)}\n- 价值主张：${exportValue(positioning.value)}\n\n## 范围\n\n### 包含范围\n${exportList(scope.inScope)}\n\n### 暂不包含\n${exportList(scope.outScope)}\n\n## 业务要求\n\n### 数据\n${exportList(business.data)}\n\n### 指标\n${exportList(business.metrics)}\n\n### 交付\n${exportList(business.delivery)}\n\n## 风险与待确认\n\n### 风险\n${exportList(risks.risks)}\n\n### 依赖\n${exportList(risks.dependencies)}\n\n## 结论\n\n- ${exportValue(verdict.title)}：${exportValue(verdict.text)}\n\n## 行动项\n${exportList(current.actions)}`; }

function renderScheduleEditor(project) {
  const schedule = project.schedule || {minutes:'', milestones:[], work_packages:[]};
  const milestoneList = document.querySelector('#schedule-milestones');
  document.querySelector('#schedule-minutes').value = schedule.minutes || '';
  const renderMilestone = (item = {}) => `<div class="schedule-row"><input data-milestone-title placeholder="例如：范围冻结" value="${escapeHtml(item.title || '')}"><input data-milestone-date type="date" value="${escapeHtml(item.due_date || '')}"><button class="button secondary" data-remove-milestone type="button">删除</button></div>`;
  milestoneList.innerHTML = (schedule.milestones || []).map(renderMilestone).join('') || renderMilestone();
  const packageList = document.querySelector('#schedule-work-packages');
  const renderPackage = (item = {}) => `<div class="work-package-row"><select data-package-role>${teamRoles.map(role => `<option value="${role}"${item.role === role ? ' selected' : ''}>${role}</option>`).join('')}</select><input data-package-title placeholder="任务" value="${escapeHtml(item.title || '')}"><input data-package-start type="date" value="${escapeHtml(item.start_date || '')}"><input data-package-due type="date" value="${escapeHtml(item.due_date || '')}"><input data-package-dependency placeholder="依赖（可选）" value="${escapeHtml(item.dependency || '')}"><select data-package-status><option${item.status === '进行中' ? '' : ' selected'}>待开始</option><option${item.status === '进行中' ? ' selected' : ''}>进行中</option><option${item.status === '已完成' ? ' selected' : ''}>已完成</option></select><button class="button secondary" data-remove-work-package type="button">删除</button></div>`;
  packageList.innerHTML = (schedule.work_packages || []).map(renderPackage).join('') || renderPackage();
  document.querySelector('#schedule-analysis').textContent = schedule.analysis || 'AI 建议仅为草案，保存前可由 PL 调整。';
}

async function saveProjectSchedule() {
  if (!projectViewData) return;
  const milestones = [...document.querySelectorAll('#schedule-milestones .schedule-row')].map(row => ({title: row.querySelector('[data-milestone-title]').value.trim(), due_date: row.querySelector('[data-milestone-date]').value}));
  const work_packages = [...document.querySelectorAll('#schedule-work-packages .work-package-row')].map(row => ({role: row.querySelector('[data-package-role]').value, title: row.querySelector('[data-package-title]').value.trim(), start_date: row.querySelector('[data-package-start]').value, due_date: row.querySelector('[data-package-due]').value, dependency: row.querySelector('[data-package-dependency]').value.trim(), status: row.querySelector('[data-package-status]').value}));
  const team_schedules = projectViewData.schedule?.team_schedules || {};
  try {
    const updated = await api(`/api/pl-projects/${encodeURIComponent(projectViewData.id)}/schedule`, {method:'POST', body:JSON.stringify({role:'PL', minutes:document.querySelector('#schedule-minutes').value.trim(), milestones, team_schedules, work_packages})});
    projectViewData.schedule = updated.schedule;
    renderProjectSchedule(projectViewData);
    renderScheduleEditor(projectViewData);
    setFeedback('#iteration-feedback', '项目计划已确认并分发到各团队 Overview 甘特图。');
  } catch (error) { setFeedback('#iteration-feedback', error.message, true); }
}

function renderProjectSchedule(project) {
  const milestones = project.schedule?.milestones || [];
  document.querySelector('#project-milestone-list').innerHTML = milestones.length ? milestones.map(item => `<div class="check"><b>${escapeHtml(item.title)}</b>${item.due_date ? `计划完成：${escapeHtml(item.due_date)}` : '待确定日期'}</div>`).join('') : '<div class="check"><b>关键节点待补充</b>PL 保存排期后将显示节点与计划完成日期。</div>';
  const packages = project.schedule?.work_packages || [];
  document.querySelector('#iteration-task-list').innerHTML = packages.length ? packages.map(item => `<div class="team-task"><span class="tag blue">${escapeHtml(item.role)}</span><b>${escapeHtml(item.title)}</b><span>${escapeHtml(item.start_date)} 至 ${escapeHtml(item.due_date)}${item.dependency ? ` · 依赖 ${escapeHtml(item.dependency)}` : ''}</span></div>`).join('') : '<div class="empty">尚未确认可分发的团队工作包。</div>';
}

function downloadProjectExport(kind) {
  if (kind === 'ppt') { location.href = `/api/pl-projects/${encodeURIComponent(projectViewData.id)}/export/pptx`; return; }
  const text = buildProjectExportMarkdown(projectViewData.final_plan, projectViewData.context);
  const link = document.createElement('a'); link.href = URL.createObjectURL(new Blob([text], {type:'text/markdown;charset=utf-8'})); link.download = `${exportValue(projectViewData.name).replace(/[\\/:*?"<>|\x00-\x1f]/g, '-')}${kind === 'ppt' ? '-PPT大纲' : ''}.md`; link.click(); setTimeout(() => URL.revokeObjectURL(link.href), 0);
  setFeedback('#iteration-feedback', kind === 'ppt' ? 'PPT 大纲已下载。' : 'Markdown 已下载。');
}

async function setupIterationProject() {
  if (!document.querySelector('#iteration-project-app')) return;
  const projectId = new URLSearchParams(location.search).get('project');
  if (!projectId) {
    document.querySelector('#iteration-feedback').textContent = '请选择一个项目。';
    document.querySelector('#iteration-feedback').className = 'workflow-feedback show error';
    return;
  }
  try {
    const project = await api(`/api/projects/${projectId}?role=${encodeURIComponent(currentRole())}`);
    projectViewData = project;
    const persisted = Boolean(project.pl_project);
    document.title = `DisT · ${project.name} 项目概览`;
    document.querySelector('#iteration-sidebar-name').textContent = project.name;
    document.querySelector('#iteration-sidebar-stage').textContent = project.stage;
    document.querySelector('#iteration-project-name').textContent = `${project.name} · 项目概览`;
    document.querySelector('#iteration-project-objective').textContent = project.objective;
    const versionTag = document.querySelector('#iteration-project-version');
    versionTag.textContent = project.iteration || '';
    versionTag.hidden = persisted && !project.context?.iterationVersion;
    document.querySelector('#iteration-project-stage').textContent = project.stage;
    document.querySelector('#iteration-objective').textContent = project.objective;
    document.querySelector('#iteration-scope').textContent = project.scope;
    document.querySelector('#iteration-risk').textContent = project.risk;
    document.querySelector('#project-sidebar-note').textContent = persisted ? '已确认项目 · 可维护排期' : '仅供查看的模拟项目';
    document.querySelector('#project-eyebrow').textContent = persisted ? 'Confirmed project · execution planning' : 'Existing product · iteration snapshot';
    document.querySelector('#project-crumb').textContent = persisted ? '项目概览' : '项目迭代概览';
    document.querySelector('#project-banner-icon').textContent = persisted ? '✓' : '↻';
    document.querySelector('#project-banner-title').textContent = persisted ? '已确认项目' : '存量项目迭代';
    document.querySelector('#project-banner-text').textContent = persisted ? '确认方案已归档；PL 可维护排期会议结论与关键节点。' : '这个项目已进入迭代阶段；用于查看当前目标、边界、风险和各团队的工作。';
    document.querySelector('#project-scope-title').textContent = persisted ? '已确认方案范围' : '本轮迭代范围';
    document.querySelector('#project-schedule-title').textContent = persisted ? '跨团队项目排期' : '跨团队迭代排期';
    document.querySelector('#project-schedule-description').textContent = persisted ? 'PL 可分析排期会议纪要、确认关键节点与团队排期建议。' : '显示当前迭代中各团队的分工与截止时间。';
    document.querySelector('#project-view-note').innerHTML = persisted ? '<h2>项目状态</h2><div class="check"><b>已确认项目</b>最终方案、排期和工作包均保存于服务器。</div>' : '<h2>项目状态</h2><div class="check"><b>这是模拟快照</b>可切换项目和角色查看对应工作，不会改变模拟项目状态。</div>';
    renderProjectSchedule(project);
    document.querySelector('#project-schedule-editor').hidden = !persisted || project.role !== 'PL';
    const canExport = persisted && project.role === 'PL';
    document.querySelector('#project-export-card').hidden = !canExport;
    document.querySelector('#project-view-note').hidden = canExport;
    document.querySelector('.project-spec-layout').classList.toggle('single-column', persisted && !canExport);
    if (persisted && project.role === 'PL') renderScheduleEditor(project);
    if (persisted && project.role === 'PL') {
      document.querySelector('#simulate-schedule-minutes').addEventListener('click', () => { document.querySelector('#schedule-minutes').value = '会议主题：项目排期确认（2026-08-19）\n\n会议结论：8月20日确认范围与依赖；8月23日完成方法复核；8月26日完成数据核对；8月29日试点验收。\n\n团队任务：Dsci 负责方法与标准复核；DA & RV 负责数据口径与样本核对；Ops 负责上线窗口与验收准备。'; setFeedback('#iteration-feedback', '已填入带日期、团队和任务的模拟纪要，请点击分析生成工作包。'); });
      document.querySelector('#analyze-project-schedule').addEventListener('click', async () => { const form = new FormData(); form.append('minutes', document.querySelector('#schedule-minutes').value.trim()); const file = document.querySelector('#schedule-file').files[0]; if (file) form.append('file', file); try { const response = await fetch(`/api/pl-projects/${encodeURIComponent(project.id)}/schedule/analyze`, {method:'POST', body:form}); const data = await response.json(); if (!response.ok) throw new Error(data.error); project.schedule = {...project.schedule, ...data}; renderScheduleEditor(project); renderProjectSchedule(project); setFeedback('#iteration-feedback', data.analysis); } catch (error) { setFeedback('#iteration-feedback', error.message, true); } });
    }
    if (project.role !== 'PL') {
      document.querySelector('#iteration-my-work').hidden = !persisted;
      const packages = project.my_work_packages || [];
      document.querySelector('#iteration-my-task').innerHTML = packages.length ? packages.map(item => `<div class="team-task"><span class="tag blue">${escapeHtml(project.role)}</span><b>${escapeHtml(item.title)}</b><span>${escapeHtml(statusText(item.status))} · ${escapeHtml(item.start_date)} 至 ${escapeHtml(item.due_date)}</span></div>`).join('') : '<div class="empty">PL 尚未确认分发你的项目工作包。</div>';
    }
    document.querySelector('#add-schedule-milestone')?.addEventListener('click', () => { document.querySelector('#schedule-milestones').insertAdjacentHTML('beforeend', '<div class="schedule-row"><input data-milestone-title placeholder="例如：范围冻结"><input data-milestone-date type="date"><button class="button secondary" data-remove-milestone type="button">删除</button></div>'); });
    document.querySelector('#schedule-milestones')?.addEventListener('click', event => { if (event.target.closest('[data-remove-milestone]')) event.target.closest('.schedule-row').remove(); });
    document.querySelector('#add-work-package')?.addEventListener('click', () => { document.querySelector('#schedule-work-packages').insertAdjacentHTML('beforeend', '<div class="work-package-row"><select data-package-role><option>Dsci</option><option>DA &amp; RV</option><option>Ops</option></select><input data-package-title placeholder="任务"><input data-package-start type="date"><input data-package-due type="date"><input data-package-dependency placeholder="依赖（可选）"><select data-package-status><option>待开始</option><option>进行中</option><option>已完成</option></select><button class="button secondary" data-remove-work-package type="button">删除</button></div>'); });
    document.querySelector('#schedule-work-packages')?.addEventListener('click', event => { if (event.target.closest('[data-remove-work-package]')) event.target.closest('.work-package-row').remove(); });
    document.querySelector('#save-project-schedule')?.addEventListener('click', saveProjectSchedule);
    document.querySelector('#export-ppt')?.addEventListener('click', () => downloadProjectExport('ppt'));
    document.querySelector('#export-md')?.addEventListener('click', () => downloadProjectExport('md'));
    document.querySelector('#copy-summary')?.addEventListener('click', async () => { try { await navigator.clipboard.writeText(buildProjectExportMarkdown(projectViewData.final_plan, projectViewData.context)); setFeedback('#iteration-feedback', '方案摘要已复制。'); } catch (_) { setFeedback('#iteration-feedback', '复制失败：请检查剪贴板权限。', true); } });
  } catch (error) { setFeedback('#iteration-feedback', error.message, true); }
}

function projectLink(project, role) {
  return `project-view.html?project=${encodeURIComponent(project.id)}`;
}

let reviewAssistantProjectId = null;

function appendReviewAssistantMessage(role, text) {
  const log = document.querySelector('#review-assistant-log');
  const message = document.createElement('div');
  message.className = `message ${role}`;
  const avatar = document.createElement('span');
  avatar.className = 'avatar';
  avatar.textContent = role === 'user' ? currentRole().slice(0, 2).toUpperCase() : 'AI';
  const body = document.createElement('div');
  const paragraph = document.createElement('p');
  paragraph.textContent = text;
  body.append(paragraph); message.append(avatar, body); log.append(message);
  log.scrollTop = log.scrollHeight;
}

function renderPlRoleReview(state, role) {
  document.querySelector('#role-review-title').textContent = `${state.name} · 团队评审`;
  document.querySelector('#role-review-role').textContent = role;
  document.querySelector('#role-review-focus').textContent = state.role_focus;
  const finalPlan = state.final_plan || {};
  const planText = (...values) => values.flat().filter(value => value != null && value !== '').join('； ') || '未提供';
  document.querySelector('#role-review-background').textContent = finalPlan.positioning?.background || state.context?.projectDesc || state.name;
  document.querySelector('#role-review-report-label').textContent = state.review_phase === 'final_review' ? '更新报告关键内容' : '初版报告说明';
  document.querySelector('#role-review-report').textContent = state.review_phase === 'final_review' ? `报告 v${state.report_version}：${(state.minutes_updates || []).join('； ') || '会议更新已持久化。'}` : '初版报告：请重点检查背景、范围、数据与交付假设。';
  document.querySelector('#role-review-positioning').textContent = planText(finalPlan.positioning?.target, finalPlan.positioning?.pain, finalPlan.positioning?.value, finalPlan.positioning?.pitch);
  document.querySelector('#role-review-scope').textContent = planText(finalPlan.scope?.inScope, finalPlan.scope?.outScope);
  document.querySelector('#role-review-business').textContent = planText(finalPlan.business?.data, finalPlan.business?.metrics, finalPlan.business?.delivery, finalPlan.business?.roles);
  document.querySelector('#role-review-risks').textContent = planText(finalPlan.risks?.risks, finalPlan.risks?.dependencies, finalPlan.risks?.assumptions, finalPlan.risks?.pending);
  document.querySelector('#role-review-phase').textContent = ({initial_review:'首次评审：可提交 Issue 或确认无 Issue 后提交结论。', meeting:'会议进行中：等待 PL 更新报告。', final_review:'最终评审：请先确认本人会议项已解决，再提交最终结论。', final_complete:'最终评审已完成，等待 Leader Check。'})[state.review_phase] || state.stage;
  document.querySelector('#role-review-instruction').textContent = state.team_instructions[role];
  const task = state.review_phase === 'final_review' ? state.final_review_tasks?.[role] : state.first_review_tasks?.[role] || state.role_review_task || {};
  document.querySelector('#role-review-task-status').textContent = statusText(task.status || 'pending');
  const firstRound = state.review_phase === 'initial_review', finalRound = state.review_phase === 'final_review';
  document.querySelectorAll('#role-review-app input,#role-review-app select,#role-review-app textarea,#submit-pl-issue,#submit-pl-review').forEach(node => node.disabled = task.status !== 'pending');
  document.querySelector('#initial-review-issue-form').hidden = !(firstRound || finalRound);
  const assistant = document.querySelector('#role-review-assistant');
  assistant.hidden = !firstRound;
  document.querySelector('#review-assistant-question').disabled = !firstRound;
  document.querySelector('#send-review-assistant').disabled = !firstRound;
  if (firstRound && reviewAssistantProjectId !== state.id) {
    reviewAssistantProjectId = state.id;
    document.querySelector('#review-assistant-log').replaceChildren();
    appendReviewAssistantMessage('ai', `我是项目问答助手，可以结合当前方案和“${state.role_focus}”回答你的评审问题。`);
  }
  document.querySelector('#submit-pl-review').textContent = finalRound ? '通过并自动确认 →' : '完成首次评审 →';
  const issues = state.my_issues || [];
  document.querySelector('#pl-my-issues').innerHTML = issues.length ? issues.map(issue => `<div class="check ${issue.status === 'closed' ? 'good' : issue.status === 'open' ? 'high' : ''}"><b>${escapeHtml(issue.title)} · ${escapeHtml(statusText(issue.status))}</b><span>${escapeHtml(issue.detail)}</span>${issue.pl_response ? `<span><b>PL 回复：</b>${escapeHtml(issue.pl_response)}</span>` : ''}${issue.status === 'awaiting_submitter' ? `<button class="button secondary issue-confirm-action" type="button" data-pl-issue-confirm="${issue.id}">确认直接回复已解决</button>` : ''}${issue.status === 'meeting_required' && state.review_phase === 'final_review' ? `<button class="button secondary issue-confirm-action" type="button" data-pl-issue-confirm="${issue.id}">确认会议项已解决</button>` : ''}</div>`).join('') : '<div class="empty">尚未提交 Issue。</div>';
}

async function setupPlRoleReview() {
  const app = document.querySelector('#role-review-app'); if (!app) return;
  const role = currentRole(); if (!teamRoles.includes(role)) return location.href = 'index.html';
  const projectId = new URLSearchParams(location.search).get('project');
  if (!projectId) return setFeedback('#pl-role-feedback', '未指定需要评审的新项目。', true);
  const load = async () => { try { renderPlRoleReview(await api(`/api/pl-projects/${encodeURIComponent(projectId)}?role=${encodeURIComponent(role)}`), role); } catch (error) { setFeedback('#pl-role-feedback', error.message, true); } };
  await load();
  document.querySelector('#submit-pl-issue').addEventListener('click', async () => { try { const state = await api(`/api/pl-projects/${encodeURIComponent(projectId)}/issues`, {method:'POST', body:JSON.stringify({role, category:document.querySelector('#pl-issue-category').value, priority:document.querySelector('#pl-issue-priority').value, title:document.querySelector('#pl-issue-title').value.trim(), detail:document.querySelector('#pl-issue-detail').value.trim()})}); renderPlRoleReview(state, role); setFeedback('#pl-role-feedback', 'Issue 已提交给 PL。'); } catch (error) { setFeedback('#pl-role-feedback', error.message, true); } });
  document.querySelector('#submit-pl-review').addEventListener('click', async () => { try { const current = await api(`/api/pl-projects/${encodeURIComponent(projectId)}?role=${encodeURIComponent(role)}`); const endpoint = current.review_phase === 'final_review' ? 'final-reviews' : 'reviews'; const state = await api(`/api/pl-projects/${encodeURIComponent(projectId)}/${endpoint}`, {method:'POST', body:JSON.stringify({role, conclusion:document.querySelector('#pl-review-conclusion').value.trim()})}); renderPlRoleReview(state, role); setFeedback('#pl-role-feedback', current.review_phase === 'final_review' ? '最终结论已提交。' : '首次评审已提交。'); } catch (error) { setFeedback('#pl-role-feedback', error.message, true); } });
  const askReviewAssistant = async () => {
    const input = document.querySelector('#review-assistant-question');
    const question = input.value.trim();
    if (!question) return setFeedback('#review-assistant-feedback', '请先输入想了解的项目问题。', true);
    const button = document.querySelector('#send-review-assistant');
    button.disabled = true;
    try {
      appendReviewAssistantMessage('user', question);
      const answer = await api(`/api/pl-projects/${encodeURIComponent(projectId)}/review-assistant`, {method:'POST', body:JSON.stringify({role, question})});
      input.value = '';
      appendReviewAssistantMessage('ai', answer.reply);
      setFeedback('#review-assistant-feedback', '已结合当前项目方案生成参考回答。');
    } catch (error) {
      setFeedback('#review-assistant-feedback', error.message, true);
    } finally {
      button.disabled = false;
    }
  };
  document.querySelector('#send-review-assistant').addEventListener('click', askReviewAssistant);
  document.querySelector('#review-assistant-question').addEventListener('keydown', event => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); askReviewAssistant(); } });
  document.querySelector('#pl-my-issues').addEventListener('click', async event => { const button = event.target.closest('[data-pl-issue-confirm]'); if (!button) return; try { const state = await api(`/api/pl-projects/${encodeURIComponent(projectId)}/issues/${button.dataset.plIssueConfirm}/confirm`, {method:'POST', body:JSON.stringify({role})}); renderPlRoleReview(state, role); setFeedback('#pl-role-feedback', 'Issue 已确认关闭。'); } catch (error) { setFeedback('#pl-role-feedback', error.message, true); } });
}

function isCurrentProject(link) {
  return `${location.pathname.split('/').pop()}${location.search}` === link;
}

async function setupSidebarProjects() {
  const nav = document.querySelector('#project-nav'); if (!nav) return;
  try {
    const role = currentRole();
    const data = await api(`/api/overview?role=${encodeURIComponent(role)}`);
    nav.innerHTML = data.projects.map(project => {
      const link = projectLink(project, role);
      return `<a href="${link}"${isCurrentProject(link) ? ' class="active" aria-current="page"' : ''}><span class="icon">▣</span>${escapeHtml(project.name)}</a>`;
    }).join('');
  } catch (_) { /* Keep Overview available when the local server is unavailable. */ }
}

function setupSidebar() {
  const sidebar = document.querySelector('.sidebar'); if (!sidebar) return;
  const toggle = document.createElement('button'); toggle.className = 'sidebar-toggle'; toggle.type = 'button'; toggle.setAttribute('aria-label', '折叠侧边栏'); toggle.textContent = '‹';
  toggle.addEventListener('click', () => { const collapsed = document.querySelector('.shell').classList.toggle('sidebar-collapsed'); toggle.textContent = collapsed ? '›' : '‹'; toggle.setAttribute('aria-label', collapsed ? '展开侧边栏' : '折叠侧边栏'); }); sidebar.append(toggle);
}

setupRoles(); setupSidebarProjects(); setupPlRoleReview(); setupOverview(); setupIterationProject(); setupSidebar();
