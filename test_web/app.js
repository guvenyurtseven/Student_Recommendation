const els = {
  programSelect: document.querySelector("#programSelect"),
  showIsolated: document.querySelector("#showIsolated"),
  showEdgeLabels: document.querySelector("#showEdgeLabels"),
  nodeCount: document.querySelector("#nodeCount"),
  edgeCount: document.querySelector("#edgeCount"),
  chainCount: document.querySelector("#chainCount"),
  isolatedCount: document.querySelector("#isolatedCount"),
  programName: document.querySelector("#programName"),
  programSource: document.querySelector("#programSource"),
  legend: document.querySelector("#legend"),
  graphScroller: document.querySelector("#graphScroller"),
  graphBoard: document.querySelector("#graphBoard"),
  edgeLayer: document.querySelector("#edgeLayer"),
  semesterGrid: document.querySelector("#semesterGrid"),
  detailsContent: document.querySelector("#detailsContent"),
};

let graphData = null;
let selectedProgram = null;
let selectedNodeId = null;
let resizeTimer = null;

init();

async function init() {
  try {
    const response = await fetch("graph-data.json", { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`graph-data.json could not be loaded (${response.status})`);
    }
    graphData = await response.json();
  } catch (error) {
    renderFatalError(error);
    return;
  }

  const programs = Object.values(graphData.programs).sort((left, right) =>
    left.abbr.localeCompare(right.abbr),
  );

  els.programSelect.innerHTML = programs
    .map((program) => `<option value="${escapeHtml(program.abbr)}">${escapeHtml(program.abbr)} - ${escapeHtml(program.name_en)}</option>`)
    .join("");

  const remembered = localStorage.getItem("metu-validator-program");
  const initialProgram = graphData.programs[remembered] ? remembered : graphData.programs.CENG ? "CENG" : programs[0]?.abbr;
  els.programSelect.value = initialProgram;

  els.programSelect.addEventListener("change", () => {
    localStorage.setItem("metu-validator-program", els.programSelect.value);
    renderProgram(els.programSelect.value);
  });

  els.showIsolated.addEventListener("change", () => renderProgram(els.programSelect.value));
  els.showEdgeLabels.addEventListener("change", () => drawEdges());
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(drawEdges, 90);
  });

  renderProgram(initialProgram);
}

function renderProgram(abbr) {
  selectedProgram = graphData.programs[abbr];
  selectedNodeId = null;
  const visibleNodes = getVisibleNodes(selectedProgram);
  const visibleNodeIds = new Set(visibleNodes.map((node) => node.id));
  const visibleEdges = getVisibleEdges(selectedProgram, visibleNodeIds);
  const connectedComponents = getConnectedComponents(selectedProgram);
  const isolatedCount = selectedProgram.nodes.filter((node) => node.is_isolated).length;

  els.nodeCount.textContent = selectedProgram.node_count;
  els.edgeCount.textContent = selectedProgram.edge_count;
  els.chainCount.textContent = connectedComponents.length;
  els.isolatedCount.textContent = isolatedCount;
  els.programName.textContent = `${selectedProgram.abbr} - ${selectedProgram.name_en}`;
  els.programSource.textContent = selectedProgram.source_url;

  renderLegend(connectedComponents);
  renderSemesters(selectedProgram, visibleNodeIds, visibleEdges);
  renderDetails(null);
  requestAnimationFrame(drawEdges);
}

function renderLegend(components) {
  if (!components.length) {
    els.legend.innerHTML = `<span class="subtle">Bagli zincir yok</span>`;
    return;
  }

  els.legend.innerHTML = components
    .map(
      (component, index) => `
        <span class="legend-item" title="${component.nodeCount} ders, ${component.edgeCount} bag">
          <span class="legend-dot" style="--legend-color: ${component.color}"></span>
          <span>Z${index + 1}: ${component.nodeCount}/${component.edgeCount}</span>
        </span>
      `,
    )
    .join("");
}

