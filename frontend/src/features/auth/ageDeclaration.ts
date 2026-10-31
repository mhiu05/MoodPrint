import { ApiError } from "../../api/client";
import type { components } from "../../api/generated/schema";

export function bangkokYear(
  serverTime: string = new Date().toISOString(),
): number {
  return Number(
    new Intl.DateTimeFormat("en", {
      timeZone: "Asia/Bangkok",
      year: "numeric",
    }).format(new Date(serverTime)),
  );
}

export function ageDeclaration(
  year: string,
  confirmed: boolean,
  currentYear: number,
  expectedVersion = 0,
): components["schemas"]["EligibilityInput"] {
  const birthYear = Number(year);
  if (
    !confirmed ||
    !year.trim() ||
    !Number.isInteger(birthYear) ||
    birthYear < 1900 ||
    birthYear > currentYear - 18
  )
    throw new ApiError(
      403,
      "AGE_RESTRICTED",
      "Bạn cần đủ 18 tuổi để sử dụng MoodPrint.",
    );
  return {
    birthYear,
    confirmedMinimumAge: true,
    confirmedAdultAge: birthYear === currentYear - 18,
    policyVersion: "self-declared-age-v2-18plus",
    expectedVersion,
  };
}
