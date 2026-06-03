import { Workbook } from "exceljs";
import { beforeEach, describe, expect, it, vi } from "vitest";

const filesystemMock = {
  excel: {
    create: vi.fn(),
    read: vi.fn(),
    write: vi.fn(),
  },
};

vi.mock("@/services/filesystem", () => ({
  default: filesystemMock,
}));

describe("offline validation export", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("creates a new dataset workbook when the existing workbook has no worksheets", async () => {
    const emptyWorkbook = new Workbook();
    const createdWorkbook = new Workbook();
    createdWorkbook.addWorksheet("set_de_datos");

    filesystemMock.excel.read.mockResolvedValueOnce(emptyWorkbook);
    filesystemMock.excel.create.mockReturnValueOnce(createdWorkbook);

    const { default: offline } = await import("../offline");
    const result = await offline([["value"]]);

    expect(filesystemMock.excel.create).toHaveBeenCalledTimes(1);
    expect(result).toBe(createdWorkbook);
    expect(createdWorkbook.worksheets[0].getCell("A1").value).toBe("value");
    expect(filesystemMock.excel.write).toHaveBeenCalledWith(createdWorkbook);
  });
});
