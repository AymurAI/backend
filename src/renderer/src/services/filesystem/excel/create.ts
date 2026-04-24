import { excelStructure } from "@/utils/file";
import { Workbook, type Worksheet } from "exceljs";

function setMetadata(workbook: Workbook) {
  workbook.creator = "AymurAI";
  workbook.company = "DataGenero";
  workbook.description = "Set de datos con perspectiva de genero";

  workbook.created = new Date();
  workbook.modified = new Date();
}

function addWorksheet(workbook: Workbook) {
  const worksheet = workbook.addWorksheet("set_de_datos", {
    properties: {
      tabColor: { argb: "B7E1CD" },
    },
  });

  return worksheet;
}

function addHeader(worksheet: Worksheet) {
  worksheet.columns = excelStructure.map((label) => ({
    header: label,
    key: label,
  }));

  // Paint first row
  const row = worksheet.getRow(1);
  row.eachCell((cell) => {
    cell.fill = {
      type: "pattern",
      pattern: "solid",
      fgColor: { argb: "B7E1CD" },
    };
  });

  // Freeze first row
  worksheet.views = [{ state: "frozen", ySplit: 1 }];
}

/**
 * Creates a new and empty Workbook with one Worksheet to start working with the dataset
 * @returns A formatted Workbook
 */
export default function create() {
  const workbook = new Workbook();

  setMetadata(workbook);
  const worksheet = addWorksheet(workbook);

  addHeader(worksheet);

  return workbook;
}
