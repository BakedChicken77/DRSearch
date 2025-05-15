// app\utils\helpers.ts


import crypto from "crypto";

export function hashValue(value: string): string {
  return crypto.createHash("sha256").update(value).digest("hex");
}