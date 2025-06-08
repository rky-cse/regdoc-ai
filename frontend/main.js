// Enhanced file input handling and analysis
console.log("🚀 RegDoc AI Change Analyzer loaded");

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
  initializeFileInputs();
  initializeForm();
});

/**
 * Initialize custom file input behaviors
 */
function initializeFileInputs() {
  const fileInputs = document.querySelectorAll('.file-input__field');
  
  fileInputs.forEach(input => {
    const container = input.closest('.file-input');
    const display = container.querySelector('.file-input__display');
    const textElement = container.querySelector('.file-input__text');
    
    // Handle file selection
    input.addEventListener('change', function(e) {
      const file = e.target.files[0];
      if (file) {
        textElement.textContent = `Selected: ${file.name}`;
        container.classList.add('file-input--selected');
      } else {
        textElement.textContent = 'Choose file...';
        container.classList.remove('file-input--selected');
      }
    });
    
    // Handle click on display area
    display.addEventListener('click', function() {
      input.click();
    });
    
    // Handle drag and drop
    display.addEventListener('dragover', function(e) {
      e.preventDefault();
      e.stopPropagation();
      display.classList.add('file-input--dragover');
    });
    
    display.addEventListener('dragleave', function(e) {
      e.preventDefault();
      e.stopPropagation();
      display.classList.remove('file-input--dragover');
    });
    
    display.addEventListener('drop', function(e) {
      e.preventDefault();
      e.stopPropagation();
      display.classList.remove('file-input--dragover');
      
      const files = e.dataTransfer.files;
      if (files.length > 0 && files[0].type === 'text/plain') {
        input.files = files;
        const event = new Event('change', { bubbles: true });
        input.dispatchEvent(event);
      }
    });
  });
}

/**
 * Initialize form submission handling
 */
function initializeForm() {
  const form = document.getElementById('compareForm');
  const resultsContainer = document.getElementById('results');
  
  form.addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const fileInput1 = document.getElementById('fileV1');
    const fileInput2 = document.getElementById('fileV2');
    
    // Validate file selection
    if (!fileInput1.files.length || !fileInput2.files.length) {
      showNotification('Please select both files before analyzing.', 'error');
      return;
    }
    
    // Validate file types
    const file1 = fileInput1.files[0];
    const file2 = fileInput2.files[0];
    
    if (file1.type !== 'text/plain' || file2.type !== 'text/plain') {
      showNotification('Please select only text (.txt) files.', 'error');
      return;
    }
    
    await analyzeDocuments(file1, file2, resultsContainer);
  });
}

/**
 * Analyze documents and handle streaming response
 */
async function analyzeDocuments(file1, file2, resultsContainer) {
  // Show loading state
  showLoadingState(resultsContainer);
  
  // Prepare form data
  const formData = new FormData();
  formData.append('file_v1', file1);
  formData.append('file_v2', file2);
  
  try {
    const response = await fetch('http://localhost:8000/api/analyze', {
      method: 'POST',
      body: formData
    });
    
    if (!response.ok) {
      throw new Error(`Server error: ${response.status} ${response.statusText}`);
    }
    
    // Clear loading state
    resultsContainer.innerHTML = '';
    
    // Handle streaming response
    await handleStreamingResponse(response, resultsContainer);
    
  } catch (error) {
    console.error('Analysis error:', error);
    showErrorState(resultsContainer, error.message);
  }
}

/**
 * Handle streaming JSON response with proper array handling
 */
