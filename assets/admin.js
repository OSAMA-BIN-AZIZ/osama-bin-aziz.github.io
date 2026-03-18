const STORAGE_KEY = 'v2free-admin-demo';

const demoState = {
  users: [
    { email: 'admin@v2free.example', plan: 'Enterprise', status: '正常', usage: '128 GB / 500 GB', joinedAt: '2026-03-14' },
    { email: 'alice@example.com', plan: 'Pro', status: '正常', usage: '82 GB / 200 GB', joinedAt: '2026-03-15' },
    { email: 'beta-user@example.com', plan: 'Basic', status: '待验证', usage: '4 GB / 50 GB', joinedAt: '2026-03-16' },
    { email: 'risk-review@example.com', plan: 'Free', status: '已暂停', usage: '17 GB / 20 GB', joinedAt: '2026-03-17' }
  ],
  nodes: [
    { name: '东京 03', region: 'Japan', status: '异常', latency: 189, load: 91 },
    { name: '新加坡 02', region: 'Singapore', status: '维护中', latency: 121, load: 67 },
    { name: '香港 01', region: 'Hong Kong', status: '在线', latency: 39, load: 44 },
    { name: '洛杉矶 05', region: 'USA', status: '在线', latency: 143, load: 56 }
  ],
  orders: [
    { id: 'ORD-3201', user: 'alice@example.com', plan: 'Pro', amount: 98, status: '已支付', createdAt: '2026-03-18 08:23' },
    { id: 'ORD-3200', user: 'admin@v2free.example', plan: 'Enterprise', amount: 299, status: '已支付', createdAt: '2026-03-17 20:11' },
    { id: 'ORD-3198', user: 'beta-user@example.com', plan: 'Basic', amount: 39, status: '待支付', createdAt: '2026-03-17 15:45' },
    { id: 'ORD-3195', user: 'risk-review@example.com', plan: 'Free', amount: 0, status: '失败', createdAt: '2026-03-16 09:15' }
  ],
  tickets: [
    { id: 'TK-1004', title: '订阅链接无法导入', user: 'alice@example.com', priority: '高', status: '待处理', reply: '' },
    { id: 'TK-1003', title: '香港节点晚高峰不稳定', user: 'admin@v2free.example', priority: '中', status: '处理中', reply: '已转交网络组持续观察。' },
    { id: 'TK-1002', title: '希望支持月付试用', user: 'beta-user@example.com', priority: '低', status: '已解决', reply: '产品经理已记录，下个版本评估。' }
  ],
  announcements: [
    { title: '周末维护窗口', tag: '系统', content: '本周六 02:00 - 04:00 将执行边缘节点例行维护。', createdAt: '2026-03-18 09:00' },
    { title: '企业套餐升级', tag: '活动', content: '新增团队成员共享流量与专属客服能力。', createdAt: '2026-03-17 18:30' }
  ],
  activity: [
    { time: '09:42', action: '风控策略已更新', actor: 'System' },
    { time: '09:18', action: '工单 TK-1003 更新为处理中', actor: 'Support' },
    { time: '08:23', action: '订单 ORD-3201 支付成功', actor: 'Billing' },
    { time: '07:58', action: '东京 03 节点告警触发', actor: 'Monitor' }
  ],
  trends: [
    { day: '周四', users: 12, revenue: 320 },
    { day: '周五', users: 18, revenue: 460 },
    { day: '周六', users: 16, revenue: 420 },
    { day: '周日', users: 25, revenue: 580 },
    { day: '周一', users: 31, revenue: 720 },
    { day: '周二', users: 22, revenue: 610 },
    { day: '周三', users: 27, revenue: 690 }
  ],
  settings: {
    siteName: 'V2free 管理后台',
    currency: 'CNY',
    defaultQuota: '50 GB',
    sla: '30 分钟首次响应',
    welcomeMessage: '欢迎使用 V2free，请遵守服务条款并及时关注公告。',
    registrationOpen: true,
    emailNotice: true,
    autoDrain: true
  }
};

const $ = (selector) => document.querySelector(selector);
const state = loadState();
let toastTimer = null;

function loadState() {
  try {
    const cached = localStorage.getItem(STORAGE_KEY);
    return cached ? JSON.parse(cached) : structuredClone(demoState);
  } catch (error) {
    return structuredClone(demoState);
  }
}

