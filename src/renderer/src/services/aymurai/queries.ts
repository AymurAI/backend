import type { PredictLabel } from "@/types/aymurai";
import type { DocFile } from "@/types/file";
import { queryOptions } from "@tanstack/react-query";
import api from "../api";

interface Body {
  data: {
    // The paragraph
    document: string;
    labels: PredictLabel[];
  }[];
}

const body = (file: DocFile): Body => {
  const paragraphs = file.paragraphs ?? [];
  const labels = file.predictions ?? [];

  return {
    data: paragraphs.map((p) => ({
      document: p.value,
      labels: labels.filter((l) => l.paragraphId === p.id),
    })),
  };
};

export const anonymize = (file: DocFile) =>
  queryOptions({
    queryKey: ["anonymize", file.data.name],
    queryFn: async () => {
      const formData = new FormData();
      formData.append("file", file.data);
      // TODO: add annotations whenever the backend implements it
      formData.append("annotations", JSON.stringify(body(file)));

      const response = await api.post<Blob>(
        "/anonymizer/anonymize-document",
        formData,
        {
          headers: {
            "Content-Type": "multipart/form-data",
            Accept: "application/octet-stream",
          },
          responseType: "blob",
        },
      );

      console.log(response);

      return response.data;
    },
    select: (data) => URL.createObjectURL(data),
  });
