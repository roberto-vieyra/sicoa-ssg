import { afterEach, describe, expect, it, vi } from "vitest";
import { safeRandomUUID } from "./uuid";

afterEach(() => vi.unstubAllGlobals());
describe("safeRandomUUID en HTTP LAN", () => {
  it("aplica RFC 4122 v4 a bytes conocidos sin llamar a randomUUID", () => {
    const randomUUID = vi.fn(() => "must-not-be-used");
    vi.stubGlobal("isSecureContext", false);
    vi.stubGlobal("crypto", {
      randomUUID,
      getRandomValues: (array: Uint8Array) => {
        array.forEach((_, i) => {
          array[i] = i;
        });
        return array;
      },
    });
    expect(safeRandomUUID()).toBe("00010203-0405-4607-8809-0a0b0c0d0e0f");
    expect(randomUUID).not.toHaveBeenCalled();
  });
  it("usa la función nativa solo en contexto seguro", () => {
    const randomUUID = vi.fn(() => "9a8c0b8e-71bc-4d02-bd1a-95fe0a76c338");
    vi.stubGlobal("isSecureContext", true);
    vi.stubGlobal("crypto", { randomUUID });
    expect(safeRandomUUID()).toBe("9a8c0b8e-71bc-4d02-bd1a-95fe0a76c338");
    expect(randomUUID).toHaveBeenCalledOnce();
  });
  it("falla explícitamente si no hay entropía segura", () => {
    vi.stubGlobal("isSecureContext", false);
    vi.stubGlobal("crypto", {});
    expect(safeRandomUUID).toThrow("generador seguro");
  });
});