function persist() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

function showToast(message) {
  const toast = $('#toast');
  toast.textContent = message;
  toast.classList.add('visible');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove('visible'), 2200);
}

function statusClass(value) {
  const map = {
    在线: 'status-online',
    正常: 'status-normal',
    已解决: 'status-resolved',
    已支付: 'status-paid',
    处理中: 'status-processing',
    待处理: 'status-pending',
    待支付: 'status-pending',
    维护中: 'status-maintenance',
    已暂停: 'status-suspended',
    升级: 'status-upgrade',
    异常: 'status-error',
    失败: 'status-failed',
    待验证: 'status-warning'
  };
  return map[value] || 'status-warning';
}

function renderMetrics() {
  $('#metricUsers').textContent = state.users.length;
  $('#metricNewUsers').textContent = `本周新增 ${state.trends.reduce((sum, item) => sum + item.users, 0)} 人`;
  const onlineNodes = state.nodes.filter((item) => item.status === '在线').length;
  const abnormalNodes = state.nodes.filter((item) => item.status !== '在线').length;
  $('#metricNodes').textContent = onlineNodes;
  $('#metricNodeStatus').textContent = `${abnormalNodes} 个异常/维护`;

  const paidOrders = state.orders.filter((item) => item.status === '已支付');
  const revenue = paidOrders.reduce((sum, item) => sum + item.amount, 0);
  $('#metricRevenue').textContent = `¥${revenue}`;
  $('#metricOrders').textContent = `${state.orders.length} 笔订单`;

  const pendingTickets = state.tickets.filter((item) => item.status !== '已解决').length;
  const urgent = state.tickets.filter((item) => item.priority === '高' && item.status !== '已解决').length;
  $('#metricTickets').textContent = pendingTickets;
  $('#metricUrgent').textContent = `${urgent} 个紧急`;

  const alertNode = state.nodes.find((item) => item.status !== '在线') || state.nodes[0];
  $('#sidebarAlertTitle').textContent = `${alertNode.name} 需要关注`;
  $('#sidebarAlertBody').textContent = `${alertNode.region} 区域当前状态为 ${alertNode.status}，延迟 ${alertNode.latency}ms，负载 ${alertNode.load}%。`;
}

function renderTrends() {
  const chart = $('#chartBars');
  const maxUsers = Math.max(...state.trends.map((item) => item.users));
  const maxRevenue = Math.max(...state.trends.map((item) => item.revenue));
  chart.innerHTML = state.trends
    .map(
      (item) => `
        <div class="bar-day">
          <div class="bar-stack">
            <span class="bar users" style="height:${Math.round((item.users / maxUsers) * 180)}px"></span>
            <span class="bar revenue" style="height:${Math.round((item.revenue / maxRevenue) * 180)}px"></span>
          </div>
          <div class="bar-value">${item.users} / ¥${item.revenue}</div>
          <div class="bar-label">${item.day}</div>
        </div>
      `
    )
    .join('');
}

function renderHealth() {
  const list = $('#healthList');
  const healthItems = [
    ['注册服务', state.settings.registrationOpen ? '开放中' : '已关闭'],
    ['邮件通知', state.settings.emailNotice ? '正常' : '已关闭'],
    ['自动摘除', state.settings.autoDrain ? '启用' : '停用'],
    ['异常节点数', `${state.nodes.filter((item) => item.status !== '在线').length} 个`]
  ];
  list.innerHTML = healthItems
    .map(
      ([name, value]) => `
        <div class="list-row">
          <span>${name}</span>
          <strong>${value}</strong>
        </div>
      `
    )
    .join('');
}

function renderActivity() {
  $('#activityFeed').innerHTML = state.activity
    .map(
      (item) => `
        <div class="activity-item">
          <div>
            <strong>${item.action}</strong>
            <div class="chip">执行者：${item.actor}</div>
          </div>
          <span>${item.time}</span>
        </div>
      `
    )
    .join('');
}

function renderUsers(filter = '') {
  const keyword = filter.toLowerCase().trim();
  $('#usersTable').innerHTML = state.users
    .filter((item) => [item.email, item.plan, item.status].some((part) => part.toLowerCase().includes(keyword)))
    .map(
      (item) => `
        <tr>
          <td>${item.email}</td>
          <td>${item.plan}</td>
          <td><span class="status-pill ${statusClass(item.status)}">${item.status}</span></td>
          <td>${item.usage}</td>
          <td>${item.joinedAt}</td>
        </tr>
      `
    )
    .join('');
}