async function handleStreamingResponse(response, resultsContainer) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';
  let changeCount = 0;
  let hasSeenWrapper = false;
  let isInsideChangesArray = false;
  
  try {
    while (true) {
      const { value, done } = await reader.read();
      
      if (value) {
        const chunk = decoder.decode(value, { stream: true });
        buffer += chunk;
        
        // Handle the opening wrapper {"changes": [
        if (!hasSeenWrapper && buffer.includes('"changes"')) {
          const wrapperMatch = buffer.match(/\{\s*"changes"\s*:\s*\[/);
          if (wrapperMatch) {
            hasSeenWrapper = true;
            isInsideChangesArray = true;
            // Remove the wrapper from buffer, keep only the content after [
            const wrapperEnd = buffer.indexOf('[', buffer.indexOf('"changes"')) + 1;
            buffer = buffer.substring(wrapperEnd);
          }
        }
        
        // Only process if we're inside the changes array
        if (isInsideChangesArray) {
          const { objects, remainder } = extractChangeObjects(buffer);
          buffer = remainder;
          
          // Render each change object
          objects.forEach(obj => {
            if (safeParseAndRender(obj, resultsContainer)) {
              changeCount++;
            }
          });
        }
      }
      
      if (done) break;
    }
    
    // Show completion message
    if (changeCount === 0) {
      showNoChangesState(resultsContainer);
    } else {
      showCompletionMessage(resultsContainer, changeCount);
    }
    
  } catch (error) {
    console.error('Streaming error:', error);
    showErrorState(resultsContainer, 'Error processing analysis results');
  }
}

/**
 * Extract complete change objects from streaming buffer
 * Handles comma-separated objects within the changes array
 */
function extractChangeObjects(buffer) {
  const objects = [];
  let cleanBuffer = buffer.trim();
  
  // Remove any leading commas or whitespace
  cleanBuffer = cleanBuffer.replace(/^\s*,\s*/, '');
  
  let depth = 0;
  let start = -1;
  let inString = false;
  let escaped = false;
  let i = 0;
  
  while (i < cleanBuffer.length) {
    const char = cleanBuffer[i];
    
    if (escaped) {
      escaped = false;
      i++;
      continue;
    }
    
    if (char === '\\' && inString) {
      escaped = true;
      i++;
      continue;
    }
    
    if (char === '"') {
      inString = !inString;
      i++;
      continue;
    }
    
    if (inString) {
      i++;
      continue;
    }
    
    // Skip whitespace when not in string
    if (/\s/.test(char)) {
      i++;
      continue;
    }
    
    // Check for end of array or object
    if (char === ']' || char === '}') {
      if (char === '}' && depth === 1 && start !== -1) {
        // Complete object found
        const objectStr = cleanBuffer.slice(start, i + 1);
        objects.push(objectStr);
        
        // Move past this object and any trailing comma
        let nextStart = i + 1;
        while (nextStart < cleanBuffer.length && /[\s,]/.test(cleanBuffer[nextStart])) {
          nextStart++;
        }
        
        cleanBuffer = cleanBuffer.slice(nextStart);
        i = 0;
        start = -1;
        depth = 0;
        continue;
      } else if (char === ']') {
        // End of changes array - we're done
        break;
      }
      
      if (depth > 0) depth--;
      i++;
      continue;
    }
    
    if (char === '{') {
      if (depth === 0) {
        start = i;
      }
      depth++;
    } else if (char === ',') {
      // Comma outside of any object - skip it
      if (depth === 0) {
        i++;
        continue;
      }
    }
    
    i++;
  }
  
  // Return remaining buffer after processed objects
  let remainder = cleanBuffer;
  if (objects.length > 0) {
    // Find where the last processed object ends
    const lastObj = objects[objects.length - 1];
    const lastIndex = buffer.lastIndexOf(lastObj);
    if (lastIndex !== -1) {
      remainder = buffer.slice(lastIndex + lastObj.length);
    }
  }
  
  return { objects, remainder };
}

/**
 * Safely parse JSON and render change card
 */
function safeParseAndRender(jsonString, container) {
  try {
    // Clean the JSON string
    const cleanJson = jsonString.trim();
    
    if (!cleanJson || cleanJson === '' || cleanJson === ',') {
      return false;
    }
    
    const change = JSON.parse(cleanJson);
    
    // Validate that this is a proper change object
    if (!change || typeof change !== 'object') {
      return false;
    }
    
    // Must have at least a section, change_type, or change_summary
    if (!change.section && !change.change_type && !change.change_summary) {
      return false;
    }
    
    renderChangeCard(change, container);
    return true;
  } catch (error) {
    console.warn('Failed to parse change object:', jsonString, error);
    return false;
  }
}

/**
 * Render a single change card with proper data handling
 */
function renderChangeCard(change, container) {
  const card = document.createElement('div');
  card.className = 'change-card';
  
  // Determine change category based on change_type
  const changeType = (change.change_type || '').toLowerCase();
  if (changeType.includes('add') || changeType.includes('new')) {
    card.classList.add('added');
  } else if (changeType.includes('delet') || changeType.includes('remov')) {
    card.classList.add('deleted');
  } else if (changeType.includes('edit') || changeType.includes('modif') || changeType.includes('chang')) {
    card.classList.add('modified');
  }
  
  // Section header if available
  if (change.section) {
    const sectionLabel = document.createElement('div');
    sectionLabel.className = 'section-label';
    sectionLabel.textContent = `Section ${change.section}`;
    sectionLabel.style.cssText = `
      font-size: var(--font-size-xs);
      font-weight: 600;
      color: var(--color-text-muted);
      text-transform: uppercase;
      letter-spacing: 0.1em;
      margin-bottom: var(--spacing-sm);
    `;
    card.appendChild(sectionLabel);
  }
  
  // Change summary heading
  const heading = document.createElement('h3');
  heading.textContent = change.change_summary || 'Document change detected';
  card.appendChild(heading);
  
  // Change type badge
  if (change.change_type) {
    const typeBadge = document.createElement('div');
    typeBadge.className = 'type';
    typeBadge.textContent = change.change_type;
    card.appendChild(typeBadge);
  }
  
  // Before/After content if available
  if (change.old || change.new) {
    const changesContainer = document.createElement('div');
    changesContainer.style.cssText = `
      margin: var(--spacing-md) 0;
      padding: var(--spacing-md);
      background-color: var(--color-surface);
      border-radius: var(--radius-md);
      border: 1px solid var(--color-border-light);
    `;
    
    if (change.old) {
      const oldSection = document.createElement('div');
      oldSection.style.marginBottom = 'var(--spacing-sm)';
      oldSection.innerHTML = `
        <div style="font-weight: 600; color: var(--color-danger); font-size: var(--font-size-sm); margin-bottom: var(--spacing-xs);">
          − Before:
        </div>
        <div style="font-family: monospace; font-size: var(--font-size-sm); white-space: pre-wrap; background: rgba(239, 68, 68, 0.1); padding: var(--spacing-sm); border-radius: var(--radius-sm);">
          ${escapeHtml(change.old)}
        </div>
      `;
      changesContainer.appendChild(oldSection);
    }
    
    if (change.new) {
      const newSection = document.createElement('div');
      newSection.innerHTML = `
        <div style="font-weight: 600; color: var(--color-success); font-size: var(--font-size-sm); margin-bottom: var(--spacing-xs);">
          + After:
        </div>
        <div style="font-family: monospace; font-size: var(--font-size-sm); white-space: pre-wrap; background: rgba(16, 185, 129, 0.1); padding: var(--spacing-sm); border-radius: var(--radius-sm);">
          ${escapeHtml(change.new)}
        </div>
      `;
      changesContainer.appendChild(newSection);
    }
    
    card.appendChild(changesContainer);
  }
  
  // Potential impact
  if (change.potential_impact) {
    const impact = document.createElement('p');
    impact.innerHTML = `<strong>Potential Impact:</strong> ${escapeHtml(change.potential_impact)}`;
    card.appendChild(impact);
  }
  
  // Additional details
  if (change.details) {
    const details = document.createElement('p');
    details.innerHTML = `<strong>Details:</strong> ${escapeHtml(change.details)}`;
    card.appendChild(details);
  }
  
  // Error handling
  if (change.error) {
    const error = document.createElement('p');
    error.className = 'error';
    error.textContent = `⚠️ ${change.error}`;
    card.appendChild(error);
  }
  
  container.appendChild(card);
  
  // Animate card appearance
  requestAnimationFrame(() => {
    card.style.opacity = '0';
    card.style.transform = 'translateY(20px)';
    card.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
    
    requestAnimationFrame(() => {
      card.style.opacity = '1';
      card.style.transform = 'translateY(0)';
    });
  });
}

/**
 * Show loading state
 */
function showLoadingState(container) {
  container.innerHTML = `
    <div class="results__loading">
      <div style="display: inline-block; animation: pulse 1.5s ease-in-out infinite;">
        Analyzing documents...
      </div>
    </div>
  `;
  
  // Add pulse animation
  if (!document.querySelector('#pulse-animation')) {
    const style = document.createElement('style');
    style.id = 'pulse-animation';
    style.textContent = `
      @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.5; }
      }
    `;
    document.head.appendChild(style);
  }
}

/**
 * Show error state
 */
function showErrorState(container, message) {
  container.innerHTML = `
    <div class="change-card">
      <h3>Analysis Error</h3>
      <p class="error">❌ ${escapeHtml(message)}</p>
      <p>Please check your files and try again. Ensure both files are valid text documents.</p>
    </div>
  `;
}

/**
 * Show no changes state
 */
function showNoChangesState(container) {
  container.innerHTML = `
    <div class="change-card">
      <h3>No Changes Detected</h3>
      <p>The documents appear to be identical or no significant changes were found.</p>
    </div>
  `;
}

/**
 * Show completion message
 */
function showCompletionMessage(container, changeCount) {
  const message = document.createElement('div');
  message.className = 'change-card';
  message.style.background = 'var(--color-surface)';
  message.style.border = '1px solid var(--color-border)';
  message.style.marginTop = 'var(--spacing-lg)';
  
  message.innerHTML = `
    <h3>Analysis Complete</h3>
    <p>Found and analyzed <strong>${changeCount}</strong> change${changeCount === 1 ? '' : 's'} between the documents.</p>
  `;
  
  container.appendChild(message);
}

/**
 * Show notification (could be enhanced with a toast system)
 */
function showNotification(message, type = 'info') {
  // Simple alert for now - could be enhanced with a proper notification system
  if (type === 'error') {
    alert(`Error: ${message}`);
  } else {
    alert(message);
  }
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}