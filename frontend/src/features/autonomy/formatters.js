export function formatLabel(value, fallback = "Unavailable") {
  if (value === null || value === undefined || value === "") {
    return fallback;
  }

  return String(value)
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

export function formatBooleanLabel(value) {
  if (value === null || value === undefined) {
    return "Unavailable";
  }

  return value ? "Yes" : "No";
}

export function formatTimestamp(value, fallback = "Unavailable") {
  if (!value) {
    return fallback;
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return String(value);
  }

  return parsed.toLocaleString();
}

export function formatNumber(value, fallback = "Unavailable") {
  if (value === null || value === undefined || value === "") {
    return fallback;
  }

  return String(value);
}

export function summarizeReanchor(summary) {
  if (!summary) {
    return "No recent re-anchor summary.";
  }

  if (typeof summary === "string") {
    return summary;
  }

  if (typeof summary === "object") {
    if (typeof summary.summary === "string" && summary.summary.trim()) {
      return summary.summary.trim();
    }

    const fragments = Object.entries(summary)
      .filter(([, entryValue]) => entryValue !== null && entryValue !== undefined && entryValue !== "")
      .slice(0, 3)
      .map(([key, entryValue]) => `${formatLabel(key)}: ${String(entryValue)}`);

    if (fragments.length > 0) {
      return fragments.join(" • ");
    }
  }

  return "Re-anchor summary available.";
}

export function payloadPreview(payload) {
  if (!payload || typeof payload !== "object" || Object.keys(payload).length === 0) {
    return "No payload";
  }

  const serialized = JSON.stringify(payload);
  return serialized.length > 120
    ? `${serialized.slice(0, 117)}...`
    : serialized;
}

export function parseJsonInput(text, label) {
  const trimmed = text.trim();
  if (!trimmed) {
    return {};
  }

  try {
    const payload = JSON.parse(trimmed);
    if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
      throw new Error(`${label} must be a JSON object.`);
    }
    return payload;
  } catch (error) {
    if (error instanceof Error && error.message.includes("must be a JSON object")) {
      throw error;
    }
    throw new Error(`${label} must be valid JSON.`);
  }
}

export function latestBy(items, getKey, getTimestamp) {
  return items.reduce((accumulator, item) => {
    const key = getKey(item);
    if (!key) {
      return accumulator;
    }

    const currentTimestamp = new Date(getTimestamp(item) || 0).getTime();
    const previousItem = accumulator[key];
    const previousTimestamp = previousItem
      ? new Date(getTimestamp(previousItem) || 0).getTime()
      : -1;

    if (!previousItem || currentTimestamp >= previousTimestamp) {
      accumulator[key] = item;
    }

    return accumulator;
  }, {});
}

export function buildCountMap(items, getKey) {
  return items.reduce((accumulator, item) => {
    const key = getKey(item);
    if (!key) {
      return accumulator;
    }
    accumulator[key] = (accumulator[key] || 0) + 1;
    return accumulator;
  }, {});
}