const roles = ['PL', 'Dsci', 'DA & RV', 'Ops'];
const teamRoles = ['Dsci', 'DA & RV', 'Ops'];
const roleKey = 'dist-role';
const panels = ['clarify', 'draft', 'review', 'minutes', 'plan'];
let workflowState;

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

function showPanel(id) {
  const step = panels.indexOf(id);
  if (workflowState && !workflowState.unlocked_steps.includes(step)) return setFeedback('#workflow-feedback', '请先完成当前步骤的关键操作，再进入下一步。', true);
  document.querySelectorAll('.flow-step,.workflow-panel').forEach(item => item.classList.remove('active'));
  document.querySelector(`.flow-step[data-panel="${id}"]`)?.classList.add('active');
  document.querySelector(`#${id}`)?.classList.add('active');
  history.replaceState(null, '', `#${id}`);
}

function renderChat(chat) {
  const log = document.querySelector('#chat-log');
  if (!log) return;
  log.innerHTML = chat.map(message => `<div class="message ${message.role === 'ai' ? 'ai' : 'user'}"><span class="avatar">${message.role === 'ai' ? 'AI' : 'PL'}</span><div><p>${escapeHtml(message.text)}</p></div></div>`).join('');
  log.scrollTop = log.scrollHeight;
}

function renderPlIssues(issues) {
  const list = document.querySelector('#issue-list');
  if (!list) return;
  list.innerHTML = issues.length ? issues.map(issue => `<div class="issue-row" data-issue-id="${issue.id}">
    <span class="tag ${issue.status === 'open' ? 'red' : issue.status === 'closed' ? 'green' : 'amber'}">${statusText(issue.status)}</span>
    <div><b>${escapeHtml(issue.title)}</b><div class="issue-meta"><span>${escapeHtml(issue.owner_role)}</span><span>${escapeHtml(issue.category)}</span><span>${escapeHtml(issue.priority)}优先级</span></div><p>${escapeHtml(issue.detail)}</p>
    ${issue.pl_response ? `<div class="callout"><b>PL 处理说明：</b>${escapeHtml(issue.pl_response)}</div>` : ''}
    ${issue.status === 'open' ? `<div class="issue-response"><textarea placeholder="说明你如何更新 Spec、处理问题或接受风险"></textarea><div class="actions"><button class="button secondary" data-issue-action="awaiting_submitter">更新 Spec，待提出团队确认</button><button class="button secondary" data-issue-action="accepted_risk">接受风险</button></div></div>` : ''}</div></div>`).join('') : '<div class="empty">团队尚未提交 Issue。</div>';
}

function renderReviewStatus(state) {
  const list = document.querySelector('#review-status-list');
  if (!list) return;
  list.innerHTML = teamRoles.map(role => {
    const task = state.review_tasks[role];
    if (!task) return `<div class="review-status"><b>${role}</b><span>等待 PL 发起团队评审</span></div>`;
    return `<div class="review-status"><b>${escapeHtml(role)}</b><span>${escapeHtml(statusText(task.status))} · 截止 ${escapeHtml(task.due_date)}</span>${task.conclusion ? `<span>结论：${escapeHtml(task.conclusion)}</span>` : ''}${task.status === 'awaiting_pl_confirmation' ? `<button class="button secondary" data-review-confirm="${escapeHtml(role)}">确认 ${escapeHtml(role)} 评审完成</button>` : ''}</div>`;
  }).join('');
}

