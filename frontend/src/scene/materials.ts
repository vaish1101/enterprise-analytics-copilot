import * as THREE from 'three'

/**
 * Selective optical glass without transmission passes: a faint body plus a view-dependent
 * rim. Used only for evidence leaves and the aperture lens; structure is opaque metal.
 */
const vertex = /* glsl */`
  varying vec3 vNormal;
  varying vec3 vView;
  varying vec3 vLocal;
  void main() {
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    vNormal = normalize(normalMatrix * normal);
    vView = normalize(-mv.xyz);
    vLocal = position;
    gl_Position = projectionMatrix * mv;
  }
`

const fragment = /* glsl */`
  uniform vec3 uTint;
  uniform vec3 uRimA;
  uniform vec3 uRimB;
  uniform float uOpacity;
  uniform float uBody;
  uniform float uRim;
  uniform float uGlow;
  uniform float uLight;
  varying vec3 vNormal;
  varying vec3 vView;
  varying vec3 vLocal;
  void main() {
    float facing = abs(dot(normalize(vNormal), normalize(vView)));
    float fres = pow(1.0 - facing, 2.4);
    vec3 rim = mix(uRimA, uRimB, clamp(fres * 1.2 + vLocal.x * 0.35, 0.0, 1.0));
    float sheen = smoothstep(0.5, -0.5, vLocal.x + vLocal.y) * 0.1;
    vec3 darkColor = uTint * (uBody + sheen + uGlow * 0.6) + rim * fres * uRim;
    vec3 lightColor = mix(uTint * (0.94 + sheen * 0.4), rim, clamp(fres * uRim * 0.75 + uGlow * 0.35, 0.0, 1.0));
    vec3 color = mix(darkColor, lightColor, uLight);
    float alpha = uOpacity * clamp(uBody * 0.9 + sheen + fres * uRim * 0.85 + uGlow * 0.35, 0.0, 1.0);
    gl_FragColor = vec4(color, alpha);
  }
`

export type GlassUniforms = {
  uTint: { value: THREE.Color }; uRimA: { value: THREE.Color }; uRimB: { value: THREE.Color }
  uOpacity: { value: number }; uBody: { value: number }; uRim: { value: number }; uGlow: { value: number }; uLight: { value: number }
}

export function glass(options: { tint: string; body?: number; rim?: number }): THREE.ShaderMaterial & { uniforms: GlassUniforms } {
  const material = new THREE.ShaderMaterial({
    vertexShader: vertex, fragmentShader: fragment, transparent: true, depthWrite: false,
    uniforms: {
      uTint: { value: new THREE.Color(options.tint) }, uRimA: { value: new THREE.Color('#8fd0ff') }, uRimB: { value: new THREE.Color('#a99bff') },
      uOpacity: { value: 1 }, uBody: { value: options.body ?? 0.16 }, uRim: { value: options.rim ?? 0.9 }, uGlow: { value: 0 }, uLight: { value: 0 },
    },
  })
  return material as THREE.ShaderMaterial & { uniforms: GlassUniforms }
}

function canvasTexture(width: number, height: number, draw: (ctx: CanvasRenderingContext2D) => void, color = true): THREE.CanvasTexture {
  const canvas = document.createElement('canvas')
  canvas.width = width; canvas.height = height
  draw(canvas.getContext('2d')!)
  const texture = new THREE.CanvasTexture(canvas)
  if (color) texture.colorSpace = THREE.SRGBColorSpace
  texture.anisotropy = 4
  return texture
}

/** Fine directional streaks for a brushed, satin roughness response. Data texture, not colour. */
export function brushedTexture(): THREE.CanvasTexture {
  const texture = canvasTexture(256, 256, ctx => {
    // Roughness multiplier close to 1 with fine darker streaks: satin, never mirror-like.
    ctx.fillStyle = 'rgb(236,236,236)'; ctx.fillRect(0, 0, 256, 256)
    let seed = 7
    const rand = () => { seed = (seed * 16807) % 2147483647; return seed / 2147483647 }
    for (let i = 0; i < 900; i++) {
      const v = 196 + Math.floor(rand() * 50)
      ctx.fillStyle = `rgba(${v},${v},${v},0.5)`
      ctx.fillRect(rand() * 256, rand() * 256, 30 + rand() * 120, 1)
    }
  }, false)
  texture.wrapS = texture.wrapT = THREE.RepeatWrapping
  texture.repeat.set(3, 1)
  return texture
}

/** Soft elliptical contact shadow. */
export function shadowTexture(): THREE.CanvasTexture {
  return canvasTexture(256, 128, ctx => {
    const g = ctx.createRadialGradient(128, 64, 4, 128, 64, 124)
    g.addColorStop(0, 'rgba(0,0,0,0.55)'); g.addColorStop(0.55, 'rgba(0,0,0,0.18)'); g.addColorStop(1, 'rgba(0,0,0,0)')
    ctx.setTransform(1, 0, 0, 0.5, 0, 32)
    ctx.fillStyle = g; ctx.fillRect(0, 0, 256, 256)
  }, false)
}

/**
 * A source page, drawn abstractly: frame, two registration holes, a header block and a
 * few faint rules. No simulated text. A cited page carries a highlighted citation band.
 */