function renderSemesters(program, visibleNodeIds, visibleEdges) {
  const nodesById = mapById(program.nodes);
  els.semesterGrid.innerHTML = "";

  program.semesters.forEach((semester) => {
    const visibleSemesterNodes = semester.nodes
      .map((nodeId) => nodesById.get(nodeId))
      .filter((node) => node && visibleNodeIds.has(node.id));

    const column = document.createElement("section");
    column.className = "semester-column";
    column.innerHTML = `
      <header class="semester-header">
        <span class="semester-title">${escapeHtml(formatSemesterTitle(semester))}</span>
        <span class="semester-count">${visibleSemesterNodes.length} ders</span>
      </header>
      <div class="course-stack"></div>
    `;

    const stack = column.querySelector(".course-stack");
    if (!visibleSemesterNodes.length) {
      stack.innerHTML = `<div class="empty-column">Ders yok</div>`;
    } else {
      visibleSemesterNodes.forEach((node) => {
        stack.appendChild(createCourseNode(node, visibleEdges));
      });
    }
    els.semesterGrid.appendChild(column);
  });
}

function createCourseNode(node, visibleEdges) {
  const incoming = visibleEdges.filter((edge) => edge.to === node.id).length;
  const outgoing = visibleEdges.filter((edge) => edge.from === node.id).length;
  const button = document.createElement("button");
  button.type = "button";
  button.className = `course-node ${node.is_isolated ? "is-isolated" : "is-connected"}`;
  button.dataset.nodeId = node.id;
  button.style.setProperty("--chain-color", node.color);
  button.innerHTML = `
    <span class="course-code">${escapeHtml(node.course_code)}</span>
    <span class="course-title">${escapeHtml(node.course_title || "Untitled course")}</span>
    <span class="course-meta">
      <span>${incoming} pre</span>
      <span>${outgoing} next</span>
    </span>
  `;
  button.addEventListener("click", () => selectNode(node.id));
  return button;
}

function drawEdges() {
  if (!selectedProgram) {
    return;
  }

  const nodeElements = new Map(
    [...els.semesterGrid.querySelectorAll(".course-node")].map((element) => [element.dataset.nodeId, element]),
  );
  const visibleNodeIds = new Set(nodeElements.keys());
  const edges = getVisibleEdges(selectedProgram, visibleNodeIds);
  const boardRect = els.graphBoard.getBoundingClientRect();
  const width = Math.max(els.graphBoard.scrollWidth, els.graphScroller.clientWidth);
  const height = Math.max(els.graphBoard.scrollHeight, els.graphScroller.clientHeight);

  els.edgeLayer.setAttribute("width", width);
  els.edgeLayer.setAttribute("height", height);
  els.edgeLayer.setAttribute("viewBox", `0 0 ${width} ${height}`);
  els.edgeLayer.style.width = `${width}px`;
  els.edgeLayer.style.height = `${height}px`;
  els.edgeLayer.innerHTML = "";

  const defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");
  els.edgeLayer.appendChild(defs);
  const markerByColor = new Map();

  edges.forEach((edge, index) => {
    const fromEl = nodeElements.get(edge.from);
    const toEl = nodeElements.get(edge.to);
    if (!fromEl || !toEl) {
      return;
    }

    const start = getAnchorPoint(fromEl, toEl, boardRect, "start");
    const end = getAnchorPoint(toEl, fromEl, boardRect, "end");
    const forward = end.x >= start.x;
    const distance = Math.abs(end.x - start.x);
    const curve = Math.max(70, Math.min(190, distance * 0.46));
    const direction = forward ? 1 : -1;
    const d = [
      `M ${start.x.toFixed(1)} ${start.y.toFixed(1)}`,
      `C ${(start.x + curve * direction).toFixed(1)} ${start.y.toFixed(1)}`,
      `${(end.x - curve * direction).toFixed(1)} ${end.y.toFixed(1)}`,
      `${end.x.toFixed(1)} ${end.y.toFixed(1)}`,
    ].join(" ");

    const markerId = getMarkerForColor(defs, markerByColor, edge.color);
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", d);
    path.setAttribute("class", getEdgeClass(edge));
    path.setAttribute("style", `--edge-color: ${edge.color}`);
    path.setAttribute("marker-end", `url(#${markerId})`);
    path.dataset.from = edge.from;
    path.dataset.to = edge.to;
    els.edgeLayer.appendChild(path);

    if (els.showEdgeLabels.checked && edge.min_grade) {
      const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
      label.setAttribute("x", ((start.x + end.x) / 2).toFixed(1));
      label.setAttribute("y", ((start.y + end.y) / 2 - 7 - (index % 3) * 4).toFixed(1));
      label.setAttribute("class", "edge-label");
      label.setAttribute("text-anchor", "middle");
      label.textContent = edge.min_grade;
      els.edgeLayer.appendChild(label);
    }
  });

  applySelectionVisuals();
}

