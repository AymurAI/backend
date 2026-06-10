import api, { getApiBaseUrl, setApiBaseUrl } from "@/services/api";

import z from "zod";

import { useMutation } from "@tanstack/react-query";

export const useConnectToHost = () => {
  return useMutation({
    mutationKey: ["healthcheck"],
    mutationFn: async (host: string) => {
      const url = getApiBaseUrl(host);
      const response = await api
        .get(`${url}/server/healthcheck`)
        .then((r) => r.data);

      return z.object({ status: z.string() }).parse(response);
    },
    onSuccess: (_data, host) => {
      setApiBaseUrl(host);
    },
  });
};
