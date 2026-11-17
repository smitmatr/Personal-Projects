let chart;
let selectedSpecies = "sheep";

function buildChart(series, gmuLabel = "", huntCode = "") {
  const ctx = document.getElementById("trendChart").getContext("2d");
  if (chart) {
    chart.destroy();
  }

  const titleText = huntCode
    ? `Unit ${gmuLabel || "Unknown"} — ${huntCode} Trend Data`
    : `Unit ${gmuLabel || "Unknown"} Trend Data`;

  chart = new Chart(ctx, {
    data: {
      labels: series.years,
      datasets: [
        {
          type: "line",
          label: "Permits",
          data: series.permits,
          borderColor: "#1f77b4",
          backgroundColor: "#1f77b4",
          tension: 0.2,
          yAxisID: "y",
        },
        {
          type: "line",
          label: "Hunters",
          data: series.hunters,
          borderColor: "#2ca02c",
          backgroundColor: "#2ca02c",
          tension: 0.2,
          yAxisID: "y",
        },
        {
          type: "line",
          label: "Total Harvest",
          data: series.total_harvest,
          borderColor: "#d62728",
          backgroundColor: "#d62728",
          tension: 0.2,
          yAxisID: "y",
        },
        {
          type: "line",
          label: "Success %",
          data: series.success_pct,
          borderColor: "#9467bd",
          backgroundColor: "#9467bd",
          borderDash: [6, 4],
          tension: 0.2,
          yAxisID: "y2",
        },
      ],
    },
    options: {
      responsive: true,
      plugins: {
        title: {
          display: true,
          text: titleText,
          font: {
            size: 15,
            weight: "600",
          },
        },
      },
      interaction: {
        mode: "index",
        intersect: false,
      },
      scales: {
        y: {
          position: "left",
          title: {
            display: true,
            text: "Counts (Permits/Hunters/Harvest)",
          },
        },
        y2: {
          position: "right",
          min: 0,
          max: 100,
          grid: {
            drawOnChartArea: false,
          },
          title: {
            display: true,
            text: "Success %",
          },
        },
      },
    },
  });
}

async function loadHunt(code) {
  const status = document.getElementById("statusText");
  status.textContent = `Loading data for ${code}...`;

  const species = selectedSpecies || "sheep";
  const res = await fetch(`/api/hunt/${encodeURIComponent(code)}?species=${encodeURIComponent(species)}`);
  if (!res.ok) {
    status.textContent = "Failed to load hunt data.";
    return;
  }

  const data = await res.json();

  document.getElementById("infoHeading").textContent = `Draw Unit Map & Details for ${data.hunt_code}`;
  document.getElementById("huntLabel").textContent = data.hunt_code;

  const gmuTarget = (data.gmus && data.gmus.length) ? String(data.gmus[0]) : (document.getElementById("gmuSelect").value || "13");
  const mapUrl = getGmuMapUrl(gmuTarget);
  document.getElementById("huntMapFrame").src = mapUrl;

  const resolved = document.getElementById("resolvedUrl");
  resolved.href = mapUrl;
  resolved.textContent = `Open official ADF&G GMU page for ${data.hunt_code}`;

  const selectedGmu = document.getElementById("gmuSelect").value || "Unknown";
  buildChart(data.series, selectedGmu, data.hunt_code);

  status.textContent = `Updated ${data.hunt_code} in GMU ${selectedGmu}.`;
}

function normalizeGmu(gmu) {
  return String(gmu ?? "").trim().replace(/^0+/, "");
}

function getGmuMapUrl(gmu) {
  const normalized = normalizeGmu(gmu);

  if (normalized === "1" || normalized === "8") {
    return `https://www.adfg.alaska.gov/index.cfm?adfg=huntingmaps.gmuinfo&gmu=${normalized}`;
  }

  if (normalized === "14") {
    return "https://www.adfg.alaska.gov/static/hunting/maps/gmumaps/gif/14ab.gif";
  }
  if (normalized === "13") {
    return "https://www.adfg.alaska.gov/static/hunting/maps/gmumaps/gif/13.gif";
  }

  return `https://www.adfg.alaska.gov/static/hunting/maps/gmumaps/gif/${normalized}.gif`;
}