function renderPlan(state) {
  document.querySelectorAll('[data-plan-role]').forEach(card => {
    const task = state.plan_tasks[card.dataset.planRole];
    card.querySelector('[data-plan-title]').value = task.title;
    card.querySelector('[data-plan-due]').value = task.due_date;
    const locked = state.stage !== 'plan';
    card.querySelectorAll('input').forEach(input => input.disabled = locked);
  });
  document.querySelector('#save-plan').disabled = state.stage !== 'plan';
  document.querySelector('#complete-plan').disabled = state.stage !== 'plan';
  const list = document.querySelector('#delivery-status-list');
  const tasks = state.delivery_tasks || {};
  list.innerHTML = Object.keys(tasks).length ? `<div class="delivery-status"><b>任务分发进度</b>${teamRoles.map(role => {
    const task = tasks[role];
    return `<div class="review-status"><b>${escapeHtml(role)} · ${escapeHtml(task.title)}</b><span>${escapeHtml(statusText(task.status))} · 截止 ${escapeHtml(task.due_date)}</span>${task.result ? `<span>结果：${escapeHtml(task.result)}</span>` : ''}${task.status === 'awaiting_pl_confirmation' ? `<button class="button secondary" data-delivery-confirm="${escapeHtml(role)}">确认 ${escapeHtml(role)} 交付完成</button>` : ''}</div>`;
  }).join('')}</div>` : '';
}

function renderWorkflow(state) {
  workflowState = state;
  document.querySelector('#workflow-project-name').textContent = state.project.name;
  document.querySelector('#sidebar-project-name').textContent = state.project.name;
  document.querySelector('#workflow-status').textContent = state.stage_label;
  document.querySelector('#sidebar-stage').textContent = state.stage_label;
  document.querySelector('#issue-count').textContent = `${state.open_issue_count} 个待处理问题`;
  document.querySelector('#review-issue-badge').textContent = `${state.open_issue_count} 个 Issue`;
  document.querySelector('#summary-confirmed').textContent = state.summary.confirmed;
  document.querySelector('#summary-pending').textContent = state.summary.pending;
  document.querySelector('#summary-suggestion').textContent = state.summary.suggestion;
  renderChat(state.chat); renderPlIssues(state.issues); renderReviewStatus(state); renderPlan(state);
  document.querySelectorAll('.flow-step').forEach((button, index) => {
    const unlocked = state.unlocked_steps.includes(index); button.disabled = !unlocked; button.classList.toggle('locked', !unlocked);
  });
  document.querySelector('#start-feasibility').disabled = !state.ready_for_feasibility;
  document.querySelector('#minutes-input').value = state.minutes || document.querySelector('#minutes-input').value;
  document.querySelector('#minutes-success').classList.toggle('show', state.minutes_applied);
  document.querySelector('#plan-success').classList.toggle('show', state.plan_completed);
}

async function plAction(path, body, success, nextPanel) {
  try { const state = await api(path, {method: 'POST', body: JSON.stringify(body || {})}); renderWorkflow(state); setFeedback('#workflow-feedback', success); if (nextPanel) showPanel(nextPanel); }
  catch (error) { setFeedback('#workflow-feedback', error.message, true); }
}

