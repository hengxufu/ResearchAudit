import { test, expect } from "@playwright/test";
import fs from "node:fs/promises";
import path from "node:path";
import { randomUUID } from "node:crypto";

test("TEST DATA: v3 reproduction, workflow editor, data studio and claim evidence", async ({
  page,
  request,
}) => {
  test.setTimeout(120000);
  const root = path.resolve("..");
  const python =
    process.env.RESEARCHAUDIT_PYTHON ||
    path.join(
      root,
      ".venv",
      process.platform === "win32" ? "Scripts/python.exe" : "bin/python",
    );
  const directory = path.join(
    root,
    ".artifacts",
    "test-runs",
    randomUUID(),
    "TEST_DATA",
  );
  await fs.mkdir(directory, { recursive: true });
  await fs.writeFile(path.join(directory, "metrics.csv"), "loss\n3\n1\n");
  const params = {
    seed: 7,
    dataset: "TEST",
    dataset_version: "1",
    split: "test",
    evaluation_protocol: "TEST-v1",
    metric_definitions: {
      loss: { direction: "minimize", unit: "1", method: "TEST mean" },
    },
  };
  await fs.writeFile(
    path.join(directory, "config.json"),
    JSON.stringify(params),
  );
  const created = await request.post("/api/executions", {
    data: {
      cwd: root,
      argv: [python, path.join(root, "examples", "TEST_DATA_train.py")],
      params,
    },
  });
  expect(created.ok()).toBeTruthy();
  const original = await created.json();
  await request.post("/api/executions/" + original.id + "/start");
  await expect
    .poll(
      async () =>
        (await (await request.get("/api/executions/" + original.id)).json())
          .state,
      { timeout: 30000 },
    )
    .toBe("Succeeded");
  const done = await (
    await request.get("/api/executions/" + original.id)
  ).json();
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  await page.goto("/");
  await page.getByRole("button", { name: "实验执行中心", exact: true }).click();
  const replay = page.locator("section").filter({
    has: page.getByRole("heading", {
      name: "Experiment reproduction / 实验复现",
      exact: true,
    }),
  });
  await replay.getByLabel("Reproduction source").selectOption(original.id);
  await replay
    .getByLabel("Reproduction tolerances")
    .fill('{"loss":{"atol":0.000001,"rtol":0.000001}}');
  await replay
    .getByRole("button", {
      name: "Create manifest / 创建复现清单",
      exact: true,
    })
    .click();
  await expect(
    replay.getByRole("link", { name: "Manifest JSON ↓" }),
  ).toBeVisible();
  await replay.getByLabel("Confirm reproduction execution").check();
  await replay
    .getByRole("button", { name: "Replay / 复现执行", exact: true })
    .click();
  await expect
    .poll(
      async () => {
        const records = await (
          await request.get("/api/v3/reproductions")
        ).json();
        if (!records[0]?.execution) return "";
        return (
          await (
            await request.get("/api/executions/" + records[0].execution)
          ).json()
        ).state;
      },
      { timeout: 30000 },
    )
    .toBe("Succeeded");
  await replay
    .getByRole("button", { name: "Evaluate / 复现验证", exact: true })
    .click();
  await expect(replay.locator(".scorecard")).toContainText(
    "result_consistency",
  );
  await expect(replay.locator(".scorecard .PASS")).toHaveCount(3);
  const studio = page.locator("section").filter({
    has: page.getByRole("heading", {
      name: "Research Workflow Studio / 工作流编排",
      exact: true,
    }),
  });
  await studio
    .getByRole("button", {
      name: "Import/report template / 导入报告模板",
      exact: true,
    })
    .click();
  await studio
    .getByLabel("Node config import")
    .fill(JSON.stringify({ path: directory }));
  await studio.getByLabel("Node config figure").fill(
    JSON.stringify({
      snapshot_id: { $ref: "import.snapshot_id" },
      metric: "loss",
      format: "svg",
    }),
  );
  await studio
    .getByRole("button", { name: "Save workflow / 保存版本", exact: true })
    .click();
  await studio.getByLabel("Confirm workflow execution").check();
  await studio
    .getByRole("button", { name: "Run workflow / 执行工作流", exact: true })
    .click();
  await expect(
    studio.getByRole("cell", { name: "Succeeded", exact: true }),
  ).toBeVisible({ timeout: 30000 });
  await expect(
    studio.getByRole("link", { name: "↓", exact: true }),
  ).toHaveCount(2);
  const downloadPromise = page.waitForEvent("download");
  await studio.getByRole("link", { name: "↓", exact: true }).last().click();
  const download = await downloadPromise;
  expect(
    (await fs.readFile((await download.path())!)).subarray(0, 4).toString(),
  ).toBe("%PDF");
  await page.screenshot({
    path: path.join(
      root,
      ".artifacts",
      "browser",
      "screenshots",
      "workflows-v3.png",
    ),
    fullPage: true,
  });
  const asset = await (
    await request.post("/api/v2/assets", {
      data: { label: "TEST browser dataset", kind: "dataset", path: directory },
    })
  ).json();
  await page
    .getByRole("button", { name: "项目与数据资产", exact: true })
    .click();
  const data = page.locator("section").filter({
    has: page.getByRole("heading", {
      name: "Research Data Studio / 科研数据浏览",
      exact: true,
    }),
  });
  await data
    .getByRole("button", { name: "Refresh assets", exact: true })
    .click();
  await data.getByLabel("Data Studio asset").selectOption(asset.id);
  await data.getByLabel("Data Studio file").fill("metrics.csv");
  await data
    .getByRole("button", { name: "Inspect structure / 检查结构", exact: true })
    .click();
  await expect(data.locator("pre")).toContainText("columns");
  await data
    .getByRole("button", { name: "Read table page / 分页读取", exact: true })
    .click();
  await expect(
    data.getByRole("cell", { name: "3", exact: true }),
  ).toBeVisible();
  await page
    .getByLabel("Snapshot context")
    .selectOption(String(done.snapshot_id));
  await page.getByRole("button", { name: "科研分析", exact: true }).click();
  await page.getByLabel("Research question").fill("最好 loss");
  await page
    .getByRole("button", { name: "Query experiments / 查询实验", exact: true })
    .click();
  await expect(
    page.getByText('"operation": "rank"', { exact: false }),
  ).toBeVisible();
  await page.getByRole("button", { name: "证据图谱", exact: true }).click();
  await page
    .getByLabel("Knowledge title")
    .fill("TEST neural training observation");
  await page
    .getByLabel("Knowledge body")
    .fill("TEST ONLY: finite training result, causal validity unverified");
  await page
    .getByRole("button", {
      name: "Link current snapshot / 关联当前快照",
      exact: true,
    })
    .click();
  await page
    .getByRole("button", {
      name: "Save knowledge revision / 保存知识版本",
      exact: true,
    })
    .click();
  await expect(
    page.getByRole("cell", {
      name: "TEST neural training observation",
      exact: true,
    }),
  ).toBeVisible();
  expect(errors).toEqual([]);
});
