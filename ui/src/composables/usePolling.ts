import {
  onBeforeUnmount,
  onMounted,
  unref,
  watch,
  type Ref,
} from "vue";

type PollingOptions = {
  interval: number | Ref<number>;
  enabled: () => boolean;
  immediate?: boolean;
};

export function usePolling(
  task: () => Promise<void> | void,
  options: PollingOptions,
) {
  let timer: ReturnType<typeof setInterval> | undefined;
  let inFlight = false;
  let active = false;

  async function run() {
    if (!active || inFlight || document.hidden) return;
    inFlight = true;
    try {
      await task();
    } finally {
      inFlight = false;
    }
  }

  function stop() {
    active = false;
    if (timer) {
      clearInterval(timer);
      timer = undefined;
    }
  }

  function start() {
    stop();
    if (!options.enabled()) return;
    active = true;
    if (options.immediate) void run();
    timer = setInterval(run, unref(options.interval));
  }

  function onVisibilityChange() {
    if (document.hidden) {
      if (timer) {
        clearInterval(timer);
        timer = undefined;
      }
      return;
    }
    if (active || options.enabled()) start();
  }

  onMounted(() => {
    start();
    document.addEventListener("visibilitychange", onVisibilityChange);
  });

  watch(
    () => [options.enabled(), unref(options.interval)],
    () => start(),
  );

  onBeforeUnmount(() => {
    stop();
    document.removeEventListener("visibilitychange", onVisibilityChange);
  });

  return { refresh: run, start, stop };
}
