import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { Workbook } from "exceljs";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("electron", () => ({
  shell: {
    openPath: vi.fn(),
  },
}));

vi.mock("@electron-toolkit/utils", () => ({
  is: {
    dev: true,
  },
}));

describe("main excel filesystem bridge", () => {
  let tempHome: string;

  beforeEach(async () => {
    tempHome = await fs.mkdtemp(path.join(os.tmpdir(), "aymurai-excel-"));
    vi.spyOn(os, "homedir").mockReturnValue(tempHome);
    vi.resetModules();
  });

  afterEach(async () => {
    vi.restoreAllMocks();
    await fs.rm(tempHome, { recursive: true, force: true });
  });

  it("returns the exact file bytes when reading the dataset workbook", async () => {
    const { default: excel } = await import("../excel");
    const workbook = new Workbook();
    workbook.addWorksheet("set_de_datos").addRow(["ok"]);

    const original = await workbook.xlsx.writeBuffer();
    await excel.write(original);

    const loaded = await excel.read();
    expect(loaded.byteLength).toBe(original.byteLength);

    const reloaded = new Workbook();
    const loadedBuffer = Buffer.from(new Uint8Array(loaded as ArrayBuffer));
    const loadWorkbook = reloaded.xlsx.load.bind(reloaded.xlsx) as (
      data: unknown,
    ) => Promise<unknown>;
    await expect(loadWorkbook(loadedBuffer)).resolves.toBeDefined();
    expect(reloaded.worksheets[0].getCell("A1").value).toBe("ok");
  });
});