function getAnchorPoint(element, otherElement, boardRect, role) {
  const rect = element.getBoundingClientRect();
  const otherRect = otherElement.getBoundingClientRect();
  const centerY = rect.top - boardRect.top + rect.height / 2;
  const ownCenterX = rect.left - boardRect.left + rect.width / 2;
  const otherCenterX = otherRect.left - boardRect.left + otherRect.width / 2;

  if (role === "start") {
    return {
      x: otherCenterX >= ownCenterX ? rect.right - boardRect.left : rect.left - boardRect.left,
      y: centerY,
    };
  }

  return {
    x: otherCenterX <= ownCenterX ? rect.left - boardRect.left : rect.right - boardRect.left,
    y: centerY,
  };
}

function getMarkerForColor(defs, markerByColor, color) {
  if (markerByColor.has(color)) {
    return markerByColor.get(color);
  }

  const id = `arrow-${markerByColor.size + 1}`;
  const marker = document.createElementNS("http://www.w3.org/2000/svg", "marker");
  marker.setAttribute("id", id);
  marker.setAttribute("markerWidth", "10");
  marker.setAttribute("markerHeight", "10");
  marker.setAttribute("refX", "8");
  marker.setAttribute("refY", "3");
  marker.setAttribute("orient", "auto");
  marker.setAttribute("markerUnits", "strokeWidth");

  const point = document.createElementNS("http://www.w3.org/2000/svg", "path");
  point.setAttribute("d", "M 0 0 L 8 3 L 0 6 z");
  point.setAttribute("fill", color);
  marker.appendChild(point);
  defs.appendChild(marker);
  markerByColor.set(color, id);
  return id;
}

function selectNode(nodeId) {
  selectedNodeId = selectedNodeId === nodeId ? null : nodeId;
  renderDetails(selectedNodeId);
  applySelectionVisuals();
}

function applySelectionVisuals() {
  const nodeButtons = [...els.semesterGrid.querySelectorAll(".course-node")];
  const paths = [...els.edgeLayer.querySelectorAll(".edge-path")];
  if (!selectedNodeId) {
    nodeButtons.forEach((button) => button.classList.remove("is-selected", "is-muted"));
    paths.forEach((path) => path.classList.remove("is-highlighted", "is-muted"));
    return;
  }

  const connectedIds = new Set([selectedNodeId]);
  selectedProgram.edges.forEach((edge) => {
    if (edge.from === selectedNodeId) {
      connectedIds.add(edge.to);
    }
    if (edge.to === selectedNodeId) {
      connectedIds.add(edge.from);
    }
  });

  nodeButtons.forEach((button) => {
    const isSelected = button.dataset.nodeId === selectedNodeId;
    button.classList.toggle("is-selected", isSelected);
    button.classList.toggle("is-muted", !connectedIds.has(button.dataset.nodeId));
  });

  paths.forEach((path) => {
    const touchesSelected = path.dataset.from === selectedNodeId || path.dataset.to === selectedNodeId;
    path.classList.toggle("is-highlighted", touchesSelected);
    path.classList.toggle("is-muted", !touchesSelected);
  });
}

