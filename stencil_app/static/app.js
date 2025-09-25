// static/app.js
// Full app.js with auth prompt (validated immediately), show/hide toggle, and Change Credentials modal

// ---------------- GLOBAL STATE ----------------
let selectedRow = null;
let selectedCell = null;
let editModeId = null;

const modalEl = document.getElementById('editModal');
const modal = modalEl ? new bootstrap.Modal(modalEl) : null;

const actionModalEl = document.getElementById('actionModal');
const actionModal = actionModalEl ? new bootstrap.Modal(actionModalEl) : null;
let currentAction = null;

// ---------------- AUTH MODAL ----------------
function ensureAuthModal() {
  if (document.getElementById('authModal')) return;

  const html = `
  <div class="modal fade" id="authModal" tabindex="-1">
    <div class="modal-dialog">
      <form id="authForm" class="modal-content">
        <div class="modal-header">
          <h5 class="modal-title">Authenticate</h5>
          <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
        </div>
        <div class="modal-body">
          <div class="mb-2">
            <label class="form-label">Username</label>
            <input name="username" class="form-control" required>
          </div>
          <div class="mb-2">
            <label class="form-label">Password</label>
            <div class="input-group">
              <input name="password" class="form-control" type="password" required aria-describedby="showPass">
              <button class="btn btn-outline-secondary" type="button" id="toggleShowPass">Show</button>
            </div>
          </div>
          <div class="form-text">Enter credentials to continue.</div>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
          <button type="submit" class="btn btn-primary">OK</button>
        </div>
      </form>
    </div>
  </div>
  `;
  document.body.insertAdjacentHTML('beforeend', html);

  const toggleBtn = document.getElementById('toggleShowPass');
  toggleBtn.addEventListener('click', () => {
    const pw = document.querySelector('#authForm [name="password"]');
    if (!pw) return;
    if (pw.type === 'password') {
      pw.type = 'text';
      toggleBtn.textContent = 'Hide';
    } else {
      pw.type = 'password';
      toggleBtn.textContent = 'Show';
    }
  });
}

function promptAuth() {
  ensureAuthModal();
  return new Promise(resolve => {
    const authModalEl = document.getElementById('authModal');
    const bs = new bootstrap.Modal(authModalEl);
    const form = document.getElementById('authForm');

    async function onSubmit(e) {
      e.preventDefault();
      const fm = new FormData(form);
      const username = fm.get('username')?.trim();
      const password = fm.get('password')?.trim();

      // 🔥 Validate with server immediately
      const res = await fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
      });

      const out = await res.json().catch(() => ({}));
      if (!out.ok) {
        alert(out.error || 'Invalid username or password');
        return; // stay in modal
      }

      cleanup();
      resolve({ username, password });
    }

    function cleanup() {
      form.removeEventListener('submit', onSubmit);
      authModalEl.removeEventListener('hidden.bs.modal', onHidden);
      bs.hide();
      form.reset(); // wipe credentials every time
    }

    function onHidden() {
      cleanup();
      resolve(null);
    }

    form.addEventListener('submit', onSubmit);
    authModalEl.addEventListener('hidden.bs.modal', onHidden);
    bs.show();
  });
}

