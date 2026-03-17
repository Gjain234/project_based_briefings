// FCV Portfolio Briefing Generator - Client-side JavaScript

let currentCountry = '';
let generating = false;
let briefingText = ''; // Store original briefing text for download

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
  loadCountries();
  setupEventListeners();
  initializePromptEditor(); // Initialize prompt editor on page load
});

// Setup event listeners
function setupEventListeners() {
  // Country change
  document.getElementById('countrySelect').addEventListener('change', (e) => {
    const country = e.target.value;
    if (country) {
      currentCountry = country;
      loadRecentBriefings(country);
      loadLastScanDate(country);
    }
  });
  
  // Briefing mode change
  document.getElementById('briefingMode').addEventListener('change', handleBriefingModeChange);
  
  // Paragraphs slider
  const slider = document.getElementById('nParagraphs');
  const value = document.getElementById('nParagraphsValue');
  slider.addEventListener('input', () => {
    value.textContent = slider.value;
  });

  // Generate button
  document.getElementById('generateBtn').addEventListener('click', generateBriefing);
  
  // Custom Prompt button
  document.getElementById('customPromptBtn').addEventListener('click', () => {
    switchTab('edit-prompt');
    // Scroll to results section to show the tab
    const resultsSection = document.getElementById('resultsSection');
    if (resultsSection.style.display === 'none' || resultsSection.style.display === '') {
      resultsSection.style.display = 'block';
    }
    resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
  
  // Stop button
  document.getElementById('stopBtn').addEventListener('click', stopGeneration);
  
  // Download button
  document.getElementById('downloadBtn').addEventListener('click', downloadBriefing);
  
  // Copy button
  document.getElementById('copyBtn').addEventListener('click', copyBriefing);
  
  // Modal handlers
  document.getElementById('modalCloseBtn').addEventListener('click', closeModal);
  document.getElementById('briefingModal').addEventListener('click', (e) => {
    if (e.target.id === 'briefingModal') closeModal();
  });
  
  // Tab buttons
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => switchTab(btn.dataset.tab));
  });
}

// Load available countries
async function loadCountries() {
  console.log('loadCountries called');
  try {
    console.log('Fetching /api/briefing/countries...');
    const response = await fetch('/api/briefing/countries');
    console.log('Response status:', response.status);
    const data = await response.json();
    console.log('Countries data:', data);
    
    const select = document.getElementById('countrySelect');
    
    // Clear loading message and populate countries
    select.innerHTML = '<option value="">-- Select a country --</option>' + 
      data.countries.map(c => `<option value="${c}">${c}</option>`).join('');
    
    console.log('Countries loaded, total:', data.countries.length);
    
    // Set default country (but don't load briefings yet)
    if (data.countries.includes('Djibouti')) {
      select.value = 'Djibouti';
      currentCountry = 'Djibouti';
      loadLastScanDate(currentCountry);
      loadRecentBriefings(currentCountry);
    }
  } catch (error) {
    console.error('Error loading countries:', error);
    showStatus('Error loading countries: ' + error.message, 'error');
    document.getElementById('countrySelect').innerHTML = '<option value="">Error loading countries</option>';
  }
}

// Check last scan date for selected country
async function loadLastScanDate(country) {
  if (!country) return;
  
  try {
    const response = await fetch(`/api/briefing/last-scan/${encodeURIComponent(country)}`);
    const data = await response.json();
    
    const dateDiv = document.getElementById('lastScanDate');
    if (data.last_scan) {
      dateDiv.innerHTML = `📅 Last news scan: <strong>${data.last_scan}</strong>. Check "Regenerate with fresh news" for latest data.`;
      dateDiv.style.display = 'block';
    } else {
      dateDiv.innerHTML = '⚠️ No previous scan found - will generate from scratch (~10 minutes)';
      dateDiv.style.display = 'block';
      document.getElementById('forceRegenerate').checked = true;
    }
  } catch (error) {
    console.error('Error checking last scan:', error);
  }
}