export function leafTexture(cited: boolean, theme: 'light' | 'dark'): THREE.CanvasTexture {
  const ink = theme === 'light' ? (a: number) => `rgba(46, 52, 70, ${a})` : (a: number) => `rgba(222, 232, 252, ${Math.min(1, a * 1.5)})`
  const band = theme === 'light' ? 'rgba(109, 100, 173, 0.28)' : 'rgba(180, 166, 255, 0.34)'
  return canvasTexture(216, 300, ctx => {
    ctx.strokeStyle = ink(0.55); ctx.lineWidth = 2; ctx.strokeRect(2, 2, 212, 296)
    ctx.fillStyle = ink(0.5)
    for (const x of [58, 158]) { ctx.beginPath(); ctx.arc(x, 20, 5, 0, Math.PI * 2); ctx.fill() }
    ctx.fillStyle = ink(0.42); ctx.fillRect(22, 44, 96, 10)
    ctx.fillStyle = ink(0.16)
    for (const y of [86, 128, 238]) ctx.fillRect(22, y, 172, 3)
    if (cited) { ctx.fillStyle = band; ctx.fillRect(16, 160, 184, 40); ctx.fillStyle = ink(0.34); ctx.fillRect(22, 178, 140, 3) }
    else { ctx.fillStyle = ink(0.16); ctx.fillRect(22, 180, 150, 3) }
  })
}

export type Rect01 = { u: number; v: number; w: number; h: number }
/** Positions of the real workspace elements, normalised to the answer region. */
export type FaceLayout = {
  aspect: number
  context?: Rect01; question?: Rect01; verification?: Rect01; mark?: Rect01; summary?: Rect01; visual?: Rect01
  kpis: Rect01[]; nodes: Rect01[]; leaves: Rect01[]; bars: Record<string, Rect01>
}

/**
 * The instrument's output surface. It carries only abstract structural zones, placed where
 * the real workspace puts them, so the hand-off from 3D to the page lines up. No text.
 */
export function faceTexture(theme: 'light' | 'dark', layout: FaceLayout): THREE.CanvasTexture {
  const W = 1024, H = Math.round(W / layout.aspect)
  const dark = theme === 'dark'
  const c = dark
    ? { bg: 'rgba(20, 25, 33, 0.97)', line: 'rgba(170, 195, 235, 0.3)', fill: 'rgba(170, 195, 235, 0.2)', strong: 'rgba(214, 226, 244, 0.6)' }
    : { bg: 'rgba(251, 249, 245, 0.98)', line: 'rgba(38, 34, 28, 0.16)', fill: 'rgba(38, 34, 28, 0.07)', strong: 'rgba(30, 32, 38, 0.36)' }
  return canvasTexture(W, H, ctx => {
    const px = (r: Rect01) => ({ x: r.u * W, y: r.v * H, w: r.w * W, h: r.h * H })
    const round = (r: { x: number; y: number; w: number; h: number }, radius: number) => { ctx.beginPath(); ctx.roundRect(r.x, r.y, r.w, r.h, Math.min(radius, r.h / 2, r.w / 2)) }
    // Lines only: the surface they are etched into is the cover itself.
    void c.bg
    layout.nodes.forEach(n => { const r = px(n); round({ x: r.x, y: r.y + r.h * 0.3, w: r.w, h: r.h * 0.4 }, 6); ctx.fillStyle = c.fill; ctx.fill() })
    // The question is never drawn here: it travels as real text, so there is only ever one of it.
    if (layout.verification) { const r = px(layout.verification); round(r, 14); ctx.strokeStyle = c.line; ctx.lineWidth = 2; ctx.stroke() }
    if (layout.mark) { const r = px(layout.mark); ctx.beginPath(); ctx.arc(r.x + r.w / 2, r.y + r.h / 2, Math.min(r.w, r.h) * 0.42, 0, Math.PI * 2); ctx.strokeStyle = c.strong; ctx.lineWidth = 2; ctx.stroke() }
    layout.leaves.forEach(l => { const r = px(l); round(r, 4); ctx.strokeStyle = c.line; ctx.lineWidth = 2; ctx.stroke() })
    if (layout.summary) {
      const r = px(layout.summary)
      for (let i = 0; i < 3; i++) { ctx.fillStyle = c.fill; ctx.fillRect(r.x, r.y + r.h * (0.18 + i * 0.3), r.w * (i === 2 ? 0.6 : 0.96), Math.max(3, r.h * 0.1)) }
    }
    layout.kpis.forEach(k => {
      const r = px(k)
      ctx.fillStyle = c.fill; ctx.fillRect(r.x, r.y + r.h * 0.1, r.w * 0.3, Math.max(3, r.h * 0.1))
      round({ x: r.x, y: r.y + r.h * 0.38, w: r.w * 0.34, h: r.h * 0.38 }, 6); ctx.fillStyle = c.strong; ctx.fill()
    })
    if (layout.visual) {
      const r = px(layout.visual)
      ctx.fillStyle = c.fill; ctx.fillRect(r.x, r.y + r.h * 0.06, r.w * 0.2, Math.max(3, r.h * 0.035))
      // Ghost outlines where the governed blocks will stand.
      Object.values(layout.bars).forEach(b => { const q = px(b); ctx.strokeStyle = c.line; ctx.lineWidth = 1.5; ctx.strokeRect(q.x, q.y, q.w, Math.max(2, q.h)) })
      ctx.strokeStyle = c.line; ctx.lineWidth = 2
      const base = Math.max(...Object.values(layout.bars).map(b => (b.v + b.h) * H), r.y + r.h * 0.85)
      ctx.beginPath(); ctx.moveTo(r.x, base + 1); ctx.lineTo(r.x + r.w, base + 1); ctx.stroke()
    }
  })
}