function renderNodes(filter = '') {
  const keyword = filter.toLowerCase().trim();
  $('#nodesGrid').innerHTML = state.nodes
    .filter((item) => [item.name, item.region, item.status].some((part) => part.toLowerCase().includes(keyword)))
    .map(
      (item) => `
        <article class="node-card">
          <header>
            <strong>${item.name}</strong>
            <span class="status-pill ${statusClass(item.status)}">${item.status}</span>
          </header>
          <div class="node-meta">${item.region} · 延迟 ${item.latency}ms</div>
          <div class="node-meta">当前负载 ${item.load}%</div>
          <div class="progress"><span style="width:${item.load}%"></span></div>
        </article>
      `
    )
    .join('');
}

function renderOrders(filter = '') {
  const keyword = filter.toLowerCase().trim();
  $('#ordersTable').innerHTML = state.orders
    .filter((item) => [item.id, item.user, item.plan, item.status].some((part) => part.toLowerCase().includes(keyword)))
    .map(
      (item) => `
        <tr>
          <td>${item.id}</td>
          <td>${item.user}</td>
          <td>${item.plan}</td>
          <td>¥${item.amount}</td>
          <td><span class="status-pill ${statusClass(item.status)}">${item.status}</span></td>
          <td>${item.createdAt}</td>
        </tr>
      `
    )
    .join('');

  const revenueByPlan = state.orders.reduce((acc, item) => {
    acc[item.plan] = (acc[item.plan] || 0) + item.amount;
    return acc;
  }, {});

  $('#planRevenueList').innerHTML = Object.entries(revenueByPlan)
    .sort((a, b) => b[1] - a[1])
    .map(
      ([plan, amount]) => `
        <div class="list-row">
          <span>${plan}</span>
          <strong>¥${amount}</strong>
        </div>
      `
    )
    .join('');
}

function renderTickets(filter = '') {
  const keyword = filter.toLowerCase().trim();
  $('#ticketList').innerHTML = state.tickets
    .filter((item) => [item.id, item.title, item.user, item.status, item.priority].some((part) => part.toLowerCase().includes(keyword)))
    .map(
      (item) => `
        <article class="ticket-item">
          <header>
            <strong>${item.id} · ${item.title}</strong>
            <span class="status-pill ${statusClass(item.status)}">${item.status}</span>
          </header>
          <div class="ticket-meta">用户：${item.user}</div>
          <div class="ticket-meta">优先级：${item.priority}</div>
          <div class="ticket-meta">回复：${item.reply || '暂无处理记录'}</div>
        </article>
      `
    )
    .join('');
}

function renderAnnouncements(filter = '') {
  const keyword = filter.toLowerCase().trim();
  $('#announcementList').innerHTML = state.announcements
    .filter((item) => [item.title, item.tag, item.content].some((part) => part.toLowerCase().includes(keyword)))
    .map(
      (item) => `
        <article class="announcement-item">
          <header>
            <strong>${item.title}</strong>
            <span class="status-pill status-online">${item.tag}</span>
          </header>
          <div class="announcement-meta">发布时间：${item.createdAt}</div>
          <p>${item.content}</p>
        </article>
      `
    )
    .join('');
}

function renderSettingsSummary() {
  const entries = [
    ['站点名称', state.settings.siteName],
    ['默认币种', state.settings.currency],
    ['新用户初始流量', state.settings.defaultQuota],
    ['工单 SLA', state.settings.sla],
    ['注册开关', state.settings.registrationOpen ? '已开启' : '已关闭'],
    ['邮件通知', state.settings.emailNotice ? '已启用' : '已关闭'],
    ['自动摘除', state.settings.autoDrain ? '已启用' : '已关闭']
  ];
  $('#settingsSummary').innerHTML = entries
    .map(
      ([label, value]) => `
        <div class="list-row">
          <span>${label}</span>
          <strong>${value}</strong>
        </div>
      `
    )
    .join('');
}

