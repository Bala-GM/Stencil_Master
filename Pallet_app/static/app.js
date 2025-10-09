// static/app.js
// Full app.js with auth, modals, and separate condition_status + production_status

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

// ---------------- CHANGE EMP CREDENTIALS MODAL ----------------
function ensureChangeCredsModal() {
  if (document.getElementById('changeCredsModal')) return;

  const html = `
  <div class="modal fade" id="changeCredsModal" tabindex="-1">
    <div class="modal-dialog">
      <form id="changeCredsForm" class="modal-content">
        <div class="modal-header">
          <h5 class="modal-title">Change EMP Credentials</h5>
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
          <hr>
          <div class="mb-2">
            <label class="form-label">New Username (optional)</label>
            <input name="new_username" class="form-control">
          </div>
          <div class="mb-2">
            <label class="form-label">New Password (optional)</label>
            <input name="new_password" class="form-control" type="password">
          </div>
          <div class="mb-2">
            <label class="form-label">New EMP ID (optional)</label>
            <input name="new_emp_id" class="form-control">
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
      alert('✅ Credentials updated successfully');
      bootstrap.Modal.getInstance(document.getElementById('changeCredsModal')).hide();
    } else {
      alert('❌ Error: ' + (out.error || 'Failed to update'));
    }
  });
}

function openChangeCredsModal() {
  ensureChangeCredsModal();
  const bs = new bootstrap.Modal(document.getElementById('changeCredsModal'));
  document.getElementById('changeCredsForm').reset();
  bs.show();
}

// ---------------- CHANGE OPERATOR MODAL ----------------
function ensureChangeOperatorModal() {
  if (document.getElementById('changeOperatorModal')) return;

  const html = `
  <div class="modal fade" id="changeOperatorModal" tabindex="-1">
    <div class="modal-dialog">
      <form id="changeOperatorForm" class="modal-content">
        <div class="modal-header">
          <h5 class="modal-title">Change Operator Username / OP ID</h5>
          <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
        </div>
        <div class="modal-body">
          <div class="mb-2">
            <label class="form-label">Current Username</label>
            <input name="username" class="form-control" required>
          </div>
          <div class="mb-2">
            <label class="form-label">Current OP ID</label>
            <input name="operator_id" class="form-control" required>
          </div>
          <div class="mb-2">
            <label class="form-label">New Username (optional)</label>
            <input name="new_username" class="form-control">
          </div>
          <div class="mb-2">
            <label class="form-label">New OP ID (optional)</label>
            <input name="new_operator_id" class="form-control">
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

  const form = document.getElementById('changeOperatorForm');
  form.addEventListener('submit', async function(e) {
    e.preventDefault();
    const fm = new FormData(form);
    const payload = Object.fromEntries(fm.entries());

    const res = await fetch('/api/change_operator', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const out = await res.json();

    if (out.ok) {
      alert('Operator updated successfully');
      bootstrap.Modal.getInstance(document.getElementById('changeOperatorModal')).hide();
    } else {
      alert('Error: ' + (out.error || 'Failed to update operator'));
    }
  });
}

function openChangeOperatorModal() {
  ensureChangeOperatorModal();
  const bs = new bootstrap.Modal(document.getElementById('changeOperatorModal'));
  document.getElementById('changeOperatorForm').reset();
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
        { data: 'customer' },
        { data: 'pallet_no' },
        { data: 'pallet_qty' },
        { data: 'rack_no' },
        { data: 'location' },
        { data: 'condition_status' },
        { data: 'production_status' }
      ],
      pageLength: 25,
      responsive: true,
      rowCallback: function(row, data) {
        $(row).removeClass('purple-row');
        if (data.condition_status === 'MOVE' || data.condition_status === 'REWORK') {
          $(row).addClass('purple-row');
        }
      }
    });

    // Row selection + add/edit/save/delete handlers (unchanged logic) …
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
      $('#modalTitle').text('Add New Pallet');
      document.getElementById('palletForm').reset();
      const form = document.getElementById('palletForm');
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
      $('#modalTitle').text(`Edit Pallet #${editModeId}`);
      const res = await fetch(`/api/get/${editModeId}`);
      const data = await res.json();
      for (const [k,v] of Object.entries(data)) {
        const el = document.querySelector(`#palletForm [name="${k}"]`);
        if (el) el.value = v || '';
      }
      const form = document.getElementById('palletForm');
      form.dataset.authUsername = creds.username;
      form.dataset.authPassword = creds.password;
      modal.show();
    });

    // Save
    $('#saveBtn').on('click', async function(){
      const form = document.getElementById('palletForm');
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
      const form = document.getElementById('palletForm');
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
      $('#actionModalTitle').text(`${actionName} Pallet #${selectedRow.id}`);
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
      if (!confirm('Delete pallet #' + selectedRow.id + '?')) return;
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
    // just remember payload now includes condition_status and production_status
  

  // ---------------- RECEIVED PAGE ----------------
  const recTableEl = $('#recTable');
  if (recTableEl.length) {
    recTableEl.DataTable({
      ajax: { url: '/api/received', dataSrc: '' },
      columns: [
        { data: 'id' },
        { data: 'fg' },
        { data: 'customer' },
        { data: 'pallet_no' },
        { data: 'pallet_qty' },
        { data: 'rack_no' },
        { data: 'location' },
        { data: 'pallet_supplier' },
        { data: 'supplier_prt_no' },
        { data: 'date_received' },
        { data: 'pallet_validation_dt' },
        { data: 'pallet_revalidation_dt' },
        { data: 'received_by' },
        { data: 'condition_status' },
        { data: 'production_status' },
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
        { data: 'customer' },
        { data: 'pallet_no' },
        { data: 'pallet_qty' },
        { data: 'rack_no' },
        { data: 'location' },
        { data: 'pallet_validation_dt' },
        { data: 'pallet_revalidation_dt' },
        { data: 'remarks' },
        { data: 'condition_status' },
        { data: 'production_status' },
        { data: 'emp_id' }
      ],
      pageLength: 25,
      responsive: true,
      rowCallback: function(row, data) {
        $(row).removeClass('case1 case2 case3 tension-red tension-pink');

        const today = new Date();
        const reval = new Date(Date.parse(data.pallet_revalidation_dt));
        const diffDays = Math.ceil((reval - today) / (1000*60*60*24));

        let condStatus = data.condition_status || "";

        if (!isNaN(diffDays)) {
          if (diffDays <= 1) {
            $(row).addClass('case3');
            condStatus = "REVALIDATION TIME END";
          } else if (diffDays <= 5) {
            $(row).addClass('case2');
            condStatus = "RE-VALIDATION NEED TO DONE SOON";
          } else if (diffDays <= 10) {
            $(row).addClass('case1');
            condStatus = "RE-VALIDATION NEED TO DONE SOON";
          }
        }

        $('td:eq(9)', row).text(condStatus); // condition_status col
      }
    });
  }

  // ---------------- DOWNLOAD EXCEL ----------------
async function downloadExcel() {
  try {
    const [homeRes, recRes, statusRes, isosRes] = await Promise.allSettled([
      fetch('/api/list').then(r => r.json()),
      fetch('/api/received').then(r => r.json()),
      fetch('/api/status').then(r => r.json()),
      fetch('/api/isos_list').then(r => r.json())
    ]);

    if (homeRes.status !== "fulfilled") throw new Error("Home fetch failed");
    if (recRes.status !== "fulfilled") throw new Error("Received fetch failed");
    if (statusRes.status !== "fulfilled") throw new Error("Status fetch failed");
    if (isosRes.status !== "fulfilled") throw new Error("ISOS fetch failed");

    const wb = XLSX.utils.book_new();

    // ✅ Formatter for date/time
    function formatExcelDate(dateString) {
      if (!dateString) return "";
      const date = new Date(dateString);
      if (isNaN(date)) return dateString; // fallback if not parseable
      const day = String(date.getDate()).padStart(2, '0');
      const month = String(date.getMonth() + 1).padStart(2, '0');
      const year = date.getFullYear();
      let hours = date.getHours();
      const minutes = String(date.getMinutes()).padStart(2, '0');
      const ampm = hours >= 12 ? 'PM' : 'AM';
      hours = hours % 12 || 12;
      return `${day}/${month}/${year} ${hours}:${minutes} ${ampm}`;
    }

    function makeSheet(data, cols, sheetName) {
      const rows = data.map(r => cols.map(k => {
        // ✅ Reformat all date/time fields ["date_received", "pallet_validation_dt", "pallet_revalidation_dt", "out_time", "in_time"]
        if (["out_time", "in_time"].includes(k)) {
          return formatExcelDate(r[k]);
        }
        return r[k] ?? "";
      }));

      const aoa = [cols.map(c => c.toUpperCase()), ...rows];
      aoa.push(["Pallet Master List"]);
      const ws = XLSX.utils.aoa_to_sheet(aoa);

      // Auto column widths
      const colWidths = cols.map((c, i) => {
        let maxLen = c.length;
        rows.forEach(r => {
          const val = r[i] ? String(r[i]) : "";
          if (val.length > maxLen) maxLen = val.length;
        });
        return { wch: maxLen + 2 };
      });
      ws['!cols'] = colWidths;

      XLSX.utils.book_append_sheet(wb, ws, sheetName);
    }

    // --- Sheets ---
    makeSheet(homeRes.value, 
      ["id","fg","customer","pallet_no","pallet_qty","rack_no","location","condition_status","production_status"], 
      "Home"
    );

    makeSheet(recRes.value, [
      "id","fg","customer","pallet_no","pallet_qty","rack_no","location",
      "pallet_supplier",
      "supplier_prt_no","date_received","pallet_validation_dt","pallet_revalidation_dt",
      "received_by","condition_status","production_status","remarks","emp_id"
    ], "Received List");

    makeSheet(statusRes.value, [
      "fg","customer","pallet_no","pallet_qty","rack_no","location",
      "pallet_validation_dt","pallet_revalidation_dt",
      "remarks","condition_status","production_status","emp_id"
    ], "Status");

    makeSheet(isosRes.value, 
      ["pallet_no","fg","customer","rack_no","location","out_time","in_time","remarks","status","operator_id"], 
      "ISOS"
    );

    XLSX.writeFile(wb, "Pallet_Data.xlsx");
    alert("✅ Excel downloaded successfully!");
  } catch (err) {
    console.error(err);
    alert("❌ Excel download failed: " + err.message);
  }
}

$(document).ready(function () {
  const btn = document.getElementById("downloadExcelBtn");
  if (btn) btn.addEventListener("click", downloadExcel);
});

  // ---------------- ISOS PAGE ----------------
if ($("#isosTable").length) {
  
  // Helper function to format date/time
  function formatDateTime(dateString) {
    if (!dateString) return "";
    const date = new Date(dateString);
    const day = String(date.getDate()).padStart(2, '0');
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const year = date.getFullYear();
    let hours = date.getHours();
    const minutes = String(date.getMinutes()).padStart(2, '0');
    const ampm = hours >= 12 ? 'PM' : 'AM';
    hours = hours % 12 || 12;
    return `${day}/${month}/${year} ${hours}:${minutes} ${ampm}`;
  }

  const isosTable = $("#isosTable").DataTable({
    ajax: { url: "/api/isos_list", dataSrc: "" },
    columns: [
      { data: "pallet_no" },
      { data: "fg" },
      { data: "customer" },
      { data: "rack_no" },
      { data: "location" },
      { 
        data: "out_time", 
        defaultContent: "",
        render: function(data) {
          return data ? formatDateTime(data) : "";
        }
      },
      { 
        data: "in_time", 
        defaultContent: "",
        render: function(data) {
          return data ? formatDateTime(data) : "";
        }
      },
      { data: "remarks", defaultContent: "" },
      { data: "status" },
      { data: "operator_id", defaultContent: "" }
    ],
    pageLength: 25,
    responsive: true
  });

  const modalEl = new bootstrap.Modal(document.getElementById("isosModal"));
  let currentAction = null; // OUT or IN

  // Scan handler
  $("#scanInput").on("keypress", async function (e) {
    if (e.which === 13) {
      e.preventDefault();
      const palletNo = $(this).val().trim();
      if (!palletNo) return;

      try {
        const res = await fetch(`/api/isos_lookup/${encodeURIComponent(palletNo)}`);
        const data = await res.json();

        if (!data.ok) {
          alert(data.error || "Pallet not found");
          return;
        }

        // 🚨 Condition Status Gate
        const blockedStatuses = [
          "MOVE", "REWORK", "SCRAP",
          "REVALIDATION TIME END", "RE-VALIDATION NEED TO DONE SOON"
        ];

        if (data.pallet.condition_status && blockedStatuses.includes(data.pallet.condition_status.toUpperCase())) {
          alert(`❌ Access Denied: Pallet is in Condition Status "${data.pallet.condition_status}"`);
          $(this).val("");
          return;
        }

        // ✅ Allowed → fill form
        $("#pallet_no").val(palletNo);

        if (data.active_cycle) {
          currentAction = "IN";
          $("#isosModalTitle").text(`Scan IN: ${palletNo}`);
        } else {
          currentAction = "OUT";
          $("#isosModalTitle").text(`Scan OUT: ${palletNo}`);
        }

        modalEl.show();
      } catch (err) {
        console.error(err);
        alert("Lookup failed");
      } finally {
        $(this).val("");
      }
    }
  });

  // Save handler
  $("#isosSubmitBtn").on("click", async function () {
    const formData = Object.fromEntries(new FormData(document.getElementById("isosForm")));
    const opId = formData.operator_id ? formData.operator_id.trim().toUpperCase() : "";

    // 🚨 Validate operator ID . Only OP-USER1 … OP-USER20 
    try {
      const resOp = await fetch(`/api/operators`);
      const operators = await resOp.json();

      const validIds = operators.map(o => o.operator_id.toUpperCase());
      if (!validIds.includes(opId)) {
        alert("❌ Invalid Operator ID are Notallowed.");
        return;
      }
    } catch (err) {
      console.error("Operator validation failed:", err);
      alert("Could not validate operator ID");
      return;
    }

    try {
      const url = currentAction === "OUT" ? "/api/isos_out" : "/api/isos_in";
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(formData)
      });
      const data = await res.json();

      if (!data.ok) {
        alert(data.error || "Error saving");
        return;
      }

      alert(`✅ Pallet ${currentAction} recorded: ${data.status}`);
      modalEl.hide();
      isosTable.ajax.reload(null, false);
    } catch (err) {
      console.error(err);
      alert("Save failed");
    }
  });
}

});