async function setupWorkflow() {
  if (!document.querySelector('#workflow-app')) return;
  try { renderWorkflow(await api('/api/o2o')); } catch (error) { setFeedback('#workflow-feedback', '无法读取 O2O 项目，请确认 Flask 服务已启动。', true); return; }
  document.querySelectorAll('.flow-step').forEach(button => button.addEventListener('click', () => showPanel(button.dataset.panel)));
  const initial = location.hash.slice(1); if (initial && workflowState.unlocked_steps.includes(panels.indexOf(initial))) showPanel(initial);
  const input = document.querySelector('#chat-input');
  document.querySelector('#send-message').addEventListener('click', () => {
    const text = input.value.trim(); if (!text) return setFeedback('#workflow-feedback', '请先补充需求信息。', true);
    plAction('/api/o2o/chat', {text}, '信息已保存，并已同步到结构化总结。'); input.value = '';
  });
  document.querySelectorAll('[data-prompt]').forEach(button => button.addEventListener('click', () => { input.value = button.dataset.prompt; input.focus(); }));
  document.querySelector('#confirm-draft').addEventListener('click', () => plAction('/api/o2o/draft/confirm', {}, 'Draft Spec 已确认，团队已收到 O2O 评审任务。下一步：等待并处理团队反馈。', 'review'));
  document.querySelector('#back-clarify').addEventListener('click', () => showPanel('clarify'));
  document.querySelector('#load-draft').addEventListener('click', () => setFeedback('#workflow-feedback', 'Draft Spec 已基于当前访谈记录重新整理，请审阅并确认。'));
  document.querySelector('#review').addEventListener('click', event => {
    const action = event.target.closest('[data-issue-action]');
    if (action) {
      const row = action.closest('[data-issue-id]'); const response = row.querySelector('textarea').value.trim();
      return plAction(`/api/o2o/issues/${row.dataset.issueId}/respond`, {response, action: action.dataset.issueAction}, action.dataset.issueAction === 'accepted_risk' ? 'Issue 已标记为接受风险。' : 'PL 回复已发送，等待提出团队确认。');
    }
    const confirm = event.target.closest('[data-review-confirm]');
    if (confirm) plAction(`/api/o2o/reviews/${encodeURIComponent(confirm.dataset.reviewConfirm)}/confirm`, {}, `${confirm.dataset.reviewConfirm} 的评审结论已由 PL 确认。`);
  });
  document.querySelector('#start-feasibility').addEventListener('click', () => plAction('/api/o2o/feasibility/start', {}, '团队评审已完成。下一步：上传或粘贴可行性会议纪要。', 'minutes'));
  const minutes = document.querySelector('#minutes-input');
  document.querySelector('#load-minutes').addEventListener('click', () => { minutes.value = '可行性评审会议纪要（模拟）\n\n1. 首发范围确认：先覆盖中国市场、华东现代渠道与饮料品类。\n2. 数据团队确认：每周二完成数据更新；销售指标以标准化口径提供。\n3. 风险：需在试点前确认两家客户的数据使用授权。\n4. 结论：满足进入排期讨论条件；由 PL 更新最终 Product Spec。'; setFeedback('#workflow-feedback', '已加载模拟纪要。确认内容无误后，保存并更新 Product Spec。'); });
  document.querySelector('#apply-minutes').addEventListener('click', () => plAction('/api/o2o/minutes', {minutes: minutes.value.trim()}, '会议纪要与最终 Product Spec 已保存。下一步：编辑并确认任务分发。', 'plan'));
  document.querySelector('#load-schedule').addEventListener('click', () => setFeedback('#workflow-feedback', '已载入建议排期。请检查各团队的任务名称和截止时间。'));
  const planTasks = () => Object.fromEntries([...document.querySelectorAll('[data-plan-role]')].map(card => [card.dataset.planRole, {title: card.querySelector('[data-plan-title]').value.trim(), due_date: card.querySelector('[data-plan-due]').value}]));
  document.querySelector('#save-plan').addEventListener('click', () => {
    const tasks = planTasks();
    plAction('/api/o2o/plan', {tasks}, '任务计划已保存。确认无误后即可分发。');
  });
  document.querySelector('#complete-plan').addEventListener('click', async () => {
    try {
      let state = await api('/api/o2o/plan', {method: 'POST', body: JSON.stringify({tasks: planTasks()})});
      state = await api('/api/o2o/plan/complete', {method: 'POST', body: JSON.stringify({})});
      renderWorkflow(state);
      setFeedback('#workflow-feedback', '任务已按当前内容分发；各角色 Overview 已出现对应的 O2O 任务。');
    } catch (error) { setFeedback('#workflow-feedback', error.message, true); }
  });
  document.querySelector('#plan').addEventListener('click', event => { const confirm = event.target.closest('[data-delivery-confirm]'); if (confirm) plAction(`/api/o2o/delivery/${encodeURIComponent(confirm.dataset.deliveryConfirm)}/confirm`, {}, `${confirm.dataset.deliveryConfirm} 的交付结果已由 PL 确认。`); });
}

