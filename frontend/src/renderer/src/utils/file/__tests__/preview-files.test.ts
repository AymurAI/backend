import { FeatureFlowEnum } from "@/types/features";
import { describe, expect, it } from "vitest";
import { filesForFeatureLoad } from "../preview-files";

function makeFile(name: string): File {
	return new File(["content"], name, {
		type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
	});
}

describe("filesForFeatureLoad", () => {
	it("keeps only the newest file for anonymizer", () => {
		const files = [makeFile("old.docx"), makeFile("new.docx")];

		expect(filesForFeatureLoad(FeatureFlowEnum.Anonymizer, files)).toEqual([
			files[1],
		]);
	});

	it("keeps all files for dataset", () => {
		const files = [makeFile("first.docx"), makeFile("second.docx")];

		expect(filesForFeatureLoad(FeatureFlowEnum.Dataset, files)).toEqual(files);
	});
});
