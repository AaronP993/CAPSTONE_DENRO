// static/js/global.js

// Only run the old logic if the new auto-inheritance elements don't exist
(function () {
  // Check if we're on the create account page with new auto-inheritance logic
  const inheritedInfo = document.getElementById('inheritedInfo');
  const manualSelection = document.getElementById('manualSelection');
  
  // If the new elements exist, don't run the old logic
  if (inheritedInfo || manualSelection) {
    return;
  }
  
  // Legacy logic for pages that still use the old system
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