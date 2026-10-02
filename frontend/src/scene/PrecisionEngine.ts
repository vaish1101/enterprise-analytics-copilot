import * as THREE from 'three'
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js'
import { RoundedBoxGeometry } from 'three/examples/jsm/geometries/RoundedBoxGeometry.js'
import { ConvexGeometry } from 'three/examples/jsm/geometries/ConvexGeometry.js'
import { brushedTexture, faceTexture, glass, leafTexture, shadowTexture, type FaceLayout, type GlassUniforms, type Rect01 } from './materials'

/*
 * The Glass Core: stepped planes of indigo glass around a tall crystal.
 *
 *   At rest    a dark base and four glass tiers, each smaller than the one below, with a
 *              faceted crystal standing through them. Thin columns of data rise around it and
 *              a quiet ring of nodes turns slowly above.
 *   Question   a node travels in from the ring to the crystal, which brightens.
 *   Figures    the top tier lifts away; the figures tier rises out to the left and the rising
 *              columns give way to this answer's bars on it.
 *   Evidence   the evidence tier slides out to the right; document planes stand up on it.
 *   Analysis   the two tiers draw in towards the crystal.
 *   Checks     the crystal rises; findings from both tiers converge on it and its heart turns
 *              mint only when they pass.
 *   Answer     a thin glass frame rises behind; the bars leave the figures tier and grow into
 *              the chart on it, at the real chart's positions, and the page takes over.
 *
 * Glass parts are drawn in a fixed order, bottom to top, so overlapping panes never swap from
 * frame to frame. Scene units are CSS pixels at fit = 1. Every pose is a pure function of
 * scalars plus one slow idle drift; the sequence is reversible and never reads or writes
 * application state.
 */

export type StoryState = {
  hero: number; enter: number; register: number; open: number; split: number; blocks: number; leaves: number
  converge: number; claims: number; align: number; lock: number; drop: number; release: number
  /** Outside the scroll timeline: submission receive, neutral scan, recede, and the two stop states. */
  receive: number; scan: number; recede: number; hold: number; boundary: number
}
export const initialStory = (): StoryState => ({
  hero: 1, enter: 0, register: 0, open: 0, split: 0, blocks: 0, leaves: 0, converge: 0, claims: 0, align: 0, lock: 0,
  drop: 0, release: 0, receive: 0, scan: 0, recede: 0, hold: 0, boundary: 0,
})

export type Theme = 'light' | 'dark'
export type InstrumentFocus = 'wake' | 'metric' | 'analytics' | 'evidence' | null
export type SubjectFamily = 'driver' | 'breakdown' | 'ranking' | 'comparison' | 'fact' | 'definition' | 'document' | 'findings'

/**
 * One governed figure as a block. `from`/`to` place it on the value scale. `land` says how it
 * becomes its workspace element: standing into a waterfall/comparison bar, lying into a
 * horizontal bar, as the underline of a headline value, or folding into a small target.
 */
export type BarSpec = { key: string; kind: 'endpoint' | 'up' | 'down' | 'delta'; from: number; to: number; land: 'stand' | 'lie' | 'underline' | 'dissolve'; target: string }

export type Subject = {
  family: SubjectFamily
  bars: BarSpec[]
  analytics: boolean; evidence: boolean
  leaves: number; cited: number
  supported: number; failed: number
  nodes: number
}

type Land = 'rect-z' | 'rect-x' | 'rect-zr' | 'circle-x' | 'circle-z' | 'underline' | 'dissolve' | 'veil' | 'none'
type Role = 'shard' | 'spine' | 'body' | 'tray' | 'detail' | 'carriage' | 'index' | 'plate' | 'up' | 'down' | 'end' | 'delta' | 'claim' | 'ring' | 'plane'

type Part = {
  name: string
  mesh: THREE.Mesh
  base: THREE.Vector3
  land: Land
  target?: string
  delay: number
  role?: Role
  material?: THREE.MeshStandardMaterial
  edges?: THREE.LineSegments<THREE.EdgesGeometry, THREE.LineBasicMaterial>
  edgeBase: number
  subject?: boolean
  pos: THREE.Vector3
  quat: THREE.Quaternion
  size: THREE.Vector3
  opacity: number
  setOpacity: (v: number) => void
}

type Palette = Record<Exclude<Role, 'shard'>, string> & { shard: string; glow: string } & { page: string; leaf: string; tab: string; mint: string; windowA: string; windowB: string; accent: string; edge: string; shadow: number }
type Finish = { metalness: number; roughness: number; env: number; brushed: boolean; emissive: number }

const PALETTE: Record<Theme, Palette> = {
  dark: {
    shard: '#16233f', glow: '#7fb4f0', spine: '#59626d', body: '#0f1828', tray: '#30353c', detail: '#14171b', carriage: '#aab6c6', index: '#55606d', plate: '#3a4048',
    up: '#5fa7df', down: '#dc8467', end: '#8d99aa', delta: '#c9d6e6', claim: '#e3eaf4', ring: '#9fc4ff', plane: '#0f1622',
    page: '#0b0e13', leaf: '#cfdaea', tab: '#8fb2d8', mint: '#74e3bf', windowA: '#58aeff', windowB: '#a092ff', accent: '#7cc8ff', edge: '#c6d4e6', shadow: 0.55,
  },
  light: {
    shard: '#1c2b4d', glow: '#4f8fd6', spine: '#3b4048', body: '#141d30', tray: '#474d56', detail: '#2c3035', carriage: '#2b6590', index: '#8ea2b8', plate: '#2f343b',
    up: '#2d6d9d', down: '#b85a3f', end: '#6b7888', delta: '#2c3744', claim: '#eef2f6', ring: '#8fb6f2', plane: '#172030',
    page: '#f3f4f2', leaf: '#dfe8f2', tab: '#4f6b8a', mint: '#17805f', windowA: '#3d84c0', windowB: '#786cbe', accent: '#3d84c0', edge: '#2d3036', shadow: 0.34,
  },
}
const FINISH: Record<Theme, Record<'structure' | 'detail' | 'data' | 'claim', Finish>> = {
  dark: {
    structure: { metalness: 0.28, roughness: 0.62, env: 0.6, brushed: false, emissive: 0 },
    detail: { metalness: 0.7, roughness: 0.3, env: 1.3, brushed: false, emissive: 0 },
    data: { metalness: 0.12, roughness: 0.34, env: 0.9, brushed: false, emissive: 0.32 },
    claim: { metalness: 0.05, roughness: 0.5, env: 0.7, brushed: false, emissive: 0.08 },
  },
  light: {
    structure: { metalness: 0.12, roughness: 0.7, env: 0.55, brushed: false, emissive: 0 },
    detail: { metalness: 0.6, roughness: 0.35, env: 1.0, brushed: false, emissive: 0 },
    data: { metalness: 0.1, roughness: 0.4, env: 0.7, brushed: false, emissive: 0 },
    claim: { metalness: 0.05, roughness: 0.55, env: 0.6, brushed: false, emissive: 0 },
  },
}
const FINISH_OF: Record<Role, 'structure' | 'detail' | 'data' | 'claim'> = {
  shard: 'structure', spine: 'detail', body: 'structure', tray: 'structure', plate: 'structure', plane: 'structure', ring: 'detail', detail: 'detail',
  carriage: 'data', index: 'data', up: 'data', down: 'data', end: 'data', delta: 'data', claim: 'claim',
}

const lerp = THREE.MathUtils.lerp
const clamp01 = (v: number) => Math.min(1, Math.max(0, v))
const smooth = (a: number, b: number, v: number) => { const t = clamp01((v - a) / (b - a)); return t * t * (3 - 2 * t) }
const inOut = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2)
const pulse = (v: number) => Math.sin(Math.PI * clamp01(v))
const Q = (x: number, y: number, z: number) => new THREE.Quaternion().setFromEuler(new THREE.Euler(x, y, z))

