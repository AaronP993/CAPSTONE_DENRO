// Region dropdown logic
function updateRegionDropdown() {
  const roleSelect = document.getElementById('role');
  const regionSelect = document.getElementById('region');
  const regionLabel = document.getElementById('regionLabel');
  const selectedRole = roleSelect.value;

  if (selectedRole === 'PENRO' || selectedRole === 'CENRO') {
    regionSelect.style.display = 'inline-block';
    regionLabel.style.display = 'inline-block';
    regionSelect.innerHTML = '<option value="">All Offices</option>';
    let options = [];

    if (selectedRole === 'PENRO') {
      options = ['Bohol', 'Cebu', 'Negros Oriental', 'Siquijor'];
    } else {
      options = ['Argao', 'Ayungon', 'Cebu', 'Dumaguete', 'Talibon', 'Tagbiliran'];
    }

    options.forEach(option => {
      const opt = document.createElement('option');
      opt.value = option;
      opt.textContent = option;
      regionSelect.appendChild(opt);
    });
  } else {
    regionSelect.style.display = 'none';
    regionLabel.style.display = 'none';
  }
}

document.getElementById('role').addEventListener('change', updateRegionDropdown);
updateRegionDropdown();

// Modal logic
const modal = document.getElementById('userModal');
const closeBtn = modal.querySelector('.close');

document.querySelectorAll('.user-link').forEach(link => {
  link.addEventListener('click', e => {
    e.preventDefault();
    modal.style.display = 'block';
  });
});

closeBtn.onclick = () => modal.style.display = 'none';
window.onclick = e => { if (e.target == modal) modal.style.display = 'none'; };

// Notification dropdown toggle
document.addEventListener('DOMContentLoaded', function() {
  const notifBtn = document.getElementById('notifBtn');
  const notifDropdown = document.getElementById('notifDropdown');

  if (notifBtn && notifDropdown) {
    notifBtn.addEventListener('click', function(e) {
      e.stopPropagation();
      notifDropdown.classList.toggle('show');
    });

    // Close dropdown when clicking outside
    document.addEventListener('click', function(e) {
      if (!notifBtn.contains(e.target) && !notifDropdown.contains(e.target)) {
        notifDropdown.classList.remove('show');
      }
    });
  }
});
