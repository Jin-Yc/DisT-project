const flow = [
  {
    title: '问题与客户',
    question: '谁会在什么决策中使用这个产品？',
    hint: '请写出优先客户角色、他们的具体决策，以及现在如何完成该决策。',
    example: '首发面向中国市场的快消品牌品类经理，帮助他们每周判断哪些品类需要调整补货和促销。',
    challenge: '挑战：如果不能指出“决策”，周度更新只是功能，不是客户价值。',
    risk: '已建立一个初步决策场景，但还缺少客户访谈证据。',
  },
  {
    title: '场景与证据',
    question: '什么证据表明这是高优先级问题？',
    hint: '区分已知事实、客户反馈和你的假设；没有证据也可以诚实标记。',
    example: '两位客户在季度回顾中提到周度变化难以及时发现；尚未验证他们是否愿意为此付费。',
    challenge: '挑战：两位客户的反馈能说明问题存在，不能证明市场规模或付费意愿。',
    risk: '客户痛点有初步证据；商业化假设仍需验证。',
  },
  {
    title: '价值与边界',
    question: '首发版本明确做什么，又坚决不做什么？',
    hint: '以客户能获得的结果描述价值；列出一个最重要的 Out of Scope。',
    example: '提供品类异常预警、变化解释和补货建议；首发不提供自定义报表、实时数据或跨国比较。',
    challenge: '挑战：请避免把“异常预警”写成卖点；卖点应是客户缩短判断和行动的时间。',
    risk: 'Scope 已开始收敛；仍需确认首发市场、品类和数据粒度。',
  },
  {
    title: '依赖与成功标准',
    question: '上线后，什么指标能证明它解决了问题？谁负责关键依赖？',
    hint: '给出一个用户结果指标与一个交付指标，并标明数据或团队依赖。',
    example: '目标客户每周使用率达到 60%，并将异常发现到行动建议的时间缩短 30%；数据团队确认周度更新和品类口径。',
    challenge: '挑战：使用率不等于业务价值；试点中应补充“建议被采纳”的证据。',
    risk: '已识别数据依赖；成功指标可用于试点，但需定义测量基线。',
  },
];

const elements = {
  question: document.querySelector('#question'),
  hint: document.querySelector('#hint'),
  answer: document.querySelector('#answer'),
  module: document.querySelector('#module'),
  challenge: document.querySelector('#challenge'),
  risk: document.querySelector('#risk'),
  chips: document.querySelector('#chips'),
  steps: document.querySelectorAll('#steps li'),
  layout: document.querySelector('.layout'),
  result: document.querySelector('#result'),
};

let stepIndex = 0;

function renderStep() {
  const step = flow[stepIndex];
  elements.module.textContent = `步骤 ${stepIndex + 1} / ${flow.length} · ${step.title}`;
  elements.question.textContent = step.question;
  elements.hint.textContent = step.hint;
  elements.answer.value = step.example;
  elements.challenge.textContent = step.challenge;
  elements.steps.forEach((item, index) => item.classList.toggle('active', index === stepIndex));
}

function addStatusChip(isPending) {
  const chip = document.createElement('span');
  chip.className = `chip ${isPending ? 'assume' : 'fact'}`;
  chip.textContent = `${isPending ? '待确认' : '已确认'}：${flow[stepIndex].title}`;
  elements.chips.append(chip);
}

function advance(isPending) {
  addStatusChip(isPending);
  elements.risk.textContent = flow[stepIndex].risk;
  stepIndex += 1;

  if (stepIndex < flow.length) {
    renderStep();
    return;
  }

  elements.layout.style.display = 'none';
  elements.result.classList.add('show');
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

document.querySelector('#next').addEventListener('click', () => advance(false));
document.querySelector('#skip').addEventListener('click', () => advance(true));
renderStep();
