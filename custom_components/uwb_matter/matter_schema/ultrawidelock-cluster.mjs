var __create = Object.create;
var __defProp = Object.defineProperty;
var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
var __knownSymbol = (name, symbol) => (symbol = Symbol[name]) ? symbol : /* @__PURE__ */ Symbol.for("Symbol." + name);
var __typeError = (msg) => {
  throw TypeError(msg);
};
var __defNormalProp = (obj, key, value) => key in obj ? __defProp(obj, key, { enumerable: true, configurable: true, writable: true, value }) : obj[key] = value;
var __name = (target, value) => __defProp(target, "name", { value, configurable: true });
var __decoratorStart = (base) => [, , , __create(base?.[__knownSymbol("metadata")] ?? null)];
var __decoratorStrings = ["class", "method", "getter", "setter", "accessor", "field", "value", "get", "set"];
var __expectFn = (fn) => fn !== void 0 && typeof fn !== "function" ? __typeError("Function expected") : fn;
var __decoratorContext = (kind, name, done, metadata, fns) => ({ kind: __decoratorStrings[kind], name, metadata, addInitializer: (fn) => done._ ? __typeError("Already initialized") : fns.push(__expectFn(fn || null)) });
var __decoratorMetadata = (array, target) => __defNormalProp(target, __knownSymbol("metadata"), array[3]);
var __runInitializers = (array, flags, self, value) => {
  for (var i = 0, fns = array[flags >> 1], n = fns && fns.length; i < n; i++) flags & 1 ? fns[i].call(self) : value = fns[i].call(self, value);
  return value;
};
var __decorateElement = (array, flags, name, decorators, target, extra) => {
  var fn, it, done, ctx, access, k = flags & 7, s = !!(flags & 8), p = !!(flags & 16);
  var j = k > 3 ? array.length + 1 : k ? s ? 1 : 2 : 0, key = __decoratorStrings[k + 5];
  var initializers = k > 3 && (array[j - 1] = []), extraInitializers = array[j] || (array[j] = []);
  var desc = k && (!p && !s && (target = target.prototype), k < 5 && (k > 3 || !p) && __getOwnPropDesc(k < 4 ? target : { get [name]() {
    return __privateGet(this, extra);
  }, set [name](x) {
    return __privateSet(this, extra, x);
  } }, name));
  k ? p && k < 4 && __name(extra, (k > 2 ? "set " : k > 1 ? "get " : "") + name) : __name(target, name);
  for (var i = decorators.length - 1; i >= 0; i--) {
    ctx = __decoratorContext(k, name, done = {}, array[3], extraInitializers);
    if (k) {
      ctx.static = s, ctx.private = p, access = ctx.access = { has: p ? (x) => __privateIn(target, x) : (x) => name in x };
      if (k ^ 3) access.get = p ? (x) => (k ^ 1 ? __privateGet : __privateMethod)(x, target, k ^ 4 ? extra : desc.get) : (x) => x[name];
      if (k > 2) access.set = p ? (x, y) => __privateSet(x, target, y, k ^ 4 ? extra : desc.set) : (x, y) => x[name] = y;
    }
    it = (0, decorators[i])(k ? k < 4 ? p ? extra : desc[key] : k > 4 ? void 0 : { get: desc.get, set: desc.set } : target, ctx), done._ = 1;
    if (k ^ 4 || it === void 0) __expectFn(it) && (k > 4 ? initializers.unshift(it) : k ? p ? extra = it : desc[key] = it : target = it);
    else if (typeof it !== "object" || it === null) __typeError("Object expected");
    else __expectFn(fn = it.get) && (desc.get = fn), __expectFn(fn = it.set) && (desc.set = fn), __expectFn(fn = it.init) && initializers.unshift(fn);
  }
  return k || __decoratorMetadata(array, target), desc && __defProp(target, name, desc), p ? k ^ 4 ? extra : desc : target;
};
var __publicField = (obj, key, value) => __defNormalProp(obj, typeof key !== "symbol" ? key + "" : key, value);
var __accessCheck = (obj, member, msg) => member.has(obj) || __typeError("Cannot " + msg);
var __privateIn = (member, obj) => Object(obj) !== obj ? __typeError('Cannot use the "in" operator on this value') : member.has(obj);
var __privateGet = (obj, member, getter) => (__accessCheck(obj, member, "read from private field"), getter ? getter.call(obj) : member.get(obj));
var __privateSet = (obj, member, value, setter) => (__accessCheck(obj, member, "write to private field"), setter ? setter.call(obj, value) : member.set(obj, value), value);
var __privateMethod = (obj, member, method) => (__accessCheck(obj, member, "access private method"), method);
var _ultraWideLockUnlockEnabled_dec, _ultraWideLockRelockEnabled_dec, _boundUnlockEnabled_dec, _distanceRelockEnabled_dec, _motorMs_dec, _relockCm_dec, _approachCm_dec, _movement_dec, _unlockCm_dec, _credentialId_dec, _distanceMm_dec, _deviceInRange_dec, _UltraWideLockCluster_decorators, _init;
import {
  Matter,
  Schema,
  attribute,
  bool,
  cluster,
  int32,
  nullable,
  uint8,
  uint16,
  uint32,
  writable
} from "/app/node_modules/@matter/model/dist/esm/index.js";
_UltraWideLockCluster_decorators = [cluster(4294048784)], _deviceInRange_dec = [attribute(0, bool)], _distanceMm_dec = [attribute(1, int32, nullable)], _credentialId_dec = [attribute(2, uint32)], _unlockCm_dec = [attribute(3, uint16, writable)], _movement_dec = [attribute(4, uint8)], _approachCm_dec = [attribute(5, uint16, writable)], _relockCm_dec = [attribute(6, uint16, writable)], _motorMs_dec = [attribute(7, uint16, writable)], _distanceRelockEnabled_dec = [attribute(8, bool, writable)], _boundUnlockEnabled_dec = [attribute(9, bool, writable)], _ultraWideLockRelockEnabled_dec = [attribute(10, bool, writable)], _ultraWideLockUnlockEnabled_dec = [attribute(11, bool, writable)];
class UltraWideLockCluster {
  constructor() {
    __publicField(this, "deviceInRange", __runInitializers(_init, 8, this)), __runInitializers(_init, 11, this);
    __publicField(this, "distanceMm", __runInitializers(_init, 12, this)), __runInitializers(_init, 15, this);
    __publicField(this, "credentialId", __runInitializers(_init, 16, this)), __runInitializers(_init, 19, this);
    __publicField(this, "unlockCm", __runInitializers(_init, 20, this)), __runInitializers(_init, 23, this);
    __publicField(this, "movement", __runInitializers(_init, 24, this)), __runInitializers(_init, 27, this);
    __publicField(this, "approachCm", __runInitializers(_init, 28, this)), __runInitializers(_init, 31, this);
    __publicField(this, "relockCm", __runInitializers(_init, 32, this)), __runInitializers(_init, 35, this);
    __publicField(this, "motorMs", __runInitializers(_init, 36, this)), __runInitializers(_init, 39, this);
    __publicField(this, "distanceRelockEnabled", __runInitializers(_init, 40, this)), __runInitializers(_init, 43, this);
    __publicField(this, "boundUnlockEnabled", __runInitializers(_init, 44, this)), __runInitializers(_init, 47, this);
    __publicField(this, "ultraWideLockRelockEnabled", __runInitializers(_init, 48, this)), __runInitializers(_init, 51, this);
    __publicField(this, "ultraWideLockUnlockEnabled", __runInitializers(_init, 52, this)), __runInitializers(_init, 55, this);
  }
}
_init = __decoratorStart(null);
__decorateElement(_init, 5, "deviceInRange", _deviceInRange_dec, UltraWideLockCluster);
__decorateElement(_init, 5, "distanceMm", _distanceMm_dec, UltraWideLockCluster);
__decorateElement(_init, 5, "credentialId", _credentialId_dec, UltraWideLockCluster);
__decorateElement(_init, 5, "unlockCm", _unlockCm_dec, UltraWideLockCluster);
__decorateElement(_init, 5, "movement", _movement_dec, UltraWideLockCluster);
__decorateElement(_init, 5, "approachCm", _approachCm_dec, UltraWideLockCluster);
__decorateElement(_init, 5, "relockCm", _relockCm_dec, UltraWideLockCluster);
__decorateElement(_init, 5, "motorMs", _motorMs_dec, UltraWideLockCluster);
__decorateElement(_init, 5, "distanceRelockEnabled", _distanceRelockEnabled_dec, UltraWideLockCluster);
__decorateElement(_init, 5, "boundUnlockEnabled", _boundUnlockEnabled_dec, UltraWideLockCluster);
__decorateElement(_init, 5, "ultraWideLockRelockEnabled", _ultraWideLockRelockEnabled_dec, UltraWideLockCluster);
__decorateElement(_init, 5, "ultraWideLockUnlockEnabled", _ultraWideLockUnlockEnabled_dec, UltraWideLockCluster);
UltraWideLockCluster = __decorateElement(_init, 0, "UltraWideLockCluster", _UltraWideLockCluster_decorators, UltraWideLockCluster);
__runInitializers(_init, 1, UltraWideLockCluster);
Matter.children.push(Schema.Required(UltraWideLockCluster));
