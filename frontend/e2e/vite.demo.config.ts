import config from "../vite.config";

// Demo E2E works without Docker or dotenv, even when the owner configured hosted.
export default { ...config, envDir: false };