// Handle briefing mode change
function handleBriefingModeChange() {
  const mode = document.getElementById('briefingMode').value;
  const customSection = document.getElementById('customCategoriesSection');
  const slider = document.getElementById('nParagraphs');
  const sliderValue = document.getElementById('nParagraphsValue');
  
  if (mode === 'custom') {
    customSection.style.display = 'block';
    const categories = document.getElementById('customCategories').value.split('\n').filter(c => c.trim());
    slider.value = categories.length;
    sliderValue.textContent = categories.length;
    slider.disabled = true;
  } else {
    customSection.style.display = 'none';
    slider.disabled = false;
  }
  
  // Reinitialize prompt editor to update default prompts and paragraph counts
  initializePromptEditor();
}

// Generate briefing
async function generateBriefing(customPrompt = null) {
  if (generating) return;
  
  generating = true;
  const country = document.getElementById('countrySelect').value;
  const modeSelect = document.getElementById('briefingMode');
  const mode = modeSelect.value;
  const nParagraphs = parseInt(document.getElementById('nParagraphs').value);
  const forceRegenerate = document.getElementById('forceRegenerate').checked;
  
  console.log('DEBUG generateBriefing called');
  console.log('  - modeSelect element:', modeSelect);
  console.log('  - modeSelect.value:', modeSelect.value);
  console.log('  - mode:', mode);
  console.log('  - country:', country);
  console.log('  - customPrompt:', customPrompt ? 'provided' : 'null');
  
  let customCategories = null;
  if (mode === 'custom') {
    customCategories = document.getElementById('customCategories').value
      .split('\n')
      .map(c => c.trim())
      .filter(c => c);
    console.log('  - customCategories:', customCategories);
  }
  
  // Show generating state
  document.getElementById('generateBtn').disabled = true;
  document.getElementById('stopBtn').style.display = 'flex';
  showStatus('Generating briefing...', 'info');
  document.getElementById('resultsSection').style.display = 'none';
  
  try {
    const response = await fetch('/api/briefing/generate', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        country,
        mode,
        n_paragraphs: nParagraphs,
        custom_categories: customCategories,
        custom_prompt: customPrompt,
        force_regenerate: forceRegenerate
      })
    });
    
    console.log('DEBUG generateBriefing: Sent to server:', {
      country,
      mode,
      n_paragraphs: nParagraphs,
      custom_categories: customCategories,
      custom_prompt: customPrompt ? '***PROMPT PROVIDED***' : null,
      force_regenerate: forceRegenerate
    });
    
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    
    while (true) {
      const {done, value} = await reader.read();
      if (done) break;
      
      const chunk = decoder.decode(value);
      const lines = chunk.split('\n');
      
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6));
            console.log('Received SSE data:', data);  // Debug logging
            
            if (data.status) {
              showStatus(data.status, 'info');
            }
            
            if (data.error) {
              console.error('Error from server:', data.error);
              showStatus(data.error, 'error');
              generating = false;
              resetGenerateUI();
              return;
            }
            
            if (data.complete) {
              console.log('Briefing complete, loading results...');
              
              // Fetch all data separately (too large for SSE)
              const country = data.country;
              
              Promise.all([
                fetch(`/api/briefing/content/${encodeURIComponent(country)}`).then(r => r.json()),
                fetch(`/api/briefing/risks/${encodeURIComponent(country)}`).then(r => r.json()),
                fetch(`/api/briefing/project-names/${encodeURIComponent(country)}`).then(r => r.json())
              ])
                .then(([briefingData, risksData, projectNames]) => {
                  const results = {
                    briefing: briefingData.briefing,
                    ...risksData,
                    projectNames: projectNames
                  };
                  
                  // Load all results
                  loadResults(results);
                  showStatus('Briefing generated successfully!', 'success');
                  generating = false;
                  resetGenerateUI();
                  document.getElementById('resultsSection').style.display = 'block';
                  
                  // Switch to briefing tab automatically
                  switchTab('briefing');
                  
                  // Scroll to results section
                  const resultsSection = document.getElementById('resultsSection');
                  resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
                  
                  // Hide status after 3 seconds
                  setTimeout(() => {
                    document.getElementById('statusContainer').style.display = 'none';
                  }, 3000);
                })
                .catch(err => {
                  console.error('Error loading briefing data:', err);
                  showStatus('Error loading briefing data: ' + err.message, 'error');
                  generating = false;
                  resetGenerateUI();
                });
            }
          } catch (e) {
            console.error('Error parsing SSE data:', e, 'Line:', line);
          }
        }
      }
    }
  } catch (error) {
    showStatus('Error: ' + error.message, 'error');
    generating = false;
    resetGenerateUI();
  }
}

