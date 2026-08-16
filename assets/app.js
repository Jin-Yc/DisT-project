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

async function setupOverview() {
  const table = document.querySelector('#projects tbody'); if (!table) return;
  try {
    const role = currentRole(); const data = await api(`/api/overview?role=${encodeURIComponent(role)}`);
    table.innerHTML = data.projects.map(project => {
      const link = project.pl_project ? (role === 'PL' ? `new-project.html?project_id=${encodeURIComponent(project.id)}` : 'index.html#team-workspace') : `project-view.html?project=${encodeURIComponent(project.id)}`;
      return `<tr><td><a href="${link}">${escapeHtml(project.name)}</a></td><td>${escapeHtml(project.type)}</td><td><span class="tag ${project.pl_project ? 'amber' : 'blue'}">${escapeHtml(project.stage)}</span></td><td><span class="tag ${project.readiness.includes('待处理') || project.readiness.includes('风险') ? 'red' : 'amber'}">${escapeHtml(project.readiness)}</span></td><td>${escapeHtml(project.next)}</td></tr>`;
    }).join('');
    const workspace = document.querySelector('#team-workspace');
    if (workspace) {
      if (role === 'PL') {
        const pendingProjects = data.pending_projects || [];
        document.querySelector('#team-workspace-title').textContent = 'PL 工作台';
        document.querySelector('#team-workspace-desc').textContent = pendingProjects.length ? '以下未确认项目保存在服务器中；选择项目后可继续当前阶段。' : '暂无需要继续处理的未确认项目。';
        document.querySelector('#team-task-list').innerHTML = pendingProjects.length ? pendingProjects.map(project => `<a class="team-task task-link" href="new-project.html?project_id=${encodeURIComponent(project.project_id)}"><span class="tag amber">PL 新项目 · ${escapeHtml(project.project)}</span><b>${escapeHtml(project.title)}</b><span>${escapeHtml(project.action)} · ${escapeHtml(project.status)}</span></a>`).join('') : '<div class="empty">暂无待处理任务。</div>';
      } else {
        document.querySelector('#team-workspace-title').textContent = `${role} 的工作台`;
        document.querySelector('#team-workspace-desc').textContent = data.tasks.length ? '以下任务区分既有项目与 PL 新项目；请按工作指示完成评审或执行。' : `PL 尚未向 ${role} 分配新项目任务。`;
        document.querySelector('#team-task-list').innerHTML = data.tasks.length ? data.tasks.map(task => task.pl_project ? `<a class="team-task task-link" href="${task.phase === 'final_complete' ? `new-project.html?project_id=${encodeURIComponent(task.project_id)}` : `role-review.html?project=${encodeURIComponent(task.project_id)}`}"><span class="tag amber">PL 新项目 · ${escapeHtml(task.project)}</span><b>${escapeHtml(task.title)}</b><span>${escapeHtml(task.action || task.status)} · 点击完成当前角色操作</span></a>` : `<a class="team-task task-link" href="project-view.html?project=${encodeURIComponent(task.project_id)}"><span class="tag blue">${escapeHtml(task.kind)} · ${escapeHtml(task.project)}</span><b>${escapeHtml(task.title)}</b><span>${escapeHtml(statusText(task.status))} · 查看项目</span></a>`).join('') : '<div class="empty">暂无待处理任务。</div>';
      }
    }
  } catch (error) {
    setFeedback('#team-task-list', `无法加载团队工作台：${error.message}`, true);
  }
}

async function setupIterationProject() {
  if (!document.querySelector('#iteration-project-app')) return;
  const projectId = new URLSearchParams(location.search).get('project');
  if (!['ri', 'ecom'].includes(projectId)) {
    document.querySelector('#iteration-feedback').textContent = '请选择 RI 或 Ecom 项目。';
    document.querySelector('#iteration-feedback').className = 'workflow-feedback show error';
    return;
  }
  try {
    const project = await api(`/api/projects/${projectId}?role=${encodeURIComponent(currentRole())}`);
    document.title = `DisT · ${project.name} 迭代概览`;
    document.querySelector('#iteration-sidebar-name').textContent = project.name;
    document.querySelector('#iteration-sidebar-stage').textContent = project.stage;
    document.querySelector('#iteration-project-name').textContent = `${project.name} · 项目迭代概览`;
    document.querySelector('#iteration-project-objective').textContent = project.objective;
    document.querySelector('#iteration-project-version').textContent = project.iteration;
    document.querySelector('#iteration-project-stage').textContent = project.stage;
    document.querySelector('#iteration-objective').textContent = project.objective;
    document.querySelector('#iteration-scope').textContent = project.scope;
    document.querySelector('#iteration-risk').textContent = project.risk;
    document.querySelector('#iteration-task-list').innerHTML = teamRoles.map(role => {
      const task = project.tasks[role];
      return `<div class="team-task"><span class="tag blue">${escapeHtml(role)}</span><b>${escapeHtml(task.title)}</b><span>${escapeHtml(statusText(task.status))} · 截止 ${escapeHtml(task.due_date)}</span></div>`;
    }).join('');
    if (project.role !== 'PL') {
      document.querySelector('#iteration-my-task').innerHTML = `<div class="team-task"><span class="tag blue">${escapeHtml(project.role)}</span><b>${escapeHtml(project.my_task.title)}</b><span>${escapeHtml(statusText(project.my_task.status))} · 截止 ${escapeHtml(project.my_task.due_date)}</span></div>`;
    }
  } catch (error) { setFeedback('#iteration-feedback', error.message, true); }
}

function projectLink(project, role) {
  return project.pl_project ? `new-project.html?project_id=${encodeURIComponent(project.id)}` : `project-view.html?project=${encodeURIComponent(project.id)}`;
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
  document.querySelector('#initial-review-issue-form').hidden = !firstRound;
  const assistant = document.querySelector('#role-review-assistant');
  assistant.hidden = !firstRound;
  document.querySelector('#review-assistant-question').disabled = !firstRound;
  document.querySelector('#send-review-assistant').disabled = !firstRound;
  if (firstRound && reviewAssistantProjectId !== state.id) {
    reviewAssistantProjectId = state.id;
    document.querySelector('#review-assistant-log').replaceChildren();
    appendReviewAssistantMessage('ai', `我是项目问答助手，可以结合当前方案和“${state.role_focus}”回答你的评审问题。`);
  }
  document.querySelector('#submit-pl-review').textContent = finalRound ? '提交最终结论 →' : '完成首次评审 →';
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
