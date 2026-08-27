class UwbApproachCard extends HTMLElement {
  static getConfigElement() {
    return document.createElement("uwb-approach-card-editor");
  }

  static getStubConfig() { return {}; }

  setConfig(config) {
    if (this.config?.lock_entity !== config.lock_entity) {
      this._resolved = false;
      this._discovered = undefined;
    }
    this.config = { approach_cm: 180, session_cm: 300, ...config };
  }

  set hass(hass) {
    this._hass = hass;
    if (this.config?.lock_entity && !this._resolved && !this._resolving) this.discoverEntities();
    this.render();
  }

  getCardSize() { return 4; }

  entity(key) { return this.config[key] || this._discovered?.[key]; }

  value(entity) { return this._hass?.states[entity]; }

  async discoverEntities() {
    this._resolving = true;
    try {
      const entries = await this._hass.callWS({ type: "config/entity_registry/list" });
      const lockEntry = entries.find(entry => entry.entity_id === this.config.lock_entity);
      if (!lockEntry) return;
      const operationalId = lockEntry.unique_id?.match(
        /(?:deviceid_)?([0-9A-F]{16}-[0-9A-F]{16})-MatterNodeDevice/i)?.[1]?.toUpperCase();
      const peers = entries.filter(entry =>
        (operationalId && entry.unique_id?.toUpperCase().includes(
          `${operationalId}-MATTERNODEDEVICE-1-`)) ||
        (lockEntry.device_id && entry.device_id === lockEntry.device_id));
      const cluster = 4294048784;
      const find = attribute => peers.find(entry =>
        entry.unique_id?.endsWith(`-1-${cluster}-${attribute}`))?.entity_id;
      const special = suffix => peers.find(entry =>
        entry.unique_id?.endsWith(suffix))?.entity_id;
      this._discovered = {
        presence_entity: find(0),
        distance_entity: find(1),
        credential_entity: find(2),
        threshold_entity: find(3),
        movement_entity: find(4),
        approach_entity: find(5),
        status_entity: special("-freshness-status"),
      };
      this._resolved = true;
    } catch (error) {
      console.warn("Unable to discover UltraWideLock card entities", error);
    } finally {
      this._resolving = false;
      this.render();
    }
  }

  render() {
    if (!this.config || !this._hass) return;
    if (!this.config.lock_entity) {
      if (!this.shadowRoot) this.attachShadow({ mode: "open" });
      this.shadowRoot.innerHTML = `<ha-card><div style="padding:20px;color:var(--secondary-text-color)">Select a lock in the card settings.</div></ha-card>`;
      return;
    }
    const lock = this.value(this.config.lock_entity);
    const presence = this.value(this.entity("presence_entity"))?.state === "on";
    const distanceState = this.value(this.entity("distance_entity"));
    const distance = Number.parseFloat(distanceState?.state);
    const threshold = Number.parseFloat(this.value(this.entity("threshold_entity"))?.state);
    const configuredApproach = Number.parseFloat(this.value(this.entity("approach_entity"))?.state);
    const movement = this.value(this.entity("movement_entity"))?.state || "unknown";
    const dataStatus = this.value(this.entity("status_entity"))?.state;
    const credentialEntity = this.entity("credential_entity");
    const credential = credentialEntity ? this.value(credentialEntity)?.state : "";
    const unlockAt = Number.isFinite(threshold) ? threshold : 100;
    const approachAt = Number.isFinite(configuredApproach)
      ? configuredApproach
      : Number(this.config.approach_cm) || 180;
    const session = Math.max(Number(this.config.session_cm) || 300, unlockAt, approachAt, 1);
    const approach = Math.min(approachAt, session);
    const validRange = presence && Number.isFinite(distance);
    const position = validRange ? Math.max(0, Math.min(100, (1 - distance / session) * 100)) : 0;
    const thresholdPosition = Math.max(0, Math.min(100, (1 - unlockAt / session) * 100));
    const approachPosition = Math.max(0, Math.min(100, (1 - approach / session) * 100));
    const unlocked = lock?.state === "unlocked";
    const stage = dataStatus === "stale" ? "UWB data stale"
      : !presence ? "Waiting for authenticated device"
      : !validRange ? "Session detected"
      : distance <= unlockAt ? (unlocked ? "Unlocked" : "Inside unlock zone")
      : distance <= approach ? "Approach armed" : "Authenticated";
    const distanceText = validRange ? `${Math.round(distance)} cm` : "—";
    const movementText = movement.charAt(0).toUpperCase() + movement.slice(1);
    const lockText = lock?.state
      ? lock.state.charAt(0).toUpperCase() + lock.state.slice(1)
      : "Unavailable";
    const deviceText = credential && !["unknown", "unavailable"].includes(credential) ? credential : "No device";
    const isWatch = deviceText.toLowerCase().includes("watch");
    const title = this.config.title || lock?.attributes?.friendly_name || "UltraWideLock";
    const previousPosition = this._position ?? position;
    this._position = position;

    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    this.shadowRoot.innerHTML = `
      <style>
        :host { display:block; --accent:#5b8cff; --unlock:#35c77a; --muted:var(--secondary-text-color,#777); }
        ha-card { padding:20px; overflow:hidden; background:var(--ha-card-background,var(--card-background-color,#fff)); }
        .head,.metrics,.controls { display:flex; align-items:center; justify-content:space-between; gap:12px; }
        h2 { margin:0; font-size:20px; font-weight:600; }
        .stage { color:${unlocked ? "var(--unlock)" : "var(--primary-text-color)"}; font-weight:600; font-size:14px; text-align:right; }
        .path { position:relative; height:116px; margin:18px 4px 8px; }
        .track { position:absolute; inset:0 64px 0 0; }
        .rail { position:absolute; left:0; right:0; top:55px; height:8px; border-radius:8px; background:linear-gradient(90deg,#83909c 0 ${approachPosition}%,#e5aa38 ${approachPosition}% ${thresholdPosition}%,var(--unlock) ${thresholdPosition}% 100%); opacity:.65; }
        .marker { position:absolute; top:40px; width:2px; height:38px; background:var(--primary-text-color); opacity:.35; }
        .marker span { position:absolute; top:42px; transform:translateX(-50%); white-space:nowrap; color:var(--muted); font-size:11px; }
        .device { position:absolute; left:${previousPosition}%; transform:translateX(-50%); transition:left 1.25s cubic-bezier(.22,.61,.36,1),opacity .25s; background:var(--card-background-color,#fff); box-shadow:0 3px 12px #0003; opacity:${validRange ? 1 : .25}; z-index:2; }
        .phone { top:33px; width:27px; height:41px; border:3px solid var(--primary-text-color); border-radius:7px; }
        .phone:after { content:""; position:absolute; width:8px; height:2px; border-radius:3px; background:var(--primary-text-color); left:9px; bottom:3px; }
        .watch { top:36px; width:29px; height:31px; border:3px solid var(--primary-text-color); border-radius:9px; }
        .watch:before,.watch:after { content:""; position:absolute; left:7px; width:15px; height:13px; background:var(--primary-text-color); z-index:-1; }
        .watch:before { top:-14px; border-radius:5px 5px 1px 1px; }
        .watch:after { bottom:-14px; border-radius:1px 1px 5px 5px; }
        .bubble { position:absolute; left:50%; top:-31px; transform:translateX(-50%); white-space:nowrap; color:var(--primary-text-color); font-size:13px; font-weight:650; letter-spacing:.15px; }
        .bubble:after { content:""; position:absolute; left:50%; top:20px; height:10px; border-left:1px dashed color-mix(in srgb,var(--primary-text-color) 35%,transparent); }
        .lock { position:absolute; right:9px; top:56px; transform:translateY(-50%); color:${unlocked ? "var(--unlock)" : "var(--primary-text-color)"}; line-height:0; }
        .lock ha-icon { --mdc-icon-size:27px; }
        .metrics { margin-top:10px; display:grid; grid-template-columns:repeat(3,1fr); }
        .metric { padding:10px 12px; border-radius:12px; background:color-mix(in srgb,var(--primary-text-color) 6%,transparent); min-width:0; }
        .label { font-size:11px; color:var(--muted); margin-bottom:4px; }
        .value { font-size:15px; font-weight:600; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
        .controls { margin-top:14px; justify-content:flex-end; }
        button { border:0; border-radius:18px; padding:8px 16px; color:var(--text-primary-color,#fff); background:var(--primary-color,#03a9f4); cursor:pointer; font-weight:600; }
        @media(max-width:500px){ .metrics{grid-template-columns:1fr 1fr}.metric:last-child{grid-column:1/-1}.stage{font-size:12px}.path{margin-left:8px;margin-right:8px} }
      </style>
      <ha-card>
        <div class="head"><h2>${this.escape(title)}</h2><div class="stage">${this.escape(stage)}</div></div>
        <div class="path">
          <div class="track">
            <div class="rail"></div>
            <div class="marker" style="left:${approachPosition}%"><span>${Math.round(approach)} cm</span></div>
            <div class="marker" style="left:${thresholdPosition}%"><span>${Math.round(unlockAt)} cm</span></div>
            <div class="device ${isWatch ? "watch" : "phone"}"><div class="bubble">${distanceText}</div></div>
          </div>
          <div class="lock"><ha-icon icon="${unlocked ? "mdi:lock-open-variant-outline" : "mdi:lock-outline"}"></ha-icon></div>
        </div>
        <div class="metrics">
          <div class="metric"><div class="label">DEVICE</div><div class="value">${this.escape(deviceText)}</div></div>
          <div class="metric"><div class="label">MOVEMENT</div><div class="value">${this.escape(movementText)}</div></div>
          <div class="metric"><div class="label">LOCK</div><div class="value">${this.escape(lockText)}</div></div>
        </div>
        <div class="controls"><button id="lock-control">${unlocked ? "Lock" : "Unlock"}</button></div>
      </ha-card>`;
    this.shadowRoot.getElementById("lock-control").onclick = () =>
      this._hass.callService("lock", unlocked ? "lock" : "unlock", { entity_id: this.config.lock_entity });
    requestAnimationFrame(() => {
      const device = this.shadowRoot?.querySelector(".device");
      if (device) device.style.left = `${position}%`;
    });
  }

  escape(value) {
    return String(value).replace(/[&<>'"]/g, char => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", "'":"&#39;", '\"':"&quot;" }[char]));
  }
}

class UwbApproachCardEditor extends HTMLElement {
  set hass(hass) {
    this._hass = hass;
    if (!this._locksLoaded && !this._loadingLocks) this.loadLocks();
    this.render();
  }

  setConfig(config) {
    this._config = { ...config };
    this.render();
  }

  changed(key, value) {
    const config = { ...this._config };
    if (value === "") delete config[key];
    else config[key] = value;
    this._config = config;
    this.dispatchEvent(new CustomEvent("config-changed", {
      detail: { config }, bubbles: true, composed: true,
    }));
  }

  async loadLocks() {
    this._loadingLocks = true;
    try {
      const entries = await this._hass.callWS({ type: "config/entity_registry/list" });
      this._eligibleLocks = entries
        .filter(entry => entry.platform === "uwb_matter" && entry.entity_id.startsWith("lock."))
        .map(entry => entry.entity_id);
    } catch (error) {
      console.warn("Unable to load UltraWideLock entities for the card editor", error);
      this._eligibleLocks = [];
    } finally {
      this._locksLoaded = true;
      this._loadingLocks = false;
      this.render();
    }
  }

  render() {
    if (!this._hass || !this._config) return;
    this.innerHTML = `
      <style>.form{display:grid;gap:16px;padding:8px 0}</style>
      <div class="form"><ha-entity-picker></ha-entity-picker><ha-textfield></ha-textfield></div>`;
    const picker = this.querySelector("ha-entity-picker");
    picker.hass = this._hass;
    picker.label = "Lock";
    picker.value = this._config.lock_entity || "";
    picker.includeDomains = ["lock"];
    picker.includeEntities = this._eligibleLocks || [];
    picker.allowCustomEntity = false;
    picker.addEventListener("value-changed", event =>
      this.changed("lock_entity", event.detail.value));
    const title = this.querySelector("ha-textfield");
    title.label = "Title (optional)";
    title.value = this._config.title || "";
    title.addEventListener("input", event => this.changed("title", event.target.value));
  }
}

class UwbOverviewCard extends HTMLElement {
  static getConfigElement() { return document.createElement("uwb-overview-card-editor"); }
  static getStubConfig() { return {}; }

  setConfig(config) {
    if (this.config?.lock_entity !== config.lock_entity) {
      this._resolved = false;
      this._entities = undefined;
    }
    this.config = { ...config };
  }

  set hass(hass) {
    this._hass = hass;
    if (this.config?.lock_entity && !this._resolved && !this._resolving) this.discoverEntities();
    this.render();
  }

  getCardSize() { return 9; }
  entity(key) { return key === "lock" ? this.config.lock_entity : this._entities?.[key]; }
  state(key) { return this._hass?.states[this.entity(key)]; }
  escape(value) {
    return String(value).replace(/[&<>'"]/g, char => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", "'":"&#39;", '"':"&quot;" }[char]));
  }

  async discoverEntities() {
    this._resolving = true;
    try {
      const entries = await this._hass.callWS({ type: "config/entity_registry/list" });
      const lockEntry = entries.find(entry => entry.entity_id === this.config.lock_entity);
      if (!lockEntry) return;
      const operationalId = lockEntry.unique_id?.match(
        /(?:deviceid_)?([0-9A-F]{16}-[0-9A-F]{16})-MatterNodeDevice/i)?.[1]?.toUpperCase();
      const peers = entries.filter(entry =>
        (operationalId && entry.unique_id?.toUpperCase().includes(`${operationalId}-MATTERNODEDEVICE-1-`)) ||
        (lockEntry.device_id && entry.device_id === lockEntry.device_id));
      const find = (domain, cluster, attribute) => peers.find(entry =>
        entry.entity_id.startsWith(`${domain}.`) &&
        entry.unique_id?.endsWith(`-1-${cluster}-${attribute}`))?.entity_id;
      const history = suffix => peers.find(entry =>
        entry.entity_id.startsWith("sensor.") && entry.unique_id?.endsWith(`-history-${suffix}`))?.entity_id;
      const special = suffix => peers.find(entry =>
        entry.entity_id.startsWith("sensor.") && entry.unique_id?.endsWith(suffix))?.entity_id;
      const custom = 4294048784;
      const doorLock = 257;
      const binding = 30;
      this._entities = {
        presence: find("binary_sensor", custom, 0), distance: find("sensor", custom, 1),
        credential: find("sensor", custom, 2),
        unlockDistance: find("number", custom, 3), movement: find("sensor", custom, 4),
        approachDistance: find("number", custom, 5), relockDistance: find("number", custom, 6),
        motorTime: find("number", custom, 7), boundRelock: find("switch", custom, 8),
        boundUnlock: find("switch", custom, 9), lockRelock: find("switch", custom, 10),
        lockUnlock: find("switch", custom, 11),
        autoRelock: find("number", doorLock, 35), operatingMode: find("select", doorLock, 37),
        lastSeen: history("last_seen"), lastSeenAt: history("last_seen_at"),
        lastUnlocked: history("last_unlocked"), lastUnlockedAt: history("last_unlocked_at"),
        lastUnlockedDistance: history("last_unlocked_distance"),
        dataStatus: special("-freshness-status"),
        lastUwbUpdate: special("-freshness-last-update"),
        boundLock: find("sensor", binding, 0),
        boundLockEntity: special("-bound-entity_id"),
      };
      this._resolved = true;
    } catch (error) {
      console.warn("Unable to discover UltraWideLock overview entities", error);
    } finally {
      this._resolving = false;
      this.render();
    }
  }

  display(key, capitalize = false) {
    const state = this.state(key);
    if (!state || ["unknown", "unavailable"].includes(state.state)) return "—";
    let value = state.state;
    if (["distance", "lastUnlockedDistance"].includes(key) && Number.isFinite(Number(value))) {
      value = String(Math.round(Number(value)));
    }
    if (capitalize) value = value.charAt(0).toUpperCase() + value.slice(1);
    return `${value}${state.attributes.unit_of_measurement ? ` ${state.attributes.unit_of_measurement}` : ""}`;
  }

  timestamp(key) {
    const state = this.state(key);
    if (!state || ["unknown", "unavailable"].includes(state.state)) return "—";
    const value = new Date(state.state);
    if (Number.isNaN(value.getTime())) return state.state;
    const seconds = Math.round((value.getTime() - Date.now()) / 1000);
    const intervals = [[31536000, "year"], [2592000, "month"], [86400, "day"],
      [3600, "hour"], [60, "minute"], [1, "second"]];
    const [interval, unit] = intervals.find(([size]) => Math.abs(seconds) >= size) || intervals.at(-1);
    return new Intl.RelativeTimeFormat(this._hass.locale?.language || undefined, { numeric:"auto" })
      .format(Math.round(seconds / interval), unit);
  }

  numberControl(key, label, icon) {
    const entity = this.entity(key);
    const state = this.state(key);
    if (!entity || !state) return "";
    const unit = state.attributes.unit_of_measurement || "";
    return `<div class="control" data-info="${entity}"><ha-icon icon="${icon}"></ha-icon><span>${label}</span>
      <div class="stepper"><button data-number="${entity}" data-delta="-1">−</button>
      <b>${this.escape(state.state)}${unit ? ` ${this.escape(unit)}` : ""}</b>
      <button data-number="${entity}" data-delta="1">+</button></div></div>`;
  }

  switchControl(key, label, detail) {
    const entity = this.entity(key);
    const state = this.state(key);
    if (!entity || !state) return "";
    return `<label class="switch"><span><b>${label}</b><small>${detail}</small></span>
      <input type="checkbox" data-switch="${entity}" ${state.state === "on" ? "checked" : ""}
      ${state.state === "unavailable" ? "disabled" : ""}><i></i></label>`;
  }

  historyRow(key, label, timeKey) {
    const entity = this.entity(key);
    if (!entity) return "";
    return `<button class="history" data-info="${entity}"><span><small>${label}</small><b>${this.escape(this.display(key))}</b></span>
      ${timeKey ? `<time>${this.escape(this.timestamp(timeKey))}</time>` : ""}</button>`;
  }

  render() {
    if (!this.config || !this._hass) return;
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    if (!this.config.lock_entity) {
      this.shadowRoot.innerHTML = `<ha-card><div class="empty">Select an UltraWideLock in the card settings.</div></ha-card>`;
      return;
    }
    const lock = this.state("lock");
    const unlocked = lock?.state === "unlocked";
    const available = lock && lock.state !== "unavailable";
    const title = this.config.title || lock?.attributes?.friendly_name || "UltraWideLock";
    const operating = this.state("operatingMode");
    const boundEntityId = this.state("boundLockEntity")?.state;
    const boundLock = boundEntityId ? this._hass.states[boundEntityId] : undefined;
    const boundAvailable = boundLock && !["unknown", "unavailable"].includes(boundLock.state);
    const boundUnlocked = boundLock?.state === "unlocked";
    const options = (operating?.attributes?.options || []).map(option =>
      `<option ${option === operating.state ? "selected" : ""}>${this.escape(option)}</option>`).join("");
    this.shadowRoot.innerHTML = `
      <style>
        :host{display:block;--uwb:#4f7cff;--ok:#32bf73;--soft:color-mix(in srgb,var(--primary-text-color) 6%,transparent)}
        ha-card{overflow:hidden}.empty{padding:20px;color:var(--secondary-text-color)}
        header{padding:18px 20px;display:flex;align-items:center;justify-content:space-between;gap:16px}
        h2,h3{margin:0}h2{font-size:22px}h3{font-size:15px}.status{display:flex;align-items:center;gap:10px}.status span{font-weight:650;color:${unlocked ? "var(--ok)" : "var(--primary-text-color)"}}
        .primary{border:0;border-radius:20px;padding:9px 18px;background:var(--primary-color);color:var(--text-primary-color);font-weight:650;cursor:pointer}
        section{padding:15px 20px;border-top:1px solid var(--divider-color)}.section-head{display:flex;align-items:center;margin-bottom:10px;color:var(--secondary-text-color)}.section-head ha-icon{display:none}
        .metrics{display:flex;flex-wrap:wrap;gap:1px;background:var(--divider-color);border:1px solid var(--divider-color);border-radius:10px;overflow:hidden}.metric{flex:1 1 140px;border:0;text-align:left;background:var(--card-background-color);border-radius:0;padding:10px 11px;color:var(--primary-text-color);min-width:0;cursor:pointer}
        .metric ha-icon{display:none}.metric small,.history small,.switch small{display:block;color:var(--secondary-text-color);margin:0 0 3px}.metric b{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.bound-metric{display:flex;align-items:center;justify-content:space-between;gap:8px}.bound-metric>span{min-width:0}.bound-action{border:0;border-radius:16px;padding:6px 10px;background:var(--soft);color:var(--primary-color);font-weight:650;cursor:pointer;flex:none}.bound-action:disabled{opacity:.45;cursor:default}
        .configuration,.switches,.history-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,280px),1fr));gap:1px;background:var(--divider-color);border:1px solid var(--divider-color);border-radius:10px;overflow:hidden}.control{display:grid;grid-template-columns:20px minmax(0,1fr) auto;align-items:center;gap:8px;padding:9px 11px;background:var(--card-background-color);cursor:pointer;min-width:0}.control ha-icon{color:var(--secondary-text-color);--mdc-icon-size:18px}.control>span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
        .stepper{display:flex;align-items:center;gap:4px;min-width:0}.stepper button{width:26px;height:26px;border:0;border-radius:50%;background:var(--soft);color:var(--primary-color);font-size:17px;cursor:pointer;flex:none}.stepper b{min-width:52px;text-align:center;font-size:13px;white-space:nowrap}
        .select{display:grid;grid-template-columns:20px minmax(0,1fr) auto;align-items:center;gap:8px;padding:9px 11px;background:var(--card-background-color);min-width:0}.select ha-icon{color:var(--secondary-text-color);--mdc-icon-size:18px}select{min-width:0;max-width:150px;border:0;border-radius:8px;padding:7px;background:var(--soft);color:var(--primary-text-color)}
        .switch{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:10px 12px;background:var(--card-background-color);min-width:0}.switch span{min-width:0}.switch small{margin:2px 0 0}.switch input{display:none}.switch i{position:relative;width:40px;height:22px;border-radius:14px;background:var(--disabled-color);flex:none;transition:.2s}.switch i:after{content:"";position:absolute;width:16px;height:16px;border-radius:50%;left:3px;top:3px;background:white;box-shadow:0 1px 3px #0005;transition:.2s}.switch input:checked+i{background:var(--primary-color)}.switch input:checked+i:after{transform:translateX(18px)}
        .history{border:0;background:var(--card-background-color);color:var(--primary-text-color);padding:10px 12px;text-align:left;display:flex;justify-content:space-between;align-items:center;gap:10px;cursor:pointer;min-width:0}.history span{min-width:0}.history b{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.history time{color:var(--secondary-text-color);font-size:12px;text-align:right;flex:none}
        @media(max-width:600px){.metric{flex-basis:calc(50% - 1px)}}
        @media(max-width:500px){header{align-items:flex-start;padding:16px}.status{flex-direction:column;align-items:flex-end}section{padding:14px 16px}.configuration,.switches,.history-grid{grid-template-columns:1fr}.control{grid-template-columns:18px minmax(0,1fr) auto}.stepper b{min-width:46px}.primary{padding:8px 14px}}
      </style>
      <ha-card>
        <header><div><h2>${this.escape(title)}</h2><small>UltraWideLock overview</small></div><div class="status"><span>${this.escape(this.display("lock", true))}</span><button class="primary" id="lock">${unlocked ? "Lock" : "Unlock"}</button></div></header>
        <section><div class="section-head"><ha-icon icon="mdi:access-point"></ha-icon><h3>Live UWB</h3></div><div class="metrics">
          <button class="metric" data-info="${this.entity("presence") || ""}"><ha-icon icon="mdi:account-radar"></ha-icon><small>In range</small><b>${this.state("presence")?.state === "on" ? "Yes" : "No"}</b></button>
          <button class="metric" data-info="${this.entity("distance") || ""}"><ha-icon icon="mdi:ruler"></ha-icon><small>Distance</small><b>${this.escape(this.display("distance"))}</b></button>
          <button class="metric" data-info="${this.entity("credential") || ""}"><ha-icon icon="mdi:cellphone-key"></ha-icon><small>Current device</small><b>${this.escape(this.display("credential"))}</b></button>
          <button class="metric" data-info="${this.entity("movement") || ""}"><ha-icon icon="mdi:swap-horizontal"></ha-icon><small>Movement</small><b>${this.escape(this.display("movement", true))}</b></button>
          <button class="metric" data-info="${this.entity("dataStatus") || ""}"><ha-icon icon="mdi:access-point-check"></ha-icon><small>Data status</small><b>${this.escape(this.display("dataStatus", true))}</b></button>
          <button class="metric" data-info="${this.entity("lastUwbUpdate") || ""}"><ha-icon icon="mdi:update"></ha-icon><small>Last update</small><b>${this.escape(this.timestamp("lastUwbUpdate"))}</b></button>
          <div class="metric bound-metric" data-info="${this.entity("boundLock") || ""}"><span><small>Bound lock</small><b>${this.escape(this.display("boundLock"))}</b></span>${boundLock ? `<button class="bound-action" id="bound-lock" ${boundAvailable ? "" : "disabled"}>${boundUnlocked ? "Lock" : "Unlock"}</button>` : ""}</div>
        </div></section>
        <section><div class="section-head"><ha-icon icon="mdi:tune-variant"></ha-icon><h3>Unlock &amp; Relock Configuration</h3></div><div class="configuration">
          ${this.numberControl("approachDistance", "Approach distance", "mdi:map-marker-distance")}
          ${this.numberControl("unlockDistance", "Unlock distance", "mdi:lock-open-outline")}
          ${this.numberControl("relockDistance", "Relock distance", "mdi:lock-outline")}
          ${this.numberControl("motorTime", "Motor time", "mdi:engine-outline")}
          ${this.numberControl("autoRelock", "Auto-relock time", "mdi:timer-lock-outline")}
          <div class="select"><ha-icon icon="mdi:list-status"></ha-icon><span>Operating mode</span><select id="mode" ${operating ? "" : "disabled"}>${options}</select></div>
        </div></section>
        <section><div class="section-head"><ha-icon icon="mdi:shield-lock-outline"></ha-icon><h3>Automatic actions</h3></div><div class="switches">
          ${this.switchControl("lockUnlock", "Unlock UltraWideLock", "Allow automatic local unlock")}
          ${this.switchControl("lockRelock", "Relock UltraWideLock", "Allow automatic local relock")}
          ${this.switchControl("boundUnlock", "Unlock bound lock", "Allow automatic bound-lock unlock")}
          ${this.switchControl("boundRelock", "Relock bound lock", "Allow automatic bound-lock relock")}
        </div></section>
        <section><div class="section-head"><ha-icon icon="mdi:history"></ha-icon><h3>History</h3></div><div class="history-grid">
          ${this.historyRow("lastSeen", "Last device seen", "lastSeenAt")}
          ${this.historyRow("lastUnlocked", "Last device unlocked", "lastUnlockedAt")}
          ${this.historyRow("lastUnlockedDistance", "Last unlocked at distance")}
        </div></section>
      </ha-card>`;

    this.shadowRoot.getElementById("lock").disabled = !available;
    this.shadowRoot.getElementById("lock").onclick = () => this._hass.callService(
      "lock", unlocked ? "lock" : "unlock", { entity_id: this.config.lock_entity });
    const boundControl = this.shadowRoot.getElementById("bound-lock");
    if (boundControl) boundControl.onclick = event => {
      event.stopPropagation();
      this._hass.callService("lock", boundUnlocked ? "lock" : "unlock", { entity_id: boundEntityId });
    };
    this.shadowRoot.querySelectorAll("[data-switch]").forEach(input => input.onchange = event =>
      this._hass.callService("switch", event.target.checked ? "turn_on" : "turn_off", { entity_id:event.target.dataset.switch }));
    this.shadowRoot.querySelectorAll("[data-number]").forEach(button => button.onclick = event => {
      event.stopPropagation();
      const entity = event.currentTarget.dataset.number;
      const state = this._hass.states[entity];
      const step = Number(state.attributes.step) || 1;
      const min = Number(state.attributes.min);
      const max = Number(state.attributes.max);
      let value = Number(state.state) + Number(event.currentTarget.dataset.delta) * step;
      if (Number.isFinite(min)) value = Math.max(min, value);
      if (Number.isFinite(max)) value = Math.min(max, value);
      this._hass.callService("number", "set_value", { entity_id:entity, value });
    });
    const mode = this.shadowRoot.getElementById("mode");
    if (mode && this.entity("operatingMode")) mode.onchange = event => this._hass.callService(
      "select", "select_option", { entity_id:this.entity("operatingMode"), option:event.target.value });
    this.shadowRoot.querySelectorAll("[data-info]").forEach(element => element.onclick = event => {
      if (event.target.closest("[data-number]")) return;
      const entityId = event.currentTarget.dataset.info;
      if (entityId) this.dispatchEvent(new CustomEvent("hass-more-info", { detail:{ entityId }, bubbles:true, composed:true }));
    });
  }
}

class UwbOverviewCardEditor extends UwbApproachCardEditor {}

if (!customElements.get("uwb-approach-card-editor")) customElements.define("uwb-approach-card-editor", UwbApproachCardEditor);
if (!customElements.get("uwb-approach-card")) customElements.define("uwb-approach-card", UwbApproachCard);
if (!customElements.get("uwb-overview-card-editor")) customElements.define("uwb-overview-card-editor", UwbOverviewCardEditor);
if (!customElements.get("uwb-overview-card")) customElements.define("uwb-overview-card", UwbOverviewCard);
window.customCards = window.customCards || [];
window.customCards.push({ type:"uwb-approach-card", name:"UWB Approach Path", description:"Live UltraWideLock approach and unlock path" });
window.customCards.push({ type:"uwb-overview-card", name:"UltraWideLock Overview", description:"Complete UltraWideLock status, configuration, controls, and history" });
