interface StableIntentEntry {
  fingerprint: string;
  key: string;
}

/**
 * Keeps one idempotency key for one unresolved user intent.
 *
 * Call `complete` only after an authoritative success response. A rejected or
 * ambiguous request deliberately retains its key so a user retry cannot create
 * a duplicate server-side action.
 */
export class StableIntentKeyStore {
  private readonly entries = new Map<string, StableIntentEntry>();

  constructor(private readonly prefix: string) {}

  key(scope: string, payload: unknown): string {
    const fingerprint = stableFingerprint(payload);
    const current = this.entries.get(scope) ?? this.restore(scope);
    if (current?.fingerprint === fingerprint) return current.key;
    const key = `${this.prefix}-${scope}-${randomKeyPart()}`;
    const entry = { fingerprint, key };
    this.entries.set(scope, entry);
    this.persist(scope, entry);
    return key;
  }

  complete(scope: string): void {
    this.entries.delete(scope);
    try {
      globalThis.localStorage?.removeItem(this.storageKey(scope));
    } catch {
      // Non-browser hosts and privacy-restricted storage stay memory-only.
    }
  }

  private restore(scope: string): StableIntentEntry | undefined {
    try {
      const raw = globalThis.localStorage?.getItem(this.storageKey(scope));
      if (!raw) return undefined;
      const candidate = JSON.parse(raw) as Partial<StableIntentEntry>;
      if (
        typeof candidate.fingerprint !== "string"
        || typeof candidate.key !== "string"
      ) {
        return undefined;
      }
      const entry = { fingerprint: candidate.fingerprint, key: candidate.key };
      this.entries.set(scope, entry);
      return entry;
    } catch {
      return undefined;
    }
  }

  private persist(scope: string, entry: StableIntentEntry): void {
    try {
      globalThis.localStorage?.setItem(
        this.storageKey(scope),
        JSON.stringify(entry),
      );
    } catch {
      // The action still remains stable for the lifetime of this instance.
    }
  }

  private storageKey(scope: string): string {
    return `zhangwen.pending-intent.v1:${this.prefix}:${scope}`;
  }
}

function stableFingerprint(value: unknown): string {
  const serialized = stableSerialize(value);
  let hash = 0x811c9dc5;
  for (let index = 0; index < serialized.length; index += 1) {
    hash ^= serialized.charCodeAt(index);
    hash = Math.imul(hash, 0x01000193);
  }
  return `fnv1a-${(hash >>> 0).toString(16).padStart(8, "0")}-${serialized.length}`;
}

function stableSerialize(value: unknown): string {
  if (Array.isArray(value)) {
    return `[${value.map((item) => stableSerialize(item)).join(",")}]`;
  }
  if (value !== null && typeof value === "object") {
    const record = value as Record<string, unknown>;
    return `{${Object.keys(record)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${stableSerialize(record[key])}`)
      .join(",")}}`;
  }
  return JSON.stringify(value) ?? String(value);
}

function randomKeyPart(): string {
  return (
    globalThis.crypto?.randomUUID?.()
    ?? `${Date.now()}-${Math.random().toString(36).slice(2)}`
  );
}
