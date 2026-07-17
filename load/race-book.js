/**
 * Stage 3: 100 VUs race to book the SAME slot.
 * Expectation: exactly 1 HTTP 200, rest 409 (or 404/422), never >1 success.
 *
 * Usage:
 *   SLOT_ID=123 k6 run load/race-book.js
 *   # or auto-pick open slot:
 *   k6 run load/race-book.js
 */
import http from "k6/http";
import { check, sleep } from "k6";
import { SharedArray } from "k6/data";
import { Counter } from "k6/metrics";

const BASE = __ENV.BASE_URL || "http://127.0.0.1:8100";
const successCount = new Counter("book_success");
const conflictCount = new Counter("book_conflict");
const otherCount = new Counter("book_other");

export const options = {
  scenarios: {
    race: {
      executor: "shared-iterations",
      vus: 100,
      iterations: 100,
      maxDuration: "30s",
    },
  },
  thresholds: {
    book_success: ["count<=1"], // hard: at most one winner
  },
};

function pickSlot() {
  if (__ENV.SLOT_ID) return Number(__ENV.SLOT_ID);
  const res = http.get(`${BASE}/v1/slots?limit=5`);
  if (res.status !== 200) {
    throw new Error(`cannot list slots: ${res.status} ${res.body}`);
  }
  const data = res.json();
  if (!data.items || !data.items.length) throw new Error("no open slots");
  return data.items[0].id;
}

// Resolve slot once in setup
export function setup() {
  const slotId = pickSlot();
  // verify still open
  return { slotId };
}

export default function (data) {
  const slotId = data.slotId;
  const vu = __VU;
  const payload = JSON.stringify({
    slot_id: slotId,
    student_name: `Racer ${vu}`,
    student_phone: `+3736000${String(1000 + vu).padStart(4, "0")}`,
    source: "k6-race",
    lang: "ro",
  });
  const res = http.post(`${BASE}/v1/bookings`, payload, {
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": `race-vu-${vu}-${slotId}`,
    },
    timeout: "10s",
  });

  const ok = check(res, {
    "status is 200 or 409": (r) => r.status === 200 || r.status === 409,
  });

  if (res.status === 200) {
    successCount.add(1);
    console.log(`WINNER vu=${vu} booking=${res.body}`);
  } else if (res.status === 409) {
    conflictCount.add(1);
  } else {
    otherCount.add(1);
    console.log(`OTHER vu=${vu} status=${res.status} body=${res.body}`);
  }
}

export function handleSummary(data) {
  const succ = data.metrics.book_success ? data.metrics.book_success.values.count : 0;
  const conf = data.metrics.book_conflict ? data.metrics.book_conflict.values.count : 0;
  const other = data.metrics.book_other ? data.metrics.book_other.values.count : 0;
  const text = [
    "=== DriveBook Stage-3 race summary ===",
    `success(200): ${succ}`,
    `conflict(409): ${conf}`,
    `other: ${other}`,
    succ === 1 ? "PASS: exactly one winner" : `FAIL: expected 1 winner, got ${succ}`,
    "",
  ].join("\n");
  return {
    stdout: text,
    "load/results/race-summary.txt": text,
    "load/results/race-summary.json": JSON.stringify(data, null, 2),
  };
}
