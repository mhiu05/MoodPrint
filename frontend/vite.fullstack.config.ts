// Imported only by the disposable synthetic harness, never by a production build.
import { defineConfig, mergeConfig } from "vite";
import base from "./vite.config";

export default mergeConfig(base, defineConfig({
  plugins: [{
    name: "synthetic-captcha-loopback-only",
    transformIndexHtml: () => [{ tag: "script", attrs: { src: "/__synthetic-captcha.js" }, injectTo: "head-prepend" }],
    configureServer(server) {
      server.middlewares.use("/__synthetic-captcha.js", (_request, response) => {
        response.setHeader("Content-Type", "application/javascript");
        response.end(`(() => {
          let next = 0; const widgets = new Map();
          const solve = id => { const options = widgets.get(id); if (options) options.callback('synthetic-captcha-token'); };
          window.turnstile = {
            render(el, options) { const id = String(++next); widgets.set(id, options); setTimeout(() => solve(id), 0); return id; },
            reset(id) { setTimeout(() => solve(id), 0); }, remove(id) { widgets.delete(id); }
          };
        })();`);
      });
    },
  }],
  server: { proxy: { "/__test": { target: "http://127.0.0.1:8002" } } },
}));
