import { Workbook } from "exceljs";
import { beforeEach, describe, expect, it, vi } from "vitest";

const downloadBlob = vi.fn();

vi.mock("../../browser/download", () => ({
  downloadBlob,
}));

describe("excel write", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal("window", { filesystem: undefined });
  });

  it("downloads the workbook in browser mode when the Electron filesystem API is unavailable", async () => {
    const { default: write } = await import("../write");
    const workbook = new Workbook();
    workbook.addWorksheet("set_de_datos").addRow(["ok"]);

    await write(workbook);

    expect(downloadBlob).toHaveBeenCalledTimes(1);
    expect(downloadBlob).toHaveBeenCalledWith(
      expect.any(Blob),
      "set_de_datos.xlsx",
    );
  });
  it("returns null without logging an error when reading in browser mode", async () => {
    const { default: read } = await import("../read");

    await expect(read()).resolves.toBeNull();
  });
});
