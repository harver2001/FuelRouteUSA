// Fuel Route Planner - Interactive Frontend Application

let map;
let routeLayer;
let markersLayer;
let stopMarkers = [];

document.addEventListener("DOMContentLoaded", () => {
    initMap();
    initEventListeners();
    // Default load Dallas -> Chicago for instant wow factor
    loadPreset("Dallas, TX", "Chicago, IL");
});

function initMap() {
    // Center map over continental USA
    map = L.map("map", {
        zoomControl: false,
        attributionControl: false
    }).setView([39.8283, -98.5795], 5);

    // Zoom control at bottom right
    L.control.zoom({ position: "bottomright" }).addTo(map);

    // 100% Free Tile Layers with ZERO API key, NO watermarks, and NO localhost blocking
    const esriStreet = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}", {
        maxZoom: 19,
        attribution: "Tiles &copy; Esri &mdash; National Geographic, DeLorme, NAVTEQ"
    });

    const esriTopo = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}", {
        maxZoom: 19,
        attribution: "Tiles &copy; Esri"
    });

    const esriDark = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}", {
        maxZoom: 16,
        attribution: "Tiles &copy; Esri"
    });

    // Default to ESRI Street Map (Crisp, highways, terrain, completely free & unblocked)
    esriStreet.addTo(map);

    // Add layer switcher control on map
    L.control.layers({
        "ESRI Street Map (Default)": esriStreet,
        "ESRI Topographic": esriTopo,
        "ESRI Dark Canvas": esriDark,
    }, null, { position: "topright" }).addTo(map);

    routeLayer = L.geoJSON(null, {
        style: {
            color: "#06b6d4",
            weight: 5,
            opacity: 0.85,
            lineJoin: "round",
            lineCap: "round"
        }
    }).addTo(map);

    markersLayer = L.layerGroup().addTo(map);
}

function initEventListeners() {
    const form = document.getElementById("planner-form");
    const swapBtn = document.getElementById("btn-swap");
    const advToggle = document.getElementById("advanced-toggle");
    const advPanel = document.getElementById("advanced-panel");

    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const start = document.getElementById("input-start").value.trim();
        const finish = document.getElementById("input-finish").value.trim();
        const corridor = document.getElementById("input-corridor").value;
        const mpg = document.getElementById("input-mpg").value;
        const range = document.getElementById("input-range").value;

        if (!start || !finish) {
            showError("Please enter both Start and Finish locations.");
            return;
        }

        await fetchAndRenderRoute(start, finish, { corridor, mpg, range });
    });

    if (swapBtn) {
        swapBtn.addEventListener("click", () => {
            const startInput = document.getElementById("input-start");
            const finishInput = document.getElementById("input-finish");
            const temp = startInput.value;
            startInput.value = finishInput.value;
            finishInput.value = temp;
        });
    }

    if (advToggle && advPanel) {
        advToggle.addEventListener("click", () => {
            advPanel.classList.toggle("active");
            const arrow = advToggle.querySelector(".toggle-arrow");
            if (arrow) {
                arrow.textContent = advPanel.classList.contains("active") ? "▲" : "▼";
            }
        });
    }

    // Preset buttons
    document.querySelectorAll(".chip[data-start]").forEach((chip) => {
        chip.addEventListener("click", () => {
            const start = chip.getAttribute("data-start");
            const finish = chip.getAttribute("data-finish");
            loadPreset(start, finish);
        });
    });
}

function loadPreset(start, finish) {
    document.getElementById("input-start").value = start;
    document.getElementById("input-finish").value = finish;
    fetchAndRenderRoute(start, finish);
}

