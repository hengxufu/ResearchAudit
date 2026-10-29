import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs/promises";
import { execFileSync } from "node:child_process";
test("TEST DATA: nine-page workbench and real experiment lifecycle", async ({
  page,
}) => {
  const root = path.resolve("..");
  const python =
    process.env.RESEARCHAUDIT_PYTHON ||
    path.join(
      root,
      ".venv",
      process.platform === "win32" ? "Scripts/python.exe" : "bin/python",
    );
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "项目总览", exact: true }),
  ).toBeVisible();
  for (const name of [
    "项目与数据资产",
    "实验执行中心",
    "实验记录",
    "科研分析",
    "科研绘图",
    "证据图谱",
    "科研审计",
    "报告与成果",
  ]) {
    await page.getByRole("button", { name, exact: true }).click();
    await expect(
      page.getByRole("heading", { name, exact: true }),
    ).toBeVisible();
  }
  await page.getByRole("button", { name: "实验执行中心", exact: true }).click();
  await page.getByLabel("Execution working directory").fill(root);
  const script =
    "import os,pathlib; p=pathlib.Path(os.environ['RESEARCHAUDIT_OUTPUT_DIR']); (p/'metrics.csv').write_text('loss\\n3\\n1\\n'); print('TEST DATA playwright completed')";
  await page
    .getByLabel("Execution argument array")
    .fill(JSON.stringify([python, "-c", script]));
  await page
    .getByRole("button", { name: "Create Pending / 创建", exact: true })
    .click();
  await expect(
    page.getByRole("cell", { name: "Pending", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Start / 启动", exact: true }).click();
  await expect(
    page.getByRole("cell", { name: "Succeeded", exact: true }),
  ).toBeVisible({ timeout: 25000 });
  await page.getByRole("button", { name: "Logs", exact: true }).click();
  await expect(
    page.getByText("TEST DATA playwright completed", { exact: false }).last(),
  ).toBeVisible();
  await page.getByRole("button", { name: "Results", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "科研分析", exact: true }),
  ).toBeVisible();
  await page
    .getByLabel("Analysis run", { exact: true })
    .selectOption({ index: 1 });
  await page
    .getByLabel("Analysis metric", { exact: true })
    .selectOption({ label: "loss" });
  await page
    .getByRole("button", { name: "Compute / 计算", exact: true })
    .click();
  await expect(page.getByText("Analysis ID:", { exact: false })).toBeVisible();
  await page.screenshot({
    path: "test-results/analysis-v2.png",
    fullPage: false,
  });
  await page.getByRole("button", { name: "科研绘图", exact: true }).click();
  await page.getByLabel("Figure metric").selectOption("loss");
  await expect(page.locator(".js-plotly-plot")).toBeVisible();
  await page.getByRole("button", { name: "科研审计", exact: true }).click();
  await page.getByRole("button", { name: "Run audit", exact: true }).click();
  await expect(page.locator("tbody .UNKNOWN").first()).toBeVisible();
  await page.getByRole("button", { name: "报告与成果", exact: true }).click();
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("link", { name: "PDF report ↓", exact: true }).click();
  const download = await downloadPromise;
  const filename = await download.path();
  expect(filename).toBeTruthy();
  expect((await fs.readFile(filename!)).subarray(0, 4).toString()).toBe("%PDF");
  await page.getByRole("button", { name: "Dark / 深色", exact: true }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  const archivePromise = page.waitForEvent("download");
  await page.getByRole("link", { name: "Evidence ZIP ↓", exact: true }).click();
  const archive = await archivePromise;
  const archivePath = await archive.path();
  const verified = JSON.parse(
    execFileSync(
      python,
      [path.join(root, "backend", "v2", "verify_package.py"), archivePath!],
      { encoding: "utf-8" },
    ),
  );
  expect(verified.status).toBe("PASS");
  await page.screenshot({
    path: "test-results/workbench-v2.png",
    fullPage: true,
  });
  expect(errors).toEqual([]);
});
