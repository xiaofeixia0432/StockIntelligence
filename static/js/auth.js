async function api(path, options = {}) {
  const { method = 'GET', body } = options;
  const init = {
    method,
    headers: { Accept: 'application/json' },
    credentials: 'include',
  };
  if (body !== undefined && body !== null) {
    init.headers['Content-Type'] = 'application/json';
    init.body = JSON.stringify(body);
  }

  const response = await fetch(`/api${path}`, init);
  const text = await response.text();
  let payload = {};
  try {
    payload = JSON.parse(text);
  } catch (error) {
    payload = { success: false, error: text || '接口返回非 JSON' };
  }

  if (!response.ok || payload.success === false) {
    throw new Error(payload.error || '请求失败');
  }

  return payload.data;
}

const form = document.getElementById('authForm');
const usernameInput = document.getElementById('username');
const passwordInput = document.getElementById('password');

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const username = usernameInput.value.trim();
  const password = passwordInput.value;

  if (!username || !password) {
    window.alert('用户名和密码不能为空');
    return;
  }

  try {
    const endpoint = window.AUTH_MODE === 'login' ? '/auth/login' : '/auth/register';
    const payload = { username, password };
    await api(endpoint, { method: 'POST', body: payload });
    window.location.href = '/';
  } catch (error) {
    window.alert(error.message || '操作失败');
  }
});
