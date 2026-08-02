import { beforeEach, describe, expect, it } from "vitest";
import { StableIntentKeyStore } from "../utils/stableIntentKey";

describe("StableIntentKeyStore", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("reuses unresolved intent keys, rotates on payload changes and clears after success", () => {
    const keys = new StableIntentKeyStore("creator-test");
    const first = keys.key("save", { values: { threshold: 42, enabled: true } });

    expect(keys.key("save", { values: { enabled: true, threshold: 42 } })).toBe(first);
    expect(keys.key("save", { values: { enabled: true, threshold: 43 } })).not.toBe(first);

    const changed = keys.key("save", { values: { enabled: true, threshold: 43 } });
    keys.complete("save");
    expect(keys.key("save", { values: { enabled: true, threshold: 43 } })).not.toBe(changed);
  });

  it("restores an unresolved device-write key after component remount", () => {
    const firstMount = new StableIntentKeyStore("device-lab");
    const payload = {
      sessionId: "session-1",
      parameterSetId: "parameters-3",
      confirmSync: true,
    };
    const first = firstMount.key("sync-parameters:work-1", payload);

    const remounted = new StableIntentKeyStore("device-lab");
    expect(remounted.key("sync-parameters:work-1", payload)).toBe(first);

    remounted.complete("sync-parameters:work-1");
    expect(
      new StableIntentKeyStore("device-lab").key(
        "sync-parameters:work-1",
        payload,
      ),
    ).not.toBe(first);
  });
});
