const uploadBtn = document.getElementById("uploadBtn");
const fileInput = document.getElementById("file");
const status = document.getElementById("status");
const resultsDiv = document.getElementById("results");

const BACKEND_URL = "http://127.0.0.1:8000/upload";

// Display selected file name
fileInput.addEventListener("change", () => {
  if (fileInput.files.length > 0) {
    status.textContent = `Selected file: ${fileInput.files[0].name}`;
  } else {
    status.textContent = "";
  }
});

uploadBtn.addEventListener("click", async () => {
  resultsDiv.innerHTML = "";
  if (!fileInput.files[0]) {
    status.textContent = "Please select a file first.";
    return;
  }

  const file = fileInput.files[0];
  const form = new FormData();
  form.append("file", file);

  status.textContent = `Uploading "${file.name}" and matching...`;

  try {
    const res = await fetch(BACKEND_URL, {
      method: "POST",
      body: form
    });

    if (!res.ok) {
      let eText = await res.text();
      try {
        const eJson = JSON.parse(eText);
        status.textContent = "Error: " + (eJson.detail || eJson.message || res.statusText);
      } catch {
        status.textContent = "Error: " + res.statusText;
      }
      return;
    }

    const data = await res.json();
    status.textContent = `File: ${file.name} | Resume words: ${data.resume_summary.words}, chars: ${data.resume_summary.chars}`;
    renderResults(data);

  } catch (err) {
    status.textContent = "Network or server error: " + err.message;
  }
});

function renderResults(data) {
  resultsDiv.innerHTML = "";

  if (!data.top_matches || data.top_matches.length === 0) {
    const msg = document.createElement("div");
    msg.textContent = data.message || "No suitable jobs found";
    msg.style.color = "red";
    msg.style.fontWeight = "bold";
    resultsDiv.appendChild(msg);
    return;
  }

  data.top_matches.forEach((job, idx) => {
    const card = document.createElement("div");
    card.className = "card";
    card.style.border = "1px solid #ccc";
    card.style.padding = "10px";
    card.style.margin = "10px 0";
    card.style.borderRadius = "6px";
    card.style.boxShadow = "0 2px 5px rgba(0,0,0,0.1)";
    
    card.innerHTML = `
      <h3>#${idx+1} ${job.title} @ ${job.company}</h3>
      <p><strong>Location:</strong> ${job.location || "N/A"} • <strong>Mode:</strong> ${job.mode || "N/A"}</p>
      <p><strong>Score:</strong> ${job.score}</p>
      <p>${job.description}</p>
    `;
    resultsDiv.appendChild(card);
  });
}