function syncSettingsForm() {
  const form = $('#settingsForm');
  Object.entries(state.settings).forEach(([key, value]) => {
    const field = form.elements.namedItem(key);
    if (!field) return;
    if (field.type === 'checkbox') {
      field.checked = Boolean(value);
    } else {
      field.value = value;
    }
  });
}

function renderAll(filter = '') {
  renderMetrics();
  renderTrends();
  renderHealth();
  renderActivity();
  renderUsers(filter);
  renderNodes(filter);
  renderOrders(filter);
  renderTickets(filter);
  renderAnnouncements(filter);
  renderSettingsSummary();
  syncSettingsForm();
  persist();
}

function addActivity(action, actor) {
  state.activity.unshift({
    time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false }),
    action,
    actor
  });
  state.activity = state.activity.slice(0, 8);
}

function bindNavigation() {
  document.querySelectorAll('.nav-item').forEach((button) => {
    button.addEventListener('click', () => {
      document.querySelectorAll('.nav-item').forEach((item) => item.classList.remove('active'));
      document.querySelectorAll('.panel').forEach((panel) => panel.classList.remove('active'));
      button.classList.add('active');
      document.getElementById(button.dataset.target).classList.add('active');
    });
  });

  $('#focusNodesButton').addEventListener('click', () => {
    document.querySelector('.nav-item[data-target="nodes"]').click();
  });
}

function bindForms() {
  $('#userForm').addEventListener('submit', (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    state.users.unshift({
      email: form.get('email').toString(),
      plan: form.get('plan').toString(),
      status: form.get('status').toString(),
      usage: '0 GB / 50 GB',
      joinedAt: new Date().toISOString().slice(0, 10)
    });
    addActivity(`新增用户 ${form.get('email')}`, 'Admin');
    renderAll($('#globalSearch').value);
    event.currentTarget.reset();
    showToast('用户已添加');
  });

  $('#nodeForm').addEventListener('submit', (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    state.nodes.unshift({
      name: form.get('name').toString(),
      region: form.get('region').toString(),
      status: form.get('status').toString(),
      latency: 88,
      load: 20
    });
    addActivity(`新增节点 ${form.get('name')}`, 'Network');
    renderAll($('#globalSearch').value);
    event.currentTarget.reset();
    showToast('节点已创建');
  });

  $('#ticketForm').addEventListener('submit', (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const ticket = state.tickets.find((item) => item.id === form.get('id').toString());
    if (!ticket) {
      showToast('未找到对应工单');
      return;
    }
    ticket.status = form.get('status').toString();
    ticket.reply = form.get('reply').toString();
    addActivity(`工单 ${ticket.id} 更新为 ${ticket.status}`, 'Support');
    renderAll($('#globalSearch').value);
    event.currentTarget.reset();
    showToast('工单状态已更新');
  });

  $('#announcementForm').addEventListener('submit', (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    state.announcements.unshift({
      title: form.get('title').toString(),
      tag: form.get('tag').toString(),
      content: form.get('content').toString(),
      createdAt: new Date().toLocaleString('zh-CN', { hour12: false })
    });
    addActivity(`发布公告 ${form.get('title')}`, 'Ops');
    renderAll($('#globalSearch').value);
    event.currentTarget.reset();
    showToast('公告已发布');
  });

  $('#settingsForm').addEventListener('submit', (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    state.settings = {
      siteName: form.get('siteName').toString(),
      currency: form.get('currency').toString(),
      defaultQuota: form.get('defaultQuota').toString(),
      sla: form.get('sla').toString(),
      welcomeMessage: form.get('welcomeMessage').toString(),
      registrationOpen: event.currentTarget.elements.registrationOpen.checked,
      emailNotice: event.currentTarget.elements.emailNotice.checked,
      autoDrain: event.currentTarget.elements.autoDrain.checked
    };
    addActivity('系统设置已保存', 'Admin');
    renderAll($('#globalSearch').value);
    showToast('设置已保存');
  });
}

function bindSearch() {
  $('#globalSearch').addEventListener('input', (event) => {
    renderAll(event.currentTarget.value);
  });

  $('#seedDemoButton').addEventListener('click', () => {
    Object.assign(state, structuredClone(demoState));
    renderAll('');
    $('#globalSearch').value = '';
    showToast('演示数据已重置');
  });
}

bindNavigation();
bindForms();
bindSearch();
renderAll();
