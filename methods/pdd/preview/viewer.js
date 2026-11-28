import { seeds, scaleNames, packageURL, resourceURL, validateManifest, prepareVoxels } from "./model.js";
import { Renderer } from "./renderer.js";

const element = id => document.getElementById(id);
const canvas = element("scene");
const status = element("status");
const camera = { azimuth: -1.1, elevation: .65, distance: 85, top: false };
const cache = new Map();
let renderer;
let scale = "coarse";
let requestNumber = 0;
let fine = false;
let busy = false;

function message(text, error = false) {
  status.textContent = text;
  status.classList.toggle("error", error);
}
function draw() {
  renderer?.draw(camera, fine);
}
function view(top) {
  camera.top = top;
  element("orbit").setAttribute("aria-pressed", String(!top));
  element("top").setAttribute("aria-pressed", String(top));
  draw();
}
async function readJSON(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`读取 ${url.pathname} 失败（${response.status}）`);
  return response.json();
}

async function load() {
  const currentRequest = ++requestNumber;
  busy = true;
  fine = false;
  renderer.count = 0;
  draw();
  const seed = seeds[0];
  const requestedScale = scale;
  const root = packageURL(seed, window.location.href);
  document.querySelectorAll("[data-scale]").forEach(button =>
    button.setAttribute("aria-pressed", String(button.dataset.scale === scale)));
  for (const id of ["native", "config", "log", "manifest"]) element(id).removeAttribute("href");
  for (const id of ["sample-id", "shape", "voxel-size", "count", "coverage-note"]) element(id).textContent = "—";
  element("legend").replaceChildren();
  message(`正在读取 ${seed} · ${scaleNames[scale]}…`);
  try {
    const manifest = await readJSON(new URL("manifest.json", root));
    const { states, labels } = validateManifest(manifest);
    const state = states.get(requestedScale);
    const key = `${seed}/${requestedScale}`;
    let prepared = cache.get(key);
    if (!prepared) {
      const data = await readJSON(resourceURL(state.path, root));
      prepared = prepareVoxels(data, labels, manifest.coordinates);
      cache.set(key, prepared);
    }
    if (currentRequest !== requestNumber) return;
    renderer.setData(prepared);
    fine = requestedScale === "fine" && manifest.regions.some(item => item.state_id === "fine" && item.role === "issue");
    element("sample-id").textContent = manifest.sample_id;
    element("shape").textContent = state.native_shape_xyz.join(" × ");
    element("voxel-size").textContent = prepared.size.map(v => Number(v.toFixed(4))).join(" × ");
    element("count").textContent = prepared.count.toLocaleString("zh-CN");
    element("coverage-note").textContent = fine
      ? "灰色为默认切块未生成的 1.6 m 边带，占平面约 6.15%。展示已补偿 Y 方向 8 格偏移。"
      : (requestedScale === "fine"
        ? "域内九块覆盖 100%。V3 从原生子块选取小空列补入，保留原有非空列。"
        : "覆盖完整场景网格。各尺度使用相同的米制坐标。");
    for (const [id, path] of [["native", state.native_path], ["config", state.config_path],
      ["log", state.log_path], ["manifest", "manifest.json"]]) {
      element(id).href = resourceURL(path, root).href;
      element(id).target = "_blank";
      element(id).rel = "noopener";
    }
    const legend = element("legend");
    legend.replaceChildren();
    const names = ["空闲", "建筑", "障碍", "其他", "行人", "杆状物", "道路", "地面", "人行道", "植被", "车辆"];
    for (const [id, label] of labels) {
      if (label.role !== "semantic") continue;
      const line = document.createElement("label");
      const input = document.createElement("input");
      input.type = "checkbox";
      input.checked = renderer.visible[id] > .5;
      input.addEventListener("change", () => { renderer.visible[id] = input.checked ? 1 : 0; draw(); });
      const swatch = document.createElement("span");
      swatch.className = "swatch";
      swatch.style.background = label.color;
      const text = document.createElement("span");
      text.textContent = `${names[id]} ${(prepared.counts.get(id) || 0).toLocaleString("zh-CN")}`;
      line.append(input, swatch, text);
      legend.append(line);
    }
    message(`${scaleNames[requestedScale]} · ${prepared.count.toLocaleString("zh-CN")} 个占据体素`);
    draw();
  } catch (error) {
    if (currentRequest !== requestNumber) return;
    message(`${error.message}。请检查本地服务及样例文件，再切换样例重试。`, true);
  } finally {
    if (currentRequest === requestNumber) busy = false;
  }
}

try {
  renderer = new Renderer(canvas);
  document.querySelectorAll("[data-scale]").forEach(button => {
    button.addEventListener("click", () => { scale = button.dataset.scale; load(); });
  });
  element("orbit").addEventListener("click", () => view(false));
  element("top").addEventListener("click", () => view(true));
  element("reset").addEventListener("click", () => {
    Object.assign(camera, { azimuth: -1.1, elevation: .65, distance: 85 });
    draw();
  });
  new ResizeObserver(draw).observe(canvas);
  let pointer = null;
  canvas.addEventListener("pointerdown", event => {
    if (busy) return;
    pointer = [event.clientX, event.clientY];
    canvas.setPointerCapture(event.pointerId);
    canvas.focus();
  });
  canvas.addEventListener("pointermove", event => {
    if (!pointer) return;
    const dx = event.clientX - pointer[0];
    const dy = event.clientY - pointer[1];
    camera.azimuth -= dx * .008;
    camera.elevation = Math.min(1.5, Math.max(.12, camera.elevation + dy * .008));
    pointer = [event.clientX, event.clientY];
    view(false);
  });
  const release = () => { pointer = null; };
  canvas.addEventListener("pointerup", release);
  canvas.addEventListener("pointercancel", release);
  canvas.addEventListener("wheel", event => {
    event.preventDefault();
    camera.distance = Math.min(180, Math.max(15, camera.distance * Math.exp(event.deltaY * .001)));
    draw();
  }, { passive: false });
  canvas.addEventListener("keydown", event => {
    if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "=", "-", "+", "Home"].includes(event.key)) return;
    event.preventDefault();
    if (event.key === "ArrowLeft") camera.azimuth -= .12;
    if (event.key === "ArrowRight") camera.azimuth += .12;
    if (event.key === "ArrowUp") camera.elevation = Math.min(1.5, camera.elevation + .1);
    if (event.key === "ArrowDown") camera.elevation = Math.max(.12, camera.elevation - .1);
    if (event.key === "=" || event.key === "+") camera.distance = Math.max(15, camera.distance * .9);
    if (event.key === "-") camera.distance = Math.min(180, camera.distance * 1.1);
    if (event.key === "Home") Object.assign(camera, { azimuth: -1.1, elevation: .65, distance: 85 });
    if (event.key.startsWith("Arrow")) view(false);
    else draw();
  });
  canvas.addEventListener("webglcontextlost", event => {
    event.preventDefault();
    message("图形上下文已中断，请刷新页面重新加载。", true);
  });
  load();
} catch (error) {
  message(error.message, true);
}
