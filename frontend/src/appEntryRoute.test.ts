import { describe, expect, it } from "vitest";
import { classifyEntry } from "./appEntryRoute";

describe("classifyEntry", () => {
  it("classifiesLegacyHashesAndCallback", () => {
    expect(classifyEntry("/", "", false)).toBe("public");
    expect(classifyEntry("/", "#", false)).toBe("public");
    expect(classifyEntry("/", "#/assistants", false)).toBe("app");
    expect(classifyEntry("/", "#/", false)).toBe("app");
    expect(classifyEntry("/", "#/login?mode=signup", false)).toBe("app");
    expect(classifyEntry("/auth/callback", "", true)).toBe("app");
    expect(classifyEntry("/index.html", "", false)).toBe("public");
  });

  it("keeps unknown real paths public and never an app or identity route", () => {
    expect(classifyEntry("/admin", "", false)).toBe("not_found");
    expect(classifyEntry("/api/v1/session", "", false)).toBe("not_found");
    expect(classifyEntry("/pricing", "#/assistants", false)).toBe("not_found");
  });
});
