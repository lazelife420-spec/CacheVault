// Cache Vault Companion Extension Popup Logic

let allExtractedLinks = [];
let filteredLinks = [];
let pageDomain = '';
let pageUrl = '';

// DOM Elements
const connBadge = document.getElementById('conn-badge');
const settingsToggle = document.getElementById('settings-toggle');
const pairingPanel = document.getElementById('pairing-panel');
const pairHostInput = document.getElementById('pair-host');
const pairDeviceIdInput = document.getElementById('pair-device-id');
const pairTokenInput = document.getElementById('pair-token');
const savePairBtn = document.getElementById('save-pair-btn');

const collectBtn = document.getElementById('collect-btn');
const linkSourceFilter = document.getElementById('link-source-filter');
const targetSafe = document.getElementById('target-safe');
const searchInput = document.getElementById('search-input');
const listHeader = document.getElementById('list-header');
const linkList = document.getElementById('link-list');

const copySelectedBtn = document.getElementById('copy-selected-btn');
const copyMarkdownBtn = document.getElementById('copy-markdown-btn');
const copyNumberedBtn = document.getElementById('copy-numbered-btn');
const sendVaultBtn = document.getElementById('send-vault-btn');
const toast = document.getElementById('toast');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
  loadPairingData();
  setupEventListeners();
});

// Load Pairing Data
function loadPairingData() {
  chrome.storage.local.get(['vaultHost', 'deviceId', 'pairingToken'], (res) => {
    if (res.vaultHost) pairHostInput.value = res.vaultHost;
    if (res.deviceId) pairDeviceIdInput.value = res.deviceId;
    if (res.pairingToken) pairTokenInput.value = res.pairingToken;

    if (res.deviceId && res.pairingToken) {
      connBadge.textContent = 'Paired';
      connBadge.className = 'badge paired';
      sendVaultBtn.disabled = false;
    } else {
      connBadge.textContent = 'Unpaired';
      connBadge.className = 'badge unpaired';
      sendVaultBtn.disabled = true;
    }
  });
}

// Setup Event Listeners
function setupEventListeners() {
  settingsToggle.addEventListener('click', () => {
    pairingPanel.style.display = pairingPanel.style.display === 'none' ? 'block' : 'none';
  });

  savePairBtn.addEventListener('click', savePairing);
  collectBtn.addEventListener('click', collectLinks);
  linkSourceFilter.addEventListener('change', updateFiltersAndSearch);
  searchInput.addEventListener('input', updateFiltersAndSearch);

  copySelectedBtn.addEventListener('click', () => copySelected('plain'));
  copyMarkdownBtn.addEventListener('click', () => copySelected('markdown'));
  copyNumberedBtn.addEventListener('click', () => copySelected('numbered'));
  sendVaultBtn.addEventListener('click', sendToVault);
}

// Save Pairing Settings
function savePairing() {
  const host = pairHostInput.value.trim() || 'http://127.0.0.1:8742';
  const deviceId = pairDeviceIdInput.value.trim();
  const token = pairTokenInput.value.trim();

  chrome.storage.local.set({
    vaultHost: host,
    deviceId: deviceId,
    pairingToken: token
  }, () => {
    loadPairingData();
    pairingPanel.style.display = 'none';
    showToast('Pairing details saved');
  });
}

// Collect Links from Active Tab
function collectLinks() {
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    if (!tabs || tabs.length === 0) {
      showToast('No active tab found');
      return;
    }

    const tab = tabs[0];
    // Dynamic content script execution
    chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => {
        const links = Array.from(document.querySelectorAll('a'))
          .map(a => {
            const rect = a.getBoundingClientRect();
            const visible = rect.width > 0 && rect.height > 0 && 
                            window.getComputedStyle(a).display !== 'none' && 
                            window.getComputedStyle(a).visibility !== 'hidden';
            return {
              url: a.href,
              title: a.innerText.trim() || a.title || 'Untitled Link',
              visible: visible
            };
          })
          .filter(l => l.url.startsWith('http'));
        return {
          links: links,
          domain: window.location.hostname,
          url: window.location.href
        };
      }
    }, (results) => {
      if (chrome.runtime.lastError || !results || !results[0]) {
        showToast('Cannot access page: ' + (chrome.runtime.lastError?.message || 'unreachable'));
        return;
      }

      const res = results[0].result;
      allExtractedLinks = res.links;
      pageDomain = res.domain;
      pageUrl = res.url;

      searchInput.disabled = false;
      updateFiltersAndSearch();
      showToast(`Collected ${allExtractedLinks.length} links`);
    });
  });
}

// Update Filter and Search Results
function updateFiltersAndSearch() {
  const sourceVal = linkSourceFilter.value;
  const searchVal = searchInput.value.toLowerCase().trim();

  filteredLinks = allExtractedLinks.filter(l => {
    // 1. Source options filter
    if (sourceVal === 'visible' && !l.visible) return false;
    if (sourceVal === 'domain') {
      try {
        const linkHost = new URL(l.url).hostname;
        if (linkHost !== pageDomain) return false;
      } catch(e) {
        return false;
      }
    }

    // 2. Search query filter
    if (searchVal) {
      return l.title.toLowerCase().includes(searchVal) || l.url.toLowerCase().includes(searchVal);
    }
    return true;
  });

  renderLinks();
}

