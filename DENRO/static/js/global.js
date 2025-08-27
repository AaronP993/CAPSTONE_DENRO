// static/js/create_account.js
(function () {
  const role = document.getElementById('roleSelect');
  const region = document.getElementById('regionSelect');
  if (!role || !region) return;

  function applyRoleRules() {
    const r = role.value;
    // For now: region required for Admin/Evaluator, hidden for Super Admin
    if (r === 'Super Admin') {
      region.value = '';
      region.parentElement.style.display = 'none';
    } else {
      region.parentElement.style.display = '';
    }
  }

  role.addEventListener('change', applyRoleRules);
  applyRoleRules();
})();