// Stop generation
function stopGeneration() {
  generating = false;
  // Note: In a real implementation, you'd also need to abort the fetch
  showStatus('Generation cancelled', 'error');
  resetGenerateUI();
}

// Reset generate UI
function resetGenerateUI() {
  document.getElementById('generateBtn').disabled = false;
  document.getElementById('stopBtn').style.display = 'none';
}

// Show status message
function showStatus(message, type = 'info') {
  const container = document.getElementById('statusContainer');
  container.textContent = message;
  container.className = `status-container ${type}`;
  container.style.display = 'flex';
}

// Load results into tabs
function loadResults(results) {
  console.log('loadResults called with:', results);
  
  // Show download and copy buttons now that we have a briefing
  document.getElementById('downloadBtn').style.display = 'inline-flex';
  document.getElementById('copyBtn').style.display = 'inline-flex';
  
  // Load briefing - convert markdown newlines to HTML
  const briefingTextContent = results.briefing || 'No briefing generated.';
  briefingText = briefingTextContent; // Store original text for download
  console.log('Briefing text length:', briefingTextContent.length);
  
  // Simple markdown to HTML conversion
  const briefingHtml = briefingTextContent
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g, '<br>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>');
  
  document.getElementById('briefingContent').innerHTML = '<p>' + briefingHtml + '</p>';
  console.log('Briefing content loaded');
  
  // Enable custom prompt editing
  enablePromptEditor();
  
  // Helper to safely get array from field
  const safeArray = (field) => {
    if (!field) return [];
    if (Array.isArray(field)) return field;
    if (typeof field === 'string') {
      try {
        const parsed = JSON.parse(field.replace(/'/g, '"'));
        return Array.isArray(parsed) ? parsed : [];
      } catch {
        return [];
      }
    }
    return [];
  };
  
  // Load country risks
  if (results.country_risks && results.country_risks.length > 0) {
    document.getElementById('countryRisksContent').innerHTML = results.country_risks.map((risk, idx) => {
      const themes = safeArray(risk.themes);
      const keywords = safeArray(risk.keywords);
      const locations = safeArray(risk.locations);
      
      return `
      <div class="risk-card ${idx < 3 ? 'expanded' : ''}" onclick="this.classList.toggle('expanded')">
        <div class="risk-card-header">
          <div class="risk-card-title">${risk.title || 'Untitled Risk'}</div>
          <span>▼</span>
        </div>
        <div class="risk-card-body">
          <div class="risk-meta">
            <div class="risk-meta-item"><strong>Severity:</strong> ${risk.severity || 'Unknown'}</div>
            <div class="risk-meta-item"><strong>Time Horizon:</strong> ${risk.time_horizon || 'Unknown'}</div>
            <div class="risk-meta-item"><strong>Themes:</strong> ${themes.join(', ') || 'None'}</div>
          </div>
          <div class="risk-summary">${risk.summary || 'No summary available'}</div>
          ${keywords.length ? `<div class="risk-meta-item"><strong>Keywords:</strong> ${keywords.join(', ')}</div>` : ''}
          ${locations.length ? `<div class="risk-meta-item"><strong>Locations:</strong> ${locations.join(', ')}</div>` : ''}
        </div>
      </div>
    `;
    }).join('');
  } else {
    document.getElementById('countryRisksContent').innerHTML = '<p>No country risks data available.</p>';
  }
  
  // Load PAD risks
  if (results.pad_risks && results.pad_risks.length > 0) {
    const padsByProject = groupBy(results.pad_risks, 'PROJ_ID_IB');
    const projectNames = results.projectNames || {};
    document.getElementById('padRisksContent').innerHTML = Object.entries(padsByProject).map(([proj, risks]) => {
      const projName = projectNames[proj];
      const titleText = projName ? `${proj}: ${projName}` : proj;
      return `
      <div class="risk-card" onclick="this.classList.toggle('expanded')">
        <div class="risk-card-header">
          <div class="risk-card-title">Project: ${titleText} (${risks.length} susceptibilities)</div>
          <span>▼</span>
        </div>
        <div class="risk-card-body">
          ${risks.map(r => `
            <div style="margin-bottom:16px;padding-bottom:16px;border-bottom:1px solid var(--border)">
              <div class="risk-meta"><strong>Related Risk:</strong> ${r.related_country_risk_title}</div>
              <div class="risk-summary"><strong>Susceptibility:</strong> ${r.susceptibility_summary}</div>
              <div class="risk-meta-item"><em>${r.evidence_quote}</em></div>
              <div class="risk-meta-item"><strong>Confidence:</strong> ${r.confidence}</div>
            </div>
          `).join('')}
        </div>
      </div>
    `;
    }).join('');
  } else {
    document.getElementById('padRisksContent').innerHTML = '<p>No PAD risks data available.</p>';
  }
  
  // Load implementation risks
  if (results.impl_risks && results.impl_risks.length > 0) {
    const implByProject = groupBy(results.impl_risks, 'PROJ_ID_IB');
    const projectNames = results.projectNames || {};
    document.getElementById('implRisksContent').innerHTML = Object.entries(implByProject).map(([proj, risks]) => {
      const projName = projectNames[proj];
      const titleText = projName ? `${proj}: ${projName}` : proj;
      return `
      <div class="risk-card" onclick="this.classList.toggle('expanded')">
        <div class="risk-card-header">
          <div class="risk-card-title">Project: ${titleText} (${risks.length} risks)</div>
          <span>▼</span>
        </div>
        <div class="risk-card-body">
          ${risks.map(r => `
            <div style="margin-bottom:16px;padding-bottom:16px;border-bottom:1px solid var(--border)">
              <div class="risk-meta">
                <div class="risk-meta-item"><strong>${r.risk_title}</strong></div>
                <div class="risk-meta-item"><strong>Severity:</strong> ${r.severity}</div>
                <div class="risk-meta-item"><strong>Direction:</strong> ${r.direction}</div>
              </div>
              <div class="risk-summary">${r.risk_summary}</div>
              <div class="risk-meta-item"><em>${r.evidence_quote}</em></div>
              <div class="risk-meta-item"><strong>Document:</strong> ${r.doc_type}</div>
            </div>
          `).join('')}
        </div>
      </div>
    `;
    }).join('');
  } else {
    document.getElementById('implRisksContent').innerHTML = '<p>No implementation risks data available.</p>';
  }
  
  // Load risk mappings
  if (results.mappings && results.mappings.length > 0) {
    const mappingsByProject = groupBy(results.mappings, 'PROJ_ID_IB');
    const projectNames = results.projectNames || {};
    document.getElementById('mappingsContent').innerHTML = Object.entries(mappingsByProject).map(([proj, maps]) => {
      const projName = projectNames[proj];
      const titleText = projName ? `${proj}: ${projName}` : proj;
      return `
      <div class="risk-card" onclick="this.classList.toggle('expanded')">
        <div class="risk-card-header">
          <div class="risk-card-title">Project: ${titleText} (${maps.length} connections)</div>
          <span>▼</span>
        </div>
        <div class="risk-card-body">
          ${maps.map(m => `
            <div style="margin-bottom:16px;padding-bottom:16px;border-bottom:1px solid var(--border)">
              <div class="risk-meta"><strong>Country Risk:</strong> ${m.country_risk_title}</div>
              <div class="risk-summary">${m.connection_summary}</div>
              <div class="risk-meta-item"><strong>Confidence:</strong> ${m.confidence}</div>
              ${m.doc_type ? `<div class="risk-meta-item"><strong>Document:</strong> ${m.doc_type}</div>` : ''}
            </div>
          `).join('')}
        </div>
      </div>
    `;
    }).join('');
  } else {
    document.getElementById('mappingsContent').innerHTML = '<p>No risk mappings data available.</p>';
  }
}

// Switch tabs
function switchTab(tabId) {
  // Update tab buttons
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.tab === tabId);
  });
  
  // Update tab content
  document.querySelectorAll('.tab-content').forEach(content => {
    content.classList.toggle('active', content.id === `tab-${tabId}`);
  });
}

