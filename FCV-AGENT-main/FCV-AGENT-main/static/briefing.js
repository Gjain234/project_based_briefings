// FCV Portfolio Briefing Generator - Client-side JavaScript

let currentCountry = '';
let generating = false;
let briefingText = ''; // Store original briefing text for download
let rraComparisonAbortController = null; // Track active RRA comparison for cancellation
let lastMapData = null; // Store last loaded map data for HTML export
let compareRraBtnDefaultHtml = '';
let modalCompareRraBtnDefaultHtml = '';

const SPINNER_SVG = `<svg class="status-spinner" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/></svg>`;

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
  loadCountries();
  setupEventListeners();
  initializePromptEditor(); // Initialize prompt editor on page load
});

// Setup event listeners
function setupEventListeners() {
  const compareRraBtn = document.getElementById('compareRraBtn');
  const modalCompareRraBtn = document.getElementById('modalCompareRraBtn');
  compareRraBtnDefaultHtml = compareRraBtn ? compareRraBtn.innerHTML : '';
  modalCompareRraBtnDefaultHtml = modalCompareRraBtn ? modalCompareRraBtn.innerHTML : '';

  // Country change
  document.getElementById('countrySelect').addEventListener('change', (e) => {
    const country = e.target.value;
    if (country) {
      resetBriefingViewState();
      currentCountry = country;
      loadRecentBriefings(country);
      loadLastScanDate(country);
      // Enable map button when country is selected
      document.getElementById('loadMapBtn').disabled = false;
    } else {
      resetBriefingViewState();
      currentCountry = '';
      document.getElementById('loadMapBtn').disabled = true;
    }
  });
  
  // Load map button
  document.getElementById('loadMapBtn').addEventListener('click', () => {
    if (currentCountry) {
      const btn = document.getElementById('loadMapBtn');
      btn.disabled = true;
      btn.innerHTML = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="animation:spin 1s linear infinite"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/></svg> Loading...`;
      loadCountryMap(currentCountry);
      // Scroll to map
      const mapSection = document.getElementById('mapSection');
      if (mapSection) {
        mapSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
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

  // Export HTML button
  document.getElementById('exportHtmlBtn').addEventListener('click', exportBriefingHtml);

  // Copy button
  document.getElementById('copyBtn').addEventListener('click', copyBriefing);
  
  // Compare to RRA button
  document.getElementById('compareRraBtn').addEventListener('click', compareToRra);

  // Modal handlers
  document.getElementById('modalCloseBtn').addEventListener('click', closeModal);
  document.getElementById('briefingModal').addEventListener('click', (e) => {
    if (e.target.id === 'briefingModal') closeModal();
  });
  
  // Modal Compare to RRA button
  document.getElementById('modalCompareRraBtn').addEventListener('click', compareToRra);
  
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
      document.getElementById('loadMapBtn').disabled = false;
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
  } else if (mode === 'project-based') {
    customSection.style.display = 'none';
    slider.disabled = true;
    slider.style.opacity = '0.5';
    sliderValue.textContent = 'auto';
  } else {
    customSection.style.display = 'none';
    slider.disabled = false;
    slider.style.opacity = '1';
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
  const generateBtn = document.getElementById('generateBtn');
  generateBtn.disabled = true;
  generateBtn.innerHTML = `${SPINNER_SVG} Generating…`;
  document.getElementById('stopBtn').style.display = 'flex';
  showStatus('Generating briefing…', 'info');
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
                  
                  // Update currentCountry for RRA check
                  currentCountry = country;
                  
                  // Load all results
                  loadResults(results);
                  showStatus('Briefing generated successfully!', 'success');
                  generating = false;
                  resetGenerateUI();
                  document.getElementById('resultsSection').style.display = 'block';
                  
                  // Switch to briefing tab automatically
                  switchTab('briefing');
                  
                  // Scroll to map section if it exists and is visible, otherwise to briefing
                  const mapSection = document.getElementById('mapSection');
                  const scrollTarget = (mapSection && mapSection.style.display !== 'none') ? mapSection : document.getElementById('resultsSection');
                  scrollTarget.scrollIntoView({ behavior: 'smooth', block: 'start' });
                  
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
  const generateBtn = document.getElementById('generateBtn');
  generateBtn.disabled = false;
  generateBtn.innerHTML = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg> Generate Briefing`;
  document.getElementById('stopBtn').style.display = 'none';
}

// Show status message
function showStatus(message, type = 'info') {
  const container = document.getElementById('statusContainer');
  container.className = `status-container ${type}`;
  container.style.display = 'flex';
  if (type === 'info') {
    container.innerHTML = `${SPINNER_SVG}<span>${message}</span>`;
  } else {
    container.textContent = message;
  }
}

function resetBriefingViewState() {
  if (rraComparisonAbortController) {
    rraComparisonAbortController.abort();
    rraComparisonAbortController = null;
  }

  briefingText = '';
  lastMapData = null;

  const briefingContentEl = document.getElementById('briefingContent');
  const annotatedContentEl = document.getElementById('annotatedBriefingContent');
  const viewToggleBtn = document.getElementById('rraViewToggleBtn');
  const compareBtn = document.getElementById('compareRraBtn');
  const modalCompareBtn = document.getElementById('modalCompareRraBtn');
  const resultsSection = document.getElementById('resultsSection');
  const mapSection = document.getElementById('mapSection');
  const mapLegend = document.getElementById('mapLegend');

  if (briefingContentEl) {
    briefingContentEl.innerHTML = '';
    briefingContentEl.style.display = 'block';
  }
  if (annotatedContentEl) {
    annotatedContentEl.innerHTML = '';
    annotatedContentEl.style.display = 'none';
  }
  if (viewToggleBtn) {
    viewToggleBtn.style.display = 'none';
    viewToggleBtn.textContent = 'View Original';
    viewToggleBtn.onclick = null;
  }
  if (compareBtn) {
    compareBtn.style.display = 'none';
    compareBtn.disabled = false;
    if (compareRraBtnDefaultHtml) compareBtn.innerHTML = compareRraBtnDefaultHtml;
  }
  if (modalCompareBtn) {
    modalCompareBtn.style.display = 'none';
    modalCompareBtn.disabled = false;
    if (modalCompareRraBtnDefaultHtml) modalCompareBtn.innerHTML = modalCompareRraBtnDefaultHtml;
  }

  document.getElementById('downloadBtn').style.display = 'none';
  document.getElementById('copyBtn').style.display = 'none';
  document.getElementById('exportHtmlBtn').style.display = 'none';

  if (resultsSection) {
    resultsSection.style.display = 'none';
  }

  if (currentMap) {
    currentMap.remove();
    currentMap = null;
  }
  if (mapSection) {
    mapSection.style.display = 'none';
  }
  if (mapLegend) {
    mapLegend.innerHTML = '';
  }

  const projectCountEl = document.getElementById('projectCount');
  const eventCountEl = document.getElementById('eventCount');
  const riskScanCountEl = document.getElementById('riskScanCount');
  if (projectCountEl) projectCountEl.textContent = '0';
  if (eventCountEl) eventCountEl.textContent = '0';
  if (riskScanCountEl) riskScanCountEl.textContent = '0';
}

// Load results into tabs
function loadResults(results) {
  console.log('loadResults called with:', results);

  // Clear any stale RRA state before rendering newly generated content.
  resetBriefingViewState();
  document.getElementById('resultsSection').style.display = 'block';
  
  // Show download and copy buttons now that we have a briefing
  document.getElementById('downloadBtn').style.display = 'inline-flex';
  document.getElementById('copyBtn').style.display = 'inline-flex';
  document.getElementById('exportHtmlBtn').style.display = 'inline-flex';
  
  // Check if RRA exists for this country
  checkRraExists(currentCountry);
  
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
  
  // Load map for the country
  loadCountryMap(currentCountry);
  
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
function exportBriefingHtml() {
  const country = currentCountry || document.getElementById('countrySelect').value || 'briefing';
  const annotatedEl = document.getElementById('annotatedBriefingContent');
  const originalEl = document.getElementById('briefingContent');
  const hasRra = annotatedEl && annotatedEl.innerHTML.trim();

  const originalHtml = originalEl ? originalEl.innerHTML : '';
  const annotatedHtml = hasRra ? annotatedEl.innerHTML : '';
  const title = hasRra ? `${country} \u2014 RRA Comparison` : `${country} \u2014 Briefing`;

  // Toggle button + script (only when both versions exist)
  const toggleSection = hasRra ? `
    <div style="display:flex;gap:8px;align-items:center;margin-bottom:20px;">
      <button id="viewToggleBtn" onclick="toggleRraView()" style="background:#f5f3ff;color:#5b21b6;border:1px solid #7c3aed;border-radius:6px;padding:6px 14px;font-size:13px;font-weight:500;cursor:pointer;">View Original</button>
      <span id="viewLabel" style="font-size:12px;color:#7c3aed;font-style:italic;">Showing RRA Comparison</span>
    </div>
    <script>
    var _showingRra = true;
    function toggleRraView() {
      _showingRra = !_showingRra;
      document.getElementById('briefingOriginal').style.display = _showingRra ? 'none' : 'block';
      document.getElementById('briefingAnnotated').style.display = _showingRra ? 'block' : 'none';
      document.getElementById('viewToggleBtn').textContent = _showingRra ? 'View Original' : 'View RRA Comparison';
      document.getElementById('viewLabel').textContent = _showingRra ? 'Showing RRA Comparison' : 'Showing Original Briefing';
    }
    <\/script>` : '';

  // Map section
  const mapSection = lastMapData ? (() => {
    const md = lastMapData;
    const projectsJson = JSON.stringify(md.projects || []);
    const eventsJson = JSON.stringify(md.events || []);
    const risksJson = JSON.stringify(md.scanRisks || []);
    const colorMapJson = JSON.stringify(md.eventColorByKey || {});
    return `
  <div style="margin-bottom:32px;">
    <h3 style="color:#1e40af;margin-bottom:8px;">Project &amp; Risk Map</h3>
    <div style="display:flex;gap:16px;">
      <div id="exportMap" style="flex:1;height:500px;border-radius:8px;border:1px solid #e2e8f0;"></div>
      <div id="exportLegend" style="width:180px;background:#fff;border:1px solid #e2e8f0;border-radius:8px;padding:12px;font-family:sans-serif;font-size:12px;overflow-y:auto;max-height:500px;"></div>
    </div>
    <div style="margin-top:10px;display:flex;align-items:center;gap:10px;font-family:sans-serif;font-size:12px;color:#374151;">
      <span style="font-weight:600;">ACLED Window:</span>
      <input id="exportWeeksSlider" type="range" min="1" max="13" step="1" value="12" style="flex:1;max-width:200px;accent-color:#374151;cursor:pointer;">
      <span id="exportWeeksLabel" style="min-width:60px;">12 weeks</span>
      <span id="exportEventCount" style="color:#9ca3af;"></span>
    </div>
  </div>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"><\/script>
  <script>
  (function(){
    var projects=${projectsJson};
    var allEvents=${eventsJson};
    var risks=${risksJson};
    var eventColorByKey=${colorMapJson};

    function parseDate(v){
      if(!v) return null;
      var d=new Date(String(v).trim().split('T')[0]);
      return isNaN(d.getTime())?null:d;
    }
    function filterByWeeks(evts,w){
      var cutoff=new Date(); cutoff.setHours(0,0,0,0); cutoff.setDate(cutoff.getDate()-w*7);
      return evts.filter(function(e){var d=parseDate(e.date);return d&&d>=cutoff;});
    }
    function getEvtKey(e){ return (e.sub_event_type||e.event_type||'Other').trim()||'Other'; }
    function getEvtColor(e){ return eventColorByKey[getEvtKey(e)]||'#f59e0b'; }

    var map=L.map('exportMap').setView([20,40],4);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'\u00a9 OpenStreetMap contributors',maxZoom:19}).addTo(map);

    var projectIcon=L.divIcon({html:'<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 20 20"><polygon points="10,1 19,10 10,19 1,10" fill="#2563eb" stroke="#1e40af" stroke-width="2"/><circle cx="10" cy="10" r="3" fill="white"/></svg>',className:'',iconSize:[18,18],iconAnchor:[9,9],popupAnchor:[0,-12]});

    // Project markers (always shown)
    var projCoords=[];
    projects.forEach(function(p){
      if(p.lat&&p.lon){projCoords.push([p.lat,p.lon]);L.marker([p.lat,p.lon],{icon:projectIcon}).bindPopup('<b>'+(p.project_name||p.proj_id)+'</b><br><em style="color:#777;font-size:11px;">'+p.proj_id+'</em>').addTo(map);}
    });

    // Risk scan markers (always shown) — diamond shape on top pane
    map.createPane('riskPane'); map.getPane('riskPane').style.zIndex=650;
    var riskCoords=[];
    risks.forEach(function(r){
      if(r.lat&&r.lon){riskCoords.push([r.lat,r.lon]);
        var sev=(r.severity||'').toLowerCase();
        var rc=sev==='high'?'#dc2626':sev==='medium'?'#f87171':'#fca5a5';
        var bc=sev==='high'?'#7f1d1d':sev==='medium'?'#991b1b':'#b91c1c';
        var sz=sev==='high'?18:15;
        var icon=L.divIcon({html:'<svg xmlns="http://www.w3.org/2000/svg" width="'+sz+'" height="'+sz+'" viewBox="0 0 20 20"><polygon points="10,1 19,10 10,19 1,10" fill="'+rc+'" stroke="'+bc+'" stroke-width="2"/></svg>',className:'',iconSize:[sz,sz],iconAnchor:[sz/2,sz/2],popupAnchor:[0,-sz/2]});
        L.marker([r.lat,r.lon],{icon:icon,pane:'riskPane'}).bindPopup('<b style="color:'+rc+'">'+(r.title||'Risk')+'</b><br><span style="color:#555;">Severity: '+(r.severity||'n/a')+'</span><br>'+(r.summary||'')).addTo(map);
      }
    });

    // ACLED event layer group (re-rendered by slider)
    var eventGroup=L.layerGroup().addTo(map);

    function renderEvents(weeksBack){
      eventGroup.clearLayers();
      var filtered=filterByWeeks(allEvents,weeksBack);
      filtered.forEach(function(e){
        if(!e.lat||!e.lon) return;
        var color=getEvtColor(e);
        var note=e.notes?e.notes.substring(0,200)+(e.notes.length>200?'\u2026':''):'';
        L.circleMarker([e.lat,e.lon],{radius:6.5,fillColor:color,color:'#fff',weight:1.4,fillOpacity:0.82}).bindPopup('<div style="font-size:12px;line-height:1.6;max-width:250px;"><b style="color:'+color+'">'+(e.sub_event_type||e.event_type||'Event')+'</b><br><b>Type:</b> '+(e.event_type||'')+'<br><b>Date:</b> '+(e.date||'')+' <b>Location:</b> '+(e.location||'')+(note?'<br><span style="color:#555;">'+note+'</span>':'')+'</div>').addTo(eventGroup);
      });
      document.getElementById('exportEventCount').textContent='Events: '+filtered.length;
      buildLegend(filtered);
    }

    function buildLegend(filtered){
      var leg=document.getElementById('exportLegend');
      leg.innerHTML='<div style="font-size:11px;font-weight:700;text-transform:uppercase;color:#6b7280;letter-spacing:.5px;margin-bottom:8px;">Legend</div>';
      // Projects
      leg.innerHTML+='<div style="display:flex;align-items:center;gap:6px;padding:3px 0;border-bottom:1px solid #f3f4f6;margin-bottom:4px;"><svg width="12" height="12" viewBox="0 0 20 20"><polygon points="10,1 19,10 10,19 1,10" fill="#2563eb" stroke="#1e40af" stroke-width="2"/><circle cx="10" cy="10" r="3" fill="white"/></svg><span style="font-size:12px;font-weight:600;color:#1e40af;">Projects</span><span style="margin-left:auto;font-size:11px;color:#9ca3af;">'+projects.length+'</span></div>';
      // Risk scan
      if(risks.length){leg.innerHTML+='<div style="display:flex;align-items:center;gap:6px;padding:3px 0;border-bottom:1px solid #f3f4f6;margin-bottom:6px;"><svg width="12" height="12" viewBox="0 0 20 20"><polygon points="10,1 19,10 10,19 1,10" fill="#dc2626" stroke="#7f1d1d" stroke-width="2"/></svg><span style="font-size:12px;font-weight:600;color:#991b1b;">Risk Scan</span><span style="margin-left:auto;font-size:11px;color:#9ca3af;">'+risks.length+'</span></div>';}
      // ACLED subtypes
      if(filtered.length){
        leg.innerHTML+='<div style="font-size:11px;font-weight:700;text-transform:uppercase;color:#6b7280;letter-spacing:.5px;margin-bottom:4px;">Conflict Events</div>';
        var counts={};
        filtered.forEach(function(e){var k=getEvtKey(e);counts[k]=(counts[k]||0)+1;});
        Object.keys(counts).sort(function(a,b){return counts[b]-counts[a];}).forEach(function(k){
          var color=eventColorByKey[k]||'#f59e0b';
          leg.innerHTML+='<div style="display:flex;align-items:center;gap:6px;padding:2px 0;"><span style="width:11px;height:11px;border-radius:50%;background:'+color+';display:inline-block;flex-shrink:0;"></span><span style="font-size:11px;color:#374151;flex:1;">'+k+'</span><span style="font-size:11px;color:#9ca3af;">'+counts[k]+'</span></div>';
        });
      }
    }

    // Initial render
    renderEvents(12);

    // Fit bounds
    var allCoords=projCoords.concat(riskCoords);
    allEvents.forEach(function(e){if(e.lat&&e.lon)allCoords.push([e.lat,e.lon]);});
    if(allCoords.length>0){var g=L.featureGroup(allCoords.map(function(c){return L.marker(c);}));map.fitBounds(g.getBounds(),{padding:[40,40],maxZoom:10});}

    // Slider
    var slider=document.getElementById('exportWeeksSlider');
    var wLabel=document.getElementById('exportWeeksLabel');
    slider.addEventListener('input',function(){
      var w=Number(slider.value);
      wLabel.textContent=w===1?'1 week':w+' weeks';
      renderEvents(w);
    });
  })();
  <\/script>`;
  })() : '';

  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>${title}</title>
  <style>
    body { font-family: Georgia, serif; max-width: 900px; margin: 40px auto; padding: 0 24px; color: #1a202c; line-height: 1.75; }
    h2, h3 { color: #1e40af; }
    p { margin: 0 0 1em; }
    .rra-highlighted {
      background: #fef3c7;
      border-bottom: 2px solid #f59e0b;
      border-radius: 2px;
      padding: 1px 2px;
      cursor: help;
      position: relative;
      display: inline;
    }
    .rra-highlighted:hover { background: #fcd34d; }
    .rra-tooltip {
      visibility: hidden;
      opacity: 0;
      width: 300px;
      background: #1f2937;
      color: #fff;
      font-size: 12px;
      padding: 8px 12px;
      border-radius: 6px;
      position: absolute;
      bottom: calc(100% + 8px);
      left: 50%;
      transform: translateX(-50%);
      z-index: 999;
      white-space: normal;
      line-height: 1.5;
      box-shadow: 0 4px 12px rgba(0,0,0,.25);
      border-left: 3px solid #009FDA;
      transition: opacity 0.2s;
      pointer-events: none;
    }
    .rra-highlighted:hover .rra-tooltip { visibility: visible; opacity: 1; }
  </style>
</head>
<body>
  <h2>${title}</h2>
  ${mapSection}
  ${toggleSection}
  <div id="briefingAnnotated" style="display:${hasRra ? 'block' : 'none'}">${annotatedHtml}</div>
  <div id="briefingOriginal" style="display:${hasRra ? 'none' : 'block'}">${originalHtml}</div>
</body>
</html>`;

  const blob = new Blob([html], { type: 'text/html' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${country.replace(/[^a-z0-9]/gi, '_')}_briefing.html`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

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
    rra: `You are writing a structured FCV portfolio briefing organised around the five standard short-term RRA (Risk and Resilience Assessment) risk headings.

Write exactly 5 paragraphs, one per heading, in this order:
1. Social unrest and protests
2. Violence between refugees, host communities, and the state
3. Organized violence between political and sectarian groups
4. Political instability
5. External risks and intra-state conflict

For each paragraph:
- Begin with the exact RRA heading in bold followed by a colon (e.g. **Social unrest and protests:**).
- Summarise relevant country-level FCV dynamics under that heading.
- Show how World Bank projects are susceptible to that risk (PAD evidence).
- Show whether risks are materialising in implementation (ISR/Aide Memoire evidence).

Citation rules:
- Use [PROJ_ID | PAD] for PAD evidence.
- Use [PROJ_ID | document_type] for ISR/Aide evidence.
- Each citation in its own bracket pair. NEVER combine with semicolons.
- Do NOT create hyperlinks. Do NOT invent citations.`,

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
  editor.value = defaultPrompts[mode] || defaultPrompts.rra;
  editor.disabled = false;
  resetBtn.disabled = false;
  regenerateBtn.disabled = false;
  
  // Add event listeners
  resetBtn.onclick = () => {
    editor.value = defaultPrompts[mode] || defaultPrompts.rra;
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

// View a specific briefing in main content area
function viewBriefing(filename, country) {
  // Fetch the specific file content
  fetch(`/api/briefing/file/${encodeURIComponent(filename)}`)
    .then(response => response.json())
    .then(data => {
      if (data.briefing) {
        // Update currentCountry and briefingText for global use
        if (country) {
          currentCountry = country;
        }
        briefingText = data.briefing;
        
        // Display briefing inline in main content area
        const briefingHtml = data.briefing
          .replace(/\n\n/g, '</p><p>')
          .replace(/\n/g, '<br>')
          .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
          .replace(/\*(.+?)\*/g, '<em>$1</em>');
        
        document.getElementById('briefingContent').innerHTML = '<p>' + briefingHtml + '</p>';
        
        // Show download and export buttons
        document.getElementById('downloadBtn').style.display = 'inline-flex';
        document.getElementById('exportHtmlBtn').style.display = 'inline-flex';
        document.getElementById('copyBtn').style.display = 'inline-flex';
        document.getElementById('resultsSection').style.display = 'block';
        
        // Check if RRA exists for this country
        if (country) {
          checkRraExists(country);
        }
        
        // Switch to briefing tab and scroll into view
        switchTab('briefing');
        const resultsSection = document.getElementById('resultsSection');
        if (resultsSection) {
          resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
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
function showModal(title, content, country = null) {
  const modal = document.getElementById('briefingModal');
  const modalTitle = document.getElementById('modalTitle');
  const modalBody = document.getElementById('modalBody');
  const downloadBtn = document.getElementById('modalDownloadBtn');
  const copyBtn = document.getElementById('modalCopyBtn');
  
  // Store briefing text for comparison
  briefingText = content;
  
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
  
  // If country was provided, update currentCountry and check if RRA exists
  if (country) {
    currentCountry = country;
    checkRraExists(country);
  }
  
  modal.style.display = 'flex';
}

// Close modal
function closeModal() {
  // Cancel any active RRA comparison when modal closes
  if (rraComparisonAbortController) {
    rraComparisonAbortController.abort();
    rraComparisonAbortController = null;
    showStatus('RRA comparison cancelled', 'info');
  }
  document.getElementById('briefingModal').style.display = 'none';
}
// Check if RRA exists for the country and show/hide compare button
async function checkRraExists(country) {
  if (!country) {
    document.getElementById('compareRraBtn').style.display = 'none';
    document.getElementById('modalCompareRraBtn').style.display = 'none';
    return;
  }
  
  try {
    const response = await fetch(`/api/briefing/rra-check/${encodeURIComponent(country)}`);
    const data = await response.json();
    
    const compareBtn = document.getElementById('compareRraBtn');
    const modalCompareBtn = document.getElementById('modalCompareRraBtn');
    
    if (data.exists) {
      if (compareBtn) compareBtn.style.display = 'inline-flex';
      if (modalCompareBtn) modalCompareBtn.style.display = 'inline-flex';
    } else {
      if (compareBtn) compareBtn.style.display = 'none';
      if (modalCompareBtn) modalCompareBtn.style.display = 'none';
    }
  } catch (error) {
    console.error('Error checking RRA:', error);
    document.getElementById('compareRraBtn').style.display = 'none';
    document.getElementById('modalCompareRraBtn').style.display = 'none';
  }
}

// Compare briefing to RRA
async function compareToRra() {
  const country = currentCountry;
  const briefing = briefingText || document.getElementById('briefingContent').innerText;
  
  if (!country || !briefing) {
    alert('Please generate a briefing first');
    return;
  }
  
  const compareBtn = document.getElementById('compareRraBtn');
  const modalCompareBtn = document.getElementById('modalCompareRraBtn');
  const originalText = compareBtn ? compareBtn.innerHTML : '';
  const originalModalText = modalCompareBtn ? modalCompareBtn.innerHTML : '';
  
  // Create AbortController for this comparison
  rraComparisonAbortController = new AbortController();
  
  // Disable both buttons and show loading state
  if (compareBtn) {
    compareBtn.disabled = true;
    compareBtn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="animation: spin 1s linear infinite;"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg> Comparing...';
  }
  if (modalCompareBtn) {
    modalCompareBtn.disabled = true;
    modalCompareBtn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="animation: spin 1s linear infinite;"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg> Comparing...';
  }
  
  // Show status message
  showStatus('Comparing briefing to RRA... this may take a minute', 'info');
  
  try {
    const response = await fetch('/api/briefing/compare-to-rra', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        country: country,
        briefing: briefing
      }),
      signal: rraComparisonAbortController.signal
    });
    
    const data = await response.json();
    
    if (!response.ok) {
      throw new Error(data.error || 'Failed to compare briefing to RRA');
    }
    
    // Swap briefingContent with annotated version in-place
    const briefingContentEl = document.getElementById('briefingContent');
    const annotatedContent = document.getElementById('annotatedBriefingContent');

    // Populate annotated version
    annotatedContent.innerHTML = data.annotated_briefing;

    // Add tooltips to highlighted elements
    annotatedContent.querySelectorAll('.rra-highlighted').forEach(span => {
      if (span.querySelector('.rra-tooltip')) return; // already injected
      const rraRef = span.getAttribute('data-rra-reference') || '';
      const tooltip = document.createElement('span');
      tooltip.className = 'rra-tooltip';
      tooltip.textContent = rraRef.trim()
        ? (rraRef.length > 250 ? rraRef.substring(0, 250) + '\u2026' : rraRef)
        : 'Connected to RRA finding';
      span.appendChild(tooltip);
    });

    // Switch to annotated view
    briefingContentEl.style.display = 'none';
    annotatedContent.style.display = 'block';

    // Show and wire the toggle button
    const viewToggleBtn = document.getElementById('rraViewToggleBtn');
    if (viewToggleBtn) {
      viewToggleBtn.style.display = 'inline-flex';
      let showingRra = true;
      viewToggleBtn.onclick = () => {
        showingRra = !showingRra;
        briefingContentEl.style.display = showingRra ? 'none' : 'block';
        annotatedContent.style.display = showingRra ? 'block' : 'none';
        viewToggleBtn.textContent = showingRra ? 'View Original' : 'View RRA Comparison';
      };
    }

    // Scroll to top of briefing area
    briefingContentEl.parentElement.scrollIntoView({ behavior: 'smooth', block: 'start' });

    const cacheStatus = data.from_cache
      ? 'RRA comparison loaded from cache!'
      : 'RRA comparison complete!';
    showStatus(cacheStatus, 'success');
  } catch (error) {
    // Check if this was an abort (user closed the modal)
    if (error.name === 'AbortError') {
      console.log('RRA comparison was cancelled');
      // Don't show error message - cancellation is expected
    } else {
      console.error('Error comparing to RRA:', error);
      showStatus('Error comparing to RRA: ' + error.message, 'error');
    }
  } finally {
    // Clear the abort controller
    rraComparisonAbortController = null;
    
    if (compareBtn) {
      compareBtn.disabled = false;
      compareBtn.innerHTML = originalText;
    }
    if (modalCompareBtn) {
      modalCompareBtn.disabled = false;
      modalCompareBtn.innerHTML = originalModalText;
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Map Functions
// ─────────────────────────────────────────────────────────────────────────────

let currentMap = null;

// Color mapping for ACLED event types — kept intentionally diverse
const EVENT_TYPE_COLORS = {
  'Protests': '#14b8a6',
  'Riots': '#a3a30a',
  'Violence against civilians': '#d946ef',
  'Battles': '#c26b00',
  'Explosions/remote violence': '#7c3aed',
  'Strategic developments': '#0d9488',
  'default': '#6d28d9'
};

const FALLBACK_EVENT_COLORS = [
  '#14b8a6', '#0d9488', '#84cc16', '#a3a30a', '#c26b00', '#7c3aed', '#6d28d9', '#d946ef', '#0891b2', '#65a30d'
];

const ACLED_EXCLUDED_HUE_WINDOWS = [
  [200, 236], // avoid project blue neighborhood (#2563eb ~ hue 218)
  [345, 360], // avoid risk red neighborhood upper wrap
  [0, 16]     // avoid risk red neighborhood lower wrap
];

function hashColorSeed(value) {
  let hash = 0;
  const text = String(value || '');
  for (let i = 0; i < text.length; i += 1) {
    hash = ((hash << 5) - hash) + text.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash);
}

function isExcludedAcledHue(hue) {
  const h = ((Math.round(hue) % 360) + 360) % 360;
  return ACLED_EXCLUDED_HUE_WINDOWS.some(([start, end]) => h >= start && h <= end);
}

function buildAcledHuePool() {
  const hues = [];
  for (let hue = 0; hue < 360; hue += 3) {
    if (!isExcludedAcledHue(hue)) {
      hues.push(hue);
    }
  }
  return hues.length ? hues : [40, 110, 285];
}

const ACLED_HUE_POOL = buildAcledHuePool();

function getVividSubtypeColor(label) {
  const seed = hashColorSeed(label || 'default');
  const hue = ACLED_HUE_POOL[seed % ACLED_HUE_POOL.length];
  const saturation = 62 + (seed % 9); // 62-70%, less neon
  const lightness = 46 + (Math.floor(seed / 17) % 11); // 46-56%
  return `hsl(${hue}, ${saturation}%, ${lightness}%)`;
}

function getAcledEventKey(event) {
  if (!event || typeof event !== 'object') return 'Other';
  return String(event.sub_event_type || event.event_type || 'Other').trim() || 'Other';
}

function buildDistinctEventColorMap(events) {
  const uniqueKeys = Array.from(new Set((Array.isArray(events) ? events : []).map(getAcledEventKey))).sort();
  const total = Math.max(uniqueKeys.length, 1);
  const colorMap = {};
  const huePool = ACLED_HUE_POOL;
  const satCycle = [62, 66, 70, 64];
  const lightCycle = [46, 52, 58, 50];
  const startOffset = hashColorSeed(uniqueKeys.join('|')) % huePool.length;

  uniqueKeys.forEach((key, index) => {
    const poolIndex = (startOffset + Math.floor((index * huePool.length) / total)) % huePool.length;
    const hue = huePool[poolIndex];
    const saturation = satCycle[index % satCycle.length];
    const lightness = lightCycle[index % lightCycle.length];
    colorMap[key] = `hsl(${hue}, ${saturation}%, ${lightness}%)`;
  });

  return colorMap;
}

function getEventColor(eventType, subEventType) {
  const subtype = String(subEventType || '').trim();
  const type = String(eventType || '').trim();

  // Prioritize subtype colors so ACLED legend + markers show specific event diversity.
  if (subtype) return getVividSubtypeColor(subtype);
  if (EVENT_TYPE_COLORS[type]) return EVENT_TYPE_COLORS[type];

  const seed = hashColorSeed(type || 'default');
  return FALLBACK_EVENT_COLORS[seed % FALLBACK_EVENT_COLORS.length] || EVENT_TYPE_COLORS.default;
}

function normalizeProjId(value) {
  return String(value || '').trim().toUpperCase().replace(/[^A-Z0-9]/g, '');
}

function loadCountryMap(country) {
  const mapUrl = `/api/briefing/map-data/${encodeURIComponent(country)}`;
  const namesUrl = `/api/briefing/project-names/${encodeURIComponent(country)}`;

  Promise.all([
    fetch(mapUrl).then(response => response.json()),
    fetch(namesUrl).then(response => response.json()).catch(() => ({}))
  ])
    .then(([data, projectNames]) => {
      if (data.error) {
        console.error('Error loading map data:', data.error);
        return;
      }

      const namesByNorm = {};
      Object.entries(projectNames || {}).forEach(([pid, pname]) => {
        const norm = normalizeProjId(pid);
        if (norm && pname) {
          namesByNorm[norm] = String(pname);
        }
      });

      const mergedProjects = (data.projects || []).map(project => {
        const normId = normalizeProjId(project.proj_id);
        const padName = namesByNorm[normId] || '';
        return {
          ...project,
          project_name: project.project_name || padName
        };
      });

      lastMapData = { country, projects: mergedProjects, events: data.events || [], scanRisks: data.scan_risks || [], eventColorByKey: buildDistinctEventColorMap(data.events || []) };
      renderMap(country, mergedProjects, data.events || [], data.scan_risks || []);
    })
    .catch(error => {
      console.error('Error fetching map data:', error);
    })
    .finally(() => {
      const btn = document.getElementById('loadMapBtn');
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg> Load Map`;
      }
    });
}

function parseAcledEventDate(dateValue) {
  if (!dateValue) return null;
  const raw = String(dateValue).trim();
  const dateOnly = raw.split('T')[0];

  let parsed = new Date(dateOnly);
  if (!Number.isNaN(parsed.getTime())) {
    return parsed;
  }

  const parts = dateOnly.split('/');
  if (parts.length === 3) {
    parsed = new Date(parts[2] + '-' + parts[1] + '-' + parts[0]);
    if (!Number.isNaN(parsed.getTime())) return parsed;
  }
  return null;
}

function filterEventsByWeeks(events, weeksBack) {
  const safeWeeksBack = Math.min(13, Math.max(1, Number(weeksBack) || 12));
  const cutoff = new Date();
  cutoff.setHours(0, 0, 0, 0);
  cutoff.setDate(cutoff.getDate() - (safeWeeksBack * 7));

  return (Array.isArray(events) ? events : []).filter(event => {
    const eventDate = parseAcledEventDate(event.date);
    return eventDate && eventDate >= cutoff;
  });
}

function formatWeekWindowLabel(weeksBack) {
  return weeksBack === 1 ? '1 week' : (weeksBack + ' weeks');
}

function renderMap(country, projects, events, scanRisks) {
  const mapContainer = document.getElementById('mapContainer');
  const mapSection = document.getElementById('mapSection');
  
  if (!mapContainer) return;
  
  // Show map section FIRST so container has proper dimensions
  mapSection.style.display = 'block';
  
  // Destroy existing map if any
  if (currentMap) {
    currentMap.remove();
    currentMap = null;
  }
  
  const allEvents = Array.isArray(events) ? events : [];
  const allScanRisks = Array.isArray(scanRisks) ? scanRisks : [];
  let selectedWeeksBack = 12;
  let filteredEvents = filterEventsByWeeks(allEvents, selectedWeeksBack);
  const eventColorByKey = buildDistinctEventColorMap(allEvents);

  // Initialize map - center on first marker or world center
  let mapCenter = [0, 20];
  if (projects.length > 0) {
    mapCenter = [projects[0].lat, projects[0].lon];
  } else if (filteredEvents.length > 0) {
    mapCenter = [filteredEvents[0].lat, filteredEvents[0].lon];
  } else if (allScanRisks.length > 0) {
    mapCenter = [allScanRisks[0].lat, allScanRisks[0].lon];
  }
  
  currentMap = L.map(mapContainer).setView(mapCenter, 6);
  
  // Add basemap
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap contributors',
    maxZoom: 19
  }).addTo(currentMap);
  
  // Add project location pins
  const projectIcon = L.divIcon({
    html: `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 20 20">
      <polygon points="10,1 19,10 10,19 1,10" fill="#2563eb" stroke="#1e40af" stroke-width="2"/>
      <circle cx="10" cy="10" r="3" fill="white"/>
    </svg>`,
    className: '',
    iconSize: [18, 18],
    iconAnchor: [9, 9],
    popupAnchor: [0, -12]
  });

  const projectLayer = L.markerClusterGroup({
    maxClusterRadius: 20,
    spiderfyOnMaxZoom: true,
    showCoverageOnHover: false,
    disableClusteringAtZoom: 13,
    iconCreateFunction: function(cluster) {
      return L.divIcon({
        html: '<div style="background:#2563eb;color:#fff;border-radius:50%;width:28px;height:28px;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;border:2px solid #1e40af;">' + cluster.getChildCount() + '</div>',
        className: '',
        iconSize: [28, 28],
        iconAnchor: [14, 14]
      });
    }
  });
  projectLayer.addTo(currentMap);
  projects.forEach(project => {
    const marker = L.marker([project.lat, project.lon], { icon: projectIcon });
    const labelName = project.project_name || `Project ${project.proj_id}`;
    const displayTitle = `${labelName} (${project.proj_id})`;
    marker.bindTooltip(displayTitle, { direction: 'top', offset: [0, -22] });
    marker.bindPopup(`
      <div style="font-size: 13px; line-height: 1.6; min-width: 180px;">
        <strong>${labelName}</strong><br>
        <em style="color:#777; font-size:11px;">PCODE: ${project.proj_id}</em><br>
        <span style="color:#888; font-size:12px;">Location: ${project.name || '\u2014'}</span><br>
      </div>
    `);
    marker.addTo(projectLayer);
  });

  const riskSeverityColors = { high: '#dc2626', medium: '#f87171', low: '#fca5a5' };
  const riskLayer = L.markerClusterGroup({
    maxClusterRadius: 22,
    spiderfyOnMaxZoom: true,
    showCoverageOnHover: false,
    disableClusteringAtZoom: 13,
    iconCreateFunction: function(cluster) {
      return L.divIcon({
        html: '<div style="background:#dc2626;color:#fff;border-radius:50%;width:30px;height:30px;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;border:2px solid #991b1b;">' + cluster.getChildCount() + '</div>',
        className: '',
        iconSize: [30, 30],
        iconAnchor: [15, 15]
      });
    }
  });
  riskLayer.addTo(currentMap);

  allScanRisks.forEach(risk => {
    const severity = String(risk.severity || '').trim().toLowerCase();
    const color = riskSeverityColors[severity] || '#dc2626';
    const marker = L.circleMarker([risk.lat, risk.lon], {
      radius: 8,
      fillColor: color,
      color: '#ffffff',
      weight: 1.6,
      opacity: 0.98,
      fillOpacity: 0.88
    });
    marker.bindPopup(
      '<div style="font-size:12px;line-height:1.6;max-width:340px;">' +
      '<strong style="color:' + color + ';">' + (risk.title || 'Risk Scan Finding') + '</strong><br>' +
      '<span style="color:#555;">Severity: ' + (risk.severity || 'n/a') + '</span><br>' +
      '<span style="color:#444;">' + (risk.summary || '') + '</span>' +
      '</div>',
      { maxHeight: 280, autoPan: true }
    );
    marker.addTo(riskLayer);
  });

  // Group events by type into toggleable LayerGroups
  const eventLayers = {};
  filteredEvents.forEach(event => {
    const evType = getAcledEventKey(event);
    if (!eventLayers[evType]) {
      eventLayers[evType] = L.layerGroup().addTo(currentMap);
    }
    const color = eventColorByKey[evType] || getEventColor(event.event_type, event.sub_event_type);
    const marker = L.circleMarker([event.lat, event.lon], {
      radius: 6.5,
      fillColor: color,
      color: '#ffffff',
      weight: 1.4,
      opacity: 0.95,
      fillOpacity: 0.82
    });
    const noteSnippet = event.notes ? event.notes.substring(0, 200) + (event.notes.length > 200 ? '\u2026' : '') : '';
    marker.bindPopup(`
      <div style="font-size: 12px; line-height: 1.6; max-width: 250px;">
        <strong style="color: ${color};">${event.sub_event_type || event.event_type}</strong><br>
        <strong>Type:</strong> ${event.event_type}<br>
        <strong>Date:</strong> ${event.date} &nbsp; <strong>Location:</strong> ${event.location}
        ${noteSnippet ? `<br><span style="color:#555;">${noteSnippet}</span>` : ''}
      </div>
    `);
    marker.addTo(eventLayers[evType]);
  });
  
  // Build legend panel
  buildMapLegend(projectLayer, riskLayer, eventLayers, projects.length, allScanRisks.length, filteredEvents.length, selectedWeeksBack, allEvents, mapCenter, eventColorByKey);

  // Update counters
  document.getElementById('projectCount').textContent = projects.length;
  document.getElementById('eventCount').textContent = filteredEvents.length;
  const riskScanCountEl = document.getElementById('riskScanCount');
  if (riskScanCountEl) riskScanCountEl.textContent = allScanRisks.length;
  document.getElementById('mapCountryName').textContent = country;

  // Invalidate map size and fit bounds after a brief delay to ensure rendering
  setTimeout(() => {
    if (currentMap) {
      currentMap.invalidateSize();

      // Fit bounds if markers exist
      if (projects.length > 0 || filteredEvents.length > 0 || allScanRisks.length > 0) {
        const allMarkers = [];
        projects.forEach(p => allMarkers.push([p.lat, p.lon]));
        filteredEvents.forEach(e => allMarkers.push([e.lat, e.lon]));
        allScanRisks.forEach(r => allMarkers.push([r.lat, r.lon]));

        if (allMarkers.length > 0) {
          const group = new L.featureGroup(
            allMarkers.map(coords => L.marker(coords))
          );
          currentMap.fitBounds(group.getBounds(), { padding: [50, 50], maxZoom: 12 });
        }
      }
    }
  }, 100);
}

function buildMapLegend(projectLayer, riskLayer, eventLayers, projectCount, riskCount, eventCount, selectedWeeksBack, allEvents, mapCenter, eventColorByKey) {
  const legendEl = document.getElementById('mapLegend');
  if (!legendEl) return;

  legendEl.innerHTML = '<div style="font-size:12px; font-weight:700; text-transform:uppercase; color:#6b7280; letter-spacing:.5px; margin-bottom:10px;">Map Legend</div>';

  // Projects toggle row
  const projRow = document.createElement('label');
  projRow.style.cssText = 'display:flex; align-items:center; gap:7px; padding:5px 0 8px; cursor:pointer; border-bottom:1px solid #e5e7eb; margin-bottom:8px;';
  projRow.innerHTML = `
    <input type="checkbox" checked style="width:14px;height:14px;accent-color:#2563eb;flex-shrink:0;">
    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 20 20" style="flex-shrink:0">
      <polygon points="10,1 19,10 10,19 1,10" fill="#2563eb" stroke="#1e40af" stroke-width="2"/>
      <circle cx="10" cy="10" r="3" fill="white"/>
    </svg>
    <span style="font-size:13px; font-weight:600; color:#1e40af; flex:1;">Projects</span>
    <span style="font-size:11px; color:#9ca3af;">${projectCount}</span>
  `;
  const projCb = projRow.querySelector('input');
  projCb.addEventListener('change', () => {
    if (projCb.checked) projectLayer.addTo(currentMap);
    else projectLayer.remove();
  });
  legendEl.appendChild(projRow);

  const riskRow = document.createElement('label');
  riskRow.style.cssText = 'display:flex; align-items:center; gap:7px; padding:5px 0 8px; cursor:pointer; border-bottom:1px solid #e5e7eb; margin-bottom:8px;';
  riskRow.innerHTML = `
    <input type="checkbox" checked style="width:14px;height:14px;accent-color:#dc2626;flex-shrink:0;">
    <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 20 20" style="flex-shrink:0">
      <polygon points="10,1 19,10 10,19 1,10" fill="#dc2626" stroke="#7f1d1d" stroke-width="2"/>
    </svg>
    <span style="font-size:13px; font-weight:600; color:#991b1b; flex:1;">Risk Scan</span>
    <span style="font-size:11px; color:#9ca3af;">${riskCount}</span>
  `;
  const riskCb = riskRow.querySelector('input');
  riskCb.addEventListener('change', () => {
    if (riskCb.checked) riskLayer.addTo(currentMap);
    else riskLayer.remove();
  });
  legendEl.appendChild(riskRow);

  const eventWindowWrap = document.createElement('div');
  eventWindowWrap.style.cssText = 'padding:8px 0 10px; border-bottom:1px solid #e5e7eb; margin-bottom:8px;';
  eventWindowWrap.innerHTML =
    '<div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:6px;">' +
      '<span style="font-size:13px; font-weight:600; color:#374151;">ACLED Event Window</span>' +
      '<span id="acledWeeksBackValue" style="font-size:11px; color:#6b7280;">' + formatWeekWindowLabel(selectedWeeksBack) + '</span>' +
    '</div>' +
    '<input id="acledWeeksBackSlider" type="range" min="1" max="13" step="1" value="' + selectedWeeksBack + '" style="width:100%; accent-color:#374151; cursor:pointer;">' +
    '<div id="acledEventCount" style="font-size:11px; color:#9ca3af; margin-top:4px;">Events shown: ' + eventCount + '</div>';
  legendEl.appendChild(eventWindowWrap);

  const acledSlider = eventWindowWrap.querySelector('#acledWeeksBackSlider');
  const acledValue = eventWindowWrap.querySelector('#acledWeeksBackValue');
  const acledCount = eventWindowWrap.querySelector('#acledEventCount');
  acledSlider.addEventListener('input', () => {
    const weeksBack = Number(acledSlider.value);
    acledValue.textContent = formatWeekWindowLabel(weeksBack);

    Object.values(eventLayers).forEach(layer => layer.remove());

    const refreshedEvents = filterEventsByWeeks(allEvents, weeksBack);
    const refreshedLayers = {};
    refreshedEvents.forEach(event => {
      const evType = getAcledEventKey(event);
      if (!refreshedLayers[evType]) {
        refreshedLayers[evType] = L.layerGroup().addTo(currentMap);
      }
      const color = eventColorByKey[evType] || getEventColor(event.event_type, event.sub_event_type);
      const marker = L.circleMarker([event.lat, event.lon], {
        radius: 6.5,
        fillColor: color,
        color: '#ffffff',
        weight: 1.4,
        opacity: 0.95,
        fillOpacity: 0.82
      });
      const noteSnippet = event.notes ? event.notes.substring(0, 200) + (event.notes.length > 200 ? '\u2026' : '') : '';
      marker.bindPopup(
        '<div style="font-size: 12px; line-height: 1.6; max-width: 250px;">' +
        '<strong style="color: ' + color + ';">' + (event.sub_event_type || event.event_type) + '</strong><br>' +
        '<strong>Type:</strong> ' + (event.event_type || '') + '<br>' +
        '<strong>Date:</strong> ' + (event.date || '') + ' &nbsp; <strong>Location:</strong> ' + (event.location || '') +
        (noteSnippet ? '<br><span style="color:#555;">' + noteSnippet + '</span>' : '') +
        '</div>'
      );
      marker.addTo(refreshedLayers[evType]);
    });

    buildMapLegend(projectLayer, riskLayer, refreshedLayers, projectCount, riskCount, refreshedEvents.length, weeksBack, allEvents, mapCenter, eventColorByKey);
    document.getElementById('eventCount').textContent = refreshedEvents.length;
  });

  // Events section heading
  if (Object.keys(eventLayers).length > 0) {
    const evHdr = document.createElement('div');
    evHdr.style.cssText = 'font-size:11px; font-weight:700; text-transform:uppercase; color:#6b7280; letter-spacing:.5px; margin-bottom:6px;';
    evHdr.textContent = 'Conflict Events';
    legendEl.appendChild(evHdr);
  }

  // Sort event types by count descending, add toggle row for each
  Object.entries(eventLayers)
    .sort(([, a], [, b]) => b.getLayers().length - a.getLayers().length)
    .forEach(([evType, layer]) => {
      const count = layer.getLayers().length;
      const firstMarker = layer.getLayers()[0];
      const color = firstMarker ? firstMarker.options.fillColor : '#6b7280';
      const row = document.createElement('label');
      row.style.cssText = 'display:flex; align-items:center; gap:7px; padding:4px 0; cursor:pointer;';
      row.innerHTML = `
        <input type="checkbox" checked style="width:13px;height:13px;accent-color:${color};flex-shrink:0;">
        <span style="display:inline-block;width:11px;height:11px;border-radius:50%;background:${color};flex-shrink:0;"></span>
        <span style="font-size:12px; color:#374151; flex:1; line-height:1.3;">${evType}</span>
        <span style="font-size:11px; color:#9ca3af;">${count}</span>
      `;
      const cb = row.querySelector('input');
      cb.addEventListener('change', () => {
        if (cb.checked) layer.addTo(currentMap);
        else layer.remove();
      });
      legendEl.appendChild(row);
    });
}