import { createRouter, createWebHistory } from "vue-router";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", redirect: "/projects" },
    {
      path: "/projects",
      name: "projects",
      component: () => import("./pages/ProjectsPage.vue"),
    },
    {
      path: "/projects/:id",
      name: "project",
      component: () => import("./pages/ProjectPage.vue"),
      props: true,
    },
    {
      path: "/runs/:id",
      name: "run",
      component: () => import("./pages/RunPage.vue"),
      props: true,
    },
    {
      path: "/:pathMatch(.*)*",
      name: "not-found",
      component: () => import("./pages/NotFoundPage.vue"),
    },
  ],
  scrollBehavior: () => ({ top: 0 }),
});

export default router;