// Download briefing
function downloadBriefing() {
  const country = document.getElementById('countrySelect').value;
  const mode = document.getElementById('briefingMode').value;
  // Use the original briefing text (which has the [PROJ_ID | DOC_TYPE] markers)
  const content = briefingText || document.getElementById('briefingContent').innerText;
  const blob = new Blob([content], {type: 'text/markdown'});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${country}_${mode}_briefing.md`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function copyBriefing() {
  // Copy the briefing text to clipboard
  const content = briefingText || document.getElementById('briefingContent').innerText;
  navigator.clipboard.writeText(content).then(() => {
    // Show success feedback
    const copyBtn = document.getElementById('copyBtn');
    const originalText = copyBtn.innerHTML;
    copyBtn.innerHTML = '✓ Copied!';
    copyBtn.style.background = '#10b981';
    setTimeout(() => {
      copyBtn.innerHTML = originalText;
      copyBtn.style.background = '';
    }, 2000);
  }).catch(err => {
    alert('Failed to copy: ' + err.message);
  });
}

// Utility: Group array by key
function groupBy(array, key) {
  return array.reduce((result, item) => {
    const group = item[key] || 'Unknown';
    if (!result[group]) result[group] = [];
    result[group].push(item);
    return result;
  }, {});
}

// Initialize prompt editor on page load and when mode changes
function initializePromptEditor() {
  const editor = document.getElementById('customPromptEditor');
  const resetBtn = document.getElementById('resetPromptBtn');
  const regenerateBtn = document.getElementById('regenerateWithPromptBtn');
  
  // Get current mode to set default prompt
  const mode = document.getElementById('briefingMode').value;
  const nParagraphs = parseInt(document.getElementById('nParagraphs').value);
  
  const defaultPrompts = {
    risk: `You are writing a structured FCV portfolio briefing.

Write exactly ${nParagraphs} paragraphs.
Each paragraph must correspond to a distinct country-level FCV risk.

For each paragraph:
- Describe the country-level risk clearly without using technical risk IDs.
- Explain how projects are susceptible (PAD evidence).
- Explain whether risks are materializing (ISR/Aide evidence).
- Integrate both forward-looking and realized risks.

Important rules:
- Do NOT mention risk_id or any technical identifiers.
- Describe risks in natural language for senior leadership.
- Focus on substance, not reference codes.

Citation rules:
- When referencing PAD evidence use marker: [PROJ_ID | PAD]
- When referencing ISR/Aide evidence use marker: [PROJ_ID | document_type]
- Do NOT create hyperlinks.
- Do NOT invent citations.`,
    
    sector: `You are writing a sector-aligned FCV portfolio briefing.

Write exactly ${nParagraphs} paragraphs.
Each paragraph should correspond to a major sectoral cluster inferred from the evidence.

For each paragraph:
- Identify the sector cluster clearly in the first sentence.
- Integrate country risk context.
- Integrate PAD risks.
- Integrate realized implementation risks.

Citation rules:
- Use [PROJ_ID | PAD] for PAD evidence.
- Use [PROJ_ID | document_type] for ISR/Aide evidence.`,
    
    custom: `You are writing a structured FCV portfolio briefing.

Write exactly ${nParagraphs} paragraphs.
Each paragraph must correspond exactly to one of the provided categories.

For each paragraph:
- Use the category name clearly in the first sentence.
- Integrate relevant country risks.
- Integrate PAD risks.
- Integrate realized implementation risks.

Citation rules:
- Use marker: [PROJ_ID | PAD]
- Use marker: [PROJ_ID | document_type]`
  };
  
  // Set the default prompt
  editor.value = defaultPrompts[mode] || defaultPrompts.risk;
  editor.disabled = false;
  resetBtn.disabled = false;
  regenerateBtn.disabled = false;
  
  // Add event listeners
  resetBtn.onclick = () => {
    editor.value = defaultPrompts[mode] || defaultPrompts.risk;
  };
  
  regenerateBtn.onclick = () => {
    // Get custom prompt from editor - ensure it's a string
    let customPrompt = editor.value;
    if (customPrompt && typeof customPrompt === 'string') {
      customPrompt = customPrompt.trim();
      if (!customPrompt) {
        customPrompt = null;
      }
    } else {
      customPrompt = null;
    }
    // Log what mode is being used
    const mode = document.getElementById('briefingMode').value;
    console.log(`DEBUG: Regenerating with custom prompt, current mode=${mode}`);
    // Call generateBriefing with custom prompt (don't force regenerate - use existing country risks)
    generateBriefing(customPrompt);
  };
}

// Enable prompt editor after first briefing generation (kept for compatibility, but now does same as initialize)
function enablePromptEditor() {
  initializePromptEditor();
}

// Load recent briefings for a country
function loadRecentBriefings(country) {
  fetch(`/api/briefing/recent/${encodeURIComponent(country)}`)
    .then(response => response.json())
    .then(data => {
      const section = document.getElementById('recentBriefingsSection');
      const list = document.getElementById('recentBriefingsList');
      
      if (data.briefings && data.briefings.length > 0) {
        section.style.display = 'block';
        
        list.innerHTML = data.briefings.map(b => `
          <div class="briefing-card" onclick="viewBriefing('${b.filename}', '${country}')">
            <div class="briefing-card-title">${country} - ${b.mode.charAt(0).toUpperCase() + b.mode.slice(1)} Briefing</div>
            <div class="briefing-card-meta">
              <div class="briefing-card-meta-item">
                📅 ${b.date} at ${b.time}
              </div>
              <div class="briefing-card-meta-item">
                <span class="briefing-type-badge ${b.mode}">${b.mode}</span>
                <span style="margin-left: 8px;">📝 ${b.paragraph_count} sections</span>
              </div>
            </div>
          </div>
        `).join('');
      } else {
        section.style.display = 'none';
      }
    })
    .catch(err => {
      console.error('Error loading recent briefings:', err);
      document.getElementById('recentBriefingsSection').style.display = 'none';
    });
}

// View a specific briefing in modal
function viewBriefing(filename, country) {
  // Fetch the specific file content
  fetch(`/api/briefing/file/${encodeURIComponent(filename)}`)
    .then(response => response.json())
    .then(data => {
      if (data.briefing) {
        showModal(filename, data.briefing);
      } else {
        alert('Error: ' + (data.error || 'Briefing not found'));
      }
    })
    .catch(err => {
      console.error('Error loading briefing:', err);
      alert('Error loading briefing: ' + err.message);
    });
}

// Show modal with briefing content
function showModal(title, content) {
  const modal = document.getElementById('briefingModal');
  const modalTitle = document.getElementById('modalTitle');
  const modalBody = document.getElementById('modalBody');
  const downloadBtn = document.getElementById('modalDownloadBtn');
  const copyBtn = document.getElementById('modalCopyBtn');
  
  modalTitle.textContent = title;
  
  // Convert markdown to HTML
  const html = content
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g, '<br>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>');
  
  modalBody.innerHTML = '<p>' + html + '</p>';
  
  // Set up copy button
  copyBtn.onclick = () => {
    navigator.clipboard.writeText(content).then(() => {
      const originalText = copyBtn.innerHTML;
      copyBtn.innerHTML = '✓ Copied!';
      copyBtn.style.background = '#10b981';
      setTimeout(() => {
        copyBtn.innerHTML = originalText;
        copyBtn.style.background = '';
      }, 2000);
    }).catch(err => {
      alert('Failed to copy: ' + err.message);
    });
  };
  
  // Set up download button
  downloadBtn.onclick = () => {
    const blob = new Blob([content], {type: 'text/markdown'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = title;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };
  
  modal.style.display = 'flex';
}

// Close modal
function closeModal() {
  document.getElementById('briefingModal').style.display = 'none';
}
