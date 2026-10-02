import '@testing-library/jest-dom/vitest'

// jsdom lacks these browser APIs; the app treats their absence as "no WebGL / no motion".
if (!window.matchMedia) {
  window.matchMedia = (query: string) => ({
    matches: false, media: query, onchange: null,
    addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {}, dispatchEvent() { return false },
  }) as MediaQueryList
}
if (!('ResizeObserver' in window)) {
  class ResizeObserverShim { observe() {} unobserve() {} disconnect() {} }
  ;(window as unknown as { ResizeObserver: unknown }).ResizeObserver = ResizeObserverShim
}
