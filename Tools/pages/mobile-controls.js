// Two analog sticks feed Unreal's WebAssembly gamepad sampler. The trigger uses
// the same canvas mouse button as the rifle's native press/release binding.
(() => {
  const device = window.ueCompat?.deviceClass();
  if (!['ios', 'android'].includes(device)) return;

  const canvas = document.getElementById('canvas');
  const cover = document.getElementById('cover');
  const html = document.documentElement;
  html.classList.add('canopy-touch');
  document.querySelector('meta[name="ue-start"]').content = 'click';
  const landscape = matchMedia('(orientation: landscape)');
  const controls = document.createElement('div');
  controls.id = 'canopy-controls';
  controls.hidden = true;
  controls.setAttribute('role', 'group');
  controls.setAttribute('aria-label', 'Combat controls');
  document.body.appendChild(controls);

  function addControl(id, title, label) {
    const control = document.createElement('button');
    control.type = 'button';
    control.id = 'canopy-' + id;
    control.setAttribute('aria-label', title);
    const symbol = document.createElement('span');
    symbol.className = 'canopy-symbol';
    const caption = document.createElement('span');
    caption.className = 'canopy-label';
    caption.textContent = label;
    control.append(symbol, caption);
    controls.appendChild(control);
    return control;
  }
  const move = addControl('move', 'Movement joystick', 'Move');
  const look = addControl('look', 'Aim joystick', 'Aim');
  const fire = addControl('fire', 'Fire weapon; drag to aim while firing', 'Fire');
  const pause = addControl('pause', 'Pause game', '');
  const owners = new Map();
  const positions = new Map();
  const pad = { id: 'Canopy touch controls', connected: true, mapping: 'standard', axes: [0, 0, 0, 0], buttons: [] };
  const pads = [pad];
  let gameplay = true;

  // The engine polls on its existing 8 ms timer, using the player's first
  // gamepad. A plugged-in controller keeps all axes and buttons not in use.
  window.canopyTouch = { gamepads() {
    let physical;
    try { physical = navigator.getGamepads?.(); } catch { /* Disabled by browser policy. */ }
    const first = physical?.[0];
    const movement = positions.get(move);
    const aiming = positions.get(look) || positions.get(fire);
    pad.axes[0] = movement ? movement.x : (first?.axes[0] || 0);
    pad.axes[1] = movement ? movement.y : (first?.axes[1] || 0);
    pad.axes[2] = aiming ? aiming.x : (first?.axes[2] || 0);
    pad.axes[3] = aiming ? aiming.y : (first?.axes[3] || 0);
    if (first) pad.buttons = first.buttons;
    else if (pad.buttons.length) pad.buttons = [];
    pads.length = Math.max(1, physical?.length || 0);
    for (let i = 1; i < pads.length; i++) pads[i] = physical[i];
    return pads;
  } };

  function trigger(pressed) {
    const box = canvas.getBoundingClientRect();
    canvas.dispatchEvent(new MouseEvent(pressed ? 'mousedown' : 'mouseup', {
      view: window, bubbles: true, cancelable: true, button: 0, buttons: pressed ? 1 : 0,
      clientX: box.left + box.width / 2, clientY: box.top + box.height / 2,
    }));
  }

  function updateStick(control, event) {
    const pos = positions.get(control);
    const dx = (event.clientX - pos.centerX) / pos.radius;
    const dy = (event.clientY - pos.centerY) / pos.radius;
    const max = Math.max(1, Math.hypot(dx, dy));
    pos.x = dx / max;
    pos.y = dy / max;
    if (control !== fire) {
      control.style.setProperty('--thumb-x', (pos.x * pos.radius * .66) + 'px');
      control.style.setProperty('--thumb-y', (pos.y * pos.radius * .66) + 'px');
    }
  }

  function release(control) {
    if (!positions.has(control)) return;
    const id = positions.get(control).id;
    positions.delete(control);
    owners.delete(id);
    control.classList.remove('held');
    control.style.removeProperty('--thumb-x');
    control.style.removeProperty('--thumb-y');
    if (control === fire) trigger(false);
    if (control.hasPointerCapture(id)) control.releasePointerCapture(id);
  }
  function releaseAll() {
    for (const control of positions.keys()) release(control);
  }
  controls.addEventListener('pointerdown', event => {
    const control = event.target.closest('button');
    if (!control || controls.hidden || owners.has(event.pointerId) || positions.has(control)) return;
    if (control === pause) return; // Handle the click, including a tap cancelled before release.
    event.preventDefault();
    const bounds = control.getBoundingClientRect();
    const isTrigger = control === fire;
    positions.set(control, {
      id: event.pointerId, centerX: isTrigger ? event.clientX : bounds.left + bounds.width / 2,
      centerY: isTrigger ? event.clientY : bounds.top + bounds.height / 2, radius: bounds.width * .40,
      x: 0, y: 0,
    });
    owners.set(event.pointerId, control);
    control.setPointerCapture(event.pointerId);
    control.classList.add('held');
    updateStick(control, event);
    if (isTrigger) trigger(true);
  });
  controls.addEventListener('pointermove', event => {
    const control = owners.get(event.pointerId);
    if (control) { event.preventDefault(); updateStick(control, event); }
  });
  for (const name of ['pointerup', 'pointercancel', 'lostpointercapture']) {
    controls.addEventListener(name, event => {
      const control = owners.get(event.pointerId);
      if (control) release(control);
    });
  }
  pause.addEventListener('click', () => {
    releaseAll();
    for (const type of ['keydown', 'keyup']) {
      canvas.dispatchEvent(new KeyboardEvent(type, {
        bubbles: true, cancelable: true, key: 'Escape', code: 'Escape', keyCode: 27, which: 27,
      }));
    }
  });

  function showControls() {
    controls.hidden = !cover.hidden || !gameplay || document.hidden || !landscape.matches;
    if (controls.hidden) releaseAll();
  }
  // Unreal toggles "wanted" when it opens or closes an interactive Slate
  // menu. Let taps reach the native UI in that state and leave pointer lock
  // to mouse users. The engine retains its existing high-precision input mode.
  function installPageHook() {
    const module = window.Module;
    if (!module || module.ueWebPage?.canopyTouch) return;
    let wanted = !!module.ueWebPageWanted;
    let capturedGameplay = wanted;
    module.ueWebPage = {
      canopyTouch: true, lock() {},
      get wanted() { return wanted; },
      set wanted(value) {
        wanted = !!value;
        // The initial value may be false until the first canvas input.
        // A later release from gameplay opens an interactive Unreal menu.
        if (wanted) capturedGameplay = true;
        gameplay = !capturedGameplay || wanted;
        showControls();
      },
    };
  }

  function enterFullscreen() {
    const fullscreen = html.requestFullscreen || html.webkitRequestFullscreen;
    async function lockOrientation() {
      try { await screen.orientation?.lock?.('landscape'); } catch { /* The player can turn the phone. */ }
    }
    if (document.fullscreenElement || document.webkitFullscreenElement || navigator.standalone ||
        matchMedia('(display-mode: standalone), (display-mode: fullscreen)').matches) {
      lockOrientation();
    } else if (fullscreen) {
      try {
        Promise.resolve(fullscreen.call(html, { navigationUI: 'hide' })).then(lockOrientation, () => {});
      } catch { /* Keep using the full browser viewport. */ }
    }
  }
  cover.addEventListener('click', event => {
    if (!event.isTrusted || !cover.classList.contains('click') || event.target.closest('#error, #ended')) return;
    installPageHook();
    enterFullscreen();
  }, true);
  const rotate = document.getElementById('rotate');
  rotate?.addEventListener('click', enterFullscreen);
  new MutationObserver(() => { installPageHook(); showControls(); })
    .observe(cover, { attributes: true, attributeFilter: ['hidden', 'class'] });
  window.addEventListener('blur', releaseAll);
  window.addEventListener('pagehide', releaseAll);
  document.addEventListener('visibilitychange', showControls);
  landscape.addEventListener('change', () => { releaseAll(); showControls(); });
  screen.orientation?.addEventListener('change', releaseAll);
  document.addEventListener('fullscreenchange', releaseAll);
  document.addEventListener('webkitfullscreenchange', releaseAll);
})();
