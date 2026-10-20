const origin = (
  process.env.API_ORIGIN || "http://transcributed.homelab.home.arpa"
).replace(/\/+$/, "");

async function check(path, expected = 200) {
  const response = await fetch(`${origin}${path}`, {
    signal: AbortSignal.timeout(10000),
  });
  if (response.status !== expected) {
    throw new Error(`${path}: expected ${expected}, got ${response.status}`);
  }
  console.log(`${response.status} ${path}`);
  return response;
}

async function main() {
  console.log(`API smoke test: ${origin}`);
  await check("/healthz");
  await check("/readyz");
  await check("/api/v1/projects?limit=1");

  const uiUrl = process.env.UI_URL;
  if (uiUrl) {
    const response = await fetch(uiUrl, { signal: AbortSignal.timeout(10000) });
    const html = await response.text();
    if (!response.ok || !html.includes('id="app"')) {
      throw new Error(`UI smoke test failed for ${uiUrl}`);
    }
    console.log(`${response.status} ${uiUrl}`);
  }
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : error);
  process.exitCode = 1;
});
