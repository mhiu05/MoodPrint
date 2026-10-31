import { describe, expect, it } from "vitest";
import { ageDeclaration, bangkokYear } from "./ageDeclaration";

describe("adult self declaration", () => {
  it.each([2010, 2009, 2008])(
    "does not submit birth year %i without an adult attestation",
    (year) => {
      expect(() => ageDeclaration(String(year), false, 2026)).toThrow();
    },
  );
  it.each([2010, 2009])("rejects an attested minor born in %i", (year) => {
    expect(() => ageDeclaration(String(year), true, 2026)).toThrow();
  });
  it("uses explicit adult confirmation for the ambiguous eighteenth year", () => {
    expect(ageDeclaration("2008", true, 2026)).toEqual({
      birthYear: 2008,
      confirmedMinimumAge: true,
      confirmedAdultAge: true,
      policyVersion: "self-declared-age-v2-18plus",
      expectedVersion: 0,
    });
  });
  it("accepts an older adult and preserves optimistic version", () => {
    expect(ageDeclaration("2000", true, 2026, 4)).toEqual({
      birthYear: 2000,
      confirmedMinimumAge: true,
      confirmedAdultAge: false,
      policyVersion: "self-declared-age-v2-18plus",
      expectedVersion: 4,
    });
  });
  it.each(["", "invalid", "2000.5", "1800", "2027"])(
    "rejects invalid year %s",
    (year) => {
      expect(() => ageDeclaration(year, true, 2026)).toThrow();
    },
  );
  it("uses Bangkok's year across the UTC New Year boundary", () => {
    expect(bangkokYear("2026-12-31T17:00:00Z")).toBe(2027);
    expect(bangkokYear("2026-12-31T16:59:59Z")).toBe(2026);
  });
});