// ---------------- CHANGE CREDENTIALS MODAL ----------------
function ensureChangeCredsModal() {
  if (document.getElementById('changeCredsModal')) return;

  const html = `
  <div class="modal fade" id="changeCredsModal" tabindex="-1">
    <div class="modal-dialog">
      <form id="changeCredsForm" class="modal-content">
        <div class="modal-header">
          <h5 class="modal-title">Change Username / Password</h5>
          <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
        </div>
        <div class="modal-body">
          <div class="mb-2">
            <label class="form-label">Current Username</label>
            <input name="username" class="form-control" required>
          </div>
          <div class="mb-2">
            <label class="form-label">Old Password</label>
            <input name="old_password" class="form-control" type="password" required>
          </div>
          <div class="mb-2">
            <label class="form-label">New Username (optional)</label>
            <input name="new_username" class="form-control">
          </div>
          <div class="mb-2">
            <label class="form-label">New Password (optional)</label>
            <input name="new_password" class="form-control" type="password">
          </div>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
          <button type="submit" class="btn btn-primary">Update</button>
        </div>
      </form>
    </div>
  </div>
  `;
  document.body.insertAdjacentHTML('beforeend', html);

  const form = document.getElementById('changeCredsForm');
  form.addEventListener('submit', async function(e) {
    e.preventDefault();
    const fm = new FormData(form);
    const payload = Object.fromEntries(fm.entries());

    const res = await fetch('/api/change_credentials', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const out = await res.json();

    if (out.ok) {
      alert('Credentials updated successfully');
      bootstrap.Modal.getInstance(document.getElementById('changeCredsModal')).hide();
    } else {
      alert('Error: ' + (out.error || 'Failed to update'));
    }
  });
}

function openChangeCredsModal() {
  ensureChangeCredsModal();
  const bs = new bootstrap.Modal(document.getElementById('changeCredsModal'));
  document.getElementById('changeCredsForm').reset();
  bs.show();
}

// ---------------- HELPERS ----------------
const toUpperObj = (obj) => {
  const out = {};
  Object.entries(obj).forEach(([k,v]) => out[k] = (v==null?'':String(v)).trim().toUpperCase());
  return out;
};

function formToObj(form) {
  const data = new FormData(form);
  const obj = {};
  for (const [k,v] of data.entries()) obj[k] = v;
  return obj;
}

function showHistory() {
  document.getElementById('historyPanel').classList.add('open');
}
function hideHistory() {
  document.getElementById('historyPanel').classList.remove('open');
}

// ---------------- HOME PAGE ----------------
$(async function(){
  const homeTableEl = $('#homeTable');
  let table = null;

  if (homeTableEl.length) {
    table = homeTableEl.DataTable({
      ajax: { url: '/api/list', dataSrc: '' },
      columns: [
        { data: 'id' },
        { data: 'fg' },
        { data: 'side' },
        { data: 'customer' },
        { data: 'stencil_no' },
        { data: 'rack_no' },
        { data: 'location' },
        { data: 'status' }
      ],
      pageLength: 25,
      responsive: true,
      rowCallback: function(row, data) {
        $(row).removeClass('purple-row');
        if (data.status === 'MOVE' || data.status === 'REWORK') {
          $(row).addClass('purple-row');
        }
      }
    });

    // Row selection
    $('#homeTable tbody').on('click', 'tr', function (e) {
      if (e.target && e.target.nodeName === 'TD') selectedCell = e.target;

      if ($(this).hasClass('selected')) {
        $(this).removeClass('selected');
        selectedRow = null;
        $('#editBtn, #historyBtn, #moveBtn, #reworkBtn, #scrapBtn').prop('disabled', true);
      } else {
        table.$('tr.selected').removeClass('selected');
        $(this).addClass('selected');
        selectedRow = table.row(this).data();
        $('#editBtn, #historyBtn, #moveBtn, #reworkBtn, #scrapBtn').prop('disabled', false);
      }
    });

    // Add
    $('#addBtn').on('click', async function(){
      const creds = await promptAuth();
      if (!creds) return;
      editModeId = null;
      $('#modalTitle').text('Add New Stencil');
      document.getElementById('stencilForm').reset();
      const form = document.getElementById('stencilForm');
      form.dataset.authUsername = creds.username;
      form.dataset.authPassword = creds.password;
      modal.show();
    });

    // Edit
    $('#editBtn').on('click', async function(){
      if (!selectedRow) return;
      const creds = await promptAuth();
      if (!creds) return;
      editModeId = selectedRow.id;
      $('#modalTitle').text(`Edit Stencil #${editModeId}`);
      const res = await fetch(`/api/get/${editModeId}`);
      const data = await res.json();
      for (const [k,v] of Object.entries(data)) {
        const el = document.querySelector(`#stencilForm [name="${k}"]`);
        if (el) el.value = v || '';
      }
      const form = document.getElementById('stencilForm');
      form.dataset.authUsername = creds.username;
      form.dataset.authPassword = creds.password;
      modal.show();
    });

    // Save
    $('#saveBtn').on('click', async function(){
      const form = document.getElementById('stencilForm');
      if (!form.reportValidity()) return;
      const payload = toUpperObj(formToObj(form));
      payload.username = form.dataset.authUsername;
      payload.password = form.dataset.authPassword;
      if (!payload.username || !payload.password) {
        alert('Authentication required.');
        return;
      }

      let url = '/api/add';
      if (editModeId != null) url = `/api/update/${editModeId}`;

      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (res.status === 403) {
        const body = await res.json().catch(()=>({}));
        alert('Unauthorized: ' + (body.error || 'invalid credentials'));
        return;
      }

      const out = await res.json();
      if (out.ok) {
        delete form.dataset.authUsername;
        delete form.dataset.authPassword;
        modal.hide();
        table.ajax.reload(null, false);
      } else {
        alert('Save failed');
      }
    });

    $('#editModal').on('hidden.bs.modal', function(){
      const form = document.getElementById('stencilForm');
      delete form.dataset.authUsername;
      delete form.dataset.authPassword;
    });

    // History
    $('#historyBtn').on('click', async function(){
      if (!selectedRow) return;
      const r = await fetch(`/api/history/${selectedRow.id}`);
      const items = await r.json();
      const body = document.getElementById('historyBody');
      if (items.length === 0) {
        body.innerHTML = '<div class="text-muted p-2">No history.</div>';
      } else {
        body.innerHTML = items.map(x => `
          <div class="hist-item">
            <div class="small text-muted">${x.changed_at}</div>
            <div><strong>${x.changed_column}</strong></div>
            <div><span class="badge bg-secondary me-1">OLD</span> ${x.old_value ?? ''}</div>
            <div><span class="badge bg-primary me-1">NEW</span> ${x.new_value ?? ''}</div>
          </div>
        `).join('');
      }
      showHistory();
    });

    // Actions (Move/Rework/Scrap)
    function openActionModal(actionName, creds=null) {
      if (!selectedRow) return;
      currentAction = actionName;
      $('#actionModalTitle').text(`${actionName} Stencil #${selectedRow.id}`);
      document.getElementById('actionForm').reset();
      const aform = document.getElementById('actionForm');
      if (creds) {
        aform.dataset.authUsername = creds.username;
        aform.dataset.authPassword = creds.password;
      }
      actionModal.show();
    }

    $('#moveBtn').on('click', async function(){
      const creds = await promptAuth();
      if (!creds) return;
      openActionModal('MOVE', creds);
    });
    $('#reworkBtn').on('click', async function(){
      const creds = await promptAuth();
      if (!creds) return;
      openActionModal('REWORK', creds);
    });
    $('#scrapBtn').on('click', async function(){
      const creds = await promptAuth();
      if (!creds) return;
      openActionModal('SCRAP', creds);
    });

    $('#actionSaveBtn').on('click', async function(){
      if (!selectedRow || !currentAction) return;
      const form = document.getElementById('actionForm');
      if (!form.reportValidity()) return;
      const payload = toUpperObj(formToObj(form));
      payload.action = currentAction;
      payload.username = form.dataset.authUsername;
      payload.password = form.dataset.authPassword;
      if (!payload.username || !payload.password) {
        alert('Authentication required.');
        return;
      }

      const res = await fetch(`/api/action/${selectedRow.id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (res.status === 403) {
        const b = await res.json().catch(()=>({}));
        alert('Unauthorized: ' + (b.error || 'invalid credentials'));
        return;
      }

      const out = await res.json();
      if (out.ok) {
        delete form.dataset.authUsername;
        delete form.dataset.authPassword;
        actionModal.hide();
        table.ajax.reload(null, false);
      } else {
        alert('Action failed');
      }
    });

    $('#actionModal').on('hidden.bs.modal', function(){
      const aform = document.getElementById('actionForm');
      delete aform.dataset.authUsername;
      delete aform.dataset.authPassword;
    });

    // Delete
    $('#deleteBtn').on('click', async function(){
      if (!selectedRow) return;
      const creds = await promptAuth();
      if (!creds) return;
      if (!confirm('Delete stencil #' + selectedRow.id + '?')) return;
      const res = await fetch(`/api/delete/${selectedRow.id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(creds)
      });
      if (res.status === 403) {
        const b = await res.json().catch(()=>({}));
        alert('Unauthorized: ' + (b.error || 'invalid credentials'));
        return;
      }
      const out = await res.json();
      if (out.ok) table.ajax.reload(null, false);
    });
  }

  // ---------------- RECEIVED PAGE ----------------
  const recTableEl = $('#recTable');
  if (recTableEl.length) {
    recTableEl.DataTable({
      ajax: { url: '/api/received', dataSrc: '' },
      columns: [
        { data: 'id' },
        { data: 'fg' },
        { data: 'side' },
        { data: 'customer' },
        { data: 'stencil_no' },
        { data: 'rack_no' },
        { data: 'location' },
        { data: 'stencil_mils' },
        { data: 'stencil_mils_usl' },
        { data: 'stencil_mils_lsl' },
        { data: 'stencil_supplier' },
        { data: 'stencil_pr_no' },
        { data: 'date_received' },
        { data: 'stencil_validation_dt' },
        { data: 'stencil_revalidation_dt' },
        { data: 'tension_a' },
        { data: 'tension_b' },
        { data: 'tension_c' },
        { data: 'tension_d' },
        { data: 'tension_e' },
        { data: 'received_by' },
        { data: 'status' },
        { data: 'remarks' },
        { data: 'emp_id' }
      ],
      pageLength: 25,
      responsive: true
    });
  }

  // ---------------- STATUS PAGE ----------------
  const statusTableEl = $('#statusTable');
  if (statusTableEl.length) {
    statusTableEl.DataTable({
      ajax: { url: '/api/status', dataSrc: '' },
      order: [[6, 'asc']],
      columns: [
        { data: 'fg' },
        { data: 'side' },
        { data: 'customer' },
        { data: 'stencil_no' },
        { data: 'rack_no' },
        { data: 'location' },
        { data: 'stencil_validation_dt' },
        { data: 'stencil_revalidation_dt' },
        { data: 'tension_a' },
        { data: 'tension_b' },
        { data: 'tension_c' },
        { data: 'tension_d' },
        { data: 'tension_e' },
        { data: 'remarks' },
        { data: 'status' },
        { data: 'emp_id' }
      ],
      pageLength: 25,
      responsive: true,
      rowCallback: function(row, data) {
        $(row).removeClass('case1 case2 case3 tension-red tension-pink');

        const today = new Date();
        const reval = new Date(Date.parse(data.stencil_revalidation_dt));
        const diffDays = Math.ceil((reval - today) / (1000*60*60*24));

        let statusText = data.status || "";  // fallback if DB already has status

        // ---- Revalidation Date Highlight ----
        if (!isNaN(diffDays)) {
          if (diffDays <= 1) {
            $(row).addClass('case3');
            statusText = "Revalidation Time End";
          } else if (diffDays <= 5) {
            $(row).addClass('case2');
            statusText = "Re-Validation Need to Done Soon";
          } else if (diffDays <= 10) {
            $(row).addClass('case1');
            statusText = "Re-Validation Need to Done Soon";
          }
        }

        // ---- Tension Highlight ----
        const tensions = [
          parseFloat(data.tension_a),
          parseFloat(data.tension_b),
          parseFloat(data.tension_c),
          parseFloat(data.tension_d),
          parseFloat(data.tension_e)
        ];

        for (const t of tensions) {
          if (!isNaN(t)) {
            if (t < 35) {
              $(row).addClass('tension-red');
              statusText = "Stencil EOL";
              break;
            } else if (t === 35 || t === 36) {
              $(row).addClass('tension-pink');
              statusText = "Stencil Re-Order Soon";
              break;
            }
          }
        }

        // ---- Update Status Column Cell ----
        const statusCell = $('td:eq(14)', row);  // 0-based index → status column
        statusCell.text(statusText);
      }
    });
  }

  // ---------------- DOWNLOAD EXCEL ----------------
  async function downloadExcel() {
    try {
      // Fetch all 3 datasets from API
      const [homeRes, recRes, statusRes] = await Promise.allSettled([
        fetch('/api/list').then(r => r.json()),
        fetch('/api/received').then(r => r.json()),
        fetch('/api/status').then(r => r.json())
      ]);

      // Check fetch results
      if (homeRes.status !== "fulfilled") throw new Error("Home data fetch failed");
      if (recRes.status !== "fulfilled") throw new Error("Received data fetch failed");
      if (statusRes.status !== "fulfilled") throw new Error("Status data fetch failed");

      const wb = XLSX.utils.book_new();

      // Helper to make sheet with header + footer + auto column widths
      function makeSheet(data, cols, sheetName) {
        const rows = data.map(r => cols.map(k => r[k] ?? ""));
        const aoa = [cols.map(c => c.toUpperCase()), ...rows];

        // Add footer row
        aoa.push([`Stencil Master List`]);

        const ws = XLSX.utils.aoa_to_sheet(aoa);

        // Auto-fit column widths
        const colWidths = cols.map((c, i) => {
          let maxLen = c.length;
          rows.forEach(r => {
            const val = r[i] ? String(r[i]) : "";
            if (val.length > maxLen) maxLen = val.length;
          });
          return { wch: maxLen + 2 }; // +2 for padding
        });
        ws['!cols'] = colWidths;

        XLSX.utils.book_append_sheet(wb, ws, sheetName);
      }

      // --- Home Sheet ---
      makeSheet(homeRes.value, 
        ["id","fg","side","customer","stencil_no","rack_no","location","status"], 
        "Home"
      );

      // --- Received List Sheet ---
      makeSheet(recRes.value, [
        "id","fg","side","customer","stencil_no","rack_no","location",
        "stencil_mils","stencil_mils_usl","stencil_mils_lsl","stencil_supplier",
        "stencil_pr_no","date_received","stencil_validation_dt","stencil_revalidation_dt",
        "tension_a","tension_b","tension_c","tension_d","tension_e",
        "received_by","status","remarks","emp_id"
      ], "Received List");

      // --- Status Sheet ---
      makeSheet(statusRes.value, [
        "fg","side","customer","stencil_no","rack_no","location",
        "stencil_validation_dt","stencil_revalidation_dt",
        "tension_a","tension_b","tension_c","tension_d","tension_e",
        "remarks","status","emp_id"
      ], "Status");

      // Save Excel file
      XLSX.writeFile(wb, "Stencil_Data.xlsx");
      alert("✅ Excel downloaded successfully!");

    } catch (err) {
      console.error("Excel download failed:", err);
      alert("❌ Excel download failed: " + err.message);
    }
  }

  // Attach once DOM is ready
  $(document).ready(function () {
    const btn = document.getElementById("downloadExcelBtn");
    if (btn) {
      btn.addEventListener("click", downloadExcel);
    } else {
      console.warn("⚠️ Download Excel button not found in DOM.");
    }
  });

  // ---------------- Change Creds Button ----------------
  //if (!document.getElementById('changeCredsBtn')) {
    //const btn = document.createElement('button');
    //btn.id = 'changeCredsBtn';
    //btn.className = 'btn btn-sm btn-warning position-fixed';
    //btn.style.bottom = '10px';
    //btn.style.right = '10px';
    //btn.textContent = 'Change Credentials';
    //btn.onclick = openChangeCredsModal;
    //document.body.appendChild(btn);
  //}
});
