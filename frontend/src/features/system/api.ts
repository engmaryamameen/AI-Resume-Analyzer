import type { ModelStatus } from "@/lib/types";
import { request } from "@/lib/http/client";

export const systemApi = {
  modelStatus: (signal?: AbortSignal) => request<ModelStatus>("/system/models", { signal }),
};