function getDrawMapUrl(code, species = selectedSpecies) {
  const speciesValue = species || "sheep";
  return `https://www.adfg.alaska.gov/index.cfm?adfg=hunting.largehuntmap&sp=${encodeURIComponent(speciesValue)}&hunt=${code.toLowerCase()}`;
}

async function populateHuntsForGmu(gmu) {
  const huntSelect = document.getElementById("huntCode");
  const species = selectedSpecies || "sheep";
  const res = await fetch(`/api/hunts-by-gmu/${encodeURIComponent(gmu)}?species=${encodeURIComponent(species)}`);
  if (!res.ok) {
    return;
  }

  const data = await res.json();
  const hunts = data.hunt_codes || [];
  huntSelect.innerHTML = "";

  if (!hunts.length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "No mapped hunts for this GMU";
    huntSelect.appendChild(option);
    document.getElementById("statusText").textContent = `No mapped draw hunts available for GMU ${gmu}.`;
    return;
  }

  hunts.forEach((code) => {
    const option = document.createElement("option");
    option.value = code;
    option.textContent = code;
    huntSelect.appendChild(option);
  });

  huntSelect.value = hunts[0];
  document.getElementById("statusText").textContent = `Showing ${hunts.length} draw hunt(s) for GMU ${gmu}.`;
  loadHunt(huntSelect.value);
}

async function populateGmusForSpecies(species) {
  const gmuSelect = document.getElementById("gmuSelect");
  const huntSelect = document.getElementById("huntCode");
  const status = document.getElementById("statusText");

  const res = await fetch(`/api/gmus?species=${encodeURIComponent(species)}`);
  if (!res.ok) {
    status.textContent = "Could not load GMUs.";
    return;
  }

  const payload = await res.json();
  const gmus = payload.gmus || [];

  gmuSelect.innerHTML = "";
  huntSelect.innerHTML = "";

  if (!gmus.length) {
    gmuSelect.disabled = true;
    huntSelect.disabled = true;
    const speciesLabel = species.replaceAll("_", " ");
    status.textContent = `${speciesLabel.charAt(0).toUpperCase() + speciesLabel.slice(1)} data is not available yet.`;
    return;
  }

  gmuSelect.disabled = false;
  huntSelect.disabled = false;

  gmus.forEach((gmu) => {
    const option = document.createElement("option");
    option.value = gmu;
    option.textContent = `GMU ${gmu}`;
    gmuSelect.appendChild(option);
  });

  const defaultGmu = gmus.includes("13") ? "13" : gmus[0];
  gmuSelect.value = defaultGmu;
  document.getElementById("gmuLabel").textContent = defaultGmu;
  document.getElementById("gmuMapFrame").src = getGmuMapUrl(defaultGmu);
  await populateHuntsForGmu(defaultGmu);
}

async function populateSpecies() {
  const speciesSelect = document.getElementById("speciesSelect");
  const res = await fetch("/api/species");
  if (!res.ok) {
    return;
  }

  const payload = await res.json();
  const speciesOptions = payload.species || [];
  speciesSelect.innerHTML = "";

  speciesOptions.forEach((item) => {
    const option = document.createElement("option");
    option.value = item.value;
    option.textContent = item.label;
    if (item.value === "sheep") {
      option.selected = true;
    }
    speciesSelect.appendChild(option);
  });

  selectedSpecies = speciesSelect.value || "sheep";
  await populateGmusForSpecies(selectedSpecies);

  speciesSelect.addEventListener("change", async () => {
    selectedSpecies = speciesSelect.value || "sheep";
    await populateGmusForSpecies(selectedSpecies);
  });
}

async function init() {
  const gmuSelect = document.getElementById("gmuSelect");
  const huntSelect = document.getElementById("huntCode");

  gmuSelect.addEventListener("change", async () => {
    const selectedGmu = gmuSelect.value;
    document.getElementById("gmuLabel").textContent = selectedGmu;
    document.getElementById("gmuMapFrame").src = getGmuMapUrl(selectedGmu);
    await populateHuntsForGmu(selectedGmu);
  });

  huntSelect.addEventListener("change", async () => {
    const selectedCode = huntSelect.value;
    if (!selectedCode) {
      return;
    }

    const currentGmu = gmuSelect.value;
    document.getElementById("gmuLabel").textContent = currentGmu;
    document.getElementById("gmuMapFrame").src = getGmuMapUrl(currentGmu);
    await loadHunt(selectedCode);
  });

  await populateSpecies();
}

init();