function renderDetails(nodeId) {
  if (!selectedProgram) {
    els.detailsContent.innerHTML = "";
    return;
  }

  if (!nodeId) {
    els.detailsContent.innerHTML = `
      <p class="details-kicker">${escapeHtml(selectedProgram.abbr)}</p>
      <h3 class="details-title">${escapeHtml(selectedProgram.name_en)}</h3>
      <p class="details-subtitle">${selectedProgram.node_count} ders, ${selectedProgram.edge_count} prerequisite bagi.</p>
      <div class="detail-list">
        <div class="detail-row"><span>Data</span><strong>${escapeHtml(graphData.generated_from.curricula_dir)}</strong></div>
        <div class="detail-row"><span>Prereq</span><strong>${escapeHtml(graphData.generated_from.prerequisites_dir)}</strong></div>
      </div>
      <p class="subtle">Bir ders secildiginde bu panelde prerequisite ve unlock bilgileri gorunur.</p>
    `;
    return;
  }

  const nodesById = mapById(selectedProgram.nodes);
  const node = nodesById.get(nodeId);
  const incoming = selectedProgram.edges.filter((edge) => edge.to === nodeId);
  const outgoing = selectedProgram.edges.filter((edge) => edge.from === nodeId);
  els.detailsContent.innerHTML = `
    <p class="details-kicker">${escapeHtml(formatSemesterLabel(node))}</p>
    <h3 class="details-title">${escapeHtml(node.course_code)}</h3>
    <p class="details-subtitle">${escapeHtml(node.course_title || "Untitled course")}</p>
    <div class="detail-list">
      <div class="detail-row"><span>Tip</span><strong>${escapeHtml(node.requirement_type || "-")}</strong></div>
      <div class="detail-row"><span>METU/ECTS</span><strong>${escapeHtml(`${node.metu_credit || "-"} / ${node.ects || "-"}`)}</strong></div>
      <div class="detail-row"><span>Zincir</span><strong>${node.is_isolated ? "Baglantisiz" : `#${node.component_id}`}</strong></div>
    </div>
    ${renderEdgeList("Bagli oldugu dersler", incoming, "from", nodesById)}
    ${renderEdgeList("Bagladigi dersler", outgoing, "to", nodesById)}
  `;
}

function renderEdgeList(title, edges, peerKey, nodesById) {
  if (!edges.length) {
    return `
      <div class="edge-group">
        <h3>${escapeHtml(title)}</h3>
        <p class="subtle">Kayit yok.</p>
      </div>
    `;
  }

  const items = edges
    .map((edge) => {
      const peer = nodesById.get(edge[peerKey]);
      const minGrade = edge.min_grade ? `, min ${edge.min_grade}` : "";
      return `
        <li style="--chain-color: ${edge.color}">
          ${escapeHtml(peer?.course_code || edge[`${peerKey}_course_code`] || edge[peerKey])}${escapeHtml(minGrade)}
        </li>
      `;
    })
    .join("");

  return `
    <div class="edge-group">
      <h3>${escapeHtml(title)}</h3>
      <ul class="edge-list">${items}</ul>
    </div>
  `;
}

function getVisibleNodes(program) {
  if (els.showIsolated.checked) {
    return program.nodes;
  }
  return program.nodes.filter((node) => !node.is_isolated);
}

function getVisibleEdges(program, visibleNodeIds) {
  return program.edges.filter((edge) => visibleNodeIds.has(edge.from) && visibleNodeIds.has(edge.to));
}

function getConnectedComponents(program) {
  const nodesByComponent = new Map();
  const edgeCountByComponent = new Map();

  program.nodes
    .filter((node) => !node.is_isolated)
    .forEach((node) => {
      if (!nodesByComponent.has(node.component_id)) {
        nodesByComponent.set(node.component_id, { color: node.color, nodeCount: 0, edgeCount: 0 });
      }
      nodesByComponent.get(node.component_id).nodeCount += 1;
    });

  program.edges.forEach((edge) => {
    edgeCountByComponent.set(edge.component_id, (edgeCountByComponent.get(edge.component_id) || 0) + 1);
  });

  nodesByComponent.forEach((component, componentId) => {
    component.edgeCount = edgeCountByComponent.get(componentId) || 0;
  });

  return [...nodesByComponent.values()].sort((left, right) => right.nodeCount - left.nodeCount || right.edgeCount - left.edgeCount);
}

function getEdgeClass(edge) {
  const selectedClass =
    selectedNodeId && (edge.from === selectedNodeId || edge.to === selectedNodeId)
      ? " is-highlighted"
      : selectedNodeId
        ? " is-muted"
        : "";
  return `edge-path${selectedClass}`;
}

function formatSemesterTitle(semester) {
  if (semester.semester_index >= 99) {
    return "Unplaced";
  }
  return `${semester.semester_index}. Semester`;
}

function formatSemesterLabel(node) {
  if (!node || node.semester_index >= 99) {
    return "Unplaced";
  }
  return `${node.semester_index}. Semester`;
}

function mapById(nodes) {
  return new Map(nodes.map((node) => [node.id, node]));
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function renderFatalError(error) {
  els.programName.textContent = "graph-data.json yuklenemedi";
  els.programSource.textContent = "";
  els.detailsContent.innerHTML = `<div class="error">${escapeHtml(error.message)}</div>`;
}
