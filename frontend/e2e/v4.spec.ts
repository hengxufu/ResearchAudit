import { test, expect } from "@playwright/test";
import fs from "node:fs/promises";
import path from "node:path";
import { randomUUID } from "node:crypto";
test("TEST DATA v4 project takeover optimization and saved figure", async ({
  page,
  request,
}) => {
  const root = path.resolve("..");
  const directory = path.join(
    root,
    ".test-runs-" + randomUUID(),
    "TEST_PROJECT",
  );
  await fs.mkdir(directory, { recursive: true });
  for (let i = 0; i < 3; i++) {
    const folder = path.join(directory, "run" + i);
    await fs.mkdir(folder);
    await fs.writeFile(
      path.join(folder, "metrics.csv"),
      "loss\n" + (i / 2 - 0.3) ** 2 + "\n",
    );
    await fs.writeFile(
      path.join(folder, "config.json"),
      JSON.stringify({
        x: i / 2,
        seed: i,
        dataset: "TEST",
        dataset_version: "1",
        split: "test",
        evaluation_protocol: "TEST",
        metric_definitions: {
          loss: {
            direction: "minimize",
            unit: "1",
            method: "TEST squared error",
          },
        },
      }),
    );
  }
  await page.goto("/");
  await page
    .getByRole("button", { name: "项目与数据资产", exact: true })
    .click();
  await page.getByLabel("Project intelligence path").fill(directory);
  await page
    .getByRole("button", { name: "Inspect project / 分析项目", exact: true })
    .click();
  await expect(
    page.getByRole("cell", { name: "PENDING_CONFIRMATION", exact: true }),
  ).toHaveCount(3);
  await page
    .getByRole("button", {
      name: "Backfill candidates / 批量补录",
      exact: true,
    })
    .click();
  await expect(
    page.getByText('"project_revision": 1', { exact: false }),
  ).toBeVisible();
  const snapshot = await (
    await request.post("/api/import", { data: { path: directory } })
  ).json();
  await page.getByRole("button", { name: "Refresh", exact: true }).click();
  await page.getByLabel("Snapshot context").selectOption(String(snapshot.id));
  await page.getByRole("button", { name: "科研分析", exact: true }).click();
  await page.getByLabel("Optimization space").fill('{"x":[0,1]}');
  await page
    .getByRole("button", {
      name: "Suggest experiments / 生成候选",
      exact: true,
    })
    .click();
  await expect(
    page.getByRole("columnheader", { name: "Prediction / SD", exact: true }),
  ).toBeVisible();
  expect(
    (await (await request.get("/api/v4/optimizations")).json())[0].candidates,
  ).toHaveLength(3);
  const proposal=(await (await request.get('/api/v4/optimizations')).json())[0];
  const python=process.env.RESEARCHAUDIT_PYTHON||path.join(root,'.venv',process.platform==='win32'?'Scripts/python.exe':'bin/python');
  const program=path.join(directory,'TEST_objective.py');
  await fs.writeFile(program,"import sys,os,pathlib; x=float(sys.argv[1]); (pathlib.Path(os.environ['RESEARCHAUDIT_OUTPUT_DIR'])/'metrics.csv').write_text('loss\\n'+str((x-.3)**2)+'\\n')");
  await page.getByLabel('Optimization command').fill(JSON.stringify({argv:[python,program,'{x}'],cwd:directory}));
  await page.getByLabel('Authorize optimization execution').check();
  await page.getByRole('button',{name:'Execute candidate / 执行候选',exact:true}).click();
  await expect.poll(async()=>{const r=await (await request.get('/api/v4/optimizations/'+proposal.id+'/results')).json();return r.results[0]?.execution?.state;},{timeout:25000}).toBe('Succeeded');
  await page.getByRole('button',{name:'Refresh actual results / 更新真实结果',exact:true}).click();
  await expect(page.getByText('"remaining_budget": 2',{exact:false})).toBeVisible();
  await page.getByRole("button", { name: "科研绘图", exact: true }).click();
  await page
    .getByRole("button", {
      name: "Save figure recipe / 保存绘图配置",
      exact: true,
    })
    .click();
  const download = page.waitForEvent("download");
  await page.getByRole("link", { name: "SVG ↓", exact: true }).click();
  const file = await (await download).path();
  expect((await fs.readFile(file!)).toString()).toContain("<svg");
  await page.screenshot({
    path: "test-results/v4-figures.png",
    fullPage: false,
  });
});
