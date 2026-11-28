// A local WebGL2 voxel reader. Coordinates and voxel dimensions are in meters.
function multiply(a, b) {
  const out = new Float32Array(16);
  for (let column = 0; column < 4; column++) {
    for (let row = 0; row < 4; row++) {
      for (let k = 0; k < 4; k++) out[column * 4 + row] += a[k * 4 + row] * b[column * 4 + k];
    }
  }
  return out;
}

function normalize(v) {
  const length = Math.hypot(...v);
  return v.map(value => value / length);
}
function cross(a, b) {
  return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
}
function dot(a, b) { return a.reduce((sum, value, i) => sum + value * b[i], 0); }

export function viewMatrix(camera, aspect) {
  const target = [0, 0, -1];
  const elevation = camera.top ? Math.PI / 2 - .0001 : camera.elevation;
  const azimuth = camera.top ? -Math.PI / 2 : camera.azimuth;
  const offset = [Math.cos(elevation) * Math.cos(azimuth),
    Math.cos(elevation) * Math.sin(azimuth), Math.sin(elevation)];
  const eye = offset.map((value, index) => target[index] + camera.distance * value);
  const z = normalize(offset);
  const x = normalize(cross([0, 0, 1], z));
  const y = cross(z, x);
  const view = new Float32Array([
    x[0], y[0], z[0], 0, x[1], y[1], z[1], 0,
    x[2], y[2], z[2], 0, -dot(x, eye), -dot(y, eye), -dot(z, eye), 1,
  ]);
  const halfHeight = camera.distance * .42;
  const halfWidth = halfHeight * aspect;
  const near = .1;
  const far = 500;
  const projection = new Float32Array([
    1 / halfWidth, 0, 0, 0, 0, 1 / halfHeight, 0, 0,
    0, 0, -2 / (far - near), 0, 0, 0, -(far + near) / (far - near), 1,
  ]);
  return multiply(projection, view);
}

export class Renderer {
  constructor(canvas) {
    this.canvas = canvas;
    const gl = canvas.getContext("webgl2", { antialias: true, alpha: false });
    if (!gl) throw new Error("浏览器无法启用 WebGL2，请在支持 WebGL2 的桌面浏览器打开");
    this.gl = gl;
    this.visible = new Float32Array(11).fill(1);
    this.count = 0;
    const vertex = `#version 300 es
      precision highp float;
      layout(location=0) in vec3 corner;
      layout(location=1) in vec3 center;
      layout(location=2) in vec3 color;
      layout(location=3) in float label;
      uniform mat4 matrix;
      uniform vec3 voxelSize;
      out vec3 vertexColor;
      flat out int labelId;
      void main() {
        gl_Position = matrix * vec4(center + corner * voxelSize, 1.0);
        vertexColor = color;
        labelId = int(label);
      }`;
    const fragment = `#version 300 es
      precision highp float;
      in vec3 vertexColor;
      flat in int labelId;
      uniform float visible[11];
      out vec4 result;
      void main() {
        if (visible[labelId] < 0.5) discard;
        result = vec4(vertexColor, 1.0);
      }`;
    const shader = (type, source) => {
      const compiled = gl.createShader(type);
      gl.shaderSource(compiled, source);
      gl.compileShader(compiled);
      if (!gl.getShaderParameter(compiled, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(compiled));
      return compiled;
    };
    const vs = shader(gl.VERTEX_SHADER, vertex);
    const fs = shader(gl.FRAGMENT_SHADER, fragment);
    this.program = gl.createProgram();
    gl.attachShader(this.program, vs);
    gl.attachShader(this.program, fs);
    gl.linkProgram(this.program);
    gl.deleteShader(vs);
    gl.deleteShader(fs);
    if (!gl.getProgramParameter(this.program, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(this.program));
    this.matrix = gl.getUniformLocation(this.program, "matrix");
    this.voxelSize = gl.getUniformLocation(this.program, "voxelSize");
    this.visibleLocation = gl.getUniformLocation(this.program, "visible[0]");
    this.vao = gl.createVertexArray();
    gl.bindVertexArray(this.vao);
    const vertices = [];
    const corners = [[-.5, -.5, -.5], [.5, -.5, -.5], [.5, .5, -.5], [-.5, .5, -.5],
      [-.5, -.5, .5], [.5, -.5, .5], [.5, .5, .5], [-.5, .5, .5]];
    const faces = [[0, 1, 2, 3], [4, 5, 6, 7], [0, 1, 5, 4], [2, 3, 7, 6], [0, 3, 7, 4], [1, 2, 6, 5]];
    for (const face of faces) for (const i of [0, 1, 2, 0, 2, 3]) vertices.push(...corners[face[i]]);
    this.cubeBuffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, this.cubeBuffer);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(vertices), gl.STATIC_DRAW);
    gl.enableVertexAttribArray(0);
    gl.vertexAttribPointer(0, 3, gl.FLOAT, false, 0, 0);
    this.instanceBuffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, this.instanceBuffer);
    for (const [location, size, offset] of [[1, 3, 0], [2, 3, 12], [3, 1, 24]]) {
      gl.enableVertexAttribArray(location);
      gl.vertexAttribPointer(location, size, gl.FLOAT, false, 28, offset);
      gl.vertexAttribDivisor(location, 1);
    }
    this.coverageBuffer = gl.createBuffer();
    gl.enable(gl.DEPTH_TEST);
    gl.clearColor(.984, .988, .996, 1);
  }

  setData(data) {
    this.count = data.count;
    this.size = data.size;
    this.gl.bindBuffer(this.gl.ARRAY_BUFFER, this.instanceBuffer);
    this.gl.bufferData(this.gl.ARRAY_BUFFER, data.packed, this.gl.STATIC_DRAW);
  }

  draw(camera, coverage) {
    const gl = this.gl;
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    const width = Math.max(1, Math.round(this.canvas.clientWidth * ratio));
    const height = Math.max(1, Math.round(this.canvas.clientHeight * ratio));
    if (this.canvas.width !== width || this.canvas.height !== height) {
      this.canvas.width = width;
      this.canvas.height = height;
    }
    gl.viewport(0, 0, width, height);
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    if (!this.count) return;
    gl.useProgram(this.program);
    gl.uniformMatrix4fv(this.matrix, false, viewMatrix(camera, width / height));
    gl.uniform1fv(this.visibleLocation, this.visible);
    gl.bindVertexArray(this.vao);
    gl.bindBuffer(gl.ARRAY_BUFFER, this.instanceBuffer);
    for (const [loc, size, offset] of [[1, 3, 0], [2, 3, 12], [3, 1, 24]]) {
      gl.vertexAttribPointer(loc, size, gl.FLOAT, false, 28, offset);
    }
    gl.uniform3fv(this.voxelSize, this.size);
    gl.drawArraysInstanced(gl.TRIANGLES, 0, 36, this.count);
    if (coverage) {
      gl.bindBuffer(gl.ARRAY_BUFFER, this.coverageBuffer);
      for (const [x, y, sx, sy] of [[24.8, 0, 1.6, 51.2], [-.8, -24.8, 49.6, 1.6]]) {
        gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([x, y, -2.04, .63, .65, .7, 0]), gl.STATIC_DRAW);
        for (const [loc, size, offset] of [[1, 3, 0], [2, 3, 12], [3, 1, 24]]) {
          gl.vertexAttribPointer(loc, size, gl.FLOAT, false, 28, offset);
        }
        gl.uniform3fv(this.voxelSize, [sx, sy, .04]);
        gl.drawArraysInstanced(gl.TRIANGLES, 0, 36, 1);
      }
    }
  }
}