const unitBox = new THREE.BoxGeometry(1, 1, 1)
const rounded = (w: number, h: number, d: number, r = 2) => new RoundedBoxGeometry(w, h, d, 2, Math.min(r, w / 2 - 0.01, h / 2 - 0.01, d / 2 - 0.01))

export type Study = 'A' | 'B' | 'C'

const G = {
  base: { w: 280, h: 10 }, tier0: { w: 246 }, layerE: { w: 226 }, layer: { w: 206, h: 8 }, cap: { w: 186, h: 8 },
  tier0Y: 18, evY: 33, figY: 48, capY: 63,
  // Where each tier goes when it leaves the stack, and how far the two draw in afterwards.
  figOut: [-190, 124, 34], evOut: [198, 96, -24], near: 56, capLift: [0, 150, -110],
  // The output frame rises behind the opened stack.
  pane: { w: 150, h: 90, rest: [0, 76, -160], up: [0, 216, -140] },
  // The crystal: a hexagonal prism with a pointed tip, standing through the tiers.
  core: { w: 48, h: 130, foot: 24, rise: 26 },
  orbit: { r: 176, y: 132 },
  carriageFrom: -176, carriageTo: -14, carriageY: 112,
}
/** A six-sided crystal: straight sides and a pointed tip, centred on its own height. */
function crystalGeometry(r: number, h: number, tip: number) {
  const g = new THREE.LatheGeometry([new THREE.Vector2(0.001, -h / 2), new THREE.Vector2(r, -h / 2), new THREE.Vector2(r, h / 2 - tip), new THREE.Vector2(0.001, h / 2)], 6)
  const flat = g.toNonIndexed(); flat.computeVertexNormals(); g.dispose()
  return flat
}
const LEAF = { w: 44, h: 58 }

export class PrecisionEngine {
  readonly story = initialStory()
  flat = 0
  mapToDom = true
  pointer = new THREE.Vector2()
  onFrame?: (engine: PrecisionEngine) => void
  /** Called first in every frame with the seconds since the previous one. */
  onTick?: (dt: number) => void
  private lastFrame = 0
  onDegrade?: () => void
  heroAnchor?: () => { x: number; y: number; width?: number } | null

  private renderer: THREE.WebGLRenderer
  private scene = new THREE.Scene()
  private camera = new THREE.PerspectiveCamera(26, 1, 10, 20000)
  private perspective = new THREE.Matrix4()
  private ortho = new THREE.Matrix4()
  private parts: Part[] = []
  private byName = new Map<string, Part>()
  private group = new THREE.Object3D()
  private groupMatrix = new THREE.Matrix4()
  private brushed = brushedTexture()
  private key = new THREE.DirectionalLight('#ffffff', 1.6)
  private fill = new THREE.HemisphereLight('#dfe8f5', '#20242a', 0.35)
  private idle = 1
  private mint = new THREE.MeshBasicMaterial({ transparent: true, depthWrite: false, opacity: 0 })
  private lens = glass({ tint: '#ffffff', body: 0.04, rim: 0.5 })
  private carriers: { mesh: THREE.InstancedMesh; lane: 0 | 1 }[] = []
  private carriersOn = true
  private leafFaces: { material: THREE.ShaderMaterial; cited: boolean }[] = []
  private tabs: THREE.Mesh[] = []
  private screen = new THREE.MeshBasicMaterial({ transparent: true, depthWrite: false })
  private shadow = new THREE.MeshBasicMaterial({ transparent: true, depthWrite: false, color: '#000000' })
  private subject: Subject
  private layout: FaceLayout
  private targets: Record<string, Rect01> = {}
  private planeH = 110
  private holdIndex = 2
  private focusTarget: InstrumentFocus = null
  private focus = { wake: 0, metric: 0, analytics: 0, evidence: 0 }
  private width = 1
  private height = 1
  private raf = 0
  private running = false
  private startedAt = performance.now()
  private pointerSmoothed = new THREE.Vector2()
  private frameTimes: number[] = []
  private dpr = Math.min(window.devicePixelRatio || 1, 1.75)
  private rectCache = new Map<string, DOMRect | null>()
  private root: HTMLElement | null = null
  private tmp = { m: new THREE.Matrix4(), p: new THREE.Vector3(), q: new THREE.Quaternion(), s: new THREE.Vector3(), p2: new THREE.Vector3(), q2: new THREE.Quaternion(), s2: new THREE.Vector3(), v: new THREE.Vector3() }
  private qStand = Q(0, 0, Math.PI / 2)
  private qFacing = Q(0, Math.PI / 2, 0)
  // The cover lies face-up on the block; identity (frontal) once released.
  private qPlaneHero = new THREE.Quaternion()
  private lane = new THREE.MeshBasicMaterial({ transparent: true, depthWrite: false })
  private heart = new THREE.MeshBasicMaterial({ transparent: true })
  private spike = new THREE.MeshBasicMaterial({ transparent: true, depthWrite: false })
  private orbitMat = new THREE.MeshBasicMaterial({ transparent: true, depthWrite: false })
  private lattice = new THREE.LineBasicMaterial({ transparent: true, depthWrite: false })
  private screenLit = 0
  private colorA = new THREE.Color()
  private colorB = new THREE.Color()
  private theme: Theme