function showLoading(show) {
    const overlay = document.getElementById("map-loading-overlay");
    const btn = document.getElementById("btn-calculate");
    if (show) {
        overlay.classList.add("active");
        btn.disabled = true;
        btn.innerHTML = `<span class="spinner" style="width:16px;height:16px;border-width:2px;display:inline-block;"></span> Calculating...`;
    } else {
        overlay.classList.remove("active");
        btn.disabled = false;
        btn.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg> Plan Route & Fuel Stops`;
    }
}

function showError(message) {
    const errBox = document.getElementById("error-banner");
    if (errBox) {
        errBox.textContent = message;
        errBox.style.display = "block";
        setTimeout(() => {
            errBox.style.display = "none";
        }, 6000);
    } else {
        alert(message);
    }
}

async function fetchAndRenderRoute(start, finish, options = {}) {
    showLoading(true);
    const errBox = document.getElementById("error-banner");
    if (errBox) errBox.style.display = "none";

    try {
        let url = `/api/route/?start=${encodeURIComponent(start)}&finish=${encodeURIComponent(finish)}`;
        if (options.corridor) url += `&corridor_miles=${options.corridor}`;
        if (options.mpg) url += `&mpg=${options.mpg}`;
        if (options.range) url += `&range_miles=${options.range}`;

        const resp = await fetch(url);
        const data = await resp.json();

        if (!resp.ok) {
            throw new Error(data.error || "Failed to calculate optimal route.");
        }

        renderRouteData(data);
    } catch (err) {
        showError(err.message || "An unexpected error occurred while calculating route.");
    } finally {
        showLoading(false);
    }
}

function renderRouteData(data) {
    // 1. Clear previous layers
    routeLayer.clearLayers();
    markersLayer.clearLayers();
    stopMarkers = [];

    // 2. Render Route Polyline
    if (data.geojson) {
        routeLayer.addData(data.geojson);
        map.fitBounds(routeLayer.getBounds(), { padding: [40, 40] });
    }

    // 3. Render Start & Finish Markers
    const startIcon = L.divIcon({
        className: "",
        html: `<div class="custom-pin start-pin" style="width:28px;height:28px;font-size:12px;">A</div>`,
        iconSize: [28, 28],
        iconAnchor: [14, 14],
    });
    const finishIcon = L.divIcon({
        className: "",
        html: `<div class="custom-pin finish-pin" style="width:28px;height:28px;font-size:12px;">B</div>`,
        iconSize: [28, 28],
        iconAnchor: [14, 14],
    });

    L.marker([data.start.latitude, data.start.longitude], { icon: startIcon })
        .bindPopup(`<b>Start</b><br>${data.start.display_name}`)
        .addTo(markersLayer);

    L.marker([data.finish.latitude, data.finish.longitude], { icon: finishIcon })
        .bindPopup(`<b>Destination</b><br>${data.finish.display_name}`)
        .addTo(markersLayer);

    // 4. Render Fuel Stop Markers
    if (data.fuel_stops && data.fuel_stops.length > 0) {
        data.fuel_stops.forEach((stop, index) => {
            const stopIcon = L.divIcon({
                className: "",
                html: `<div class="custom-pin fuel-pin" style="width:30px;height:30px;font-size:13px;font-weight:700;">${index + 1}</div>`,
                iconSize: [30, 30],
                iconAnchor: [15, 15],
            });

            const popupHtml = `
                <div class="popup-title">${stop.name}</div>
                <div class="popup-address">${stop.address}, ${stop.city}, ${stop.state}</div>
                <div class="popup-stat-grid">
                    <div>Price: <span class="popup-stat-val">$${stop.retail_price.toFixed(3)}/gal</span></div>
                    <div>Pumped: <span class="popup-stat-val">${stop.gallons_pumped} gal</span></div>
                    <div>Cost: <span class="popup-stat-val">$${stop.fuel_cost_usd.toFixed(2)}</span></div>
                    <div>Mile Marker: <span class="popup-stat-val">${stop.mile_marker} mi</span></div>
                </div>
                <div style="font-size:0.7rem;color:#94a3b8;margin-top:6px;font-style:italic;">${stop.step_reason || ""}</div>
            `;

            const marker = L.marker([stop.latitude, stop.longitude], { icon: stopIcon })
                .bindPopup(popupHtml)
                .addTo(markersLayer);

            stopMarkers.push(marker);
        });
    }

    // 5. Update Metrics Cards
    const summary = data.route_summary;
    document.getElementById("metric-distance").textContent = `${summary.total_distance_miles.toLocaleString()} mi`;
    document.getElementById("metric-duration").textContent = summary.total_duration_formatted;
    document.getElementById("metric-cost").textContent = `$${summary.total_fuel_cost_usd.toFixed(2)}`;
    document.getElementById("metric-gallons").textContent = `${summary.total_gallons_consumed.toFixed(1)} gal`;
    document.getElementById("metric-stops").textContent = `${summary.number_of_fuel_stops}`;
    document.getElementById("metric-avg-price").textContent = `$${summary.average_fuel_price_usd.toFixed(3)}/gal`;

    // 6. Populate Itinerary List
    const itineraryList = document.getElementById("itinerary-list");
    itineraryList.innerHTML = "";

    if (!data.fuel_stops || data.fuel_stops.length === 0) {
        itineraryList.innerHTML = `<div style="color:#64748b;font-size:0.85rem;text-align:center;padding:1.5rem;">No fuel stops needed (destination reachable within initial range).</div>`;
        return;
    }

    data.fuel_stops.forEach((stop, idx) => {
        const item = document.createElement("div");
        item.className = "stop-item";
        item.id = `stop-item-${idx}`;
        item.innerHTML = `
            <div class="stop-top">
                <div class="stop-badge">
                    <span class="stop-number">${idx + 1}</span>
                    <span class="stop-name" title="${stop.name}">${stop.name}</span>
                </div>
                <span class="stop-price">$${stop.retail_price.toFixed(3)}/gal</span>
            </div>
            <div class="stop-details">
                <span>${stop.city}, ${stop.state}</span>
                <span>Mile: <b>${stop.mile_marker}</b></span>
                <span><b>${stop.gallons_pumped} gal</b> ($${stop.fuel_cost_usd.toFixed(2)})</span>
            </div>
            <div class="stop-reason">${stop.step_reason || "Optimal cost stop"}</div>
        `;

        item.addEventListener("click", () => {
            // Remove active from all
            document.querySelectorAll(".stop-item").forEach(el => el.classList.remove("active"));
            item.classList.add("active");

            // Pan to marker and open popup
            const marker = stopMarkers[idx];
            if (marker) {
                map.flyTo([stop.latitude, stop.longitude], 12, { duration: 1.2 });
                marker.openPopup();
            }
        });

        itineraryList.appendChild(item);
    });
}
