export const seeds = ["20261015"];
export const scaleNames = { coarse: "粗尺度", medium: "中尺度", fine: "细尺度" };

export function packageURL(seed, base) {
  if (!seeds.includes(String(seed))) throw new Error("样例种子无效");
  return new URL(`../../../examples/pdd/carlasc-v3-${seed}/`, base);
}

export function resourceURL(path, root) {
  if (typeof path !== "string" || !path || path.includes("\\")) throw new Error("样例文件路径无效");
  const result = new URL(path, root);
  if (!result.href.startsWith(root.href)) throw new Error("样例引用超出自身目录");
  return result;
}

export function validateManifest(manifest) {
  if (manifest.schema_version !== "1.0" || manifest.method !== "pdd" ||
      manifest.coordinates?.up !== "+Z" || manifest.coordinates?.unit !== "m" ||
      manifest.coordinates?.handedness !== "right") throw new Error("清单版本或坐标约定不匹配");
  const labels = new Map(manifest.labels.map(item => [item.id, item]));
  if (labels.size !== manifest.labels.length ||
      manifest.labels.some(item => !Number.isInteger(item.id) || item.id < 0 || item.id > 10 ||
        !/^#[0-9a-f]{6}$/i.test(item.color))) throw new Error("标签表无效");
  const states = new Map(manifest.states.map(item => [item.id, item]));
  if (states.size !== manifest.states.length) throw new Error("状态编号重复");
  for (const id of Object.keys(scaleNames)) {
    if (states.get(id)?.format !== "voxel_points_json") throw new Error(`缺少 ${id} 体素状态`);
  }
  return { labels, states };
}

export function prepareVoxels(data, labels, coordinates) {
  if (!Array.isArray(data.voxel_size_xyz) || data.voxel_size_xyz.length !== 3 ||
      data.voxel_size_xyz.some(value => !Number.isFinite(value) || value <= 0) ||
      !Array.isArray(data.points) || !data.points.length) throw new Error("体素数据为空或格尺寸无效");
  const packed = new Float32Array(data.points.length * 7);
  const seen = new Set();
  const counts = new Map();
  data.points.forEach((point, index) => {
    if (!Array.isArray(point) || point.length !== 4 || !point.every(Number.isFinite) ||
        !Number.isInteger(point[3]) || labels.get(point[3])?.role !== "semantic") {
      throw new Error(`体素 ${index} 的坐标或标签无效`);
    }
    const minimum = coordinates.grid_min_xyz;
    const extent = coordinates.extent_xyz;
    for (let axis = 0; axis < 3; axis++) {
      if (point[axis] < minimum[axis] || point[axis] >= minimum[axis] + extent[axis]) {
        throw new Error(`体素 ${index} 超出场景范围`);
      }
      const grid = (point[axis] - minimum[axis]) / data.voxel_size_xyz[axis] - .5;
      if (Math.abs(grid - Math.round(grid)) > 1e-5) throw new Error(`体素 ${index} 偏离体素中心`);
    }
    const key = point.slice(0, 3).join(",");
    if (seen.has(key)) throw new Error("展示体素中心重复");
    seen.add(key);
    counts.set(point[3], (counts.get(point[3]) || 0) + 1);
    const color = labels.get(point[3]).color;
    packed.set([point[0], point[1], point[2],
      parseInt(color.slice(1, 3), 16) / 255, parseInt(color.slice(3, 5), 16) / 255,
      parseInt(color.slice(5, 7), 16) / 255, point[3]], index * 7);
  });
  return { packed, counts, count: data.points.length, size: data.voxel_size_xyz };
}