  constructor(canvas: HTMLCanvasElement, private options: { subject: Subject; compact: boolean; reducedMotion: boolean; theme: Theme; study?: Study }) {
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: 'high-performance' })
    this.renderer.setClearColor(0x000000, 0)
    this.renderer.outputColorSpace = THREE.SRGBColorSpace
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping
    const pmrem = new THREE.PMREMGenerator(this.renderer)
    this.scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture
    pmrem.dispose()
    this.key.position.set(-0.5, 1, 0.8)
    this.scene.add(this.key, this.fill)
    this.theme = options.theme
    this.subject = options.subject
    this.layout = this.defaultLayout()
    this.build()
    this.buildSubject()
    this.setTheme(options.theme)
    this.resize()
  }

  /* ---- construction ------------------------------------------------------------------ */

  private addPart(part: Omit<Part, 'pos' | 'quat' | 'size' | 'opacity' | 'edgeBase'> & { edgeBase?: number }) {
    const full: Part = { edgeBase: 0, ...part, pos: new THREE.Vector3(), quat: new THREE.Quaternion(), size: part.base.clone(), opacity: 1 }
    full.mesh.matrixAutoUpdate = false
    // Everything that lands on the answer plane draws after it.
    if (full.land !== 'none' && full.land !== 'veil') full.mesh.renderOrder = 3
    this.scene.add(full.mesh)
    this.parts.push(full)
    this.byName.set(full.name, full)
    return full
  }

  private solid(name: string, role: Role, geometry: THREE.BufferGeometry, base: [number, number, number], o: { land?: Land; target?: string; delay?: number; edges?: number; subject?: boolean; crystal?: boolean } = {}) {
    // Crystal parts get a clear coat and a thin-film sheen: iridescence on edges and facets, no chrome.
    const material: THREE.MeshStandardMaterial = o.crystal
      ? new THREE.MeshPhysicalMaterial({ transparent: true, clearcoat: 0.3, clearcoatRoughness: 0.4, iridescence: 0.3, iridescenceIOR: 1.35, iridescenceThicknessRange: [180, 420], sheen: 0.28, sheenRoughness: 0.5, sheenColor: new THREE.Color('#3f6fc0'), flatShading: true, side: THREE.DoubleSide, specularIntensity: 0.5 })
      : new THREE.MeshStandardMaterial({ transparent: true })
    const mesh = new THREE.Mesh(geometry, material)
    let edges: Part['edges']
    if (o.edges) {
      edges = new THREE.LineSegments(new THREE.EdgesGeometry(geometry, 35), new THREE.LineBasicMaterial({ transparent: true, depthWrite: false }))
      edges.matrixAutoUpdate = false
      mesh.add(edges)
    }
    const edgeBase = o.edges ?? 0
    return this.addPart({
      name, mesh, base: new THREE.Vector3(...base), land: o.land ?? 'none', target: o.target, delay: o.delay ?? 0, role, material, edges, edgeBase, subject: o.subject,
      // Fully visible parts are drawn opaque, so large overlapping parts never swap draw order
      // from frame to frame; a part only joins the sorted transparent pass while it fades.
      setOpacity: v => {
        const solid = v > 0.995
        if (material.transparent === solid) { material.transparent = !solid; material.needsUpdate = true }
        material.opacity = v; material.depthWrite = v > 0.5; mesh.visible = v > 0.003
        if (edges) edges.material.opacity = edgeBase * Math.min(1, v * 3)
      },
    })
  }

  private build() {
    const shadow = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), this.shadow)
    this.shadow.map = shadowTexture()
    shadow.rotation.x = -Math.PI / 2
    this.addPart({ name: 'shadow', mesh: shadow, base: new THREE.Vector3(1, 1, 1), land: 'none', delay: 0, setOpacity: v => { this.shadow.opacity = v * PALETTE[this.theme].shadow; shadow.visible = v > 0.003 } })

    // The stack: a dark base and four tiers of glass. Each has a fixed place in the draw order,
    // bottom to top, so the panes never trade places as the object drifts.
    this.solid('carriage', 'carriage', new THREE.IcosahedronGeometry(7, 1), [14, 14, 14])
    const tier = (name: string, role: Role, w: number, h: number, order: number, crystal = true) => {
      const part = this.solid(name, role, rounded(w, h, w, 3), [w, h, w], { edges: 0.7, crystal })
      part.mesh.renderOrder = order
      return part
    }
    tier('base', 'body', G.base.w, G.base.h, -6, false)
    tier('tier0', 'shard', G.tier0.w, G.layer.h, -5)
    tier('layerE', 'shard', G.layerE.w, G.layer.h, -4)
    tier('layerF', 'shard', G.layer.w, G.layer.h, -3)
    const cap = tier('cap', 'shard', G.cap.w, G.cap.h, -2)
    const pedestal = new THREE.Mesh(new THREE.TorusGeometry(38, 2.4, 10, 64), this.lane)
    pedestal.rotation.x = Math.PI / 2; pedestal.position.y = G.cap.h / 2 + 1.5; pedestal.updateMatrix(); pedestal.matrixAutoUpdate = false
    cap.mesh.add(pedestal)
    // Data rising around the crystal: thin columns, the resting hint of figures.
    const spikes = new THREE.InstancedMesh(new THREE.BoxGeometry(2.4, 1, 2.4), this.spike, 30)
    for (let i = 0; i < 30; i++) {
      const a = (i / 30) * Math.PI * 2, r = 44 + (i % 3) * 9, h = 14 + 44 * Math.abs(Math.sin(i * 1.7) * Math.cos(i * 0.6))
      this.tmp.m.compose(new THREE.Vector3(Math.cos(a) * r, h / 2, Math.sin(a) * r), new THREE.Quaternion(), new THREE.Vector3(1, h, 1))
      spikes.setMatrixAt(i, this.tmp.m)
    }
    spikes.renderOrder = 1; spikes.frustumCulled = false
    this.addPart({ name: 'spikes', mesh: spikes as unknown as THREE.Mesh, base: new THREE.Vector3(1, 1, 1), land: 'none', delay: 0, setOpacity: v => { this.spike.opacity = v; spikes.visible = v > 0.003 } })
    // A quiet ring of nodes above the stack.
    const orbit = new THREE.Mesh(new THREE.TorusGeometry(G.orbit.r, 0.6, 6, 120), this.orbitMat)
    orbit.geometry.rotateX(Math.PI / 2)
    for (const a of [0.3, 1.3, 2.2, 3.4, 4.3, 5.4]) {
      const node = new THREE.Mesh(new THREE.IcosahedronGeometry(8, 1), this.orbitMat)
      node.position.set(Math.cos(a) * G.orbit.r, 0, Math.sin(a) * G.orbit.r); node.updateMatrix(); node.matrixAutoUpdate = false
      orbit.add(node)
    }
    orbit.renderOrder = 2
    this.addPart({ name: 'orbit', mesh: orbit, base: new THREE.Vector3(1, 1, 1), land: 'none', delay: 0, setOpacity: v => { this.orbitMat.opacity = v; orbit.visible = v > 0.003 } })
    // The understood context: four keys in relief on the deck, where the context line will be.
    for (let i = 0; i < 4; i++) this.solid(`idx${i}`, 'index', rounded(2.2, 3, 12, 0.6), [2.2, 3, 12], { land: 'rect-x', target: `[data-anatomy-node="${i}"]` })
    if (!this.options.compact) for (const lane of [0, 1] as const) {
      const geometry = lane === 0 ? new THREE.BoxGeometry(5, 3, 3) : new THREE.BoxGeometry(1, 6, 5)
      const mesh = new THREE.InstancedMesh(geometry, new THREE.MeshStandardMaterial({ transparent: true, roughness: 0.4, metalness: 0.1 }), lane === 0 ? 5 : 4)
      mesh.matrixAutoUpdate = false
      mesh.frustumCulled = false
      this.scene.add(mesh)
      this.carriers.push({ mesh, lane })
    }
    // CHECKS. The crystal, where findings converge. It lands on the page's check mark.
    const core = this.solid('ring', 'ring', crystalGeometry(G.core.w / 2, G.core.h, 34), [G.core.w, G.core.h, G.core.w], { land: 'circle-z', target: '[data-anatomy-mark]', crystal: true, edges: 0.9 })
    // A brighter heart inside the crystal, drawn before the shell so the two never swap.
    const heart = new THREE.Mesh(crystalGeometry(G.core.w * 0.23, G.core.h * 0.66, 22), this.heart)
    heart.position.y = -G.core.h * 0.12; heart.updateMatrix(); heart.matrixAutoUpdate = false; heart.renderOrder = 2
    core.mesh.add(heart)
    const coreOpacity = core.setOpacity
    core.setOpacity = v => {
      // The shell is always glass: it never writes depth, so what stands behind it stays visible.
      coreOpacity(v * 0.46); core.material!.transparent = true; core.material!.depthWrite = false
      this.heart.opacity = v; if (core.edges) core.edges.material.opacity = 0.9 * Math.min(1, v * 2)
    }

    // ANSWER. The deck is the answer surface: the chamber's floor at first, the page at the end.
    this.buildPlane()
  }

  private buildPlane() {
    const old = this.byName.get('plane')
    if (old) { this.scene.remove(old.mesh); old.mesh.geometry.dispose(); this.parts = this.parts.filter(p => p !== old) }
    const W = 140, H = W / this.layout.aspect
    this.planeH = H
    const plane = this.solid('plane', 'plane', rounded(W + 4, H + 4, 2.4, 2), [W + 4, H + 4, 2.4], { land: 'veil', target: '@answer', edges: 0.7 })
    plane.mesh.renderOrder = 1
    const screen = new THREE.Mesh(new THREE.PlaneGeometry(W, H), this.screen)
    screen.position.z = 1.5; screen.updateMatrix(); screen.renderOrder = 2
    plane.mesh.add(screen)
    const set = plane.setOpacity
    plane.setOpacity = v => { set(v); this.screen.opacity = v * this.screenLit }
  }

  /** Parts that depict the answer: governed blocks, source leaves, finding plates. */
  private buildSubject() {
    const s = this.subject
    for (const bar of s.bars) {
      const role: Role = bar.kind === 'endpoint' ? 'end' : bar.kind
      const land: Land = bar.land === 'stand' ? 'rect-zr' : bar.land === 'lie' ? 'rect-z' : bar.land === 'underline' ? 'underline' : 'dissolve'
      this.solid(`bar:${bar.key}`, role, rounded(1, 1, 1, 0.12), [1, 1, 1], { land, target: bar.target, subject: true })
    }
    // Three contained plates at most: evidence is suggested, not piled up.
    const leaves = Math.min(3, s.leaves)
    for (let i = 0; i < leaves; i++) {
      const cited = i < s.cited
      const material = glass({ tint: '#ffffff', body: 0.1, rim: 0.7 })
      const mesh = new THREE.Mesh(new THREE.BoxGeometry(LEAF.w, LEAF.h, 0.8), material)
      const face = new THREE.ShaderMaterial({
        transparent: true, depthWrite: false,
        vertexShader: 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }',
        fragmentShader: 'uniform sampler2D uMap; uniform float uReveal; uniform float uOpacity; varying vec2 vUv; void main(){ vec4 c = texture2D(uMap, vUv); float m = smoothstep(uReveal - 0.18, uReveal, 1.0 - vUv.y); gl_FragColor = vec4(c.rgb, c.a * (1.0 - m) * uOpacity); }',
        uniforms: { uMap: { value: leafTexture(cited, this.theme) }, uReveal: { value: 0 }, uOpacity: { value: 1 } },
      })
      this.leafFaces.push({ material: face, cited })
      const page = new THREE.Mesh(new THREE.PlaneGeometry(LEAF.w, LEAF.h), face)
      page.position.z = 0.45; page.updateMatrix(); page.matrixAutoUpdate = false
      mesh.add(page)
      let tab: THREE.Mesh | null = null
      if (cited) {
        tab = new THREE.Mesh(new THREE.BoxGeometry(9, 7, 0.9), new THREE.MeshStandardMaterial({ transparent: true, roughness: 0.4, metalness: 0.1 }))
        tab.position.set(LEAF.w / 2 - 8, LEAF.h / 2 + 3, 0); tab.updateMatrix(); tab.matrixAutoUpdate = false
        mesh.add(tab)
        this.tabs.push(tab)
      }
      const part = this.addPart({
        name: `leaf${i}`, mesh, base: new THREE.Vector3(LEAF.w, LEAF.h, 0.8), land: cited ? 'rect-z' : 'none', target: cited ? `[data-anatomy-leaf="${i}"]` : undefined,
        delay: 0, subject: true,
        setOpacity: v => { material.uniforms.uOpacity.value = v; face.uniforms.uOpacity.value = v; if (tab) (tab.material as THREE.MeshStandardMaterial).opacity = v; mesh.visible = v > 0.003 },
      })
      part.mesh.userData.glass = material.uniforms as GlassUniforms
    }
    const claims = Math.min(6, s.supported + s.failed)
    for (let i = 0; i < claims; i++) this.solid(`claim${i}`, 'claim', rounded(12, 1.6, 9, 0.6), [12, 1.6, 9], { subject: true })
  }

  private clearSubject() {
    for (const part of this.parts.filter(p => p.subject)) {
      this.scene.remove(part.mesh)
      part.mesh.traverse(o => {
        const mesh = o as THREE.Mesh
        mesh.geometry?.dispose?.()
        const mat = mesh.material as THREE.Material | undefined
        ;(mat as THREE.ShaderMaterial | undefined)?.uniforms?.uMap?.value?.dispose?.()
        mat?.dispose?.()
      })
      this.byName.delete(part.name)
    }
    this.parts = this.parts.filter(p => !p.subject)
    this.leafFaces = []
    this.tabs = []
  }

  /** Depict a different answer: the sample, or a returned answer of any family. */
  setSubject(subject: Subject) {
    this.subject = subject
    this.clearSubject()
    this.buildSubject()
    this.refreshLayout()
    this.setTheme(this.theme)
  }

  /** Which index block stays out of register while the system asks for clarification. */
  setHold(index: number) { this.holdIndex = Math.max(0, Math.min(3, index)) }

  /* ---- theme -------------------------------------------------------------------------- */

  setTheme(theme: Theme) {
    this.theme = theme
    const pal = PALETTE[theme]
    this.renderer.toneMappingExposure = theme === 'light' ? 1.0 : 1.08
    this.key.intensity = theme === 'light' ? 2.2 : 1.45
    this.fill.intensity = theme === 'light' ? 0.6 : 0.7
    this.fill.groundColor.set(theme === 'light' ? '#b9b1a4' : '#1a1d22')
    for (const part of this.parts) {
      if (!part.material || !part.role) continue
      const f = FINISH[theme][FINISH_OF[part.role]]
      const mat = part.material
      mat.color.set(pal[part.role])
      mat.metalness = f.metalness; mat.roughness = f.roughness; mat.envMapIntensity = f.env
      mat.roughnessMap = f.brushed ? this.brushed : null
      mat.emissive.set(pal[part.role]); mat.emissiveIntensity = f.emissive
      mat.needsUpdate = true
      if (part.edges) part.edges.material.color.set(pal.edge)
    }
    this.mint.color.set(pal.mint)
    this.lane.color.set(pal.glow)
    this.spike.color.set(pal.glow)
    this.orbitMat.color.set(theme === 'dark' ? '#a9c6f2' : '#5f86c4')
    // Crystal: smoother and more reflective than the matte structure finish, in both themes.
    for (const part of this.parts) {
      if (!(part.material instanceof THREE.MeshPhysicalMaterial)) continue
      part.material.roughness = part.role === 'shard' ? 0.18 : 0.1
      part.material.metalness = part.role === 'shard' ? 0.1 : 0.2
      part.material.envMapIntensity = part.role === 'shard' ? (theme === 'light' ? 0.34 : 0.55) : 1.2
      part.material.sheenColor.set(theme === 'light' ? '#2f5fae' : '#4f86d8')
      if (part.edges) part.edges.material.color.set(pal.glow)
    }
    this.lens.uniforms.uLight.value = theme === 'light' ? 1 : 0
    this.lens.uniforms.uRimA.value.set(pal.windowA); this.lens.uniforms.uRimB.value.set(pal.windowB)
    this.carriers.forEach(c => (c.mesh.material as THREE.MeshStandardMaterial).color.set(c.lane === 0 ? pal.up : pal.leaf))
    this.tabs.forEach(t => { const mat = t.material as THREE.MeshStandardMaterial; mat.color.set(pal.tab); mat.emissive.set(pal.tab); mat.emissiveIntensity = theme === 'dark' ? 0.4 : 0.1 })
    this.leafFaces.forEach(l => { l.material.uniforms.uMap.value.dispose(); l.material.uniforms.uMap.value = leafTexture(l.cited, theme) })
    for (const part of this.parts) {
      const g = part.mesh.userData.glass as GlassUniforms | undefined
      if (!g) continue
      g.uTint.value.set(pal.leaf); g.uLight.value = theme === 'light' ? 1 : 0
      g.uRimA.value.set(pal.windowB); g.uRimB.value.set(pal.windowA)
      g.uBody.value = theme === 'light' ? 0.6 : 0.5
    }
    this.paintPlane()
  }

  private paintPlane() {
    const paint = () => { this.screen.map?.dispose(); this.screen.map = faceTexture(this.theme, this.layout); this.screen.needsUpdate = true }
    paint()
    document.fonts?.ready?.then(paint).catch(() => undefined)
  }

  /* ---- layout ------------------------------------------------------------------------- */

  setRoot(root: HTMLElement | null) { this.root = root; this.refreshLayout() }
  setFocus(focus: InstrumentFocus) { this.focusTarget = focus }

  /** Re-measure the workspace so the answer plane's zones match where the page puts them. */
  refreshLayout() {
    const measured = this.measureLayout()
    const next = measured ?? this.defaultLayout()
    const aspectChanged = Math.abs(next.aspect - this.layout.aspect) > 0.02
    this.layout = next
    if (aspectChanged) { this.buildPlane(); this.setTheme(this.theme) } else this.paintPlane()
  }

  /** The answer region: context header down to the visual (or the lead, when there is none). */
  private answerRect(q: (selector: string) => DOMRect | null): DOMRect | null {
    const ctx = q('[data-anatomy="context"]')
    const end = q('[data-anatomy="visual"]') ?? q('[data-anatomy="kpi"]') ?? q('[data-anatomy="summary"]') ?? q('[data-anatomy="verification"]')
    if (!ctx || !end) return null
    const left = Math.min(ctx.left, end.left), right = Math.max(ctx.right, end.right)
    return new DOMRect(left, ctx.top, right - left, end.bottom - ctx.top)
  }

  private measureLayout(): FaceLayout | null {
    const root = this.root
    if (!root) return null
    const q = (selector: string) => { const r = root.querySelector(selector)?.getBoundingClientRect(); return r && r.width && r.height ? r : null }
    const area = this.answerRect(q)
    if (!area || area.width < 50 || area.height < 50) return null
    const { left, top, width: W, height: H } = area
    const n = (r: DOMRect | null): Rect01 | undefined => r ? { u: (r.left - left) / W, v: (r.top - top) / H, w: r.width / W, h: r.height / H } : undefined
    const all = (selector: string) => [...root.querySelectorAll(selector)].map(e => n(e.getBoundingClientRect())!).filter(Boolean)
    const bars: Record<string, Rect01> = {}
    this.targets = {}
    for (const bar of this.subject.bars) {
      const r = n(q(bar.target))
      if (!r) continue
      this.targets[bar.key] = r
      if (bar.land === 'stand' || bar.land === 'lie') bars[bar.key] = r
    }
    return {
      aspect: W / H, context: n(q('[data-anatomy="context"]')), question: n(q('[data-anatomy="question"]')), verification: n(q('[data-anatomy="verification"]')),
      mark: n(q('[data-anatomy-mark]')), summary: n(q('[data-anatomy="summary"]')), visual: n(q('[data-anatomy="visual"] .chart-svg') ?? q('[data-anatomy="visual"]')),
      kpis: all('[data-anatomy-kpi]'), nodes: all('[data-anatomy-node]'), leaves: all('[data-anatomy-leaf]'), bars,
    }
  }

  private defaultLayout(): FaceLayout {
    return {
      aspect: 1.8, context: { u: 0, v: 0, w: 1, h: 0.04 }, question: { u: 0, v: 0.07, w: 0.72, h: 0.06 },
      verification: { u: 0, v: 0.16, w: 1, h: 0.09 }, mark: { u: 0.015, v: 0.18, w: 0.025, h: 0.045 }, summary: { u: 0, v: 0.29, w: 0.68, h: 0.18 },
      visual: { u: 0, v: 0.55, w: 1, h: 0.45 }, kpis: [], nodes: [0, 1, 2, 3].map(i => ({ u: i * 0.14, v: 0.005, w: 0.11, h: 0.03 })),
      leaves: [{ u: 0.76, v: 0.185, w: 0.018, h: 0.034 }], bars: {},
    }
  }

  resize() {
    this.width = window.innerWidth
    this.height = window.innerHeight
    this.renderer.setPixelRatio(this.dpr)
    this.renderer.setSize(this.width, this.height, false)
    const distance = (this.height / 2) / Math.tan(THREE.MathUtils.degToRad(this.camera.fov / 2))
    this.camera.aspect = this.width / this.height
    this.camera.position.set(0, 0, distance)
    this.camera.far = distance * 4
    this.camera.updateProjectionMatrix()
    this.perspective.copy(this.camera.projectionMatrix)
    this.ortho.copy(new THREE.OrthographicCamera(-this.width / 2, this.width / 2, this.height / 2, -this.height / 2, 10, distance * 4).projectionMatrix)
  }

  private fit(): number {
    const base = Math.min(this.width / 1440, this.height / 900)
    return this.options.compact ? Math.min(0.46, Math.max(0.36, this.width / 900)) : Math.min(1.0, Math.max(0.55, base * 0.9))
  }

  private set(name: string, x: number, y: number, z: number, w: number, h: number, d: number, opacity = 1, quat?: THREE.Quaternion) {
    const part = this.byName.get(name)
    if (!part) return
    part.pos.set(x, y, z); part.size.set(w, h, d)
    if (quat) part.quat.copy(quat); else part.quat.identity()
    part.opacity = opacity
  }

  /* ---- pose ----------------------------------------------------------------------------- */

  private pose(t: number) {
    const s = this.story
    const sub = this.subject
    const compact = this.options.compact
    const pal = PALETTE[this.theme]
    const reduced = this.options.reducedMotion
    const k = reduced ? 1 : 0.08
    for (const key of ['wake', 'metric', 'analytics', 'evidence'] as const) {
      const target = this.focusTarget === key || (key === 'wake' && this.focusTarget !== null) ? 1 : 0
      this.focus[key] += (target - this.focus[key]) * k
    }
    const heroOnly = smooth(0.5, 1, s.hero) * (1 - s.receive)
    const fW = Math.max(this.focus.wake * heroOnly, s.receive), fM = this.focus.metric * heroOnly, fA = this.focus.analytics * heroOnly, fE = this.focus.evidence * heroOnly
    const r = s.release, rr = inOut(r)
    const lo = inOut(s.open)

    // Placement and a restrained camera: beside the composer in the hero, centre-right while the
    // story plays, a small dolly towards the aperture while findings are checked, then centred
    // and frontal once the answer is released. No orbiting.
    const anchor = this.heroAnchor?.() ?? null
    const heroX = anchor ? anchor.x - this.width / 2 : compact ? 0 : this.width * 0.22
    const heroY = (anchor ? this.height / 2 - anchor.y : 0) - 10
    const stageX = compact ? 0 : this.width * 0.18
    const stageY = compact ? -this.height * 0.1 : -this.height * 0.16
    const relX = compact ? 0 : this.width * 0.18
    const relY = compact ? 0 : -this.height * 0.16
    const vf = compact ? 0 : Math.max(smooth(0, 0.6, s.claims) * (1 - smooth(0, 0.5, r)), s.boundary * 0.5) * 0.3
    this.group.position.set(
      lerp(lerp(stageX, heroX, s.hero), relX, rr) - 30 * this.fit() * vf,
      lerp(lerp(stageY, heroY, s.hero), relY, rr) - s.recede * 30 - 34 * vf, 0)
    // At rest the crystal drifts through a small bounded turn, so its depth and facets show
    // without its best side ever turning away. The drift eases out when analysis begins and
    // back in afterwards: the orientation is never reset, only allowed to settle.
    const resting = s.hero > 0.6 && s.receive < 0.02 && s.enter < 0.02 && !reduced ? 1 : 0
    this.idle += (resting - this.idle) * (reduced ? 1 : 0.035)
    const driftY = Math.sin(t * 0.17) * 0.26 * this.idle, driftX = Math.sin(t * 0.11 + 1.3) * 0.045 * this.idle
    this.group.rotation.set(
      lerp(lerp(0.42, 0.34, s.hero), 0.3, rr) + driftX + this.pointerSmoothed.y * 0.025 * (1 - rr),
      lerp(lerp(-0.48, -0.5, s.hero), -0.3, rr) + driftY + this.pointerSmoothed.x * 0.04 * (1 - rr), 0)
    const heroScale = anchor?.width && !compact ? Math.min(1.18, Math.max(0.6, anchor.width / 440)) : this.fit()
    this.group.scale.setScalar(lerp(lerp(this.fit() * 1.2, heroScale, s.hero), this.fit() * 1.2, rr) * (1 + 0.3 * vf))
    this.group.updateMatrix()
    this.groupMatrix.copy(this.group.matrix)
    const set = this.set.bind(this)

    // Nothing vanishes early: the opened stack stays in view, a little quieter, until the page
    // itself arrives. Then everything without a place in the workspace gives way to it.
    const recedeOp = 1 - 0.45 * smooth(0.3, 1, r)
    const use = sub.analytics || sub.evidence ? 1 : 0.4
    const o = lo * use
    const V = (a: readonly number[]) => new THREE.Vector3(a[0], a[1], a[2])
    // One driver per idea, so each stage reveals one thing.
    const lift = smooth(0, 0.6, o)
    const fig = sub.analytics ? smooth(0.2, 0.95, o) : 0
    const evi = sub.evidence ? inOut(s.leaves) * use : 0
    const join = smooth(0, 1, s.converge)
    const chk = smooth(0, 1, s.claims) * use
    const glassOp = 0.78 * recedeOp

    set('shadow', 0, -1, 0, 520, 1, 520, recedeOp)
    const tierOp = 0.78 * recedeOp
    set('base', 0, G.base.h / 2, 0, G.base.w, G.base.h, G.base.w, recedeOp)
    set('tier0', 0, G.tier0Y, 0, G.tier0.w, G.layer.h, G.tier0.w, tierOp)
    // ROUTING. The top tier lifts away, back and tilted, and thins.
    set('cap', G.capLift[0] * lift, G.capY + G.capLift[1] * lift + fW * 1.2, G.capLift[2] * lift, G.cap.w, G.cap.h, G.cap.w, lerp(0.78, 0.4, lift) * recedeOp, Q(-0.22 * lift, 0, 0))
    const arrive = Math.max(s.enter, s.receive)
    this.lane.opacity = (0.55 + 0.3 * pulse(arrive) + fW * 0.2 + s.scan * (0.2 + 0.12 * Math.sin(t * 2.2))) * (1 - 0.6 * lift) * recedeOp
    // The rising columns stand on the top tier at rest and give way as the figures appear.
    const columns = 1 - smooth(0.05, 0.5, lift)
    set('spikes', 0, G.capY + G.cap.h / 2, 0, 1, Math.max(0.001, columns), 1, 0.8 * columns * recedeOp)
    // The ring of nodes turns slowly and fades as the stack opens.
    set('orbit', 0, G.orbit.y, 0, 1, 1, 1, 0.5 * (1 - smooth(0, 0.6, lift)) * recedeOp, Q(0.16, reduced ? 0 : t * 0.1, 0.08))
    // The question travels in from the ring to the crystal. While a request is pending the
    // crystal only glows a little: neutral activity, nothing is shown as analysed or checked.
    const carriage = this.byName.get('carriage')!
    set('carriage', lerp(G.carriageFrom, G.carriageTo, arrive), lerp(G.orbit.y, G.carriageY, arrive), lerp(40, 0, arrive), 14, 14, 14, recedeOp * smooth(0.02, 0.2, arrive) * (1 - smooth(0.8, 1, arrive)))
    carriage.material!.emissive.set(pal.accent)
    carriage.material!.emissiveIntensity = (this.theme === 'dark' ? 0.6 : 0.3) + fW * 0.5

    // FIGURES and EVIDENCE planes: in the stack at rest, out to either side, then drawn in.
    const figPos = new THREE.Vector3(0, G.figY, 0).lerp(V(G.figOut).add(new THREE.Vector3(G.near * join, 0, 0)), fig)
    const evPos = new THREE.Vector3(0, G.evY, 0).lerp(V(G.evOut).add(new THREE.Vector3(-G.near * join, 0, 0)), evi)
    set('layerF', figPos.x, figPos.y + fA * 2, figPos.z, G.layer.w, G.layer.h, G.layer.w, glassOp)
    set('layerE', evPos.x, evPos.y + fE * 2, evPos.z, G.layerE.w, G.layer.h, G.layerE.w, glassOp)
    for (const name of ['layerF', 'layerE', 'tier0', 'cap']) { const m = this.byName.get(name)!.material!; m.emissive.set(pal.glow); m.emissiveIntensity = (this.theme === 'dark' ? 0.07 : 0.03) + s.scan * 0.04 }

    // OUTPUT. A thin frame of dark glass rises behind the opened stack as the answer forms.
    const planeW = lerp(G.pane.w, 380, rr)
    const planeH = lerp(G.pane.h, planeW / this.layout.aspect, rr)
    const planeD = lerp(2, 0.6, rr)
    const planePos = V(G.pane.rest).lerp(V(G.pane.up), rr)
    const planeQuat = this.qPlaneHero.clone()
    const onPlane = (rect: Rect01 | undefined, zOff = 3) => {
      if (!rect) return null
      const local = new THREE.Vector3((rect.u + rect.w / 2 - 0.5) * planeW, (0.5 - rect.v - rect.h / 2) * planeH, zOff + planeD / 2).applyQuaternion(planeQuat)
      return { pos: local.add(planePos), w: rect.w * planeW, h: rect.h * planeH }
    }
    for (let i = 0; i < 4; i++) set(`idx${i}`, planePos.x, planePos.y, planePos.z, 0.01, 0.01, 0.01, 0)

    // The answer's bars stand on the figures plane, in published order on one scale. During
    // the release each bar travels to its place on the output frame and grows into the chart
    // there: the same bars, never a second chart fading in.
    const bars = sub.bars
    const n = Math.max(1, bars.length)
    const lows = bars.map(b => Math.min(b.from, b.to)), sizes = bars.map(b => Math.abs(b.to - b.from))
    const floor = Math.min(0, ...lows), peak = Math.max(1e-9, ...bars.map((b, i) => lows[i] + sizes[i] - floor))
    const kv = 64 / peak, pitch = Math.min(22, 184 / n)
    bars.forEach((bar, i) => {
      const name = `bar:${bar.key}`
      const rect = bar.land === 'stand' || bar.land === 'lie' ? this.layout.bars[bar.key] : this.targets[bar.key]
      const to = onPlane(rect, 2.6)
      if (!rect || !to) { set(name, 0, G.figY, 0, 0.01, 0.01, 0.01, 0); return }
      const grow = inOut(clamp01(s.blocks * (n + 1.5) - i)) * fig
      const u = inOut(clamp01(r * 1.6 - i * (0.5 / Math.max(4, n))))
      const hFrom = Math.max(1.2, sizes[i] * kv) * grow, wFrom = pitch * 0.64
      const from = new THREE.Vector3(figPos.x + (i - (n - 1) / 2) * pitch, figPos.y + G.layer.h / 2 + (lows[i] - floor) * kv + hFrom / 2, figPos.z + 68)
      const upright = bar.land === 'stand'
      // Along-axis length and thickness, upright on the plane and in the bar's final attitude.
      const len = lerp(hFrom, upright ? to.h : bar.land === 'lie' ? to.w : bar.land === 'underline' ? to.w : Math.min(to.w, 24), u)
      const thick = lerp(wFrom, upright ? to.w : bar.land === 'lie' ? to.h : bar.land === 'underline' ? 2.6 : Math.min(Math.max(to.h, 3), 8), u)
      const p = from.lerp(bar.land === 'underline' ? to.pos.clone().add(new THREE.Vector3(0, -to.h / 2, 0)) : to.pos, u)
      const q = this.qStand.clone().slerp(upright ? planeQuat.clone().multiply(this.qStand) : planeQuat, u)
      const fade = bar.land === 'dissolve' ? 1 - smooth(0.6, 1, r) : 1
      set(name, p.x, p.y, p.z, Math.max(1.2, len), Math.max(2, thick), lerp(wFrom, 4, u), (grow > 0.001 ? 1 : 0) * fade, q)
    })

    // REPORTING EVIDENCE. Document planes stand up on the evidence plane. A cited one carries
    // a tab; at release it gives way to the page's own source marker.
    const leafCount = this.leafFaces.length
    const leafQ = Q(0, -0.25, 0)
    for (let i = 0; i < leafCount; i++) {
      const cited = this.leafFaces[i].cited
      const g = inOut(clamp01(s.leaves * (leafCount + 1.2) - i)) * (sub.evidence ? use : 0)
      const home = new THREE.Vector3(evPos.x - 56 + i * 56, evPos.y + G.layer.h / 2 + (LEAF.h * g) / 2 + fE * 2, evPos.z - 24 + i * 10)
      const rect = cited ? onPlane(this.layout.leaves[i], 3) : null
      const u = inOut(clamp01(r * 1.3 - 0.12 - i * 0.03))
      const visible = g > 0.001 ? 1 : 0
      if (rect && u > 0) {
        const p = home.clone().lerp(rect.pos, u)
        set(`leaf${i}`, p.x, p.y, p.z, lerp(LEAF.w, rect.w, u), lerp(LEAF.h, rect.h, u), 0.8, visible * (1 - smooth(0.1, 0.5, r)), leafQ.clone().slerp(planeQuat, u))
      } else set(`leaf${i}`, home.x, home.y, home.z, LEAF.w, Math.max(0.5, LEAF.h * g), 0.8, visible * recedeOp, leafQ)
      this.leafFaces[i].material.uniforms.uReveal.value = 1.2
      const glassU = this.byName.get(`leaf${i}`)!.mesh.userData.glass as GlassUniforms
      glassU.uGlow.value = (cited ? g * (sub.analytics ? 0.3 : 0.5) : 0) + fE * 0.25
    }
    this.tabs.forEach(tab => { (tab.material as THREE.MeshStandardMaterial).emissiveIntensity = (this.theme === 'dark' ? 0.25 : 0.05) + evi * 0.5 })

    // CHECKS. The crystal stands through the stack; it rises a little, takes findings in from
    // both tiers, its heart turns mint only when they pass, and on release it travels to the
    // check mark.
    const coreHome = new THREE.Vector3(0, G.core.foot + G.core.h / 2 + G.core.rise * chk, 0)
    const markRect = onPlane(this.layout.mark, 1)
    const toMark = inOut(smooth(0.2, 1, r))
    const corePos = markRect ? coreHome.clone().lerp(markRect.pos, toMark) : coreHome
    const snapE = pulse(smooth(0, 0.55, s.lock)) * (1 - s.boundary)
    const shrink = markRect ? Math.max(0.12, Math.min(markRect.w, markRect.h) / G.core.w) : 1
    const coreK = lerp(1, shrink, toMark) * (1 + 0.1 * snapE) * lerp(1, 0.82, s.boundary)
    const core = this.byName.get('ring')!
    const passed = smooth(0.25, 0.7, s.lock) * (1 - s.boundary)
    core.material!.color.copy(this.colorA.set(pal.ring).lerp(this.colorB.set(pal.mint), passed * 0.6))
    core.material!.emissive.copy(this.colorB.set(pal.glow).lerp(this.colorA.set(pal.mint), passed))
    core.material!.emissiveIntensity = (this.theme === 'dark' ? 0.45 : 0.3) + 0.3 * pulse(arrive) + 0.2 * chk + fW * 0.2 + s.scan * (0.2 + 0.15 * Math.sin(t * 2.2))
    this.heart.color.copy(this.colorA.set(this.theme === 'dark' ? '#d6e6ff' : '#f2f7ff').lerp(this.colorB.set(pal.mint), passed))
    if (core.edges) core.edges.material.color.set(pal.glow)
    set('ring', corePos.x, corePos.y, corePos.z, G.core.w * coreK, lerp(G.core.h * coreK, G.core.w * coreK, toMark), G.core.w * coreK, markRect ? 1 : recedeOp, new THREE.Quaternion().slerp(planeQuat, toMark))
    this.anchors.figures.set(figPos.x - G.layer.w / 2, figPos.y - 22, figPos.z + G.layer.w / 2)
    this.anchors.evidence.set(evPos.x - 20, evPos.y - 24, evPos.z + G.layer.w / 2)
    this.anchors.checks.copy(coreHome).add(new THREE.Vector3(G.core.w * 0.9, 44, 0))

    // SUPPORTED ANALYSIS. Carriers leave both planes for the core.
    const sources = [figPos.clone().add(new THREE.Vector3(0, 14, 40)), evPos.clone().add(new THREE.Vector3(0, 14, 0))]
    for (const c of this.carriers) {
      const count = c.mesh.count
      const active = c.lane === 0 ? sub.analytics : sub.evidence
      const from = sources[c.lane]
      const mat = c.mesh.material as THREE.MeshStandardMaterial
      const alive = this.carriersOn && !reduced && active && s.converge > 0 && s.converge < 1
      mat.opacity = alive ? recedeOp : 0
      c.mesh.visible = alive
      if (!alive) continue
      for (let i = 0; i < count; i++) {
        const raw = clamp01(s.converge * 1.7 - i * 0.14)
        const u = c.lane === 0 ? raw : raw * raw * (3 - 2 * raw)
        this.tmp.m.compose(from.clone().lerp(coreHome, u), Q(0, -Math.atan2(coreHome.z - from.z, coreHome.x - from.x), 0), new THREE.Vector3(1, 1, raw > 0 && raw < 1 ? 1 : 0.0001))
        c.mesh.setMatrixAt(i, this.tmp.m)
      }
      c.mesh.instanceMatrix.needsUpdate = true
      c.mesh.matrix.copy(this.groupMatrix)
    }

    // Findings: drafted from the two planes, drawn to the core, and released above it once
    // they pass. One that does not pass falls aside and is left behind.
    const total = this.byName.has('claim0') ? Math.min(6, sub.supported + sub.failed) : 0
    const failedSlots = new Set([1, 3].slice(0, sub.failed))
    for (let i = 0; i < total; i++) {
      const failed = failedSlots.has(i)
      const out = clamp01(s.claims * 1.6 - i * 0.12)
      const align = failed ? 0 : clamp01(s.align * 1.5 - i * 0.1)
      const pass = failed ? 0 : inOut(clamp01(s.lock * (total + 1) - i))
      const fromFigures = sub.analytics && (i % 2 === 0 || !sub.evidence)
      const jitter = (1 - align) * (i % 2 ? 1 : -1)
      const queued = coreHome.clone().add(new THREE.Vector3((fromFigures ? -1 : 1) * (44 + i * 6), -4 + jitter * 3, jitter * 6))
      const p = sources[fromFigures ? 0 : 1].clone().lerp(queued, inOut(out))
      p.lerp(coreHome.clone().add(new THREE.Vector3(0, G.core.h / 2 + 10 + (total - i) * 4, 0)), pass)
      let q = Q(0.1 * jitter, 0.5 * jitter, 0)
      let op = out > 0 ? 1 : 0
      const mat = this.byName.get(`claim${i}`)!.material!
      if (failed) {
        const dim = smooth(0.2, 0.9, s.align)
        p.add(new THREE.Vector3(0, -30 * s.drop, 40 * s.drop))
        q = Q(0.2 * s.drop, 0.6, 0.2 * dim)
        op = (out > 0 ? lerp(1, 0.3, dim) : 0) * recedeOp
        mat.color.set(pal.claim); mat.emissive.set(pal.claim); mat.emissiveIntensity = 0.05 * (1 - dim)
      } else {
        mat.color.set(pass > 0.5 ? pal.mint : pal.claim)
        mat.emissive.set(pass > 0.5 ? pal.mint : pal.claim)
        mat.emissiveIntensity = pass > 0.5 ? (this.theme === 'dark' ? 0.45 : 0.2) : 0.06
        if (r > 0) { p.lerp(corePos, inOut(clamp01(r * 1.4 - 0.1))); op *= 1 - smooth(0.3, 0.7, r) }
      }
      set(`claim${i}`, p.x, p.y, p.z, 14 * (1 - rr * 0.6), 2, 10 * (1 - rr * 0.6), op, q)
    }

    // The output frame: dark glass with a fine frame. It keeps its glass until the page itself
    // is arriving, and only then takes the page's colour and gives way.
    const deck = this.byName.get('plane')!
    const arriving = this.mapToDom ? smooth(0, 0.45, this.flat) : rr
    deck.material!.color.copy(this.colorA.set(pal.plane).lerp(this.colorB.set(pal.page), arriving))
    deck.material!.metalness = lerp(0.2, 0, rr)
    deck.material!.roughness = lerp(0.3, 1, rr)
    deck.material!.envMapIntensity = lerp(0.6, 0.05, rr)
    if (deck.edges) deck.edges.material.color.set(pal.glow)
    this.screenLit = 0
    set('plane', planePos.x, planePos.y, planePos.z, planeW + 4, planeH + 4, planeD, lerp(0.6 * smooth(0, 0.3, rr), 0.3, arriving), planeQuat)
  }

  /* ---- flatten: geometric hand-off to the DOM ------------------------------------------- */

  private rect(selector: string): DOMRect | null {
    if (!this.root) return null
    if (this.rectCache.has(selector)) return this.rectCache.get(selector)!
    if (selector === '@answer') {
      const r = this.answerRect(sel => this.rect(sel))
      this.rectCache.set(selector, r)
      return r
    }
    const el = this.root.querySelector(selector)
    const rect = el ? el.getBoundingClientRect() : null
    const usable = rect && rect.width && rect.height ? rect : null
    this.rectCache.set(selector, usable)
    return usable
  }

  private compose(part: Part) {
    const { m, p, q, s, p2, q2, s2 } = this.tmp
    s.set(part.size.x / part.base.x, part.size.y / part.base.y, part.size.z / part.base.z)
    m.compose(part.pos, part.quat, s).premultiply(this.groupMatrix)
    let opacity = part.opacity * (1 - this.story.recede)
    const flat = this.mapToDom ? this.flat : 0
    if (!this.mapToDom) opacity *= 1 - smooth(0, 0.35, this.flat)
    if (flat > 0) {
      const rect = part.land !== 'none' && part.target ? this.rect(part.target) : null
      const local = clamp01((flat - part.delay) / 0.62)
      const t = inOut(local)
      if (rect) {
        m.decompose(p, q, s)
        const dims = s.multiply(part.base)
        // Parts that land on the plane stay a hair in front of it so they are never covered.
        p2.set(rect.left + rect.width / 2 - this.width / 2, this.height / 2 - (rect.top + rect.height / 2), part.land === 'veil' ? 0 : 3)
        // Move to the target, lose depth and perspective, keep each shape's own proportions.
        switch (part.land) {
          case 'rect-x': q2.copy(this.qFacing); s2.set(2, rect.height, rect.width); break
          case 'rect-zr': q2.copy(this.qStand); s2.set(rect.height, rect.width, 2); break
          case 'circle-x': { const d = Math.min(rect.width, rect.height); q2.copy(this.qFacing); s2.set(2, d, d); break }
          case 'circle-z': { const d = Math.min(rect.width, rect.height); q2.identity(); s2.set(d, d, 1.5); break }
          case 'underline': q2.identity(); p2.y -= rect.height / 2 + 2; s2.set(rect.width, 2.5, 2); break
          case 'dissolve': { q2.identity(); const d = Math.min(rect.width, rect.height, 24); s2.set(d, d * 0.5, 2); break }
          case 'veil': q2.identity(); s2.set(rect.width * (part.base.x / (part.base.x - 4)), rect.height * (part.base.y / (part.base.y - 4)), 2); break
          default: q2.identity(); s2.set(rect.width, rect.height, 2)
        }
        p.lerp(p2, t); q.slerp(q2, t); dims.lerp(s2, t)
        m.compose(p, q, dims.divide(part.base))
        // Overlap, never a gap: the plane gives way only once the page has mostly
        // materialised beneath it; the parts that land on real elements go last.
        opacity *= part.land === 'veil' ? 1 - smooth(0.12, 0.55, flat) : part.land === 'dissolve' ? 1 - smooth(0.4, 0.8, flat) : 1 - smooth(0.9, 1, flat)
      } else {
        opacity *= 1 - smooth(0, 0.3, flat)
      }
    }
    part.mesh.matrix.copy(m)
    part.setOpacity(opacity)
  }

  private anchors = { figures: new THREE.Vector3(), evidence: new THREE.Vector3(), checks: new THREE.Vector3() }

  /** Where the three object labels sit on screen, and how present each part currently is. */
  labelPoints(): Record<'figures' | 'evidence' | 'checks', { x: number; y: number; o: number }> {
    const s = this.story
    const at = (key: 'figures' | 'evidence' | 'checks') => { const v = this.tmp.v.copy(this.anchors[key]).applyMatrix4(this.groupMatrix).project(this.camera); return { x: (v.x + 1) / 2 * this.width, y: (1 - v.y) / 2 * this.height } }
    const live = (1 - smooth(0, 0.25, s.release)) * (1 - s.recede)
    return {
      figures: { ...at('figures'), o: (this.subject.analytics ? smooth(0.15, 0.6, s.blocks) : 0) * (1 - smooth(0.5, 1, s.lock)) * live },
      evidence: { ...at('evidence'), o: (this.subject.evidence ? smooth(0.15, 0.6, s.leaves) : 0) * (1 - smooth(0.5, 1, s.lock)) * live },
      checks: { ...at('checks'), o: Math.max(smooth(0.5, 1, s.claims), s.boundary) * live },
    }
  }

  screenOf(name: string): { x: number; y: number } | null {
    const part = this.byName.get(name)
    if (!part) return null
    const v = this.tmp.v.setFromMatrixPosition(part.mesh.matrix).project(this.camera)
    return { x: (v.x + 1) / 2 * this.width, y: (1 - v.y) / 2 * this.height }
  }

  /* ---- loop ------------------------------------------------------------------------------- */

  private frame = () => {
    if (!this.running) return
    this.raf = requestAnimationFrame(this.frame)
    const started = performance.now()
    this.onTick?.(this.lastFrame ? Math.min(0.1, (started - this.lastFrame) / 1000) : 1 / 60)
    this.lastFrame = started
    const t = (performance.now() - this.startedAt) / 1000
    this.pointerSmoothed.lerp(this.pointer, this.options.reducedMotion ? 0 : 0.04 * (1 - this.story.release))
    this.rectCache.clear()
    this.pose(t)
    for (const part of this.parts) this.compose(part)
    const k = inOut(clamp01(((this.mapToDom ? this.flat : 0) - 0.2) / 0.72))
    const pm = this.camera.projectionMatrix
    for (let i = 0; i < 16; i++) pm.elements[i] = lerp(this.perspective.elements[i], this.ortho.elements[i], k)
    this.camera.projectionMatrixInverse.copy(pm).invert()
    this.scene.updateMatrixWorld()
    this.renderer.render(this.scene, this.camera)
    this.onFrame?.(this)
    this.adapt(performance.now() - started)
  }

  /** Degrade decoration, never content: pixel ratio, then carriers, then the static drawing. */
  private adapt(ms: number) {
    this.frameTimes.push(ms)
    if (this.frameTimes.length < 90) return
    const average = this.frameTimes.reduce((a, b) => a + b, 0) / this.frameTimes.length
    this.frameTimes.length = 0
    if (average <= 14) return
    if (this.dpr > 1) { this.dpr = Math.max(1, this.dpr - 0.25); this.resize() }
    else if (this.carriersOn) this.carriersOn = false
    else if (average > 30) this.onDegrade?.()
  }

  stats() { return { calls: this.renderer.info.render.calls, triangles: this.renderer.info.render.triangles, parts: this.parts.length } }

  start() { if (this.running) return; this.running = true; this.raf = requestAnimationFrame(this.frame) }
  stop() { this.running = false; this.lastFrame = 0; cancelAnimationFrame(this.raf) }

  dispose() {
    this.stop()
    this.scene.traverse(object => {
      const mesh = object as THREE.Mesh
      mesh.geometry?.dispose?.()
      const material = mesh.material as THREE.Material | THREE.Material[] | undefined
      if (Array.isArray(material)) material.forEach(x => x.dispose()); else material?.dispose?.()
    })
    this.brushed.dispose()
    this.scene.environment?.dispose()
    this.renderer.dispose()
  }
}
