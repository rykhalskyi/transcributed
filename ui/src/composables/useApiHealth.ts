import { onBeforeUnmount, onMounted, ref } from "vue";

import { getHealth, getReadiness } from "@/lib/endpoints";

export type ApiHealth = "checking" | "ok" | "degraded" | "down";

export function useApiHealth() {
  const health = ref<ApiHealth>("checking");
  let timer: ReturnType<typeof setInterval> | undefined;

  async function check() {
    try {
      const [healthResponse, readinessResponse] = await Promise.all([
        getHealth(),
        getReadiness(),
      ]);
      health.value =
        healthResponse.status === "ok" && readinessResponse.status === "ok"
          ? "ok"
          : "degraded";
    } catch {
      health.value = "down";
    }
  }

  onMounted(() => {
    void check();
    timer = setInterval(check, 30000);
  });

  onBeforeUnmount(() => {
    if (timer) clearInterval(timer);
  });

  return { health, check };
}
