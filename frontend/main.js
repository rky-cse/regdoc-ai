console.log("🚀 main.js loaded");

document.getElementById('compareForm').addEventListener('submit', async (e) => {
  e.preventDefault();

  const fileInput1 = document.getElementById('fileV1');
  const fileInput2 = document.getElementById('fileV2');
  if (!fileInput1.files.length || !fileInput2.files.length) {
    return alert('Please select both files.');
  }

  const resultsContainer = document.getElementById('results');
  resultsContainer.innerHTML = '<p>Analyzing changes…</p>';

  const formData = new FormData();
  formData.append('file_v1', fileInput1.files[0]);
  formData.append('file_v2', fileInput2.files[0]);

  const response = await fetch('http://localhost:8000/api/analyze', {
    method: 'POST',
    body: formData
  });
  if (!response.ok) {
    resultsContainer.innerHTML = `<p class="error">Error: ${response.statusText}</p>`;
    return;
  }

  // Clear the "Analyzing…" message
  resultsContainer.innerHTML = '';

  const reader  = response.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';

  // Helper: find and pull out all complete {...} JSON objects
  function extractJsonObjects(str) {
    const objs = [];
    let depth = 0, start = -1;
    for (let i = 0; i < str.length; i++) {
      const ch = str[i];
      if (ch === '{') {
        if (depth === 0) start = i;
        depth++;
      } else if (ch === '}') {
        depth--;
        if (depth === 0 && start !== -1) {
          objs.push(str.slice(start, i + 1));
          start = -1;
        }
      }
    }
    if (objs.length) {
      const last = objs[objs.length - 1];
      const lastEnd = str.lastIndexOf(last) + last.length;
      return { objs, remainder: str.slice(lastEnd) };
    }
    return { objs: [], remainder: str };
  }

  // Skip wrapper text like '{"changes":[', if present
  function stripWrapper(str) {
    return str.replace(/^[\s\S]*?"changes"\s*:\s*\[\s*/, '');
  }

  let stripped = false;
  while (true) {
    const { value, done } = await reader.read();
    if (value) {
      buffer += decoder.decode(value, { stream: true });

      // Strip any leading wrapper once
      if (!stripped && /"changes"\s*:\s*\[/.test(buffer)) {
        buffer = stripWrapper(buffer);
        stripped = true;
      }

      // Extract all complete JSON objects
      const { objs, remainder } = extractJsonObjects(buffer);
      buffer = remainder;

      for (const chunk of objs) {
        safeParseAndRender(chunk, resultsContainer);
      }
    }
    if (done) break;
  }
});

/**
 * Safely JSON.parse a chunk and invoke renderSingleChange.
 */
function safeParseAndRender(chunk, container) {
  try {
    const change = JSON.parse(chunk);
    renderSingleChange(change, container);
  } catch (err) {
    console.error('Failed to parse chunk:', chunk, err);
  }
}

/**
 * Create and append a card for one change object.
 */
function renderSingleChange(chg, container) {
  const card = document.createElement('div');
  // always add base class
  card.classList.add('change-card');
  // add category class only if non-empty
  if (chg.category) {
    card.classList.add(chg.category);
  }

  const heading = document.createElement('h3');
  heading.textContent = chg.change_summary || 'No summary';
  card.appendChild(heading);

  const type = document.createElement('div');
  type.classList.add('type');
  type.textContent = `Type: ${chg.change_type || 'Unknown'}`;
  card.appendChild(type);

  if (chg.potential_impact) {
    const impact = document.createElement('p');
    impact.innerHTML = `<strong>Potential Impact:</strong> ${chg.potential_impact}`;
    card.appendChild(impact);
  }

  if (chg.error) {
    const err = document.createElement('p');
    err.classList.add('error');
    err.textContent = `⚠️ ${chg.error}`;
    card.appendChild(err);
  }

  container.appendChild(card);
}