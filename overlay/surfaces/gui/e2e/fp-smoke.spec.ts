import { test, expect } from "./fixtures";

// The release gate this fork owns.
//
// The upstream E2E suite asserts upstream's product name and upstream's exact settings,
// sidebar and account wording. FP Studio renames the product and changes those strings,
// so those specs fail by construction, not because the shell regressed: on the pinned
// commit 181 of 221 upstream specs are text-pinned that way. What still has to hold is
// that this is the SAME application shell - stock sidebar, personas and composer - under
// the fork's identity. That is what this checks, against the same hermetic mocks.

test("the stock shell renders under the fork's identity", async ({ page }) => {
  await page.goto("/");

  // Fork identity, and no residual upstream brand in the shell.
  await expect(page.getByText("FP Studio").first()).toBeVisible();
  await expect(page.getByText("OpenWorker")).toHaveCount(0);

  // The stock surfaces, not a replacement GUI.
  await expect(page.getByRole("button", { name: /New session/i })).toBeVisible();
  await expect(page.getByText("Ops", { exact: true })).toBeVisible();
  await expect(page.getByPlaceholder(/Ask the agent/)).toBeVisible();

  // No second application: no canvas, inspector, template picker or project dashboard.
  for (const forbidden of [/template picker/i, /canvas/i, /inspector/i]) {
    await expect(page.getByText(forbidden)).toHaveCount(0);
  }
});

// The artifact the FP flow commits is an SVG, and the viewer has to draw it. Upstream
// classified `.svg` by suffix as text, so the user got several thousand lines of path
// data where their infographic should be. The server now serves it as an image; this is
// the other half — the stock viewer renders that image, in the stock rail, with no new
// component.
test("a committed SVG opens as a picture in the stock artifact viewer", async ({ page }) => {
  const svg =
    '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="32"><rect width="64" height="32"/></svg>';
  const dataUrl = "data:image/svg+xml;base64," + Buffer.from(svg).toString("base64");
  // Later routes win over the fixture defaults: one committed SVG, served as an image.
  await page.route(/\/v1\/sessions\/[^/]+\/artifacts$/, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        artifacts: [{
          path: "fp/infographic.svg", abs_path: "/w/fp/infographic.svg",
          name: "infographic.svg", kind: "image", size: 128, modified_at: 1,
        }],
      }),
    }),
  );
  await page.route(/\/v1\/sessions\/[^/]+\/artifacts\/read/, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ ok: true, path: "fp/infographic.svg", kind: "image", data_url: dataUrl }),
    }),
  );

  await page.goto("/");
  // The rail attaches its open-artifact listener once the shell has loaded; dispatching
  // until it takes is what the chat's artifact chip does for the user.
  const image = page.locator("img.artifact-image");
  await expect
    .poll(async () => {
      await page.evaluate(() =>
        window.dispatchEvent(
          new CustomEvent("ocw-open-artifact", { detail: { path: "fp/infographic.svg" } }),
        ),
      );
      return image.count();
    }, { timeout: 15_000 })
    .toBeGreaterThan(0);

  await expect(image).toBeVisible();
  await expect(image).toHaveAttribute("src", dataUrl);
  // The markup itself is never shown as text.
  await expect(page.getByText("<svg xmlns")).toHaveCount(0);
});
