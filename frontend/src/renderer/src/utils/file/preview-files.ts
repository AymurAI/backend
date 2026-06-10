import { FeatureFlowEnum } from "@/types/features";

export function filesForFeatureLoad(feature: FeatureFlowEnum, files: File[]) {
	if (feature === FeatureFlowEnum.Anonymizer) {
		return files.slice(-1);
	}

	return files;
}
