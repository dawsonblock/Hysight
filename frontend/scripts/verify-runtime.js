const expectedNodeMajor = 24;
const expectedYarnVersion = "1.22.22";

function fail(message) {
  console.error(message);
  process.exit(1);
}

function parseNodeMajor(version) {
  const major = Number.parseInt(version.split(".")[0], 10);
  return Number.isNaN(major) ? null : major;
}

function parseYarnVersion(userAgent) {
  const match = /yarn\/(\S+)/.exec(userAgent || "");
  return match ? match[1] : null;
}

const nodeVersion = process.versions.node;
const nodeMajor = parseNodeMajor(nodeVersion);
const userAgent = process.env.npm_config_user_agent || "";
const yarnVersion = parseYarnVersion(userAgent);

if (nodeMajor !== expectedNodeMajor) {
  fail(
    [
      `Hysight frontend requires Node ${expectedNodeMajor}.x.`,
      `Detected Node ${nodeVersion}.`,
      "Switch to the pinned runtime in frontend/.nvmrc or frontend/.node-version before installing.",
    ].join(" ")
  );
}

if (!yarnVersion) {
  fail(
    [
      "Hysight frontend must be installed with Yarn 1.22.22.",
      "No Yarn runtime was detected for this install.",
    ].join(" ")
  );
}

if (yarnVersion !== expectedYarnVersion) {
  fail(
    [
      `Hysight frontend requires Yarn ${expectedYarnVersion}.`,
      `Detected Yarn ${yarnVersion}.`,
    ].join(" ")
  );
}