// Render Extracted Links List
function renderLinks() {
  listHeader.textContent = `Collected Links (${filteredLinks.length})`;
  linkList.innerHTML = '';

  if (filteredLinks.length === 0) {
    linkList.innerHTML = '<div class="no-links">No links match filter criteria.</div>';
    setButtonsDisabled(true);
    return;
  }

  filteredLinks.forEach((link, idx) => {
    const item = document.createElement('div');
    item.className = 'link-item';
    item.innerHTML = `
      <input type="checkbox" id="chk-${idx}" checked>
      <div class="link-details">
        <div class="link-title">${escapeHtml(link.title)}</div>
        <div class="link-url">${escapeHtml(link.url)}</div>
      </div>
    `;

    // Make clicking the row toggle the checkbox
    item.addEventListener('click', (e) => {
      if (e.target.tagName !== 'INPUT') {
        const chk = item.querySelector('input[type="checkbox"]');
        chk.checked = !chk.checked;
        updateActionButtonsState();
      }
    });

    item.querySelector('input').addEventListener('change', updateActionButtonsState);

    linkList.appendChild(item);
  });

  setButtonsDisabled(false);
  updateActionButtonsState();
}

function updateActionButtonsState() {
  const selectedCount = getSelectedLinks().length;
  const hasSelected = selectedCount > 0;
  copySelectedBtn.disabled = !hasSelected;
  copyMarkdownBtn.disabled = !hasSelected;
  copyNumberedBtn.disabled = !hasSelected;
  
  // Only allow sending to Vault if paired and links are selected
  chrome.storage.local.get(['deviceId', 'pairingToken'], (res) => {
    sendVaultBtn.disabled = !(hasSelected && res.deviceId && res.pairingToken);
  });
}

function setButtonsDisabled(disabled) {
  copySelectedBtn.disabled = disabled;
  copyMarkdownBtn.disabled = disabled;
  copyNumberedBtn.disabled = disabled;
  if (disabled) sendVaultBtn.disabled = true;
}

// Get Selected Checked Links
function getSelectedLinks() {
  const selected = [];
  const checkboxes = linkList.querySelectorAll('input[type="checkbox"]');
  checkboxes.forEach(chk => {
    if (chk.checked) {
      const idx = parseInt(chk.id.replace('chk-', ''), 10);
      selected.push(filteredLinks[idx]);
    }
  });
  return selected;
}

// Copy to Clipboard Action
function copySelected(format) {
  const selected = getSelectedLinks();
  if (selected.length === 0) return;

  let text = '';
  if (format === 'plain') {
    text = selected.map(l => l.url).join('\n');
  } else if (format === 'markdown') {
    text = selected.map(l => `[${l.title}](${l.url})`).join('\n');
  } else if (format === 'numbered') {
    text = selected.map((l, idx) => `${idx + 1}. ${l.title} - ${l.url}`).join('\n');
  }

  // Use clipboard API
  navigator.clipboard.writeText(text).then(() => {
    showToast(`Copied ${selected.length} links to clipboard`);
    recordReceipt('copy', selected.length, format);
  }).catch(err => {
    showToast('Failed to copy: ' + err);
  });
}

// Send Selected to Cache Vault Desktop
function sendToVault() {
  const selected = getSelectedLinks();
  if (selected.length === 0) return;

  chrome.storage.local.get(['vaultHost', 'deviceId', 'pairingToken'], (creds) => {
    if (!creds.deviceId || !creds.pairingToken) {
      showToast('Connection parameters missing');
      return;
    }

    const host = creds.vaultHost || 'http://127.0.0.1:8742';
    const urlList = selected.map(l => l.url).join('\n');
    const safeId = targetSafe.value;

    const payload = {
      item_type: 'url',
      user_action: 'send_to_pc',
      content: urlList,
      source_app: 'Browser Extension',
      source_device_name: getBrowserName(),
      source_url: pageUrl || 'Unknown page',
      safe_id: safeId
    };

    sendVaultBtn.disabled = true;
    showToast('Sending to Cache Vault...');

    fetch(`${host}/mobile/v1/inbox/send`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Device-Id': creds.deviceId,
        'Authorization': `Bearer ${creds.pairingToken}`
      },
      body: JSON.stringify(payload)
    })
    .then(res => {
      if (res.status === 200) {
        return res.json().then(data => {
          showToast(`Sent ${selected.length} links to Vault successfully`);
          recordReceipt('vault_send', selected.length, 'json', safeId);
        });
      } else if (res.status === 401) {
        showToast('Failed to send: Pairing unauthorized/revoked');
      } else if (res.status === 503) {
        showToast('Failed to send: Mobile Access is disabled in Desktop');
      } else {
        showToast(`Failed to send: Server returned status ${res.status}`);
      }
    })
    .catch(err => {
      showToast('Connection error: Make sure loopback server is running');
    })
    .finally(() => {
      updateActionButtonsState();
    });
  });
}

// Record Receipt locally in chrome.storage.local
function recordReceipt(action, count, format, safeId = 'inbox') {
  const receipt = {
    action: action === 'copy' ? 'extension_batch_link_copy' : 'extension_batch_link_send',
    source: 'browser_extension',
    count: count,
    format: format,
    page_url: pageUrl || 'Unknown page',
    browser: getBrowserName(),
    transfer_status: 'completed',
    safe_id: safeId,
    timestamp: new Date().toISOString()
  };

  chrome.storage.local.get(['receipts'], (res) => {
    const list = res.receipts || [];
    list.push(receipt);
    chrome.storage.local.set({ receipts: list });
  });
}

// Helpers
function getBrowserName() {
  const ua = navigator.userAgent;
  if (ua.includes('Edg/')) return 'Edge';
  if (ua.includes('Chrome/')) return 'Chrome';
  if (ua.includes('Firefox/')) return 'Firefox';
  if (ua.includes('Safari/')) return 'Safari';
  return 'Browser';
}

function escapeHtml(text) {
  if (!text) return '';
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function showToast(msg) {
  toast.textContent = msg;
  toast.className = 'toast show';
  setTimeout(() => {
    toast.className = 'toast';
  }, 2500);
}