function renderRoleWorkflow(state, role) {
  document.querySelector('#role-workflow-title').textContent = `${role} · O2O 工作流`;
  document.querySelector('#role-sidebar-stage').textContent = state.stage_label;
  document.querySelector('#role-workflow-stage').textContent = state.stage_label;
  document.querySelector('#role-focus').textContent = role;
  document.querySelector('#role-focus-detail').textContent = state.role_focus;
  const review = state.role_review_task;
  document.querySelector('#role-review-status').textContent = review ? statusText(review.status) : '等待 PL 发起评审';
  document.querySelector('#role-review-guide').textContent = review ? '请先提出需要 PL 处理的问题；所有问题得到可接受的处理后，再提交评审结论。' : 'PL 确认 Draft Product Spec 后，你会收到 O2O 的评审任务。';
  const canReview = review && review.status === 'pending';
  document.querySelectorAll('#role-review-card input,#role-review-card select,#role-review-card textarea,#submit-issue,#submit-review').forEach(node => node.disabled = !canReview);
  document.querySelector('#my-issue-list').innerHTML = state.my_issues.length ? state.my_issues.map(issue => `<div class="check ${issue.status === 'closed' ? 'good' : issue.status === 'open' ? 'high' : ''}"><b>${escapeHtml(issue.title)} · ${escapeHtml(statusText(issue.status))}</b>${escapeHtml(issue.detail)}${issue.pl_response ? `<br><b>PL 回复：</b>${escapeHtml(issue.pl_response)}` : ''}${issue.status === 'awaiting_submitter' ? `<br><button class="text-link" data-role-issue-confirm="${issue.id}">确认 Issue 已解决</button>` : ''}</div>`).join('') : '<div class="empty">尚未提交 Issue。</div>';
  const delivery = state.role_delivery_task;
  document.querySelector('#delivery-status').textContent = delivery ? statusText(delivery.status) : '等待任务分发';
  document.querySelector('#delivery-title').textContent = delivery ? delivery.title : '暂无任务';
  document.querySelector('#delivery-due').textContent = delivery ? `截止 ${delivery.due_date} · 提交后由 PL 确认完成。` : 'PL 完成任务分发后显示截止时间。';
  document.querySelector('#delivery-result').disabled = !delivery || delivery.status !== 'pending';
  document.querySelector('#submit-delivery').disabled = !delivery || delivery.status !== 'pending';
}

async function roleAction(path, body, success) {
  try { const state = await api(path, {method: 'POST', body: JSON.stringify(body || {})}); renderRoleWorkflow(state, currentRole()); setFeedback('#role-feedback', success); }
  catch (error) { setFeedback('#role-feedback', error.message, true); }
}

async function setupRoleWorkflow() {
  if (!document.querySelector('#role-workflow-app')) return;
  const role = currentRole(); if (!teamRoles.includes(role)) { location.href = role === 'PL' ? 'workflow.html' : 'index.html'; return; }
  try { renderRoleWorkflow(await api(`/api/o2o/role?role=${encodeURIComponent(role)}`), role); } catch (error) { setFeedback('#role-feedback', '无法读取项目工作流，请确认 Flask 服务已启动。', true); return; }
  document.querySelector('#submit-issue').addEventListener('click', () => roleAction('/api/o2o/issues', {role, category: document.querySelector('#issue-category').value, priority: document.querySelector('#issue-priority').value, title: document.querySelector('#issue-title').value.trim(), detail: document.querySelector('#issue-detail').value.trim()}, 'Issue 已提交给 PL。'));
  document.querySelector('#submit-review').addEventListener('click', () => roleAction('/api/o2o/reviews/submit', {role, conclusion: document.querySelector('#review-conclusion').value.trim()}, '评审结论已提交，等待 PL 确认。'));
  document.querySelector('#my-issue-list').addEventListener('click', event => { const button = event.target.closest('[data-role-issue-confirm]'); if (button) roleAction(`/api/o2o/issues/${button.dataset.roleIssueConfirm}/confirm`, {role}, 'Issue 已由提出团队确认关闭。'); });
  document.querySelector('#submit-delivery').addEventListener('click', () => roleAction('/api/o2o/delivery/submit', {role, result: document.querySelector('#delivery-result').value.trim()}, '交付结果已提交，等待 PL 确认。'));
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

setupRoles(); setupSidebarProjects(); setupWorkflow(); setupRoleWorkflow(); setupPlRoleReview(); setupOverview(); setupIterationProject(); setupSidebar();
